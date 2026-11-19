import React, { useState, useEffect } from 'react';
import {
  Shield,
  PlusCircle,
  Clock,
  User,
  HeartPulse,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  PhoneCall,
  CheckCircle2,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import { listIncidents } from '@careon/api-client';
import { useAuth } from '@careon/auth';
import { getLocalDrafts } from '../services/offlineDrafts.js';

export function CitizenDashboard({ onNavigate }) {
  const { user } = useAuth();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const drafts = getLocalDrafts();

  const fetchMyIncidents = async () => {
    setLoading(true);
    try {
      const data = await listIncidents({ my_requests_only: true });
      setIncidents(data || []);
    } catch (e) {
      console.warn('Failed to load user incidents:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMyIncidents();
  }, []);

  const activeIncidents = incidents.filter(
    (inc) => !['Resolved', 'Cancelled', 'Rejected'].includes(inc.status)
  );

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Top Welcome Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          borderBottom: `1px solid ${colors.border}`,
          paddingBottom: '20px',
          marginBottom: '24px',
        }}
      >
        <div>
          <span style={{ fontSize: typography.fontSize.xs, color: colors.secondary, fontWeight: typography.fontWeight.semibold, textTransform: 'uppercase' }}>
            Civilian Emergency Portal
          </span>
          <h1 style={{ margin: '4px 0 0', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Welcome, {user?.name || 'Citizen'}
          </h1>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="sm"
            variant="primary"
            onClick={() => onNavigate('/report')}
            icon={PlusCircle}
          >
            Report Emergency
          </Button>
        </div>
      </div>

      {/* Active Incidents Banner */}
      {activeIncidents.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold, marginBottom: '12px', color: colors.secondary }}>
            Active Emergency Missions ({activeIncidents.length})
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeIncidents.map((inc) => (
              <Card
                key={inc.id}
                variant="emergency"
                padding="md"
                onClick={() => onNavigate(`/track?id=${encodeURIComponent(inc.tracking_token || inc.incident_code)}`)}
                style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
                      {inc.incident_code}
                    </strong>
                    <Badge variant="emergency">{inc.status}</Badge>
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    {inc.category} • {inc.location_name} • Reported {new Date(inc.created_at).toLocaleTimeString()}
                  </div>
                </div>
                <ArrowRight size={18} color={colors.secondary} />
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Quick Action Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
          marginBottom: '32px',
        }}
      >
        <Card
          padding="md"
          onClick={() => onNavigate('/report')}
          style={{ cursor: 'pointer', border: `1px solid ${colors.secondary}`, borderLeftWidth: '4px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '6px', backgroundColor: '#FEF2F2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.secondary }}>
              <PlusCircle size={20} />
            </div>
            <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
              Request Emergency Help
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Start guided 5-step emergency dispatch request with GPS location.
          </p>
        </Card>

        <Card
          padding="md"
          onClick={() => onNavigate('/track')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '6px', backgroundColor: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textPrimary }}>
              <Clock size={20} />
            </div>
            <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
              Track Emergency
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Look up status using incident reference or tracking credentials.
          </p>
        </Card>

        <Card
          padding="md"
          onClick={() => onNavigate('/contacts')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '6px', backgroundColor: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textPrimary }}>
              <User size={20} />
            </div>
            <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
              ICE Emergency Contacts
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Manage family or primary contacts to notify during an incident.
          </p>
        </Card>
      </div>

      {/* Offline Drafts Alert (if any) */}
      {drafts.length > 0 && (
        <Card
          padding="md"
          style={{
            backgroundColor: '#FFFBEB',
            border: '1px solid #FDE68A',
            marginBottom: '32px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong style={{ fontSize: typography.fontSize.sm, color: '#92400E' }}>
                {drafts.length} Local Draft{drafts.length > 1 ? 's' : ''} Stored Offline
              </strong>
              <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.xs, color: '#B45309' }}>
                These drafts have not been submitted to emergency dispatch.
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onNavigate('/drafts')}
            >
              Manage Drafts
            </Button>
          </div>
        </Card>
      )}

      {/* Recent History Table */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h2 style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold, margin: 0 }}>
            Recent Emergency History
          </h2>
          <Button
            size="sm"
            variant="tertiary"
            onClick={() => onNavigate('/history')}
          >
            View All
          </Button>
        </div>

        {incidents.length === 0 ? (
          <Card padding="md" style={{ textAlign: 'center', color: colors.textSecondary, fontSize: typography.fontSize.sm }}>
            {loading ? 'Loading emergency records...' : 'No emergency incidents reported yet.'}
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {incidents.slice(0, 3).map((inc) => (
              <Card
                key={inc.id}
                padding="sm"
                onClick={() => onNavigate(`/track?id=${encodeURIComponent(inc.tracking_token || inc.incident_code)}`)}
                style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div>
                  <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm }}>
                    {inc.incident_code} — {inc.category}
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    {inc.location_name} • {new Date(inc.created_at).toLocaleDateString()}
                  </div>
                </div>
                <Badge variant={inc.status === 'Resolved' ? 'success' : 'neutral'}>
                  {inc.status}
                </Badge>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
