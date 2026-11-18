import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import useAuth from './useAuth';

export default function ProtectedRoute({ children, requiredRoles = null }) {
  const { isAuthenticated, isLoading, role } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#0f172a', color: '#94a3b8' }}>
        <p>Verifying secure session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRoles && requiredRoles.length > 0) {
    const userRole = (role || '').toLowerCase();
    const isSuperAdmin = userRole === 'super_admin' || userRole === 'admin';
    const hasRole = isSuperAdmin || requiredRoles.some((r) => r.toLowerCase() === userRole);
    if (!hasRole) {
      return <Navigate to="/" replace />;
    }
  }

  return children;
}
