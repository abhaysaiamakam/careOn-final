import { request } from './client.js';

export async function listResources(params = {}) {
  const query = new URLSearchParams();
  if (params.category) query.append('category', params.category);
  if (params.status) query.append('status', params.status);
  if (params.search) query.append('search', params.search);
  const qs = query.toString();
  return request(`/api/resources${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function getResource(resourceId) {
  return request(`/api/resources/${resourceId}`, {
    method: 'GET',
  });
}

export async function updateResourceStatus(resourceId, statusVal, notes = '') {
  return request(`/api/resources/${resourceId}/status`, {
    method: 'PUT',
    body: { status: statusVal, notes },
  });
}

export async function findNearbyResources(latitude, longitude, radiusKm = 10, category = null) {
  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    radius_km: String(radiusKm),
  });
  if (category) query.append('category', category);
  return request(`/api/resources/nearby?${query.toString()}`, {
    method: 'GET',
  });
}
