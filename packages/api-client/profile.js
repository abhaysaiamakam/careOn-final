import { request } from './client.js';

export async function getMyProfile() {
  return request('/api/users/me/profile', {
    method: 'GET',
  });
}

export async function updateMyProfile(updateData) {
  return request('/api/users/me/profile', {
    method: 'PATCH',
    body: updateData,
  });
}

export async function getMySessions() {
  return request('/api/users/me/sessions', {
    method: 'GET',
  });
}

export async function revokeMySession(sessionId) {
  return request(`/api/users/me/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}
