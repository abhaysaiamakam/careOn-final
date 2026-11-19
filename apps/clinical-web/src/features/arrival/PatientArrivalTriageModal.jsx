import React, { useState } from 'react';
import { CheckCircle2, X, Bed, AlertCircle, Clock } from 'lucide-react';
import { acknowledgePatientArrival } from '@careon/api-client';

export function PatientArrivalTriageModal({
  incident,
  isOpen,
  onClose,
  onArrivalConfirmed,
}) {
  const [bedType, setBedType] = useState('emergency');
  const [triageCategory, setTriageCategory] = useState('P2');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !incident) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const incidentId = incident.incident_id || incident.id;
      const res = await acknowledgePatientArrival(incidentId, {
        bed_type: bedType,
        triage_category: triageCategory,
        notes: notes.trim() || undefined,
      });

      if (onArrivalConfirmed) {
        onArrivalConfirmed(res);
      }
      onClose();
    } catch (err) {
      setError(err?.message || 'Failed to confirm patient arrival.');
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
          maxWidth: '500px',
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
                backgroundColor: '#D1FAE5',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#065F46',
              }}
            >
              <CheckCircle2 size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '17px', fontWeight: 700, color: '#111827' }}>
                Confirm Patient Arrival & Intake
              </h2>
              <p style={{ fontSize: '13px', color: '#6B7280' }}>
                Incident #{incident.incident_id || incident.id}
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
              Allocated Bed Type (Decrements Available Capacity)
            </label>
            <select
              value={bedType}
              onChange={(e) => setBedType(e.target.value)}
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
              <option value="emergency">Emergency Department (ED) Bed</option>
              <option value="trauma">Trauma Resuscitation Bay</option>
              <option value="icu">Intensive Care Unit (ICU)</option>
              <option value="operating">Emergency Operating Room</option>
            </select>
          </div>

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
              Hospital Arrival Triage Category
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
              {[
                { code: 'P1', label: 'P1 Resus', color: '#D92D3A', bg: '#FEE2E2' },
                { code: 'P2', label: 'P2 Emergent', color: '#D99022', bg: '#FEF3C7' },
                { code: 'P3', label: 'P3 Urgent', color: '#2563EB', bg: '#EFF6FF' },
                { code: 'P4', label: 'P4 Non-urg', color: '#4B5563', bg: '#F3F4F6' },
              ].map((p) => {
                const isSelected = triageCategory === p.code;
                return (
                  <button
                    key={p.code}
                    type="button"
                    onClick={() => setTriageCategory(p.code)}
                    style={{
                      padding: '8px 6px',
                      borderRadius: '6px',
                      border: isSelected ? `2px solid ${p.color}` : '1px solid #E5E7EB',
                      backgroundColor: isSelected ? p.bg : '#F9FAFB',
                      color: isSelected ? p.color : '#374151',
                      fontWeight: 700,
                      fontSize: '12px',
                      cursor: 'pointer',
                      textAlign: 'center',
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

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
              Intake Nurse / Clinician Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Bed allocation room number, intake vitals, receiving attending physician..."
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
                backgroundColor: '#16845B',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? 'Confirming Arrival...' : 'Confirm Patient Intake'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default PatientArrivalTriageModal;
