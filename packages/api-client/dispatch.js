import { request } from './client.js';

export async function assessIncident(incidentId, payload = {}) {
  return request(`/api/dispatch/assess/${incidentId}`, {
    method: 'POST',
    body: payload,
  });
}

export async function recommendDispatchResources(incidentId, payload = {}) {
  return request(`/api/dispatch/recommend/${incidentId}`, {
    method: 'POST',
    body: payload,
  });
}

export async function optimizeDispatch(payload) {
  return request('/api/dispatch/optimize', {
    method: 'POST',
    body: payload,
  });
}

export async function approveDispatchAssignment(payload) {
  return request('/api/dispatch/approve', {
    method: 'POST',
    body: payload,
  });
}

export async function overrideDispatchAssignment(payload) {
  return request('/api/dispatch/override', {
    method: 'POST',
    body: payload,
  });
}

export async function listDispatchDecisions(params = {}) {
  const query = new URLSearchParams();
  if (params.incident_id) query.append('incident_id', params.incident_id);
  if (params.limit) query.append('limit', params.limit);
  const qs = query.toString();
  return request(`/api/dispatch/decisions${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function recommendReceivingHospitals(incidentId) {
  return request(`/api/dispatch/hospitals/recommend/${incidentId}`, {
    method: 'POST',
  });
}
