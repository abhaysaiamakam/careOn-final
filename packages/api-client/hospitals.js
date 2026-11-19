import { request } from './client.js';

export async function listHospitalFacilities(params = {}) {
  const query = new URLSearchParams();
  if (params.trauma_level) query.append('trauma_level', params.trauma_level);
  const qs = query.toString();
  return request(`/api/hospital/facilities${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function getHospitalFacility(facilityId) {
  return request(`/api/hospital/facilities/${facilityId}`, {
    method: 'GET',
  });
}

export async function getFacilityCapacity(facilityId) {
  return request(`/api/hospital/facilities/${facilityId}/capacity`, {
    method: 'GET',
  });
}

export async function updateFacilityCapacity(facilityId, capacityData) {
  return request(`/api/hospital/facilities/${facilityId}/capacity`, {
    method: 'PUT',
    body: capacityData,
  });
}

export async function getFacilityDiversion(facilityId) {
  return request(`/api/hospital/facilities/${facilityId}/diversion`, {
    method: 'GET',
  });
}

export async function listIncomingPatientRequests(params = {}) {
  const query = new URLSearchParams();
  if (params.facility_id) query.append('facility_id', params.facility_id);
  const qs = query.toString();
  return request(`/api/hospital/incoming-requests${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  });
}

export async function createIncomingPatientRequest(requestData) {
  return request('/api/hospital/incoming-requests', {
    method: 'POST',
    body: requestData,
  });
}

export async function respondIncomingPatientRequest(requestToken, responseData) {
  return request(`/api/hospital/incoming-requests/${requestToken}/respond`, {
    method: 'POST',
    body: responseData,
  });
}

export async function cancelIncomingPatientRequest(requestToken, reason = '') {
  return request(`/api/hospital/incoming-requests/${requestToken}/cancel`, {
    method: 'POST',
    body: { reason },
  });
}
