import React, { useState } from 'react';
import { Layers, Building2, AlertTriangle, RefreshCw, Send, CheckCircle2 } from 'lucide-react';
import { planMciDistribution } from '@careon/api-client';
import EmptyState from '../../components/EmptyState.jsx';

export function MCICoordinationView({
  facilities = [],
  directory = [],
  loading = false,
  onRefresh,
}) {
  const [p1Count, setP1Count] = useState(2);
  const [p2Count, setP2Count] = useState(5);
  const [p3Count, setP3Count] = useState(10);
  const [incidentId, setIncidentId] = useState(1);
  const [planResult, setPlanResult] = useState(null);
  const [planningLoading, setPlanningLoading] = useState(false);
  const [planningError, setPlanningError] = useState(null);

  const handlePlanDistribution = async (e) => {
    e.preventDefault();
    setPlanningLoading(true);
    setPlanningError(null);

    try {
      const p1s = Array(Math.max(0, parseInt(p1Count, 10) || 0)).fill('P1');
      const p2s = Array(Math.max(0, parseInt(p2Count, 10) || 0)).fill('P2');
      const p3s = Array(Math.max(0, parseInt(p3Count, 10) || 0)).fill('P3');
      const severities = [...p1s, ...p2s, ...p3s];

      const res = await planMciDistribution({
        incident_id: parseInt(incidentId, 10),
        patient_severities: severities.length > 0 ? severities : ['P1'],
      });
      setPlanResult(res);
    } catch (err) {
      setPlanningError(err?.message || 'Failed to calculate regional MCI distribution.');
    } finally {
      setPlanningLoading(false);
    }
  };

  const networkHospitals = directory.length > 0 ? directory : facilities;

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
            Mass-Casualty Incident (MCI) Regional Coordination
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280' }}>
            Multi-facility surge distribution, regional bed pooling, and casualty load balancing
          </p>
        </div>

        <button
          onClick={onRefresh}
          title="Refresh regional directory"
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
          <span>Refresh Network Directory</span>
        </button>
      </div>

      {planningError && (
        <div
          style={{
            padding: '12px',
            borderRadius: '6px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            color: '#991B1B',
            fontSize: '13px',
            marginBottom: '18px',
          }}
        >
          {planningError}
        </div>
      )}

      {/* 2-column layout: MCI distribution planner + Regional Directory */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '24px', alignItems: 'start' }}>
        {/* Left: Distribution Planner */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '20px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Layers size={18} color="#D92D3A" />
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
              MCI Surge Allocation Planner
            </h2>
          </div>

          <form onSubmit={handlePlanDistribution}>
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}>
                Incident ID
              </label>
              <input
                type="number"
                min="1"
                value={incidentId}
                onChange={(e) => setIncidentId(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #D1D5DB',
                  fontSize: '13px',
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '18px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#991B1B', marginBottom: '4px' }}>
                  P1 (Immediate)
                </label>
                <input
                  type="number"
                  min="0"
                  value={p1Count}
                  onChange={(e) => setP1Count(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #FCA5A5',
                    backgroundColor: '#FEF2F2',
                    fontSize: '14px',
                    fontWeight: 700,
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#92400E', marginBottom: '4px' }}>
                  P2 (Delayed)
                </label>
                <input
                  type="number"
                  min="0"
                  value={p2Count}
                  onChange={(e) => setP2Count(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #FCD34D',
                    backgroundColor: '#FEF3C7',
                    fontSize: '14px',
                    fontWeight: 700,
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#166534', marginBottom: '4px' }}>
                  P3 (Minor)
                </label>
                <input
                  type="number"
                  min="0"
                  value={p3Count}
                  onChange={(e) => setP3Count(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #86EFAC',
                    backgroundColor: '#F0FDF4',
                    fontSize: '14px',
                    fontWeight: 700,
                  }}
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={planningLoading}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                backgroundColor: '#D92D3A',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                border: 'none',
                cursor: planningLoading ? 'not-allowed' : 'pointer',
                opacity: planningLoading ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
            >
              <Send size={14} />
              <span>{planningLoading ? 'Computing Optimization...' : 'Plan MCI Distribution'}</span>
            </button>
          </form>

          {/* Allocation Results */}
          {planResult && (
            <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #F3F4F6' }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#111827', marginBottom: '10px' }}>
                Optimized Hospital Allocations
              </div>
              <div style={{ fontSize: '12px', color: '#4B5563', marginBottom: '8px' }}>
                Distribution Status: <strong>{planResult.status || 'Calculated'}</strong>
              </div>
              {planResult.allocations && planResult.allocations.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {planResult.allocations.map((alloc, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '10px',
                        borderRadius: '6px',
                        backgroundColor: '#F9FAFB',
                        border: '1px solid #E5E7EB',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ fontWeight: 600, color: '#111827' }}>
                        {alloc.facility_name || `Facility #${alloc.facility_id}`}
                      </div>
                      <div style={{ color: '#6B7280', marginTop: '2px' }}>
                        P1: {alloc.p1_assigned || 0} • P2: {alloc.p2_assigned || 0} • P3: {alloc.p3_assigned || 0}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '12px', color: '#6B7280' }}>
                  {JSON.stringify(planResult)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Regional Hospital Directory */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '8px',
            border: '1px solid #E5E7EB',
            padding: '20px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Building2 size={18} color="#4B5563" />
              <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
                Regional Network Hospitals
              </h2>
            </div>
            <span style={{ fontSize: '12px', color: '#6B7280' }}>
              {networkHospitals.length} Facilities Online
            </span>
          </div>

          {networkHospitals.length === 0 && !loading ? (
            <EmptyState
              icon="bed"
              title="No Network Facilities"
              message="No participating hospital facilities found in the regional emergency registry."
              compact
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {networkHospitals.map((fac) => {
                const isDiverting = fac.divert_status || fac.is_diverting;
                return (
                  <div
                    key={fac.id || fac.facility_id}
                    style={{
                      padding: '14px',
                      borderRadius: '6px',
                      border: '1px solid #E5E7EB',
                      backgroundColor: '#F9FAFB',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: '#111827' }}>
                        {fac.name || fac.facility_name || fac.organization_name || 'Hospital Facility'}
                      </div>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          backgroundColor: isDiverting ? '#FEE2E2' : '#D1FAE5',
                          color: isDiverting ? '#991B1B' : '#065F46',
                          padding: '2px 8px',
                          borderRadius: '9999px',
                        }}
                      >
                        {isDiverting ? 'Diverting' : 'Normal Ops'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '14px', fontSize: '12px', color: '#6B7280' }}>
                      <span>
                        Trauma: <strong>{fac.trauma_level || 'Level 1'}</strong>
                      </span>
                      <span>
                        ER Beds: <strong>{fac.available_er_beds ?? fac.beds_available ?? '—'}</strong>
                      </span>
                      <span>
                        ICU: <strong>{fac.icu_beds_available ?? '—'}</strong>
                      </span>
                      <span>
                        Trauma Bays: <strong>{fac.trauma_bays_available ?? '—'}</strong>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default MCICoordinationView;
