import { request } from './client.js';

export async function registerSyncDevice(payload) {
  return request('/api/sync/v1/devices/register', {
    method: 'POST',
    body: payload,
  });
}

export async function getSyncDevice(deviceId) {
  return request(`/api/sync/v1/devices/${encodeURIComponent(deviceId)}`, {
    method: 'GET',
  });
}

export async function uploadSyncBatch(payload) {
  return request('/api/sync/v1/upload', {
    method: 'POST',
    body: payload,
  });
}

export async function downloadSyncChanges(payload) {
  return request('/api/sync/v1/download', {
    method: 'POST',
    body: payload,
  });
}

export async function acknowledgeSyncCursor(payload) {
  return request('/api/sync/v1/ack', {
    method: 'POST',
    body: payload,
  });
}
