import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredUser,
  setStoredAuth,
  clearStoredAuth,
} from './storage.js';

const AuthContext = createContext({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  refreshProfile: async () => {},
});

export function AuthProvider({
  children,
  apiClient, // Injected @careon/api-client
}) {
  const [user, setUser] = useState(getStoredUser());
  const [accessToken, setAccessToken] = useState(getStoredAccessToken());
  const [isLoading, setIsLoading] = useState(true);

  // Bind token getter to api client
  useEffect(() => {
    if (apiClient && apiClient.setAuthTokenGetter) {
      apiClient.setAuthTokenGetter(() => accessToken);
    }
  }, [apiClient, accessToken]);

  // Initial session verification
  useEffect(() => {
    let mounted = true;
    async function initAuth() {
      const token = getStoredAccessToken();
      if (!token) {
        if (mounted) setIsLoading(false);
        return;
      }

      try {
        if (apiClient && apiClient.getMe) {
          const profile = await apiClient.getMe();
          if (mounted) {
            setUser(profile);
            setStoredAuth(token, getStoredRefreshToken(), profile);
          }
        }
      } catch (err) {
        // If 401 or invalid, clear stored tokens
        if (err.status === 401) {
          clearStoredAuth();
          if (mounted) {
            setUser(null);
            setAccessToken(null);
          }
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    initAuth();
    return () => {
      mounted = false;
    };
  }, [apiClient]);

  const login = useCallback(
    async (email, password) => {
      if (!apiClient) throw new Error('API client not configured');
      const resp = await apiClient.loginUser(email, password);
      const token = resp.access_token;
      const refreshTok = resp.refresh_token || null;
      let profile = resp.user || null;

      if (!profile && apiClient.getMe) {
        try {
          // Temporarily set token getter for this call
          apiClient.setAuthTokenGetter(() => token);
          profile = await apiClient.getMe();
        } catch (e) {
          profile = { email, role: 'user' };
        }
      }

      setAccessToken(token);
      setUser(profile);
      setStoredAuth(token, refreshTok, profile);
      return profile;
    },
    [apiClient]
  );

  const register = useCallback(
    async (userData) => {
      if (!apiClient) throw new Error('API client not configured');
      const newUser = await apiClient.registerUser(userData);
      // Automatically log in after registration
      return login(userData.email, userData.password);
    },
    [apiClient, login]
  );

  const logout = useCallback(async () => {
    const refreshTok = getStoredRefreshToken();
    if (apiClient && apiClient.logoutUser && refreshTok) {
      try {
        await apiClient.logoutUser(refreshTok);
      } catch (e) {
        // Silently continue local logout
      }
    }
    clearStoredAuth();
    setUser(null);
    setAccessToken(null);
  }, [apiClient]);

  const refreshProfile = useCallback(async () => {
    if (apiClient && apiClient.getMyProfile) {
      try {
        const profile = await apiClient.getMyProfile();
        setUser(profile);
        setStoredAuth(accessToken, getStoredRefreshToken(), profile);
      } catch (e) {
        console.error('Failed to refresh profile:', e);
      }
    }
  }, [apiClient, accessToken]);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated: Boolean(user && accessToken),
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
