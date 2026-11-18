export { apiClient, ApiError, request } from './client';
import { apiClient } from './client';

// Citizen Operations
export const citizenApi = {
  createIncident: (payload) => apiClient.post('incidents', payload),
  trackIncident: (token) => apiClient.get(`track/${token}`, { requiresAuth: false }),
  cancelIncident: (incidentId, payload) => apiClient.post(`incidents/${incidentId}/cancel`, payload),
  getOwnIncidents: () => apiClient.get('incidents/me'),
};

// Dispatcher Operations
export const dispatcherApi = {
  getIncidents: (params = '') => apiClient.get(`incidents${params ? '?' + params : ''}`),
  verifyIncident: (incidentId, payload) => apiClient.post(`incidents/${incidentId}/verify`, payload),
  updatePriority: (incidentId, payload) => apiClient.patch(`incidents/${incidentId}/priority`, payload),
  recommendAllocation: (incidentId) => apiClient.post(`incidents/${incidentId}/recommend-allocation`),
  confirmAllocation: (incidentId, payload) => apiClient.post(`incidents/${incidentId}/confirm-allocation`, payload),
  getResources: () => apiClient.get('resources'),
  getShortages: () => apiClient.get('algorithms/shortages'),
};

// Responder Operations (Mobile & Responsive Web)
export const responderApi = {
  getProfile: () => apiClient.get('responder/me'),
  getMissions: () => apiClient.get('responder/missions'),
  getMissionDetail: (assignmentId) => apiClient.get(`responder/missions/${assignmentId}`),
  acceptMission: (assignmentId, reason = '') => apiClient.post(`responder/missions/${assignmentId}/accept`, { reason }),
  rejectMission: (assignmentId, reason) => apiClient.post(`responder/missions/${assignmentId}/reject`, { reason }),
  updateStatus: (assignmentId, status, notes = '') => apiClient.post(`responder/missions/${assignmentId}/status`, { status, notes }),
  sendTelemetry: (latitude, longitude, speed = null) => apiClient.post('responder/telemetry', { latitude, longitude, speed }),
};

// Hospital Operations
export const hospitalApi = {
  getReadiness: () => apiClient.get('hospital/readiness'),
  updateReadiness: (payload) => apiClient.patch('hospital/readiness', payload),
  getIncomingPatients: () => apiClient.get('hospital/incoming'),
  acknowledgeArrival: (incidentId, bedType = 'er_bed', notes = '') => apiClient.post(`hospital/incoming/${incidentId}/arrival`, { bed_type: bedType, intake_notes: notes }),
  getDirectory: () => apiClient.get('hospital/directory'),
};

// Super Admin Operations
export const superAdminApi = {
  getSystemHealth: () => apiClient.get('admin/system-health'),
  getAuditLogs: (params = '') => apiClient.get(`admin/audit-logs${params ? '?' + params : ''}`),
  getUsers: (params = '') => apiClient.get(`admin/users${params ? '?' + params : ''}`),
  updateUserRole: (userId, role) => apiClient.patch(`admin/users/${userId}/role`, { role }),
  updateUserStatus: (userId, isActive, reason = '') => apiClient.patch(`admin/users/${userId}/status`, { is_active: isActive, reason }),
  getOperationsSummary: () => apiClient.get('admin/operations-summary'),
};
