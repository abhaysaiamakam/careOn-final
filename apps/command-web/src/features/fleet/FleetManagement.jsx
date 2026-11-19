import React, { useState } from 'react';
import {
  Truck,
  Activity,
  MapPin,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Clock,
  Shield,
  Edit2,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import { updateResourceStatus } from '@careon/api-client';

export function FleetManagement({
  resources = [],
  onRefresh = () => {},
  loading = false,
}) {
  const [filterCategory, setFilterCategory] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [search, setSearch] = useState('');
  const [updatingId, setUpdatingId] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const filtered = resources.filter((r) => {
    if (filterCategory !== 'ALL' && r.category !== filterCategory) return false;
    if (filterStatus !== 'ALL' && r.status !== filterStatus) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      const code = (r.resource_code || '').toLowerCase();
      const name = (r.name || '').toLowerCase();
      const loc = (r.location_name || '').toLowerCase();
      return code.includes(q) || name.includes(q) || loc.includes(q);
    }
    return true;
  });

  const handleStatusToggle = async (resource, newStatus) => {
    setUpdatingId(resource.id);
    try {
      await updateResourceStatus(resource.id, newStatus, 'Dispatcher manual fleet status update');
      setFeedback(`Status of ${resource.resource_code} changed to ${newStatus}.`);
      onRefresh();
      setTimeout(() => setFeedback(null), 3000);
    } catch (e) {
      alert(`Failed to update status: ${e.message}`);
    } finally {
      setUpdatingId(null);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Available':
        return <Badge variant="success">AVAILABLE</Badge>;
      case 'Assigned':
      case 'En Route':
        return <Badge variant="warning">{status?.toUpperCase()}</Badge>;
      case 'On Scene':
        return <Badge variant="danger">ON SCENE</Badge>;
      default:
        return <Badge variant="neutral">{status?.toUpperCase() || 'OFFLINE'}</Badge>;
    }
  };

  return (
    <div style={{ padding: '20px 24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* View Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Emergency Fleet & Tactical Resources
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Real-time operational status, spatial locations, and capability profiles across all registered EMS, Fire, and Rescue assets.
          </p>
        </div>

        <Button size="sm" variant="outline" onClick={onRefresh} loading={loading} icon={RefreshCw}>
          Refresh Fleet
        </Button>
      </div>

      {feedback && (
        <div style={{ marginBottom: '16px', background: '#ECFDF5', border: '1px solid #A7F3D0', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: '#065F46' }}>
          ✓ {feedback}
        </div>
      )}

      {/* Filter Bar */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          flexWrap: 'wrap',
          padding: '12px 16px',
          backgroundColor: '#FFFFFF',
          borderRadius: '8px',
          border: `1px solid ${colors.border}`,
          marginBottom: '20px',
        }}
      >
        <div style={{ minWidth: '220px', flex: 1 }}>
          <input
            type="text"
            placeholder="Search vehicle code, station, name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '6px',
              border: `1px solid ${colors.border}`,
              fontSize: typography.fontSize.xs,
              outline: 'none',
            }}
          />
        </div>

        {/* Category Select */}
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            border: `1px solid ${colors.border}`,
            fontSize: typography.fontSize.xs,
            background: '#FFFFFF',
          }}
        >
          <option value="ALL">All Categories</option>
          <option value="Ambulance">Ambulances</option>
          <option value="Fire Response">Fire Response</option>
          <option value="Police Patrol">Police Patrol</option>
          <option value="Rescue Team">Rescue Teams</option>
          <option value="Shelter / Relief Centre">Shelters</option>
        </select>

        {/* Status Select */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            border: `1px solid ${colors.border}`,
            fontSize: typography.fontSize.xs,
            background: '#FFFFFF',
          }}
        >
          <option value="ALL">All Statuses</option>
          <option value="Available">Available</option>
          <option value="Assigned">Assigned</option>
          <option value="En Route">En Route</option>
          <option value="Maintenance">Maintenance</option>
          <option value="Offline">Offline</option>
        </select>

        <span style={{ fontSize: '11px', color: colors.textSecondary }}>
          Showing {filtered.length} of {resources.length}
        </span>
      </div>

      {/* Fleet Data Table */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '8px',
          border: `1px solid ${colors.border}`,
          overflowX: 'auto',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
          <thead>
            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: `1px solid ${colors.border}` }}>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Asset Code</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Resource Name & Type</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Operational Status</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Current Station / Coords</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Capabilities</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                <td style={{ padding: '12px 16px', fontWeight: 700, color: colors.textPrimary }}>
                  {r.resource_code}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ fontWeight: 600, color: colors.textPrimary }}>{r.name}</div>
                  <div style={{ fontSize: '10px', color: colors.textSecondary }}>{r.category}</div>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {getStatusBadge(r.status)}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ color: colors.textPrimary }}>{r.location_name || 'Designated Station'}</div>
                  <div style={{ fontSize: '10px', color: colors.textSecondary, fontFamily: 'monospace' }}>
                    {r.latitude?.toFixed(4)}, {r.longitude?.toFixed(4)}
                  </div>
                  {r.last_updated && (
                    <div style={{ fontSize: '10px', marginTop: '2px' }}>
                      {Date.now() - new Date(r.last_updated).getTime() > 30 * 60 * 1000 ? (
                        <span style={{ color: '#D97706', fontWeight: 600 }}>⚠️ Stale GPS (&gt;30m)</span>
                      ) : (
                        <span style={{ color: '#10B981', fontWeight: 600 }}>● Live Telemetry</span>
                      )}
                    </div>
                  )}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {(r.capabilities || 'Standard').split(',').slice(0, 3).map((cap) => (
                      <span key={cap} style={{ fontSize: '10px', background: '#F1F5F9', padding: '2px 6px', borderRadius: '4px' }}>
                        {cap.trim()}
                      </span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {r.status === 'Available' ? (
                    <button
                      disabled={updatingId === r.id}
                      onClick={() => handleStatusToggle(r, 'Maintenance')}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        border: '1px solid #CBD5E1',
                        background: '#FFFFFF',
                        fontSize: '11px',
                        cursor: 'pointer',
                      }}
                    >
                      Set Maintenance
                    </button>
                  ) : r.status === 'Maintenance' ? (
                    <button
                      disabled={updatingId === r.id}
                      onClick={() => handleStatusToggle(r, 'Available')}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        border: '1px solid #A7F3D0',
                        background: '#ECFDF5',
                        color: '#065F46',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Mark Available
                    </button>
                  ) : (
                    <span style={{ fontSize: '11px', color: colors.textSecondary }}>
                      Active Mission #{r.current_assignment_id || 'Active'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
