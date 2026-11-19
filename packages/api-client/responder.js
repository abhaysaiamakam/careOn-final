import { request } from './client.js';

export async function getResponderMe() {
  return request('/api/responder/me', {
    method: 'GET',
  });
}

export async function listResponderMissions() {
  return request('/api/responder/missions', {
    method: 'GET',
  });
}

export async function getResponderMission(assignmentId) {
  return request(`/api/responder/missions/${assignmentId}`, {
    method: 'GET',
  });
}

export async function acknowledgeMission(assignmentId, payload) {
  return request(`/api/responder/missions/${assignmentId}/acknowledge`, {
    method: 'POST',
    body: payload,
  });
}

export async function transitionMission(assignmentId, payload) {
  return request(`/api/responder/missions/${assignmentId}/transition`, {
    method: 'POST',
    body: payload,
  });
}

export async function getMissionHistory(assignmentId) {
  return request(`/api/responder/missions/${assignmentId}/history`, {
    method: 'GET',
  });
}

export async function sendResponderTelemetry(payload) {
  return request('/api/realtime/telemetry', {
    method: 'POST',
    body: payload,
  });
}

export async function sendTelemetryBatch(payload) {
  return request('/api/responder/telemetry/batch', {
    method: 'POST',
    body: payload,
  });
}

export async function registerResponderDevice(payload) {
  return request('/api/responder/devices/register', {
    method: 'POST',
    body: payload,
  });
}

export async function getResponderNotificationHistory() {
  return request('/api/responder/notifications/history', {
    method: 'GET',
  });
}
