import React from 'react';
import useAuth from '../auth/useAuth';

export default function RoleGuard({ allowedRoles = [], fallback = null, children }) {
  const { role } = useAuth();
  if (!role) return fallback;
  const userRole = role.toLowerCase();
  const isSuperAdmin = userRole === 'super_admin' || userRole === 'admin';
  const isAllowed = isSuperAdmin || allowedRoles.some((r) => r.toLowerCase() === userRole);
  return isAllowed ? children : fallback;
}
