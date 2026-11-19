import React, { useState, useEffect } from 'react';
import { Clock, Activity, Heart, ShieldAlert, CheckCircle2, ChevronRight, X } from 'lucide-react';
import { getEncounterTimeline } from '@careon/api-client';

export function ClinicalPatientTimelineView({ encounterId, isOpen, onClose }) {
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !encounterId) return;

    let mounted = true;
    async function fetchTimeline() {
      setLoading(true);
      setError(null);
      try {
        const events = await getEncounterTimeline(encounterId);
        if (mounted) {
          setTimelineEvents(Array.isArray(events) ? events : events?.events || []);
        }
      } catch (err) {
        if (mounted) setError(err?.message || 'Failed to retrieve encounter timeline.');
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchTimeline();
    return () => {
      mounted = false;
    };
  }, [isOpen, encounterId]);

  if (!isOpen) return null;

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
          maxWidth: '600px',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        }}
      >
        {/* Header */}
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
                backgroundColor: '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563EB',
              }}
            >
              <Clock size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '17px', fontWeight: 700, color: '#111827' }}>
                Chronological Clinical Timeline
              </h2>
              <p style={{ fontSize: '13px', color: '#6B7280' }}>
                Encounter #{encounterId}
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

        {/* Content body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '32px', color: '#6B7280', fontSize: '13px' }}>
              Retrieving clinical audit events...
            </div>
          )}

          {error && (
            <div
              style={{
                padding: '12px',
                borderRadius: '6px',
                backgroundColor: '#FEF2F2',
                border: '1px solid #FCA5A5',
                color: '#991B1B',
                fontSize: '13px',
                marginBottom: '16px',
              }}
            >
              {error}
            </div>
          )}

          {!loading && timelineEvents.length === 0 && !error && (
            <div style={{ textAlign: 'center', padding: '32px', color: '#6B7280', fontSize: '13px' }}>
              No recorded timeline events for this clinical encounter.
            </div>
          )}

          {/* Chronological events list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {timelineEvents.map((evt, idx) => (
              <div
                key={evt.id || idx}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                }}
              >
                <div
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    backgroundColor: '#F3F4F6',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#4B5563',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  <Activity size={14} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>
                      {evt.event_type || evt.type || 'Clinical Observation'}
                    </span>
                    <span style={{ fontSize: '11px', color: '#9CA3AF' }}>
                      {evt.created_at ? new Date(evt.created_at).toLocaleTimeString() : '—'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#4B5563', lineHeight: 1.4 }}>
                    {evt.description || evt.summary || JSON.stringify(evt.payload || evt.data || {})}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ClinicalPatientTimelineView;
