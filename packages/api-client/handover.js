import { request } from './client.js';

export async function createPatient(payload) {
  return request('/api/clinical/patients', {
    method: 'POST',
    body: payload,
  });
}

export async function getPatient(patientId) {
  return request(`/api/clinical/patients/${patientId}`, {
    method: 'GET',
  });
}

export async function createEncounter(payload) {
  return request('/api/clinical/encounters', {
    method: 'POST',
    body: payload,
  });
}

export async function getEncounter(encounterId) {
  return request(`/api/clinical/encounters/${encounterId}`, {
    method: 'GET',
  });
}

export async function listIncidentEncounters(incidentId) {
  return request(`/api/clinical/incidents/${incidentId}/encounters`, {
    method: 'GET',
  });
}

export async function recordClinicalAssessment(encounterId, payload) {
  return request(`/api/clinical/encounters/${encounterId}/assessments`, {
    method: 'POST',
    body: payload,
  });
}

export async function recordVitalSigns(encounterId, payload) {
  return request(`/api/clinical/encounters/${encounterId}/vitals`, {
    method: 'POST',
    body: payload,
  });
}

export async function recordIntervention(encounterId, payload) {
  return request(`/api/clinical/encounters/${encounterId}/interventions`, {
    method: 'POST',
    body: payload,
  });
}

export async function recordMedication(encounterId, payload) {
  return request(`/api/clinical/encounters/${encounterId}/medications`, {
    method: 'POST',
    body: payload,
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

export async function createHandoverRecord(payload) {
  return request('/api/clinical/handovers', {
    method: 'POST',
    body: payload,
  });
}

export async function submitHandoverRecord(handoverToken, payload = {}) {
  return request(`/api/clinical/handovers/${encodeURIComponent(handoverToken)}/submit`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
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

export async function actionHandoverRecord(handoverToken, action, notesOrPayload = '') {
  const payload = typeof notesOrPayload === 'object'
    ? { action, ...notesOrPayload }
    : { action, clarification_notes: notesOrPayload, correction_reason: notesOrPayload, notes: notesOrPayload };
  return request(`/api/clinical/handovers/${encodeURIComponent(handoverToken)}/action`, {
    method: 'POST',
    body: payload,
  });
}
