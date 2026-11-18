import React, { useState, useEffect } from 'react';
import { hospitalApi } from '../../packages/api-client';
import useAuth from '../../auth/useAuth';
import {
  Building2,
  Bed,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Ambulance,
  Clock,
  ShieldCheck,
  RefreshCw,
  Plus,
  Minus,
} from 'lucide-react';

export default function HospitalApp() {
  const { user, isAuthenticated } = useAuth();
  const [readiness, setReadiness] = useState(null);
  const [incoming, setIncoming] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [intakeModalOpen, setIntakeModalOpen] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [selectedBedType, setSelectedBedType] = useState('er_bed');
  const [intakeNotes, setIntakeNotes] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [rData, incData] = await Promise.all([
        hospitalApi.getReadiness(),
        hospitalApi.getIncomingPatients(),
      ]);
      setReadiness(rData);
      setIncoming(Array.isArray(incData) ? incData : []);
    } catch (err) {
      setError(err.message || 'Failed to load hospital operations data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 20000);
    return () => clearInterval(interval);
  }, []);

  const handleCapacityDelta = async (field, delta) => {
    if (!readiness) return;
    const currentVal = readiness[field] || 0;
    const newVal = Math.max(0, currentVal + delta);
    try {
      setIsSaving(true);
      const updated = await hospitalApi.updateReadiness({ [field]: newVal });
      setReadiness(updated);
    } catch (err) {
      alert(`Capacity update failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleDivert = async () => {
    if (!readiness) return;
    const newDivert = !readiness.divert_status;
    let reason = readiness.divert_reason;
    if (newDivert && !reason) {
      reason = 'Emergency Department surge capacity reached';
    } else if (!newDivert) {
      reason = null;
    }
    try {
      setIsSaving(true);
      const updated = await hospitalApi.updateReadiness({
        divert_status: newDivert,
        divert_reason: reason,
      });
      setReadiness(updated);
    } catch (err) {
      alert(`Divert status update failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleArrivalAcknowledge = async () => {
    if (!selectedIncident) return;
    try {
      setIsSaving(true);
      await hospitalApi.acknowledgeArrival(selectedIncident.incident_id, selectedBedType, intakeNotes);
      setIntakeModalOpen(false);
      setSelectedIncident(null);
      setIntakeNotes('');
      await loadData();
    } catch (err) {
      alert(`Intake confirmation failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '24px 20px',
      color: '#f8fafc',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Hospital Top Operational Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        backgroundColor: '#111827',
        padding: '20px 24px',
        borderRadius: '16px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            backgroundColor: 'rgba(59, 130, 246, 0.15)',
            color: '#3b82f6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Building2 size={26} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800 }}>
              {readiness?.organization_name || 'Hospital Emergency Portal'}
            </h1>
            <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '4px' }}>
              ED Intake & Real-time Trauma Bed Readiness • Staff: {user?.name || 'Authorized Personnel'}
            </div>
          </div>
        </div>

        {/* Real-time Diversion Status Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 16px',
            borderRadius: '10px',
            backgroundColor: readiness?.divert_status ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.15)',
            border: `1px solid ${readiness?.divert_status ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.3)'}`,
          }}>
            <div style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: readiness?.divert_status ? '#ef4444' : '#10b981',
            }} />
            <span style={{
              fontSize: '0.85rem',
              fontWeight: 700,
              color: readiness?.divert_status ? '#f87171' : '#34d399',
            }}>
              {readiness?.divert_status ? 'HOSPITAL ON DIVERT' : 'RECEIVING EMERGENCIES'}
            </span>
            <button
              onClick={handleToggleDivert}
              disabled={isSaving}
              style={{
                marginLeft: '8px',
                backgroundColor: readiness?.divert_status ? '#ef4444' : '#1f2937',
                color: '#fff',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {readiness?.divert_status ? 'CLEAR DIVERT' : 'ACTIVATE DIVERT'}
            </button>
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            style={{
              backgroundColor: '#1f2937',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#94a3b8',
              padding: '10px',
              borderRadius: '10px',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Bed Capacity Cards Grid */}
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', color: '#cbd5e1' }}>
        Emergency Department Capacity Management
      </h2>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '16px',
        marginBottom: '32px',
      }}>
        {/* ER Beds */}
        <div style={{
          backgroundColor: '#111827',
          padding: '20px',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>AVAILABLE ER BEDS</span>
            <Bed size={18} style={{ color: '#38bdf8' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '14px' }}>
            <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#f8fafc' }}>
              {readiness?.available_er_beds ?? 0}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
              / {readiness?.total_er_beds ?? 0} Total
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleCapacityDelta('available_er_beds', -1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Minus size={14} style={{ margin: '0 auto' }} />
            </button>
            <button
              onClick={() => handleCapacityDelta('available_er_beds', 1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Plus size={14} style={{ margin: '0 auto' }} />
            </button>
          </div>
        </div>

        {/* ICU Beds */}
        <div style={{
          backgroundColor: '#111827',
          padding: '20px',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>ICU VENTILATORS</span>
            <Activity size={18} style={{ color: '#ec4899' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '14px' }}>
            <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#f8fafc' }}>
              {readiness?.icu_beds_available ?? 0}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
              / {readiness?.icu_beds_total ?? 0} Total
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleCapacityDelta('icu_beds_available', -1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Minus size={14} style={{ margin: '0 auto' }} />
            </button>
            <button
              onClick={() => handleCapacityDelta('icu_beds_available', 1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Plus size={14} style={{ margin: '0 auto' }} />
            </button>
          </div>
        </div>

        {/* Trauma Bays */}
        <div style={{
          backgroundColor: '#111827',
          padding: '20px',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>TRAUMA BAYS</span>
            <AlertTriangle size={18} style={{ color: '#ef4444' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '14px' }}>
            <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#f8fafc' }}>
              {readiness?.trauma_bays_available ?? 0}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
              / {readiness?.trauma_bays_total ?? 0} Total
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleCapacityDelta('trauma_bays_available', -1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Minus size={14} style={{ margin: '0 auto' }} />
            </button>
            <button
              onClick={() => handleCapacityDelta('trauma_bays_available', 1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Plus size={14} style={{ margin: '0 auto' }} />
            </button>
          </div>
        </div>

        {/* Operating Rooms */}
        <div style={{
          backgroundColor: '#111827',
          padding: '20px',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>OPERATING ROOMS</span>
            <ShieldCheck size={18} style={{ color: '#10b981' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '14px' }}>
            <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#f8fafc' }}>
              {readiness?.operating_rooms_available ?? 0}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
              / {readiness?.operating_rooms_total ?? 0} Total
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleCapacityDelta('operating_rooms_available', -1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Minus size={14} style={{ margin: '0 auto' }} />
            </button>
            <button
              onClick={() => handleCapacityDelta('operating_rooms_available', 1)}
              style={{ flex: 1, backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '6px', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Plus size={14} style={{ margin: '0 auto' }} />
            </button>
          </div>
        </div>
      </div>

      {/* Incoming Ambulances / Transport Feed */}
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', color: '#cbd5e1' }}>
        Live Incoming Patient Transports
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {incoming.map((item) => (
          <div
            key={item.incident_id}
            style={{
              backgroundColor: '#111827',
              borderRadius: '14px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              padding: '18px 22px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Ambulance size={22} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontWeight: 700, fontSize: '1rem' }}>{item.incident_code}</span>
                  <span style={{
                    fontSize: '0.75rem',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    backgroundColor: item.priority === 'Critical' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                    color: item.priority === 'Critical' ? '#f87171' : '#fbbf24',
                    fontWeight: 700,
                  }}>
                    {item.priority}
                  </span>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '4px' }}>
                  {item.category} • Unit: {item.resource_name || 'En route unit'} • From: {item.location_name}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={16} /> ~{item.eta_minutes} MINS
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{item.transport_status}</div>
              </div>

              <button
                onClick={() => {
                  setSelectedIncident(item);
                  setIntakeModalOpen(true);
                }}
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px 16px',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <CheckCircle2 size={16} /> CONFIRM INTAKE
              </button>
            </div>
          </div>
        ))}

        {incoming.length === 0 && (
          <div style={{
            backgroundColor: '#111827',
            padding: '36px',
            borderRadius: '12px',
            textAlign: 'center',
            color: '#64748b',
            border: '1px dashed rgba(255, 255, 255, 0.08)',
          }}>
            No incoming transports currently bound for this facility.
          </div>
        )}
      </div>

      {/* Intake Confirmation Modal */}
      {intakeModalOpen && selectedIncident && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: '#1e293b',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '460px',
            width: '100%',
          }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '1.2rem', fontWeight: 700 }}>
              Confirm Emergency Intake
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 16px 0' }}>
              Assign bed and confirm patient handover for {selectedIncident.incident_code}:
            </p>

            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '6px' }}>
              SELECT ADMISSION BED TYPE:
            </label>
            <select
              value={selectedBedType}
              onChange={(e) => setSelectedBedType(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: '#0f172a',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '0.85rem',
                marginBottom: '16px',
              }}
            >
              <option value="er_bed">Emergency Department Bed (ER)</option>
              <option value="icu_bed">Intensive Care Unit (ICU)</option>
              <option value="trauma_bay">Trauma Resuscitation Bay</option>
              <option value="operating_room">Operating Suite (OR)</option>
            </select>

            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '6px' }}>
              CLINICAL INTAKE NOTES:
            </label>
            <textarea
              value={intakeNotes}
              onChange={(e) => setIntakeNotes(e.target.value)}
              placeholder="e.g. Admitted directly to Trauma Bay 2; vitals stabilized."
              style={{
                width: '100%',
                height: '70px',
                backgroundColor: '#0f172a',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                color: '#fff',
                padding: '10px',
                fontSize: '0.85rem',
                marginBottom: '20px',
                boxSizing: 'border-box',
              }}
            />

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setIntakeModalOpen(false)}
                style={{
                  backgroundColor: 'transparent',
                  color: '#94a3b8',
                  border: 'none',
                  padding: '8px 14px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleArrivalAcknowledge}
                disabled={isSaving}
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px 18px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Acknowledge & Assign Bed
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
