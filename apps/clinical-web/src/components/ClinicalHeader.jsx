import React from 'react';
import {
  Activity,
  Bed,
  Radio,
  AlertTriangle,
  Building2,
  LogOut,
  User,
  Shield,
  Layers,
  FileText,
  Clock,
} from 'lucide-react';

export function ClinicalHeader({
  facility,
  facilities = [],
  onSelectFacility,
  diversionStatus,
  onOpenDiversionModal,
  onOpenCapacityModal,
  capacity,
  wsStatus,
  activeTab,
  onSelectTab,
  user,
  onLogout,
  pendingIncomingCount = 0,
  pendingHandoverCount = 0,
}) {
  const isDiverting = diversionStatus?.status === 'Diverting';
  const isOvercrowded = diversionStatus?.status === 'Overcrowded';

  const diversionBadgeBg = isDiverting ? '#FEE2E2' : isOvercrowded ? '#FEF3C7' : '#D1FAE5';
  const diversionBadgeText = isDiverting ? '#991B1B' : isOvercrowded ? '#92400E' : '#065F46';
  const diversionBadgeBorder = isDiverting ? '#FCA5A5' : isOvercrowded ? '#FCD34D' : '#6EE7B7';
  const diversionLabel = isDiverting ? 'Diverting' : isOvercrowded ? 'Overcrowded' : 'Normal Operations';

  return (
    <header
      style={{
        backgroundColor: '#FFFFFF',
        borderBottom: '1px solid #E5E7EB',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Top Banner: Hospital Identity, Diversion Pill, Live Capacity & User */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 24px',
          borderBottom: '1px solid #F3F4F6',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {/* Brand & Facility Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              backgroundColor: '#D92D3A',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
              fontWeight: 800,
              fontSize: '18px',
            }}
          >
            +
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>
                CareOn Clinical
              </span>
              <span
                style={{
                  fontSize: '11px',
                  backgroundColor: '#F3F4F6',
                  color: '#4B5563',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                }}
              >
                Hospital Ops
              </span>
            </div>

            {/* Facility Selector / Display */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <Building2 size={13} color="#6B7280" />
              {facilities.length > 1 ? (
                <select
                  value={facility?.id || ''}
                  onChange={(e) => {
                    const sel = facilities.find((f) => f.id === e.target.value);
                    if (sel && onSelectFacility) onSelectFacility(sel);
                  }}
                  style={{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#374151',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  {facilities.map((fac) => (
                    <option key={fac.id} value={fac.id}>
                      {fac.name} {fac.trauma_level ? `(${fac.trauma_level})` : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
                  {facility?.name || 'Central Regional Trauma Hospital'}
                  {facility?.trauma_level && ` (${facility.trauma_level})`}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Operational Status Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Diversion Status Button */}
          <button
            onClick={onOpenDiversionModal}
            title="Click to change Diversion Status"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '9999px',
              backgroundColor: diversionBadgeBg,
              border: `1px solid ${diversionBadgeBorder}`,
              color: diversionBadgeText,
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'opacity 0.2s',
            }}
          >
            <AlertTriangle size={14} />
            <span>Diversion: {diversionLabel}</span>
          </button>

          {/* Quick Bed Capacity Pill */}
          <button
            onClick={onOpenCapacityModal}
            title="Click to view & update capacity"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              borderRadius: '6px',
              backgroundColor: '#F9FAFB',
              border: '1px solid #E5E7EB',
              fontSize: '12px',
              color: '#374151',
              cursor: 'pointer',
            }}
          >
            <Bed size={14} color="#6B7280" />
            <span>
              ER: <strong>{capacity?.er_available ?? capacity?.beds_available ?? '—'}</strong> avl
            </span>
            <span style={{ color: '#D1D5DB' }}>|</span>
            <span>
              ICU: <strong>{capacity?.icu_available ?? '—'}</strong> avl
            </span>
            <span style={{ color: '#D1D5DB' }}>|</span>
            <span>
              Trauma: <strong>{capacity?.trauma_available ?? '—'}</strong> avl
            </span>
          </button>

          {/* WebSocket Live Status */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '9999px',
              backgroundColor: wsStatus === 'CONNECTED' ? '#ECFDF5' : '#FEF2F2',
              color: wsStatus === 'CONNECTED' ? '#065F46' : '#991B1B',
              fontSize: '12px',
              fontWeight: 500,
            }}
          >
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: wsStatus === 'CONNECTED' ? '#10B981' : '#EF4444',
              }}
              className={wsStatus === 'CONNECTED' ? 'clinical-pulse' : ''}
            />
            <span>{wsStatus === 'CONNECTED' ? 'Live Telemetry' : 'Reconnecting'}</span>
          </div>

          {/* User Profile & Logout */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderLeft: '1px solid #E5E7EB', paddingLeft: '12px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                {user?.full_name || user?.name || user?.email || 'Clinical Staff'}
              </div>
              <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'capitalize' }}>
                {user?.role ? user.role.replace('_', ' ') : 'Hospital Clinician'}
              </div>
            </div>
            <button
              onClick={onLogout}
              title="Sign out of CareOn Clinical"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                border: '1px solid #E5E7EB',
                backgroundColor: '#FFFFFF',
                color: '#6B7280',
                cursor: 'pointer',
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Primary Navigation Tabs */}
      <nav
        style={{
          display: 'flex',
          gap: '2px',
          padding: '0 24px',
          overflowX: 'auto',
        }}
      >
        {[
          { id: 'dashboard', label: 'Command Dashboard', icon: Activity },
          {
            id: 'incoming',
            label: 'Incoming Ambulances',
            icon: Radio,
            badge: pendingIncomingCount > 0 ? pendingIncomingCount : null,
          },
          { id: 'capacity', label: 'Bed & Surge Capacity', icon: Bed },
          {
            id: 'handover',
            label: 'Clinical Handovers (SBAR)',
            icon: FileText,
            badge: pendingHandoverCount > 0 ? pendingHandoverCount : null,
          },
          { id: 'mci', label: 'MCI Regional Distribution', icon: Layers },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? '#D92D3A' : '#4B5563',
                background: 'none',
                border: 'none',
                borderBottom: isActive ? '2px solid #D92D3A' : '2px solid transparent',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease-in-out',
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
              {tab.badge !== null && tab.badge !== undefined && (
                <span
                  style={{
                    backgroundColor: isActive ? '#D92D3A' : '#E5E7EB',
                    color: isActive ? '#FFFFFF' : '#374151',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '9999px',
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </header>
  );
}

export default ClinicalHeader;
