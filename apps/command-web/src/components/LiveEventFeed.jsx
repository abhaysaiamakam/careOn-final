import React, { useState } from 'react';
import {
  Activity,
  ChevronUp,
  ChevronDown,
  Clock,
  Radio,
  AlertTriangle,
  Send,
  Building2,
  Trash2,
} from 'lucide-react';
import { colors, typography, Badge } from '@careon/design-system';

export function LiveEventFeed({ events = [], onClear = () => {} }) {
  const [expanded, setExpanded] = useState(false);

  const getEventBadge = (type) => {
    switch (type) {
      case 'incident_created':
      case 'INCIDENT_CREATED':
        return <Badge variant="danger">NEW INCIDENT</Badge>;
      case 'assignment_created':
      case 'DISPATCH_APPROVED':
        return <Badge variant="success">DISPATCH</Badge>;
      case 'telemetry_updated':
        return <Badge variant="neutral">TELEMETRY</Badge>;
      case 'hospital_diversion_updated':
        return <Badge variant="warning">HOSPITAL</Badge>;
      default:
        return <Badge variant="secondary">{type?.toUpperCase() || 'EVENT'}</Badge>;
    }
  };

  return (
    <div
      style={{
        borderTop: '1px solid #1E293B',
        backgroundColor: '#0F172A',
        color: '#FFFFFF',
        transition: 'height 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Feed Toggle Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          cursor: 'pointer',
          backgroundColor: '#1E293B',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={14} color="#10B981" />
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#F1F5F9', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Live Operations Event Stream ({events.length})
          </span>
          {events.length > 0 && !expanded && (
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>
              • Latest: {events[0]?.text || events[0]?.type || 'Event received'}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded && events.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClear();
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#94A3B8',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '10px',
              }}
            >
              <Trash2 size={12} /> Clear
            </button>
          )}
          {expanded ? <ChevronDown size={16} color="#94A3B8" /> : <ChevronUp size={16} color="#94A3B8" />}
        </div>
      </div>

      {/* Expanded Stream Content */}
      {expanded && (
        <div
          style={{
            maxHeight: '180px',
            overflowY: 'auto',
            padding: '8px 16px',
            backgroundColor: '#0B132B',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          {events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px', fontSize: '11px', color: '#64748B' }}>
              Listening for real-time dispatch, responder, and telemetry events on M4 WebSocket channels...
            </div>
          ) : (
            events.map((evt, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  backgroundColor: '#0F172A',
                  borderRadius: '4px',
                  border: '1px solid #1E293B',
                  fontSize: '11px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#64748B', fontFamily: 'monospace', fontSize: '10px' }}>
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString()}
                  </span>
                  {getEventBadge(evt.type)}
                  <span style={{ color: '#E2E8F0' }}>
                    {evt.text || JSON.stringify(evt.data || evt)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
