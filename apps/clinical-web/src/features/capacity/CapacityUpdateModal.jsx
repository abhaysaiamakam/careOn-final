import React, { useState } from 'react';
import { X, Bed, Check, AlertCircle } from 'lucide-react';
import { updateHospitalReadiness, updateFacilityCapacity } from '@careon/api-client';

export function CapacityUpdateModal({
  facility,
  readiness,
  isOpen,
  onClose,
  onCapacityUpdated,
}) {
  const [erAvailable, setErAvailable] = useState(readiness?.available_er_beds ?? 14);
  const [erTotal, setErTotal] = useState(readiness?.total_er_beds ?? 20);

  const [icuAvailable, setIcuAvailable] = useState(readiness?.icu_beds_available ?? 4);
  const [icuTotal, setIcuTotal] = useState(readiness?.icu_beds_total ?? 8);

  const [traumaAvailable, setTraumaAvailable] = useState(readiness?.trauma_bays_available ?? 2);
  const [traumaTotal, setTraumaTotal] = useState(readiness?.trauma_bays_total ?? 4);

  const [orAvailable, setOrAvailable] = useState(readiness?.operating_rooms_available ?? 2);
  const [orTotal, setOrTotal] = useState(readiness?.operating_rooms_total ?? 3);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Update M3 readiness record
      await updateHospitalReadiness({
        available_er_beds: parseInt(erAvailable, 10),
        total_er_beds: parseInt(erTotal, 10),
        icu_beds_available: parseInt(icuAvailable, 10),
        icu_beds_total: parseInt(icuTotal, 10),
        trauma_bays_available: parseInt(traumaAvailable, 10),
        trauma_bays_total: parseInt(traumaTotal, 10),
        operating_rooms_available: parseInt(orAvailable, 10),
        operating_rooms_total: parseInt(orTotal, 10),
      });

      // 2. Also update facility capacity categories if facility is selected
      if (facility?.id) {
        try {
          await updateFacilityCapacity(facility.id, {
            category: 'er_beds',
            total: parseInt(erTotal, 10),
            occupied: Math.max(0, parseInt(erTotal, 10) - parseInt(erAvailable, 10)),
            reporting_source: 'staff_manual',
          });
          await updateFacilityCapacity(facility.id, {
            category: 'icu_beds',
            total: parseInt(icuTotal, 10),
            occupied: Math.max(0, parseInt(icuTotal, 10) - parseInt(icuAvailable, 10)),
            reporting_source: 'staff_manual',
          });
          await updateFacilityCapacity(facility.id, {
            category: 'trauma_bays',
            total: parseInt(traumaTotal, 10),
            occupied: Math.max(0, parseInt(traumaTotal, 10) - parseInt(traumaAvailable, 10)),
            reporting_source: 'staff_manual',
          });
        } catch (facErr) {
          console.warn('Facility-level capacity sync note:', facErr);
        }
      }

      if (onCapacityUpdated) {
        onCapacityUpdated({
          available_er_beds: parseInt(erAvailable, 10),
          total_er_beds: parseInt(erTotal, 10),
          icu_beds_available: parseInt(icuAvailable, 10),
          icu_beds_total: parseInt(icuTotal, 10),
          trauma_bays_available: parseInt(traumaAvailable, 10),
          trauma_bays_total: parseInt(traumaTotal, 10),
          operating_rooms_available: parseInt(orAvailable, 10),
          operating_rooms_total: parseInt(orTotal, 10),
          updated_at: new Date().toISOString(),
        });
      }
      onClose();
    } catch (err) {
      setError(err?.message || 'Failed to update bed capacity.');
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
          maxWidth: '540px',
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
                backgroundColor: '#EEF2FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#4F46E5',
              }}
            >
              <Bed size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '17px', fontWeight: 700, color: '#111827' }}>
                Update Live Bed Capacities
              </h2>
              <p style={{ fontSize: '13px', color: '#6B7280' }}>
                {facility?.name || 'Central Facility Registry'}
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
            {/* ER Beds */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.4fr 1fr 1fr',
                gap: '12px',
                alignItems: 'center',
                padding: '10px 14px',
                backgroundColor: '#F9FAFB',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                  Emergency Dept (ED)
                </div>
                <div style={{ fontSize: '11px', color: '#6B7280' }}>General triage beds</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Available
                </label>
                <input
                  type="number"
                  min="0"
                  value={erAvailable}
                  onChange={(e) => setErAvailable(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Total Beds
                </label>
                <input
                  type="number"
                  min="0"
                  value={erTotal}
                  onChange={(e) => setErTotal(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
            </div>

            {/* ICU Beds */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.4fr 1fr 1fr',
                gap: '12px',
                alignItems: 'center',
                padding: '10px 14px',
                backgroundColor: '#F9FAFB',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                  Intensive Care (ICU)
                </div>
                <div style={{ fontSize: '11px', color: '#6B7280' }}>Ventilator-capable units</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Available
                </label>
                <input
                  type="number"
                  min="0"
                  value={icuAvailable}
                  onChange={(e) => setIcuAvailable(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Total Beds
                </label>
                <input
                  type="number"
                  min="0"
                  value={icuTotal}
                  onChange={(e) => setIcuTotal(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
            </div>

            {/* Trauma Bays */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.4fr 1fr 1fr',
                gap: '12px',
                alignItems: 'center',
                padding: '10px 14px',
                backgroundColor: '#F9FAFB',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                  Trauma Bays
                </div>
                <div style={{ fontSize: '11px', color: '#6B7280' }}>Resuscitation suites</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Available
                </label>
                <input
                  type="number"
                  min="0"
                  value={traumaAvailable}
                  onChange={(e) => setTraumaAvailable(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Total Bays
                </label>
                <input
                  type="number"
                  min="0"
                  value={traumaTotal}
                  onChange={(e) => setTraumaTotal(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
            </div>

            {/* Operating Rooms */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.4fr 1fr 1fr',
                gap: '12px',
                alignItems: 'center',
                padding: '10px 14px',
                backgroundColor: '#F9FAFB',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                  Operating Rooms (OR)
                </div>
                <div style={{ fontSize: '11px', color: '#6B7280' }}>Active surgical suites</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Available
                </label>
                <input
                  type="number"
                  min="0"
                  value={orAvailable}
                  onChange={(e) => setOrAvailable(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#6B7280', marginBottom: '4px' }}>
                  Total Suites
                </label>
                <input
                  type="number"
                  min="0"
                  value={orTotal}
                  onChange={(e) => setOrTotal(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #D1D5DB',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  required
                />
              </div>
            </div>
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
                backgroundColor: '#D92D3A',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? 'Updating Capacities...' : 'Publish Live Capacities'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CapacityUpdateModal;
