import React, { useState } from 'react';
import {
  Search,
  Filter,
  AlertTriangle,
  Clock,
  MapPin,
  Users,
  ChevronRight,
  Flame,
  HeartPulse,
  Car,
  ShieldAlert,
} from 'lucide-react';
import { colors, typography, Badge, Input } from '@careon/design-system';
import { DISPATCH_QUEUE_TABS } from '@careon/contracts';

export function IncidentQueue({
  incidents = [],
  selectedIncident = null,
  onSelectIncident = () => {},
  loading = false,
}) {
  const [activeTab, setActiveTab] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredIncidents = incidents.filter((inc) => {
    // 1. Tab filter
    if (activeTab === 'UNASSIGNED') {
      if (['Allocated', 'Dispatched', 'En Route to Scene', 'At Scene', 'Transporting', 'Resolved', 'Cancelled'].includes(inc.status)) {
        return false;
      }
    } else if (activeTab === 'CRITICAL') {
      if (inc.priority !== 'Critical') return false;
    } else if (activeTab === 'ACTIVE') {
      if (['Resolved', 'Cancelled', 'Rejected'].includes(inc.status)) return false;
    } else if (activeTab === 'MCI') {
      if (!inc.is_disaster && (inc.affected_people || 1) <= 2) return false;
    } else if (activeTab === 'RESOLVED') {
      if (inc.status !== 'Resolved') return false;
    }

    // 2. Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const code = (inc.incident_code || '').toLowerCase();
      const cat = (inc.category || '').toLowerCase();
      const loc = (inc.location_name || '').toLowerCase();
      return code.includes(q) || cat.includes(q) || loc.includes(q);
    }

    return true;
  });

  const getPriorityBadgeVariant = (priority) => {
    switch (priority) {
      case 'Critical': return 'danger';
      case 'High': return 'warning';
      case 'Medium': return 'secondary';
      default: return 'neutral';
    }
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'Medical': return HeartPulse;
      case 'Road accident': return Car;
      case 'Fire': return Flame;
      default: return ShieldAlert;
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: '#FFFFFF',
        borderRight: `1px solid ${colors.border}`,
      }}
    >
      {/* Queue Header & Search */}
      <div style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h2 style={{ margin: 0, fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Incident Queue ({filteredIncidents.length})
          </h2>
          <span style={{ fontSize: '11px', color: colors.textSecondary }}>
            Live Feed
          </span>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Search code, category, location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 32px',
              borderRadius: '6px',
              border: `1px solid ${colors.border}`,
              fontSize: typography.fontSize.xs,
              backgroundColor: '#F8FAFC',
              outline: 'none',
            }}
          />
          <Search size={14} color="#94A3B8" style={{ position: 'absolute', left: '10px', top: '10px' }} />
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          overflowX: 'auto',
          padding: '6px 12px',
          gap: '4px',
          borderBottom: `1px solid ${colors.border}`,
          backgroundColor: '#F8FAFC',
        }}
      >
        {DISPATCH_QUEUE_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: activeTab === tab.id ? '#FFFFFF' : 'transparent',
              border: `1px solid ${activeTab === tab.id ? '#CBD5E1' : 'transparent'}`,
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: activeTab === tab.id ? 600 : 500,
              color: activeTab === tab.id ? colors.secondary : colors.textSecondary,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Incident List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '24px', color: colors.textSecondary, fontSize: typography.fontSize.xs }}>
            Syncing incident queue...
          </div>
        )}

        {!loading && filteredIncidents.length === 0 && (
          <div style={{ textAlign: 'center', padding: '36px 16px', color: colors.textSecondary }}>
            <AlertTriangle size={24} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
            <div style={{ fontSize: typography.fontSize.xs, fontWeight: 600 }}>No matching incidents</div>
            <div style={{ fontSize: '11px', marginTop: '4px' }}>Queue is clear for this filter criteria.</div>
          </div>
        )}

        {filteredIncidents.map((inc) => {
          const isSelected = selectedIncident?.id === inc.id;
          const CategoryIcon = getCategoryIcon(inc.category);
          return (
            <div
              key={inc.id}
              onClick={() => onSelectIncident(inc)}
              style={{
                backgroundColor: isSelected ? '#FEF2F2' : '#FFFFFF',
                border: `1px solid ${isSelected ? colors.secondary : colors.border}`,
                borderRadius: '6px',
                padding: '10px 12px',
                marginBottom: '8px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onMouseOver={(e) => {
                if (!isSelected) e.currentTarget.style.borderColor = '#CBD5E1';
              }}
              onMouseOut={(e) => {
                if (!isSelected) e.currentTarget.style.borderColor = colors.border;
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CategoryIcon size={14} color={inc.priority === 'Critical' ? colors.secondary : colors.textSecondary} />
                  <span style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                    {inc.incident_code || `#${inc.id}`}
                  </span>
                  {inc.is_duplicate && (
                    <span style={{ fontSize: '9px', background: '#FEF3C7', color: '#92400E', padding: '1px 4px', borderRadius: '3px', fontWeight: 700 }}>
                      DUPLICATE
                    </span>
                  )}
                  {inc.is_disaster && (
                    <span style={{ fontSize: '9px', background: '#FEE2E2', color: '#991B1B', padding: '1px 4px', borderRadius: '3px', fontWeight: 700 }}>
                      MCI
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  <Badge variant={getPriorityBadgeVariant(inc.priority)}>
                    {inc.priority}
                  </Badge>
                </div>
              </div>

              <div style={{ fontSize: '11px', color: colors.textPrimary, fontWeight: 500, marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {inc.category} • {inc.title || inc.description || 'Emergency Incident'}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px', color: colors.textSecondary }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', maxWidth: '170px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <MapPin size={11} />
                  <span>{inc.location_name || 'Location recorded'}</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, color: inc.status === 'Received' ? colors.secondary : '#475569' }}>
                    {inc.status}
                  </span>
                  <span>{inc.created_at ? new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
