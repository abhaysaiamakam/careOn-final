import { request } from './client.js';

export async function listIncidentEncounters(incidentId) {
  return request(`/api/clinical/incidents/${incidentId}/encounters`, {
    method: 'GET',
  });
}

export async function getEncounterTimeline(encounterId) {
  return request(`/api/clinical/encounters/${encounterId}/timeline`, {
    method: 'GET',
  });
}

export async function getEncounterSummary(encounterId) {
  return request(`/api/clinical/encounters/${encounterId}/summary`, {
    method: 'GET',
  });
}

export async function getHandoverRecord(handoverToken) {
  return request(`/api/clinical/handovers/${encodeURIComponent(handoverToken)}`, {
    method: 'GET',
  });
}

export async function getHandoverVersions(handoverToken) {
  return request(`/api/clinical/handovers/${encodeURIComponent(handoverToken)}/versions`, {
    method: 'GET',
  });
}
