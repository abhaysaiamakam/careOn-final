import { request } from './client.js';

export async function listMutualAidPartners() {
  return request('/api/coordination/v1/mutual-aid-partners', {
    method: 'GET',
  });
}

export async function listIncidentCollaborations(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/collaborations`, {
    method: 'GET',
  });
}

export async function inviteIncidentCollaboration(incidentId, payload) {
  return request(`/api/coordination/v1/incidents/${incidentId}/collaborations/invite`, {
    method: 'POST',
    body: payload,
  });
}

export async function actionIncidentCollaboration(collaborationId, action, notes = '') {
  return request(`/api/coordination/v1/collaborations/${collaborationId}/action`, {
    method: 'POST',
    body: { action, notes },
  });
}

export async function getIncidentCommand(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/command`, {
    method: 'GET',
  });
}

export async function establishIncidentCommand(incidentId, payload) {
  return request(`/api/coordination/v1/incidents/${incidentId}/command/establish`, {
    method: 'POST',
    body: payload,
  });
}

export async function transferIncidentCommand(commandStructureId, payload) {
  return request(`/api/coordination/v1/command/${commandStructureId}/transfer`, {
    method: 'POST',
    body: payload,
  });
}

export async function listAgencyTasks(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/tasks`, {
    method: 'GET',
  });
}

export async function createAgencyTask(incidentId, payload) {
  return request(`/api/coordination/v1/incidents/${incidentId}/tasks`, {
    method: 'POST',
    body: payload,
  });
}

export async function updateAgencyTask(taskId, payload) {
  return request(`/api/coordination/v1/tasks/${taskId}`, {
    method: 'PUT',
    body: payload,
  });
}

export async function listOperationalZones(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/zones`, {
    method: 'GET',
  });
}

export async function createOperationalZone(incidentId, payload) {
  return request(`/api/coordination/v1/incidents/${incidentId}/zones`, {
    method: 'POST',
    body: payload,
  });
}

export async function getOperationalPicture(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/operational-picture`, {
    method: 'GET',
  });
}

export async function getInterAgencyAuditLogs(incidentId) {
  return request(`/api/coordination/v1/incidents/${incidentId}/audit-logs`, {
    method: 'GET',
  });
}
