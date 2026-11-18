// Dynamic API base resolution for multi-device network support (Mac, Android phone, other laptops)
export const getApiBase = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && window.location) {
    // When served via Nginx (port 3000 or 80), use same-origin '/api' to avoid CORS and port mismatches
    if (window.location.port === '3000' || window.location.port === '80' || !window.location.port) {
      return '/api';
    }
    const host = window.location.hostname || 'localhost';
    return `http://${host}:8000/api`;
  }
  return 'http://localhost:8000/api';
};

const API_BASE = getApiBase();

// In-memory token storage (XSS protection: access tokens kept in memory)
let _inMemoryToken = null;

export function setInMemoryToken(token) {
  _inMemoryToken = token;
}

export function clearInMemoryToken() {
  _inMemoryToken = null;
}

export function getInMemoryToken() {
  return _inMemoryToken;
}

/**
 * Returns auth headers.
 * Prefers in-memory token for XSS security, falls back to localStorage.
 * Supports dual simultaneous sessions:
 * - 'admin': uses careon_admin_token
 * - 'user': uses careon_user_token
 * - 'auto': detects based on current URL path
 */
export function getAuthHeaders(scope = 'auto') {
  let token = _inMemoryToken;
  if (!token && typeof localStorage !== 'undefined') {
    if (scope === 'admin') {
      token = localStorage.getItem('careon_admin_token') || localStorage.getItem('careon_token');
    } else if (scope === 'user') {
      token = localStorage.getItem('careon_user_token') || localStorage.getItem('careon_token');
    } else {
      // Auto-detect based on route
      const isApiPathAdmin = typeof window !== 'undefined' && window.location.pathname.startsWith('/admin');
      if (isApiPathAdmin) {
        token = localStorage.getItem('careon_admin_token') || localStorage.getItem('careon_user_token');
      } else {
        token = localStorage.getItem('careon_user_token') || localStorage.getItem('careon_admin_token');
      }
    }
    // Fallback to legacy single token if neither is found
    if (!token) {
      token = localStorage.getItem('careon_token');
    }
  }

  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Session Helpers
export function getStoredUserSession() {
  try {
    const raw = localStorage.getItem('careon_user_info');
    if (raw) return JSON.parse(raw);
    const legacy = localStorage.getItem('careon_user');
    if (legacy) {
      const u = JSON.parse(legacy);
      if (u.role === 'user') return u;
    }
    return null;
  } catch {
    return null;
  }
}

export function getStoredAdminSession() {
  try {
    const raw = localStorage.getItem('careon_admin_info');
    if (raw) return JSON.parse(raw);
    const legacy = localStorage.getItem('careon_user');
    if (legacy) {
      const u = JSON.parse(legacy);
      if (u.role === 'admin') return u;
    }
    return null;
  } catch {
    return null;
  }
}

export function logoutUser() {
  localStorage.removeItem('careon_user_token');
  localStorage.removeItem('careon_user_info');
}

export function logoutAdmin() {
  localStorage.removeItem('careon_admin_token');
  localStorage.removeItem('careon_admin_info');
}

// ==============================================================================
// System & Health
// ==============================================================================
export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch statistics');
  return res.json();
}

// ==============================================================================
// Auth
// ==============================================================================
export async function registerUser(payload) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Registration failed. Please check your information.');
  }
  const data = await res.json();
  if (data.access_token && data.user) {
    localStorage.setItem('careon_user_token', data.access_token);
    localStorage.setItem('careon_user_info', JSON.stringify(data.user));
    localStorage.setItem('careon_token', data.access_token); // fallback
    localStorage.setItem('careon_user', JSON.stringify(data.user));
  }
  return data;
}

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid email or password.');
  }
  const data = await res.json();
  if (data.access_token && data.user) {
    localStorage.setItem('careon_user_token', data.access_token);
    localStorage.setItem('careon_user_info', JSON.stringify(data.user));
    localStorage.setItem('careon_token', data.access_token);
    localStorage.setItem('careon_user', JSON.stringify(data.user));
  }
  return data;
}

export async function loginAdmin(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid coordinator credentials.');
  }
  const data = await res.json();
  if (data.user?.role !== 'admin') {
    throw new Error('Access denied. Administrator privileges required to access the Command Centre.');
  }
  if (data.access_token && data.user) {
    localStorage.setItem('careon_admin_token', data.access_token);
    localStorage.setItem('careon_admin_info', JSON.stringify(data.user));
  }
  return data;
}

export async function fetchCurrentUser(scope = 'auto') {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) return null;
  return res.json();
}

// ==============================================================================
// Incidents
// ==============================================================================
export async function reportIncident(data) {
  const res = await fetch(`${API_BASE}/incidents`, {
    method: 'POST',
    headers: getAuthHeaders('user'),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit emergency report');
  }
  return res.json();
}

export async function fetchIncidents(params = {}, scope = 'auto') {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  if (params.priority) query.append('priority', params.priority);
  if (params.category) query.append('category', params.category);
  if (params.search) query.append('search', params.search);
  if (params.my_requests_only) query.append('my_requests_only', 'true');

  const res = await fetch(`${API_BASE}/incidents?${query.toString()}`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) throw new Error('Failed to fetch incidents');
  return res.json();
}

export async function fetchIncidentDetails(idOrCode, scope = 'auto') {
  const res = await fetch(`${API_BASE}/incidents/${idOrCode}`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) throw new Error(`Incident ${idOrCode} not found or access restricted`);
  return res.json();
}

export async function fetchPublicTracking(trackingToken) {
  const res = await fetch(`${API_BASE}/incidents/track/${encodeURIComponent(trackingToken)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Incident tracking record not found.');
  }
  return res.json();
}

export async function verifyIncidentOtp(incidentId, otp, scope = 'auto') {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/verify`, {
    method: 'POST',
    headers: getAuthHeaders(scope),
    body: JSON.stringify({ otp }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Verification failed. Use demo OTP 123456');
  }
  return res.json();
}

export async function updateIncidentStatus(incidentId, status, message = '', internalNotes = '') {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/status`, {
    method: 'PATCH',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify({ status, message, internal_admin_notes: internalNotes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update status');
  }
  return res.json();
}

export async function updateIncidentPriority(incidentId, priority, reason) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/priority`, {
    method: 'PATCH',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify({ priority, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update priority');
  }
  return res.json();
}

export async function cancelIncident(incidentId, reason, details = '', scope = 'user') {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/cancel`, {
    method: 'POST',
    headers: getAuthHeaders(scope),
    body: JSON.stringify({ reason, details }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to cancel incident');
  }
  return res.json();
}

export async function acknowledgeCancellation(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/acknowledge-cancellation`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to acknowledge cancellation');
  return res.json();
}

export async function resolveIncident(incidentId, notes = '') {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/resolve?notes=${encodeURIComponent(notes)}`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to resolve incident');
  return res.json();
}

// ==============================================================================
// Resources & Allocation
// ==============================================================================
export async function fetchResources(params = {}, scope = 'admin') {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  if (params.category) query.append('category', params.category);

  const res = await fetch(`${API_BASE}/resources?${query.toString()}`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) throw new Error('Failed to fetch resources');
  return res.json();
}

export async function updateResourceStatus(resourceId, status) {
  const res = await fetch(`${API_BASE}/resources/${resourceId}`, {
    method: 'PATCH',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to update resource');
  return res.json();
}

export async function getRecommendedAllocation(incidentId) {
  const res = await fetch(`${API_BASE}/allocations/recommend`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify({ incident_id: incidentId }),
  });
  if (!res.ok) throw new Error('Failed to generate recommendation');
  return res.json();
}

export async function getMultiAllocations() {
  const res = await fetch(`${API_BASE}/allocations/multi-recommend`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to evaluate multi-incident allocations');
  return res.json();
}

export async function confirmAllocation(incidentId, resourceId, notes = '') {
  const res = await fetch(`${API_BASE}/allocations/confirm`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify({ incident_id: incidentId, resource_id: resourceId, notes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Allocation conflict or invalid resource');
  }
  return res.json();
}

export async function releaseAllocation(assignmentId) {
  const res = await fetch(`${API_BASE}/allocations/${assignmentId}/release`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to release resource');
  return res.json();
}

export async function fetchShortages() {
  const res = await fetch(`${API_BASE}/allocations/shortages`, {
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to fetch shortages');
  return res.json();
}

// ==============================================================================
// External Providers
// ==============================================================================
export async function fetchProviders(scope = 'admin') {
  const res = await fetch(`${API_BASE}/providers`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) throw new Error('Failed to fetch providers');
  return res.json();
}

export async function createProviderEnquiry(payload) {
  const res = await fetch(`${API_BASE}/providers/enquiries`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to record provider enquiry');
  return res.json();
}

export async function updateProviderEnquiry(enquiryId, payload) {
  const res = await fetch(`${API_BASE}/providers/enquiries/${enquiryId}`, {
    method: 'PATCH',
    headers: getAuthHeaders('admin'),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update provider enquiry');
  return res.json();
}

// ==============================================================================
// Notifications & Feedback
// ==============================================================================
export async function fetchNotifications(scope = 'auto') {
  const res = await fetch(`${API_BASE}/notifications`, {
    headers: getAuthHeaders(scope),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function markNotificationAsRead(id, scope = 'auto') {
  const res = await fetch(`${API_BASE}/notifications/${id}/read`, {
    method: 'PATCH',
    headers: getAuthHeaders(scope),
  });
  return res.ok;
}

export async function submitFeedback(payload) {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: getAuthHeaders('user'),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit feedback');
  }
  return res.json();
}

export async function fetchFeedbackList() {
  const res = await fetch(`${API_BASE}/feedback`, {
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) return [];
  return res.json();
}

// ==============================================================================
// Chatbot & Simulation & Analytics
// ==============================================================================
export async function sendChatMessage(message, sessionId = 'careon_user_session') {
  const res = await fetch(`${API_BASE}/chatbot/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error('Chatbot service unavailable');
  return res.json();
}

export async function fetchAnalytics() {
  const res = await fetch(`${API_BASE}/admin/analytics`, {
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function fetchPredictions(zone = '') {
  const url = `${API_BASE}/admin/predictions${zone ? `?zone=${encodeURIComponent(zone)}` : ''}`;
  const res = await fetch(url, {
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function resetSimulationData() {
  const res = await fetch(`${API_BASE}/simulation/reset`, {
    method: 'POST',
    headers: getAuthHeaders('admin'),
  });
  if (!res.ok) throw new Error('Failed to reset simulation');
  return res.json();
}

// ==============================================================================
// Legacy Compatibility Methods for existing tests
// ==============================================================================
export async function fetchEmergencies(status = '', priority = '') {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (priority) params.append('priority', priority);

  const url = `${API_BASE}/emergencies${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch emergencies');
  return res.json();
}

export async function createEmergency(data) {
  const res = await fetch(`${API_BASE}/emergencies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail?.[0]?.msg || errorData.detail || 'Failed to dispatch emergency');
  }
  return res.json();
}

export async function updateEmergencyStatus(id, newStatus) {
  const res = await fetch(`${API_BASE}/emergencies/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  });
  if (!res.ok) throw new Error('Failed to update status');
  return res.json();
}

export async function deleteEmergency(id) {
  const res = await fetch(`${API_BASE}/emergencies/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete emergency');
  return true;
}
