/**
 * CareOn Milestone 13 — Clinical Real-Time Duplex WebSocket Service.
 * Implements authenticated duplex streaming via initial auth frames,
 * O(1) deduplication, ping/pong heartbeats, and replay recovery for hospital and handover events.
 */

class ClinicalWebSocketService {
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

    // Normalized aliases (e.g. hospital.incoming_patient_requested <-> hospital_incoming_patient_requested)
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
          cb({ type: eventType, payload });
        } catch (e) {
          console.error('Error in WS wildcard subscriber:', e);
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

    const envWs = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_WS_URL;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = envWs || `${protocol}//${window.location.host}/api/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.ws.send(JSON.stringify({
          action: 'auth',
          type: 'auth',
          token: this.token,
          last_event_id: this.lastEventId,
        }));

        this._startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleMessage(data);
        } catch (err) {
          console.warn('Failed to parse WebSocket message:', event.data, err);
        }
      };

      this.ws.onerror = (err) => {
        console.error('Clinical WebSocket error:', err);
        this._notifyStatus('ERROR');
      };

      this.ws.onclose = () => {
        this._stopHeartbeat();
        this._notifyStatus('DISCONNECTED');
        if (!this.explicitDisconnect) {
          this._scheduleReconnect();
        }
      };
    } catch (err) {
      console.error('Failed to initiate WebSocket connection:', err);
      this._notifyStatus('ERROR');
      this._scheduleReconnect();
    }
  }

  _handleMessage(data) {
    if (data.type === 'auth_ok' || data.type === 'connection_established' || data.type === 'connected') {
      this._notifyStatus('CONNECTED');
      return;
    }

    if (data.type === 'pong') {
      return;
    }

    const eventId = data.event_id || data.id || (data.payload && data.payload.id);
    if (eventId) {
      if (this.seenEventIds.has(eventId)) {
        return; // Deduplicated
      }
      this.seenEventIds.add(eventId);
      if (this.seenEventIds.size > this.maxSeenCache) {
        const oldest = this.seenEventIds.values().next().value;
        this.seenEventIds.delete(oldest);
      }
      this.lastEventId = eventId;
    }

    const eventType = data.type || data.event || 'unknown';
    const payload = data.payload !== undefined ? data.payload : data;
    this._emit(eventType, payload);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 25000);
  }

  _stopHeartbeat() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('Max WebSocket reconnect attempts reached');
      return;
    }

    const backoff = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 15000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.token && !this.explicitDisconnect) {
        this.connect(this.token);
      }
    }, backoff);
  }

  disconnect() {
    this.explicitDisconnect = true;
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._notifyStatus('DISCONNECTED');
  }
}

export const clinicalWs = new ClinicalWebSocketService();
export default clinicalWs;
