import { request } from './client.js';

export async function loginUser(email, password) {
  return request('/api/auth/login', {
    method: 'POST',
    body: { email, password },
  });
}

export async function registerUser(userData) {
  return request('/api/auth/register', {
    method: 'POST',
    body: userData,
  });
}

export async function getMe() {
  return request('/api/auth/me', {
    method: 'GET',
  });
}

export async function refreshToken(refreshTokenValue) {
  return request('/api/auth/refresh', {
    method: 'POST',
    body: { refresh_token: refreshTokenValue },
  });
}

export async function logoutUser(refreshTokenValue) {
  return request('/api/auth/logout', {
    method: 'POST',
    body: { refresh_token: refreshTokenValue },
  });
}
