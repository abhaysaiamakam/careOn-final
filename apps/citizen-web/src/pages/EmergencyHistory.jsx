import React, { useState, useEffect } from 'react';
import { Clock, Search, ArrowRight, RefreshCw, AlertCircle } from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  Input,
  colors,
  typography,
} from '@careon/design-system';
import { listIncidents } from '@careon/api-client';

export function EmergencyHistory({ onNavigate }) {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('ALL');

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const data = await listIncidents({ my_requests_only: true });
      setIncidents(data || []);
    } catch (e) {
      console.warn('Failed to load incident history:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const filtered = incidents.filter((inc) => {
    if (filterStatus === 'ACTIVE') {
      return !['Resolved', 'Cancelled', 'Rejected'].includes(inc.status);
    }
    if (filterStatus === 'RESOLVED') {
      return inc.status === 'Resolved';
    }
    if (filterStatus === 'CANCELLED') {
      return ['Cancelled', 'Rejected'].includes(inc.status);
    }
    return true;
  });

  return (
    <div style={{ maxWidth: '840px', margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Emergency Request History
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
            All past and ongoing emergency reports associated with your citizen account.
          </p>
        </div>
        <Button
          size="sm"
          variant="tertiary"
          onClick={fetchIncidents}
          icon={RefreshCw}
        >
          Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: `1px solid ${colors.border}`, paddingBottom: '12px' }}>
        {['ALL', 'ACTIVE', 'RESOLVED', 'CANCELLED'].map((tab) => (
          <button
            key={tab}
            onClick={() => setFilterStatus(tab)}
            style={{
              background: 'none',
              border: 'none',
              padding: '6px 12px',
              borderRadius: '4px',
              backgroundColor: filterStatus === tab ? '#FEF2F2' : 'transparent',
              color: filterStatus === tab ? colors.secondary : colors.textSecondary,
              fontWeight: filterStatus === tab ? typography.fontWeight.semibold : typography.fontWeight.normal,
              fontSize: typography.fontSize.xs,
              cursor: 'pointer',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Incidents List */}
      {loading ? (
        <Card padding="md" style={{ textAlign: 'center', color: colors.textSecondary }}>
          Loading emergency records...
        </Card>
      ) : filtered.length === 0 ? (
        <Card padding="lg" style={{ textAlign: 'center', color: colors.textSecondary }}>
          No emergency incidents found in this view.
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filtered.map((inc) => (
            <Card
              key={inc.id}
              padding="md"
              onClick={() => onNavigate(`/track?id=${encodeURIComponent(inc.tracking_token || inc.incident_code)}`)}
              style={{
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                borderLeft: !['Resolved', 'Cancelled'].includes(inc.status)
                  ? `3px solid ${colors.secondary}`
                  : `1px solid ${colors.border}`,
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
                    {inc.incident_code}
                  </strong>
                  <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    ({inc.category})
                  </span>
                  <Badge
                    variant={
                      !['Resolved', 'Cancelled', 'Rejected'].includes(inc.status)
                        ? 'emergency'
                        : inc.status === 'Resolved'
                        ? 'success'
                        : 'neutral'
                    }
                  >
                    {inc.status}
                  </Badge>
                </div>

                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  Location: {inc.location_name} • Reported: {new Date(inc.created_at).toLocaleString()}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: typography.fontSize.xs, color: colors.secondary, fontWeight: typography.fontWeight.medium }}>
                  View Live Tracking
                </span>
                <ArrowRight size={16} color={colors.secondary} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
