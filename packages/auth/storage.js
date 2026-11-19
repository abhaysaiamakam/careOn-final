/**
 * CareOn Client Auth Storage.
 * Isolates token storage logic.
 */

const ACCESS_TOKEN_KEY = 'careon_citizen_access_token';
const REFRESH_TOKEN_KEY = 'careon_citizen_refresh_token';
const USER_KEY = 'careon_citizen_user';

export function getStoredAccessToken() {
  try {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch (e) {
    return null;
  }
}

export function getStoredRefreshToken() {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch (e) {
    return null;
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function setStoredAuth(accessToken, refreshToken, user) {
  try {
    if (accessToken) localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch (e) {
    console.error('Failed to store auth tokens:', e);
  }
}

export function clearStoredAuth() {
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch (e) {
    console.error('Failed to clear auth storage:', e);
  }
}
