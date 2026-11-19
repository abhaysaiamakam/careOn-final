/**
 * CareOn Command — M4 Real-Time WebSocket Service.
 * Manages authenticated duplex streaming with initial auth frames (no URL tokens),
 * heartbeat ping-pong, O(1) deduplication, automatic replay recovery,
 * channel subscriptions, and event routing.
 */

class CommandWebSocketService {
  constructor() {
    this.ws = null;
    this.status = 'DISCONNECTED'; // CONNECTING, CONNECTED, DISCONNECTED, ERROR
    this.token = null;
    this.subscribers = new Map(); // eventType -> Set of callbacks
    this.statusListeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 15;
    this.reconnectTimer = null;
    this.pingTimer = null;
    this.explicitDisconnect = false;
    this.lastEventId = null;
    this.seenEventIds = new Set(); // O(1) deduplication ring buffer
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
    // Exact match
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

    // Wildcard listeners
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

    // Build WebSocket URL WITHOUT token in query parameters
    const envWs = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_WS_URL;
    const isSecure = typeof window !== 'undefined' && window.location.protocol === 'https:';
    const wsProto = isSecure ? 'wss:' : 'ws:';
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3003';
    // Connect to /api/ws (or /ws) without leaking token in URL
    const wsUrl = envWs || `${wsProto}//${host}/api/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._startHeartbeat();

        // 1. Send Authenticated Initial Frame (Never leak token in URL or logs)
        this.send({
          action: 'auth',
          token: this.token,
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const eventType = message.event_type || message.event || message.type || 'message';

          // Handle Authentication Handshake Responses
          if (eventType === 'auth_required') {
            this.send({
              action: 'auth',
              token: this.token,
            });
            return;
          }

          if (eventType === 'authenticated' || eventType === 'connected') {
            this._notifyStatus('CONNECTED');

            // 2. Subscribe to Global Operations Channel
            this.send({
              action: 'subscribe',
              channels: ['channel:global'],
            });

            // 3. Event Replay Recovery if reconnecting after an outage
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

          // Handle replay batch
          if (eventType === 'replay_batch') {
            const events = message.events || [];
            events.forEach((evt) => {
              this._processEvent(evt);
            });
            return;
          }

          // Process real-time event with deduplication
          this._processEvent(message);
        } catch (err) {
          console.warn('Failed to parse incoming WebSocket message:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('Command WebSocket connection error:', err);
        this._notifyStatus('ERROR');
      };

      this.ws.onclose = (event) => {
        this._stopHeartbeat();
        this._notifyStatus('DISCONNECTED');

        if (!this.explicitDisconnect) {
          this._scheduleReconnect();
        }
      };
    } catch (e) {
      console.error('Failed to construct WebSocket:', e);
      this._notifyStatus('ERROR');
      this._scheduleReconnect();
    }
  }

  _processEvent(message) {
    const eventId = message.event_id;
    if (eventId) {
      if (this.seenEventIds.has(eventId)) {
        return; // Deduplicate duplicate delivery from multi-instance Redis Pub/Sub
      }
      this.seenEventIds.add(eventId);
      if (this.seenEventIds.size > this.maxSeenCache) {
        // Trim oldest
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
      console.warn('Command WebSocket reached maximum reconnection attempts.');
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

export const commandWs = new CommandWebSocketService();
