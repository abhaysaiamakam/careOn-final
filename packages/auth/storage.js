/**
 * CareOn Client Auth Storage.
 * Isolates token storage logic with customizable storage prefixes.
 */

let activePrefix = 'careon_auth';

export function configureAuthStoragePrefix(prefix) {
  if (prefix) activePrefix = prefix;
}

export function getStoredAccessToken(prefix = activePrefix) {
  try {
    return localStorage.getItem(`${prefix}_access_token`);
  } catch (e) {
    return null;
  }
}

export function getStoredRefreshToken(prefix = activePrefix) {
  try {
    return localStorage.getItem(`${prefix}_refresh_token`);
  } catch (e) {
    return null;
  }
}

export function getStoredUser(prefix = activePrefix) {
  try {
    const raw = localStorage.getItem(`${prefix}_user`);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function setStoredAuth(accessToken, refreshToken, user, prefix = activePrefix) {
  try {
    if (accessToken) localStorage.setItem(`${prefix}_access_token`, accessToken);
    if (refreshToken) localStorage.setItem(`${prefix}_refresh_token`, refreshToken);
    if (user) localStorage.setItem(`${prefix}_user`, JSON.stringify(user));
  } catch (e) {
    console.error('Failed to store auth tokens:', e);
  }
}

export function clearStoredAuth(prefix = activePrefix) {
  try {
    localStorage.removeItem(`${prefix}_access_token`);
    localStorage.removeItem(`${prefix}_refresh_token`);
    localStorage.removeItem(`${prefix}_user`);
  } catch (e) {
    console.error('Failed to clear auth storage:', e);
  }
}
