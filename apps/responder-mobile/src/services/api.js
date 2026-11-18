import { secureStorage } from './secureStore';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

let memoryAccessToken = null;

export const mobileApi = {
  setAccessToken(token) {
    memoryAccessToken = token;
  },

  getAccessToken() {
    return memoryAccessToken;
  },

  async request(endpoint, options = {}) {
    const url = `${BASE_URL}/${endpoint.replace(/^\//, '')}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (memoryAccessToken) {
      headers['Authorization'] = `Bearer ${memoryAccessToken}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Attempt refresh with secureStore
      const refreshToken = await secureStorage.getRefreshToken();
      if (refreshToken) {
        const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          memoryAccessToken = data.access_token;
          if (data.refresh_token) {
            await secureStorage.saveRefreshToken(data.refresh_token);
          }
          headers['Authorization'] = `Bearer ${memoryAccessToken}`;
          const retryRes = await fetch(url, { ...options, headers });
          return await retryRes.json();
        }
      }
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  },

  login(email, password) {
    return this.request('auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  getProfile() {
    return this.request('responder/me');
  },

  getMissions() {
    return this.request('responder/missions');
  },

  acceptMission(assignmentId, reason = '') {
    return this.request(`responder/missions/${assignmentId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },

  updateStatus(assignmentId, status, notes = '') {
    return this.request(`responder/missions/${assignmentId}/status`, {
      method: 'POST',
      body: JSON.stringify({ status, notes }),
    });
  },

  sendTelemetry(latitude, longitude) {
    return this.request('responder/telemetry', {
      method: 'POST',
      body: JSON.stringify({ latitude, longitude }),
    });
  },

  // Milestone 9 Offline Sync Endpoints
  registerDevice(deviceData) {
    return this.request('sync/v1/devices/register', {
      method: 'POST',
      body: JSON.stringify(deviceData),
    });
  },

  uploadSyncBatch(batchData) {
    return this.request('sync/v1/upload', {
      method: 'POST',
      body: JSON.stringify(batchData),
    });
  },

  downloadSyncChanges(deviceId, sinceCursor = '0', limit = 50) {
    return this.request('sync/v1/download', {
      method: 'POST',
      body: JSON.stringify({
        device_id: deviceId,
        since_cursor: sinceCursor,
        limit,
      }),
    });
  },

  acknowledgeCursor(deviceId, cursor, acknowledgedActionUuids = []) {
    return this.request('sync/v1/ack', {
      method: 'POST',
      body: JSON.stringify({
        device_id: deviceId,
        acknowledged_cursor: cursor,
        acknowledged_action_uuids: acknowledgedActionUuids,
      }),
    });
  },

  getSyncStatus(deviceId = null) {
    const q = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : '';
    return this.request(`sync/v1/status${q}`);
  },

  getConflicts(deviceId = null) {
    const q = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : '';
    return this.request(`sync/v1/conflicts${q}`);
  },

  reconcileConflict(conflictToken, resolution, notes = '') {
    return this.request(`sync/v1/conflicts/${conflictToken}/reconcile`, {
      method: 'POST',
      body: JSON.stringify({ resolution, notes }),
    });
  },
};
