import React from 'react';
import {
  Activity,
  Bed,
  Radio,
  FileText,
  AlertTriangle,
  Clock,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import EmptyState from '../../components/EmptyState.jsx';

export function HospitalDashboard({
  facility,
  diversionStatus,
  capacity,
  readiness,
  incomingRequests = [],
  incomingTransports = [],
  handovers = [],
  onNavigateTab,
  onOpenDiversionModal,
  onOpenCapacityModal,
  onRefresh,
}) {
  const isDiverting = diversionStatus?.status === 'Diverting';
  const isOvercrowded = diversionStatus?.status === 'Overcrowded';

  const diversionColor = isDiverting ? '#D92D3A' : isOvercrowded ? '#D99022' : '#16845B';
  const diversionLabel = isDiverting ? 'Diverting Transports' : isOvercrowded ? 'Overcrowded (P1 Only)' : 'Normal Operations';

  const erAvl = readiness?.available_er_beds ?? 0;
  const erTotal = readiness?.total_er_beds ?? 0;
  const icuAvl = readiness?.icu_beds_available ?? 0;
  const icuTotal = readiness?.icu_beds_total ?? 0;
  const traumaAvl = readiness?.trauma_bays_available ?? 0;
  const traumaTotal = readiness?.trauma_bays_total ?? 0;

  const totalIncomingCount = incomingRequests.length + incomingTransports.length;

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Welcome Banner */}
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
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#111827', letterSpacing: '-0.02em' }}>
            Emergency Operations Command
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280' }}>
            {facility?.name || 'Central Regional Trauma Hospital'} • Level {facility?.trauma_level || '1'} Trauma Center
          </p>
        </div>

        <button
          onClick={onRefresh}
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
          <RefreshCw size={14} />
          <span>Refresh Ops Telemetry</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        {/* Diversion Card */}
        <div
          onClick={onOpenDiversionModal}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '18px',
            cursor: 'pointer',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Diversion State
            </span>
            <AlertTriangle size={16} color={diversionColor} />
          </div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: diversionColor, marginBottom: '4px' }}>
            {diversionLabel}
          </div>
          <div style={{ fontSize: '12px', color: '#6B7280' }}>
            {diversionStatus?.reason || 'Facility accepting all acute transports'}
          </div>
        </div>

        {/* Incoming Ambulances Card */}
        <div
          onClick={() => onNavigateTab('incoming')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '18px',
            cursor: 'pointer',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Incoming Queue
            </span>
            <Radio size={16} color="#D92D3A" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#111827', marginBottom: '4px' }}>
            {totalIncomingCount}
          </div>
          <div style={{ fontSize: '12px', color: '#6B7280' }}>
            {incomingRequests.length} pending requests • {incomingTransports.length} transports
          </div>
        </div>

        {/* ER Available Beds */}
        <div
          onClick={onOpenCapacityModal}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '18px',
            cursor: 'pointer',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              ED Beds Available
            </span>
            <Bed size={16} color="#16845B" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#16845B', marginBottom: '4px' }}>
            {erAvl} <span style={{ fontSize: '14px', fontWeight: 500, color: '#6B7280' }}>/ {erTotal}</span>
          </div>
          <div style={{ fontSize: '12px', color: '#6B7280' }}>
            ICU: {icuAvl} avl • Trauma: {traumaAvl} avl
          </div>
        </div>

        {/* Handovers Pending */}
        <div
          onClick={() => onNavigateTab('handover')}
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '18px',
            cursor: 'pointer',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Clinical Handovers
            </span>
            <FileText size={16} color="#2563EB" />
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#111827', marginBottom: '4px' }}>
            {handovers.length}
          </div>
          <div style={{ fontSize: '12px', color: '#6B7280' }}>
            SBAR pre-arrival transfers awaiting intake
          </div>
        </div>
      </div>

      {/* 2-Column Section: Live Incoming Patients & Live Handovers */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
        {/* Incoming Patients Preview */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '20px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Radio size={16} color="#D92D3A" />
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#111827' }}>
                Incoming Pre-Arrival Queue
              </h2>
            </div>
            <button
              onClick={() => onNavigateTab('incoming')}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '12px',
                fontWeight: 600,
                color: '#D92D3A',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
              }}
            >
              <span>View All</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {incomingRequests.length === 0 && incomingTransports.length === 0 ? (
            <EmptyState
              icon="inbox"
              title="No Incoming Patients"
              message="No pre-arrival ambulance notifications currently pending in registry."
              compact
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {incomingRequests.slice(0, 3).map((req) => (
                <div
                  key={req.id}
                  onClick={() => onNavigateTab('incoming')}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    backgroundColor: '#F9FAFB',
                    border: '1px solid #E5E7EB',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#111827' }}>
                      Incident #{req.incident_id}
                    </span>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: '#FEE2E2',
                        color: '#991B1B',
                        padding: '1px 6px',
                        borderRadius: '4px',
                      }}
                    >
                      {req.emergency_severity || 'P2'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#4B5563' }}>
                    {req.patient_condition_summary || 'Chief complaint not specified.'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Handovers Preview */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '20px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={16} color="#2563EB" />
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#111827' }}>
                Pending Clinical Handovers
              </h2>
            </div>
            <button
              onClick={() => onNavigateTab('handover')}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '12px',
                fontWeight: 600,
                color: '#2563EB',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
              }}
            >
              <span>Review Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {handovers.length === 0 ? (
            <EmptyState
              icon="file"
              title="No Pending Handovers"
              message="No digital SBAR handovers awaiting review or transfer of care."
              compact
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {handovers.slice(0, 3).map((ho) => (
                <div
                  key={ho.id || ho.handover_token}
                  onClick={() => onNavigateTab('handover')}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    backgroundColor: '#F9FAFB',
                    border: '1px solid #E5E7EB',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#111827' }}>
                      Token: {ho.handover_token || ho.token}
                    </span>
                    <span style={{ fontSize: '11px', color: '#6B7280' }}>
                      Status: {ho.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#4B5563' }}>
                    Encounter #{ho.encounter_id} • Version {ho.version || 1}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HospitalDashboard;
