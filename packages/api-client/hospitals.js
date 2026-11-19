import { request } from './client.js';

export async function listHospitalFacilities(params = {}) {
  const query = new URLSearchParams();
  if (params.trauma_level) query.append('trauma_level', params.trauma_level);
  if (params.organization_id) query.append('organization_id', params.organization_id);
  if (params.is_active !== undefined) query.append('is_active', params.is_active);
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

export async function updateHospitalFacility(facilityId, data) {
  return request(`/api/hospital/facilities/${facilityId}`, {
    method: 'PATCH',
    body: data,
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

export async function setFacilityDiversion(facilityId, diversionData) {
  return request(`/api/hospital/facilities/${facilityId}/diversion`, {
    method: 'POST',
    body: diversionData,
  });
}

export async function listIncomingPatientRequests(params = {}) {
  const query = new URLSearchParams();
  if (params.facility_id) query.append('facility_id', params.facility_id);
  if (params.status_filter) query.append('status_filter', params.status_filter);
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

// M3 Hospital Readiness & Arrival Endpoints
export async function getHospitalReadiness() {
  return request('/api/hospital/readiness', {
    method: 'GET',
  });
}

export async function updateHospitalReadiness(payload) {
  return request('/api/hospital/readiness', {
    method: 'PATCH',
    body: payload,
  });
}

export async function getIncomingTransports() {
  return request('/api/hospital/incoming', {
    method: 'GET',
  });
}

export async function acknowledgePatientArrival(incidentId, payload = {}) {
  return request(`/api/hospital/incoming/${incidentId}/arrival`, {
    method: 'POST',
    body: payload,
  });
}

export async function getHospitalDirectory() {
  return request('/api/hospital/directory', {
    method: 'GET',
  });
}

export async function assessFacilityReadiness(facilityId, incidentId, assignmentId = null) {
  const query = new URLSearchParams({ incident_id: incidentId });
  if (assignmentId) query.append('assignment_id', assignmentId);
  return request(`/api/hospital/readiness/assess/${facilityId}?${query.toString()}`, {
    method: 'GET',
  });
}

export async function recommendDestinations(incidentId, assignmentId = null, limit = 5) {
  const query = new URLSearchParams({ incident_id: incidentId, limit });
  if (assignmentId) query.append('assignment_id', assignmentId);
  return request(`/api/hospital/destinations/recommend?${query.toString()}`, {
    method: 'GET',
  });
}

export async function planMciDistribution(payload) {
  return request('/api/hospital/mci/distribute', {
    method: 'POST',
    body: payload,
  });
}

export async function sweepCapacityReservations() {
  return request('/api/hospital/reservations/sweep', {
    method: 'POST',
  });
}

export async function sweepIncomingRequestTimeouts() {
  return request('/api/hospital/incoming-requests/sweep', {
    method: 'POST',
  });
}
