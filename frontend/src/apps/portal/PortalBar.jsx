import React from 'react';
import useAuth from '../../auth/useAuth';
import {
  ShieldAlert,
  Radio,
  Ambulance,
  Building2,
  Lock,
  Compass,
  User,
  LogOut,
} from 'lucide-react';

export default function PortalBar({ currentApp, onSelectApp }) {
  const { user, role, isAuthenticated, logout } = useAuth();

  const userRole = (role || '').toLowerCase();
  const isSuperAdmin = userRole === 'super_admin' || userRole === 'admin';
  const isDispatcher = isSuperAdmin || userRole === 'dispatcher' || userRole === 'org_admin';
  const isResponder = isSuperAdmin || userRole === 'responder';
  const isHospital = isSuperAdmin || userRole === 'hospital_staff';

  const apps = [
    {
      id: 'citizen',
      label: 'Citizen SOS',
      icon: Compass,
      color: '#ef4444',
      badge: 'PUBLIC',
      allowed: true,
    },
    {
      id: 'dispatcher',
      label: 'Dispatch Command',
      icon: Radio,
      color: '#3b82f6',
      badge: 'DISPATCH',
      allowed: true, // accessible to dispatchers, or opens dispatcher view
    },
    {
      id: 'responder',
      label: 'Field Responder',
      icon: Ambulance,
      color: '#10b981',
      badge: 'FIELD',
      allowed: true,
    },
    {
      id: 'hospital',
      label: 'Hospital Portal',
      icon: Building2,
      color: '#8b5cf6',
      badge: 'CLINICAL',
      allowed: true,
    },
    {
      id: 'super_admin',
      label: 'Super Admin',
      icon: Lock,
      color: '#f59e0b',
      badge: 'SECURE',
      allowed: true,
    },
  ];

  return (
    <div style={{
      backgroundColor: '#070b12',
      borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
      padding: '6px 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '8px',
      fontSize: '0.8rem',
      position: 'sticky',
      top: 0,
      zIndex: 1000,
    }}>
      {/* Ecosystem Label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{
          fontWeight: 900,
          color: '#ef4444',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontSize: '0.8rem',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <ShieldAlert size={14} /> CareOn Ecosystem:
        </span>

        {/* Five Application Switcher Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
          {apps.map((app) => {
            const Icon = app.icon;
            const isCurrent = currentApp === app.id;
            return (
              <button
                key={app.id}
                onClick={() => onSelectApp(app.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '5px 10px',
                  borderRadius: '6px',
                  backgroundColor: isCurrent ? 'rgba(255, 255, 255, 0.12)' : 'transparent',
                  border: isCurrent ? `1px solid ${app.color}` : '1px solid transparent',
                  color: isCurrent ? '#f8fafc' : '#94a3b8',
                  fontSize: '0.75rem',
                  fontWeight: isCurrent ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={13} style={{ color: app.color }} />
                <span>{app.label}</span>
                <span style={{
                  fontSize: '0.65rem',
                  padding: '1px 4px',
                  borderRadius: '3px',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  color: '#94a3b8',
                }}>
                  {app.badge}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* User / Session State Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {isAuthenticated && user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              color: '#34d399',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
              {user.name} ({role})
            </span>
            <button
              onClick={logout}
              style={{
                backgroundColor: 'transparent',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.7rem',
                padding: '2px 6px',
              }}
              title="Sign Out"
            >
              <LogOut size={12} />
            </button>
          </div>
        ) : (
          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
            Public Session
          </span>
        )}
      </div>
    </div>
  );
}
