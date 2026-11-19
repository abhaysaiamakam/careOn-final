/**
 * CareOn Responder — M4 Real-Time Duplex WebSocket Service.
 * Implements authenticated duplex streaming via initial auth frames (no query parameters),
 * O(1) deduplication, ping/pong heartbeats, and replay recovery.
 */

class ResponderWebSocketService {
  constructor() {
    this.ws = null;
    this.status = 'DISCONNECTED'; // CONNECTING, CONNECTED, DISCONNECTED, ERROR
    this.token = null;
    this.subscribers = new Map();
    this.statusListeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 15;
    this.reconnectTimer = null;
    this.pingTimer = null;
    this.explicitDisconnect = false;
    this.lastEventId = null;
    this.seenEventIds = new Set();
    this.maxSeenCache = 500;
  }

  onStatusChange(callback) {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  _notifyStatus(newStatus) {
    this.status = newStatus;
    this.statusListeners.forEach((cb) => {
      try {
        cb(newStatus);
      } catch (e) {
        console.error('Status listener error:', e);
      }
    });
  }

  on(eventType, callback) {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }
    this.subscribers.get(eventType).add(callback);
    return () => {
      const set = this.subscribers.get(eventType);
      if (set) {
        set.delete(callback);
      }
    };
  }

  _emit(eventType, payload) {
    const listeners = this.subscribers.get(eventType);
    if (listeners) {
      listeners.forEach((cb) => {
        try {
          cb(payload);
        } catch (e) {
          console.error(`Error in WS subscriber for ${eventType}:`, e);
        }
      });
    }

    // Normalized aliases (e.g. incident.created <-> incident_created)
    const normalized = eventType.includes('.') ? eventType.replace(/\./g, '_') : eventType.replace(/_/g, '.');
    const aliasListeners = this.subscribers.get(normalized);
    if (aliasListeners) {
      aliasListeners.forEach((cb) => {
        try {
          cb(payload);
        } catch (e) {
          console.error(`Error in WS alias subscriber for ${normalized}:`, e);
        }
      });
    }

    const wildcard = this.subscribers.get('*');
    if (wildcard) {
      wildcard.forEach((cb) => {
        try {
          cb({ type: eventType, data: payload });
        } catch (e) {
          console.error('Error in wildcard WS subscriber:', e);
        }
      });
    }
  }

  connect(token) {
    if (!token) return;
    this.token = token;
    this.explicitDisconnect = false;

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this._notifyStatus('CONNECTING');

    const isSecure = typeof window !== 'undefined' && window.location.protocol === 'https:';
    const wsProto = isSecure ? 'wss:' : 'ws:';
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3004';
    const wsUrl = `${wsProto}//${host}/api/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._startHeartbeat();

        // 1. Send Authenticated Initial Frame (Never expose access token in URL)
        this.send({
          action: 'auth',
          token: this.token,
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const eventType = message.event_type || message.event || message.type || 'message';

          if (eventType === 'auth_required') {
            this.send({
              action: 'auth',
              token: this.token,
            });
            return;
          }

          if (eventType === 'authenticated' || eventType === 'connected') {
            this._notifyStatus('CONNECTED');

            // Subscribe to global channel
            this.send({
              action: 'subscribe',
              channels: ['channel:global'],
            });

            // Event replay recovery if reconnecting
            if (this.lastEventId) {
              this.send({
                action: 'replay',
                since_event_id: this.lastEventId,
                limit: 50,
              });
            }
            return;
          }

          if (eventType === 'pong') {
            return;
          }

          if (eventType === 'replay_batch') {
            const events = message.events || [];
            events.forEach((evt) => this._processEvent(evt));
            return;
          }

          this._processEvent(message);
        } catch (err) {
          console.warn('Failed to parse incoming WebSocket frame:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('Responder WebSocket encountered error:', err);
        this._notifyStatus('ERROR');
      };

      this.ws.onclose = () => {
        this._stopHeartbeat();
        this._notifyStatus('DISCONNECTED');

        if (!this.explicitDisconnect) {
          this._scheduleReconnect();
        }
      };
    } catch (e) {
      console.error('Failed to instantiate WebSocket:', e);
      this._notifyStatus('ERROR');
      this._scheduleReconnect();
    }
  }

  _processEvent(message) {
    const eventId = message.event_id;
    if (eventId) {
      if (this.seenEventIds.has(eventId)) {
        return; // Deduplicate
      }
      this.seenEventIds.add(eventId);
      if (this.seenEventIds.size > this.maxSeenCache) {
        const first = this.seenEventIds.values().next().value;
        this.seenEventIds.delete(first);
      }
      this.lastEventId = eventId;
    }

    const eventType = message.event_type || message.event || message.type || 'message';
    const payload = message.payload || message.data || message;
    this._emit(eventType, payload);
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('Responder WebSocket max reconnection attempts reached.');
      return;
    }

    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 15000);
    this.reconnectAttempts += 1;

    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (!this.explicitDisconnect && this.token) {
        this.connect(this.token);
      }
    }, delay);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ action: 'ping' });
      }
    }, 25000);
  }

  _stopHeartbeat() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  send(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  disconnect() {
    this.explicitDisconnect = true;
    this._stopHeartbeat();
    clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._notifyStatus('DISCONNECTED');
  }
}

export const responderWs = new ResponderWebSocketService();
export { ResponderWebSocketService, ResponderWebSocketService as ResponderWebSocketClient };
