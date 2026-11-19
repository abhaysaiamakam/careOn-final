/**
 * CareOn Core HTTP API Client.
 * Handles:
 * - Environment-aware base URLs
 * - Automatic Authorization: Bearer token injection
 * - Structured error normalization
 * - HTTP 429 rate limit reporting
 * - Network failure detection
 */

let authTokenGetter = () => null;

export function setAuthTokenGetter(fn) {
  authTokenGetter = fn;
}

export function getBaseUrl() {
  if (typeof window !== 'undefined' && window.__CAREON_API_BASE__) {
    return window.__CAREON_API_BASE__;
  }
  // If Vite env is defined
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) {
      return import.meta.env.VITE_API_URL;
    }
  } catch (e) {
    // ignore
  }
  return ''; // Default uses relative /api (proxied by Vite)
}

export async function request(endpoint, options = {}) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const token = authTokenGetter();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  try {
    const response = await fetch(url, config);

    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const errorMsg = (data && data.detail) || (typeof data === 'string' ? data : 'API Request failed');
      const error = new Error(errorMsg);
      error.status = response.status;
      error.data = data;
      if (response.status === 429) {
        error.isRateLimited = true;
      }
      throw error;
    }

    return data;
  } catch (error) {
    if (!error.status) {
      // Network failure or offline
      error.isNetworkError = true;
      error.message = 'Unable to reach CareOn emergency servers. Check your internet connection.';
    }
    throw error;
  }
}
