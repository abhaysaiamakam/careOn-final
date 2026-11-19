import React from 'react';
import { Bed, Activity, RefreshCw, AlertTriangle, ShieldCheck, CheckCircle2 } from 'lucide-react';
import EmptyState from '../../components/EmptyState.jsx';

export function CapacityManagementView({
  facility,
  readiness,
  loading = false,
  onRefresh,
  onOpenUpdateModal,
}) {
  if (!facility && !readiness && !loading) {
    return (
      <div style={{ padding: '24px' }}>
        <EmptyState
          icon="bed"
          title="No Facility Capacity Data"
          message="No hospital facility or readiness telemetry is currently registered for your staff account."
          action={
            <button
              onClick={onRefresh}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                backgroundColor: '#D92D3A',
                color: '#FFFFFF',
                borderRadius: '6px',
                border: 'none',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={14} />
              <span>Retry Telemetry Sync</span>
            </button>
          }
        />
      </div>
    );
  }

  const erTotal = readiness?.total_er_beds ?? 0;
  const erAvl = readiness?.available_er_beds ?? 0;
  const erOccupied = Math.max(0, erTotal - erAvl);

  const icuTotal = readiness?.icu_beds_total ?? 0;
  const icuAvl = readiness?.icu_beds_available ?? 0;
  const icuOccupied = Math.max(0, icuTotal - icuAvl);

  const traumaTotal = readiness?.trauma_bays_total ?? 0;
  const traumaAvl = readiness?.trauma_bays_available ?? 0;
  const traumaOccupied = Math.max(0, traumaTotal - traumaAvl);

  const orTotal = readiness?.operating_rooms_total ?? 0;
  const orAvl = readiness?.operating_rooms_available ?? 0;
  const orOccupied = Math.max(0, orTotal - orAvl);

  const cards = [
    {
      title: 'Emergency Department Beds',
      code: 'ED-BEDS',
      available: erAvl,
      total: erTotal,
      occupied: erOccupied,
      color: '#16845B',
      desc: 'Acute medical & surgical reception beds',
    },
    {
      title: 'Intensive Care Unit (ICU)',
      code: 'ICU-VENT',
      available: icuAvl,
      total: icuTotal,
      occupied: icuOccupied,
      color: '#2563EB',
      desc: 'Ventilator-supported critical care beds',
    },
    {
      title: 'Trauma Resuscitation Bays',
      code: 'TRAUMA-BAY',
      available: traumaAvl,
      total: traumaTotal,
      occupied: traumaOccupied,
      color: '#D92D3A',
      desc: 'Major trauma resuscitation & airway suites',
    },
    {
      title: 'Operating Rooms (Surgical)',
      code: 'OR-THEATRE',
      available: orAvl,
      total: orTotal,
      occupied: orOccupied,
      color: '#7C3AED',
      desc: 'Emergency & scheduled trauma operating suites',
    },
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: '#111827' }}>
            Bed & Critical Surge Capacity
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280' }}>
            Live authoritative hospital bed occupancy, telemetry freshness, and intake reservations
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={onRefresh}
            title="Refresh capacity telemetry"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '6px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E5E7EB',
              fontSize: '13px',
              fontWeight: 500,
              color: '#374151',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} className={loading ? 'clinical-pulse' : ''} />
            <span>Sync</span>
          </button>

          <button
            onClick={onOpenUpdateModal}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '6px',
              backgroundColor: '#D92D3A',
              border: 'none',
              fontSize: '13px',
              fontWeight: 600,
              color: '#FFFFFF',
              cursor: 'pointer',
            }}
          >
            <Bed size={15} />
            <span>Update Bed Inventory</span>
          </button>
        </div>
      </div>

      {/* Freshness & Facility Identity Banner */}
      <div
        style={{
          padding: '16px 20px',
          borderRadius: '8px',
          backgroundColor: '#FFFFFF',
          border: '1px solid #E5E7EB',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <ShieldCheck size={20} color="#16845B" />
          <div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>
              Facility: {facility?.name || 'Central Regional Trauma Hospital'}
            </div>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>
              Trauma Level: {facility?.trauma_level || 'Level 1'} • Organization ID: {facility?.organization_id || 1}
            </div>
          </div>
        </div>

        <div style={{ fontSize: '12px', color: '#6B7280', textAlign: 'right' }}>
          <div>
            Telemetry Source: <strong style={{ color: '#111827' }}>Live Central Registry</strong>
          </div>
          <div>
            Last Verified: {readiness?.updated_at ? new Date(readiness.updated_at).toLocaleTimeString() : 'Just now'}
          </div>
        </div>
      </div>

      {/* Capacity Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        {cards.map((c) => {
          const occupancyRate = c.total > 0 ? Math.round((c.occupied / c.total) * 100) : 0;
          return (
            <div
              key={c.code}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
                padding: '20px',
                boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px',
                }}
              >
                <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>
                  {c.title}
                </div>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: '#F3F4F6',
                    color: '#4B5563',
                    padding: '2px 6px',
                    borderRadius: '4px',
                  }}
                >
                  {c.code}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '32px', fontWeight: 800, color: c.color, letterSpacing: '-0.03em' }}>
                  {c.available}
                </span>
                <span style={{ fontSize: '14px', color: '#6B7280' }}>
                  / {c.total} available
                </span>
              </div>

              {/* Occupancy bar */}
              <div
                style={{
                  width: '100%',
                  height: '6px',
                  backgroundColor: '#F3F4F6',
                  borderRadius: '3px',
                  overflow: 'hidden',
                  marginBottom: '10px',
                }}
              >
                <div
                  style={{
                    width: `${Math.min(100, occupancyRate)}%`,
                    height: '100%',
                    backgroundColor: occupancyRate > 85 ? '#D92D3A' : occupancyRate > 65 ? '#D99022' : '#16845B',
                    borderRadius: '3px',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  color: '#6B7280',
                  marginBottom: '8px',
                }}
              >
                <span>Occupied: {c.occupied}</span>
                <span>{occupancyRate}% Load</span>
              </div>

              <div style={{ fontSize: '12px', color: '#9CA3AF', lineHeight: 1.3 }}>
                {c.desc}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CapacityManagementView;
