import { request } from './client.js';

export async function getCitizenProfile() {
  return request('/api/citizen/profile', {
    method: 'GET',
  });
}

export async function updateCitizenProfile(updateData) {
  return request('/api/citizen/profile', {
    method: 'PUT',
    body: updateData,
  });
}

export async function completeCitizenOnboarding() {
  return request('/api/citizen/onboarding/complete', {
    method: 'POST',
  });
}

export async function listCitizenContacts() {
  return request('/api/citizen/contacts', {
    method: 'GET',
  });
}

export async function createCitizenContact(contactData) {
  return request('/api/citizen/contacts', {
    method: 'POST',
    body: contactData,
  });
}

export async function updateCitizenContact(contactId, contactData) {
  return request(`/api/citizen/contacts/${contactId}`, {
    method: 'PUT',
    body: contactData,
  });
}

export async function deleteCitizenContact(contactId) {
  return request(`/api/citizen/contacts/${contactId}`, {
    method: 'DELETE',
  });
}

export async function getCitizenDashboardSummary() {
  return request('/api/citizen/dashboard-summary', {
    method: 'GET',
  });
}
