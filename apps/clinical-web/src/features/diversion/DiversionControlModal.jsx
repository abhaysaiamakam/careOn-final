import React, { useState } from 'react';
import { AlertTriangle, X, CheckCircle2, ShieldAlert } from 'lucide-react';
import { setFacilityDiversion, updateHospitalReadiness } from '@careon/api-client';

export function DiversionControlModal({
  facility,
  currentStatus,
  isOpen,
  onClose,
  onStatusUpdated,
}) {
  const [selectedStatus, setSelectedStatus] = useState(
    currentStatus?.status || (currentStatus?.is_diverting ? 'Diverting' : 'Open')
  );
  const [reason, setReason] = useState(currentStatus?.reason || '');
  const [diversionType, setDiversionType] = useState(currentStatus?.diversion_type || 'ed_saturation');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (selectedStatus !== 'Open' && (!reason || reason.trim().length < 3)) {
      setError('A clinical/operational reason of at least 3 characters is mandatory when declaring diversion.');
      return;
    }

    setLoading(true);
    try {
      const statusMap = {
        Open: 'open',
        Overcrowded: 'partial_diversion',
        Diverting: 'full_diversion',
        open: 'open',
        partial_diversion: 'partial_diversion',
        full_diversion: 'full_diversion',
        emergency_only: 'emergency_only',
        closed: 'closed',
      };
      const backendStatus = statusMap[selectedStatus] || selectedStatus.toLowerCase();

      if (facility?.id) {
        await setFacilityDiversion(facility.id, {
          new_status: backendStatus,
          reason: reason.trim() || 'Facility returned to normal operational status',
          diversion_type: selectedStatus !== 'Open' ? diversionType : null,
        });
      }

      // Also sync M3 readiness flag
      try {
        await updateHospitalReadiness({
          is_diverting: backendStatus === 'full_diversion' || backendStatus === 'closed',
        });
      } catch (m3Err) {
        console.warn('M3 readiness sync note:', m3Err);
      }

      if (onStatusUpdated) {
        onStatusUpdated({
          status: selectedStatus,
          backend_status: backendStatus,
          reason: reason.trim(),
          diversion_type: diversionType,
          updated_at: new Date().toISOString(),
        });
      }
      onClose();
    } catch (err) {
      setError(err?.message || 'Failed to update diversion status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(17, 24, 39, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '16px',
      }}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '520px',
          overflow: 'hidden',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '20px 24px',
            borderBottom: '1px solid #E5E7EB',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                backgroundColor: '#FEE2E2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#D92D3A',
              }}
            >
              <AlertTriangle size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '17px', fontWeight: 700, color: '#111827' }}>
                Facility Diversion Status
              </h2>
              <p style={{ fontSize: '13px', color: '#6B7280' }}>
                {facility?.name || 'Central Hospital'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#9CA3AF',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '24px' }}>
          {error && (
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
              {error}
            </div>
          )}

          {/* Status Choice */}
          <div style={{ marginBottom: '20px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '13px',
                fontWeight: 600,
                color: '#374151',
                marginBottom: '8px',
              }}
            >
              Select Operating Status
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              {[
                { id: 'Open', label: 'Open', desc: 'Accept all incoming transports', color: '#16845B', bg: '#D1FAE5' },
                { id: 'Overcrowded', label: 'Overcrowded', desc: 'Accept P1 only, divert lower acuity', color: '#D99022', bg: '#FEF3C7' },
                { id: 'Diverting', label: 'Diverting', desc: 'Redirect all ambulance transports', color: '#D92D3A', bg: '#FEE2E2' },
              ].map((opt) => {
                const isSelected = selectedStatus === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setSelectedStatus(opt.id)}
                    style={{
                      padding: '12px 10px',
                      borderRadius: '8px',
                      border: isSelected ? `2px solid ${opt.color}` : '1px solid #E5E7EB',
                      backgroundColor: isSelected ? opt.bg : '#F9FAFB',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '14px', color: opt.color, marginBottom: '2px' }}>
                      {opt.label}
                    </div>
                    <div style={{ fontSize: '11px', color: '#6B7280', lineHeight: 1.3 }}>
                      {opt.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Diversion Type when not Open */}
          {selectedStatus !== 'Open' && (
            <div style={{ marginBottom: '18px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#374151',
                  marginBottom: '6px',
                }}
              >
                Primary Diversion Driver
              </label>
              <select
                value={diversionType}
                onChange={(e) => setDiversionType(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #D1D5DB',
                  fontSize: '14px',
                  color: '#111827',
                  backgroundColor: '#FFFFFF',
                }}
              >
                <option value="ed_saturation">Emergency Department Saturation</option>
                <option value="icu_full">ICU at Critical Capacity</option>
                <option value="trauma">Trauma Resuscitation Bays Occupied</option>
                <option value="ct_down">Diagnostic CT Scanner Offline</option>
                <option value="staffing">Acute Specialist/Nursing Shortage</option>
                <option value="internal_disaster">Internal Facility Emergency</option>
              </select>
            </div>
          )}

          {/* Operational Justification */}
          <div style={{ marginBottom: '24px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '13px',
                fontWeight: 600,
                color: '#374151',
                marginBottom: '6px',
              }}
            >
              Clinical & Operational Justification {selectedStatus !== 'Open' && <span style={{ color: '#D92D3A' }}>*</span>}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={
                selectedStatus === 'Open'
                  ? 'Optional notes regarding capacity clearance...'
                  : 'Specify clinical rationale, expected duration, and command approval...'
              }
              rows={3}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: '1px solid #D1D5DB',
                fontSize: '13px',
                color: '#111827',
                resize: 'vertical',
                outline: 'none',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              style={{
                padding: '10px 16px',
                borderRadius: '6px',
                border: '1px solid #D1D5DB',
                backgroundColor: '#FFFFFF',
                color: '#374151',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '10px 20px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: selectedStatus === 'Open' ? '#16845B' : '#D92D3A',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? 'Submitting Update...' : 'Commit Status Change'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default DiversionControlModal;
