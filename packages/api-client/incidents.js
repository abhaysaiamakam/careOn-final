import { request } from './client.js';

export async function reportIncident(incidentData) {
  return request('/api/incidents', {
    method: 'POST',
    body: incidentData,
  });
}

export async function listIncidents(params = {}) {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  if (params.priority) query.append('priority', params.priority);
  if (params.category) query.append('category', params.category);
  if (params.search) query.append('search', params.search);
  if (params.my_requests_only) query.append('my_requests_only', 'true');

  const queryString = query.toString();
  return request(`/api/incidents${queryString ? `?${queryString}` : ''}`, {
    method: 'GET',
  });
}

export async function getIncidentDetails(identifier) {
  return request(`/api/incidents/${identifier}`, {
    method: 'GET',
  });
}

export async function trackPublicIncident(trackingToken) {
  return request(`/api/incidents/track/${encodeURIComponent(trackingToken.trim())}`, {
    method: 'GET',
  });
}

export async function verifyIncidentOtp(incidentId, otp) {
  return request(`/api/incidents/${incidentId}/verify`, {
    method: 'POST',
    body: { otp },
  });
}

export async function cancelIncident(incidentId, reason, details = '') {
  return request(`/api/incidents/${incidentId}/cancel`, {
    method: 'POST',
    body: { reason, details },
  });
}

export async function submitIncidentFeedback(incidentId, rating, comments = '', tags = []) {
  return request('/api/feedback', {
    method: 'POST',
    body: {
      incident_id: incidentId,
      rating,
      comments,
      tags,
    },
  });
}
