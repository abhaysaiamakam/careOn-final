import React, { createContext, useState, useEffect, useCallback, useRef } from 'react';
import { getApiBase, setInMemoryToken, clearInMemoryToken, getInMemoryToken } from '../api';

export const AuthContext = createContext(null);

/**
 * Decode JWT claims without verifying signature (client-side only).
 * We do NOT trust these claims for security decisions — the server validates.
 * We use them only for expiry checks and display info.
 */
function decodeJwtPayload(token) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1];
    // base64url → base64 → JSON
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function isTokenExpired(token) {
  if (!token) return true;
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.exp) return true;
  // Add 10s buffer to avoid edge cases
  return Date.now() / 1000 >= payload.exp - 10;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessTokenState] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState(null);

  // Track whether we are currently refreshing to avoid parallel refresh calls
  const refreshingRef = useRef(false);

  // Sync the in-memory token module-level variable with our state
  const updateAccessToken = useCallback((token) => {
    setAccessTokenState(token);
    if (token) {
      setInMemoryToken(token);
    } else {
      clearInMemoryToken();
    }
  }, []);

  /**
   * refreshAccessToken — exchanges the stored refresh token for a new access token.
   * Returns true on success, false on any failure.
   * Handles 404 gracefully (endpoint may not exist yet).
   */
  const refreshAccessToken = useCallback(async () => {
    if (refreshingRef.current) return false;
    refreshingRef.current = true;
    try {
      const rawToken = localStorage.getItem('careon_refresh_token');
      if (!rawToken) return false;

      const apiBase = getApiBase();
      const res = await fetch(`${apiBase}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rawToken }),
      });

      if (res.status === 404) {
        // Endpoint not implemented yet — graceful no-op
        return false;
      }

      if (res.status === 401 || res.status === 403) {
        // Refresh token is invalid/revoked — force logout
        await logout(); // eslint-disable-line no-use-before-define
        return false;
      }

      if (!res.ok) return false;

      const data = await res.json().catch(() => null);
      if (!data) return false;

      const newAccessToken = data.access_token || data.accessToken;
      const newRefreshToken = data.refresh_token || data.refreshToken;

      if (newAccessToken) {
        updateAccessToken(newAccessToken);
      }
      if (newRefreshToken) {
        localStorage.setItem('careon_refresh_token', newRefreshToken);
      }
      return !!newAccessToken;
    } catch {
      return false;
    } finally {
      refreshingRef.current = false;
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * logout — clears all auth state and localStorage tokens.
   */
  const logout = useCallback(async () => {
    // Fire-and-forget logout request — may not exist yet
    try {
      const apiBase = getApiBase();
      const token = getInMemoryToken();
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      fetch(`${apiBase}/auth/logout`, { method: 'POST', headers }).catch(() => {});
    } catch {
      // ignore
    }

    // Clear in-memory token
    updateAccessToken(null);

    // Clear all localStorage auth keys
    const keysToRemove = [
      'careon_token',
      'careon_user_token',
      'careon_admin_token',
      'careon_user_info',
      'careon_admin_info',
      'careon_refresh_token',
    ];
    keysToRemove.forEach((k) => localStorage.removeItem(k));

    setUser(null);
    setIsAuthenticated(false);
    setRole(null);
  }, [updateAccessToken]);

  /**
   * getAccessToken — returns a valid in-memory access token, refreshing silently if needed.
   */
  const getAccessToken = useCallback(async () => {
    const current = getInMemoryToken();
    if (current && !isTokenExpired(current)) {
      return current;
    }
    // Try refresh
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return getInMemoryToken();
    }
    return null;
  }, [refreshAccessToken]);

  /**
   * login — authenticates the user, stores tokens appropriately.
   */
  const login = useCallback(async (email, password) => {
    try {
      const apiBase = getApiBase();
      const res = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return { success: false, error: err.detail || 'Invalid email or password.' };
      }

      const data = await res.json().catch(() => null);
      if (!data) return { success: false, error: 'Unexpected server response.' };

      const newAccessToken = data.access_token || data.accessToken;
      const newRefreshToken = data.refresh_token || data.refreshToken;
      const userData = data.user || null;

      if (!newAccessToken) {
        return { success: false, error: 'No access token returned from server.' };
      }

      // Store access token in memory only
      updateAccessToken(newAccessToken);

      // Store refresh token in localStorage (temporary until httpOnly cookie endpoint available)
      if (newRefreshToken) {
        localStorage.setItem('careon_refresh_token', newRefreshToken);
      }

      // Build safe user info (non-sensitive)
      const userInfo = userData
        ? {
            id: userData.id,
            email: userData.email,
            name: userData.name || userData.full_name || email,
            role: userData.role,
            phone: userData.phone || null,
          }
        : null;

      if (userInfo) {
        // Store non-sensitive user info for session restore
        localStorage.setItem('careon_user_info', JSON.stringify(userInfo));

        // Backward compat — also set legacy keys so existing code doesn't break
        if (userInfo.role === 'admin' || userInfo.role === 'super_admin') {
          localStorage.setItem('careon_admin_token', newAccessToken);
          localStorage.setItem('careon_admin_info', JSON.stringify(userInfo));
        } else {
          localStorage.setItem('careon_user_token', newAccessToken);
        }
        // Always set legacy single token fallback
        localStorage.setItem('careon_token', newAccessToken);

        setUser(userInfo);
        setRole(userInfo.role);
        setIsAuthenticated(true);
      }

      return { success: true };
    } catch (err) {
      return { success: false, error: err?.message || 'Network error. Please try again.' };
    }
  }, [updateAccessToken]);

  /**
   * On mount: restore session from localStorage, then attempt token refresh.
   */
  useEffect(() => {
    async function initAuth() {
      try {
        // 1. Attempt to restore user info from localStorage
        let restoredUser = null;
        try {
          const raw = localStorage.getItem('careon_user_info');
          if (raw) restoredUser = JSON.parse(raw);
        } catch {
          // ignore parse errors
        }

        // 2. Backward compat: check legacy admin/user info if careon_user_info not set
        if (!restoredUser) {
          try {
            const adminRaw = localStorage.getItem('careon_admin_info');
            if (adminRaw) restoredUser = JSON.parse(adminRaw);
          } catch {
            // ignore
          }
        }

        if (restoredUser) {
          setUser(restoredUser);
          setRole(restoredUser.role);
          setIsAuthenticated(true);
        }

        // 3. Try to populate in-memory token from legacy localStorage (backward compat)
        //    so existing logged-in users are not forced to re-login
        const legacyToken =
          localStorage.getItem('careon_admin_token') ||
          localStorage.getItem('careon_user_token') ||
          localStorage.getItem('careon_token');

        if (legacyToken && !isTokenExpired(legacyToken)) {
          updateAccessToken(legacyToken);
        }

        // 4. Attempt a refresh to get a fresh access token
        //    This overwrites the legacy token if the refresh endpoint is available
        await refreshAccessToken();
      } catch {
        // If anything fails during init, we just leave auth state as-is
      } finally {
        setIsLoading(false);
      }
    }

    initAuth();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value = {
    user,
    accessToken,
    isLoading,
    isAuthenticated,
    role,
    login,
    logout,
    refreshAccessToken,
    getAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
