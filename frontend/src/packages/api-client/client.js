/**
 * CareOn Unified API Client.
 * 
 * Features:
 * - Dynamic base URL resolution across local dev, Docker, and separate domains
 * - In-memory access token storage (XSS prevention)
 * - Transparent token refresh on 401 Unauthorized
 * - Request timeouts and standardized error normalization
 */

import { getApiBase, getInMemoryToken, setInMemoryToken, clearInMemoryToken } from '../../api';

export class ApiError extends Error {
  constructor(message, status = 500, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export async function request(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    headers = {},
    timeout = 15000,
    requiresAuth = true,
    ...customConfig
  } = options;

  const baseUrl = getApiBase();
  // Strip duplicate leading/trailing slashes
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  const url = `${baseUrl}/${cleanEndpoint}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (requiresAuth) {
    const token = getInMemoryToken() || (typeof localStorage !== 'undefined' ? localStorage.getItem('careon_token') || localStorage.getItem('careon_user_token') || localStorage.getItem('careon_admin_token') : null);
    if (token) {
      defaultHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  const config = {
    method,
    headers: defaultHeaders,
    signal: controller.signal,
    ...customConfig,
  };

  if (body) {
    config.body = typeof body === 'string' ? body : JSON.stringify(body);
  }

  try {
    const response = await fetch(url, config);
    clearTimeout(timeoutId);

    // If 401 Unauthorized, attempt refresh token rotation once
    if (response.status === 401 && requiresAuth) {
      const refreshToken = typeof localStorage !== 'undefined' ? localStorage.getItem('careon_refresh_token') : null;
      if (refreshToken && !isRefreshing) {
        isRefreshing = true;
        try {
          const refreshRes = await fetch(`${baseUrl}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            setInMemoryToken(data.access_token);
            if (typeof localStorage !== 'undefined' && data.refresh_token) {
              localStorage.setItem('careon_refresh_token', data.refresh_token);
            }
            processQueue(null, data.access_token);
            // Retry original request
            defaultHeaders['Authorization'] = `Bearer ${data.access_token}`;
            const retryRes = await fetch(url, { ...config, headers: defaultHeaders });
            return await parseResponse(retryRes);
          } else {
            clearInMemoryToken();
            processQueue(new ApiError('Session expired. Please log in again.', 401), null);
          }
        } catch (err) {
          processQueue(err, null);
        } finally {
          isRefreshing = false;
        }
      }
    }

    return await parseResponse(response);
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out. Please check your connection.', 408);
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Network error occurred.', 500, err);
  }
}

async function parseResponse(response) {
  let data;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const message = (data && (data.detail || data.message)) || `HTTP ${response.status}: Request failed`;
    throw new ApiError(message, response.status, data);
  }

  return data;
}

export const apiClient = {
  get: (url, options = {}) => request(url, { ...options, method: 'GET' }),
  post: (url, body, options = {}) => request(url, { ...options, method: 'POST', body }),
  patch: (url, body, options = {}) => request(url, { ...options, method: 'PATCH', body }),
  put: (url, body, options = {}) => request(url, { ...options, method: 'PUT', body }),
  delete: (url, options = {}) => request(url, { ...options, method: 'DELETE' }),
};
