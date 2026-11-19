import { request } from './client.js';

export async function getDemandAnalytics(params = {}) {
  const query = new URLSearchParams();
  if (params.time_window) query.append('time_window', params.time_window);
  const qs = query.toString();
  return request(`/api/intelligence/v1/demand/analytics${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function analyzeHotspots(payload = {}) {
  return request('/api/intelligence/v1/hotspots/analyze', {
    method: 'POST',
    body: payload,
  });
}

export async function generateForecast(payload = {}) {
  return request('/api/intelligence/v1/forecasts/generate', {
    method: 'POST',
    body: payload,
  });
}

export async function analyzeCoverage(payload = {}) {
  return request('/api/intelligence/v1/coverage/analyze', {
    method: 'POST',
    body: payload,
  });
}

export async function listPositioningRecommendations(params = {}) {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  const qs = query.toString();
  return request(`/api/intelligence/v1/recommendations${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function approvePositioningRecommendation(recommendationId, payload = {}) {
  return request(`/api/intelligence/v1/recommendations/${recommendationId}/approve`, {
    method: 'POST',
    body: payload,
  });
}

export async function rejectPositioningRecommendation(recommendationId, reason = '') {
  return request(`/api/intelligence/v1/recommendations/${recommendationId}/reject`, {
    method: 'POST',
    body: { rejection_reason: reason },
  });
}

export async function getModelHealth() {
  return request('/api/intelligence/v1/models/health', {
    method: 'GET',
  });
}
