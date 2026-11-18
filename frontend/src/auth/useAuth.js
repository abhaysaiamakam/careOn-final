import { useContext } from 'react';
import { AuthContext } from './AuthContext';

export default function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    return {
      user: null,
      role: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: async () => {},
      logout: () => {},
      refreshSession: async () => {},
    };
  }
  return context;
}
