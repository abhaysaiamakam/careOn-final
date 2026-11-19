import React from 'react';
import {
  Radio,
  Wifi,
  WifiOff,
  Bell,
  BellOff,
  LogOut,
  User,
  Shield,
  Activity,
  Layers,
  MapPin,
  Building2,
  Users,
  Brain,
  BarChart3,
} from 'lucide-react';
import { colors, typography, Badge, Button } from '@careon/design-system';
import { useAuth } from '@careon/auth';

export function CommandHeader({
  activeView,
  onViewChange,
  wsStatus,
  audioAlertsEnabled,
  onToggleAudioAlerts,
  pendingAlertsCount = 0,
}) {
  const { user, logout } = useAuth();

  const navItems = [
    { id: 'overview', label: 'Command Centre', icon: Radio },
    { id: 'map', label: 'Operations Map', icon: MapPin },
    { id: 'fleet', label: 'Fleet & Resources', icon: Activity },
    { id: 'hospitals', label: 'Hospital Coordination', icon: Building2 },
    { id: 'multi-agency', label: 'Multi-Agency / MCI', icon: Users },
    { id: 'intelligence', label: 'Predictive Intelligence', icon: Brain },
    { id: 'analytics', label: 'Operational Metrics', icon: BarChart3 },
  ];

  const getWsStatusBadge = () => {
    switch (wsStatus) {
      case 'CONNECTED':
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              borderRadius: '9999px',
              backgroundColor: '#ECFDF5',
              border: '1px solid #A7F3D0',
              color: '#065F46',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: '#10B981',
                boxShadow: '0 0 0 2px rgba(16, 185, 129, 0.3)',
              }}
            />
            M4 LIVE STREAM
          </div>
        );
      case 'CONNECTING':
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              borderRadius: '9999px',
              backgroundColor: '#FFFBEB',
              border: '1px solid #FDE68A',
              color: '#92400E',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#F59E0B' }} />
            SYNCING...
          </div>
        );
      default:
        return (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              borderRadius: '9999px',
              backgroundColor: '#FEF2F2',
              border: '1px solid #FECACA',
              color: '#991B1B',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <WifiOff size={11} />
            OFFLINE (REST FALLBACK)
          </div>
        );
    }
  };

  return (
    <header
      style={{
        backgroundColor: '#0F172A',
        borderBottom: '1px solid #1E293B',
        color: '#FFFFFF',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}
    >
      {/* Top Primary Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          height: '56px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Brand & System Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: colors.secondary,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF',
                fontWeight: typography.fontWeight.bold,
                fontSize: '18px',
              }}
            >
              +
            </div>
            <div>
              <span
                style={{
                  fontSize: '1.1rem',
                  fontWeight: typography.fontWeight.bold,
                  letterSpacing: '-0.02em',
                  color: '#FFFFFF',
                }}
              >
                CareOn
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: typography.fontWeight.bold,
                  color: colors.secondary,
                  marginLeft: '6px',
                  padding: '2px 6px',
                  backgroundColor: 'rgba(217, 45, 58, 0.15)',
                  borderRadius: '4px',
                  border: '1px solid rgba(217, 45, 58, 0.3)',
                  letterSpacing: '0.05em',
                }}
              >
                COMMAND
              </span>
            </div>
          </div>

          <div style={{ height: '24px', width: '1px', backgroundColor: '#334155' }} />

          {/* Real-time WebSocket connection state */}
          {getWsStatusBadge()}
        </div>

        {/* Right Tools & Operator Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Audio Chime Alert Toggle */}
          <button
            onClick={onToggleAudioAlerts}
            title={audioAlertsEnabled ? 'Mute incoming mission chimes' : 'Enable incoming mission chimes'}
            style={{
              background: audioAlertsEnabled ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${audioAlertsEnabled ? '#3B82F6' : '#334155'}`,
              borderRadius: '6px',
              padding: '6px 10px',
              color: audioAlertsEnabled ? '#60A5FA' : '#94A3B8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              fontWeight: 500,
            }}
          >
            {audioAlertsEnabled ? <Bell size={13} /> : <BellOff size={13} />}
            <span>{audioAlertsEnabled ? 'Chime On' : 'Chime Off'}</span>
          </button>

          {/* Dispatcher Operator Identity */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                backgroundColor: '#334155',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#94A3B8',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {user?.name ? user.name.charAt(0).toUpperCase() : 'D'}
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9' }}>
                {user?.name || 'Lead Dispatcher'}
              </div>
              <div style={{ fontSize: '10px', color: '#64748B' }}>
                Role: {user?.role?.toUpperCase() || 'DISPATCHER'}
              </div>
            </div>
          </div>

          {/* Log Out Action */}
          <button
            onClick={logout}
            title="Terminate operator session"
            style={{
              background: 'none',
              border: '1px solid #334155',
              borderRadius: '6px',
              padding: '6px 10px',
              color: '#EF4444',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              fontWeight: 500,
              transition: 'background 0.15s ease',
            }}
            onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'; }}
            onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <LogOut size={13} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      {/* Sub-Header Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          height: '42px',
          overflowX: 'auto',
          gap: '6px',
        }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: isActive ? colors.secondary : 'transparent',
                color: isActive ? '#FFFFFF' : '#94A3B8',
                fontSize: '12px',
                fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
              onMouseOver={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = '#1E293B';
              }}
              onMouseOut={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <Icon size={14} />
              {item.label}
            </button>
          );
        })}
      </div>
    </header>
  );
}
