/**
 * CareOn Command — M4 Real-Time WebSocket Service.
 * Manages authenticated duplex streaming with auto-reconnection,
 * heartbeat management, channel subscriptions, and event routing.
 */

class CommandWebSocketService {
  constructor() {
    this.ws = null;
    this.status = 'DISCONNECTED'; // CONNECTING, CONNECTED, DISCONNECTED, ERROR
    this.token = null;
    this.subscribers = new Map(); // eventType -> Set of callbacks
    this.statusListeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectTimer = null;
    this.pingTimer = null;
    this.explicitDisconnect = false;
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

    // Also notify wildcard listeners
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

    // Build WebSocket URL
    const isSecure = window.location.protocol === 'https:';
    const wsProto = isSecure ? 'wss:' : 'ws:';
    const host = window.location.host;
    // In dev, if on 3003, proxy points to backend, or direct to port 8000
    const wsUrl = `${wsProto}//${host}/ws?token=${encodeURIComponent(token)}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._notifyStatus('CONNECTED');
        this._startHeartbeat();

        // Send initial auth frame as well for maximum protocol compatibility
        this.send({
          action: 'auth',
          token: this.token,
        });

        // Request global channel subscription
        this.send({
          action: 'subscribe',
          channel: 'channel:global',
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const eventType = message.event || message.type || 'message';

          if (eventType === 'pong') {
            return;
          }

          this._emit(eventType, message.data || message);
        } catch (err) {
          console.warn('Failed to parse incoming WebSocket message:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('Command WebSocket encountered an error:', err);
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

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  disconnect() {
    this.explicitDisconnect = true;
    this._stopHeartbeat();
    clearTimeout(this.reconnectTimer);
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
      this.ws = null;
    }
    this._notifyStatus('DISCONNECTED');
  }
}

export const commandWs = new CommandWebSocketService();
