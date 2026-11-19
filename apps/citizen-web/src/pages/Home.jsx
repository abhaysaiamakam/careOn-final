import React, { useState } from 'react';
import {
  AlertTriangle,
  HeartPulse,
  Car,
  Flame,
  ShieldAlert,
  Users,
  Search,
  ArrowRight,
  PhoneCall,
  Clock,
  CheckCircle,
} from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import { INCIDENT_CATEGORIES } from '@careon/contracts';
import { getLocalDrafts } from '../services/offlineDrafts.js';
import { useAuth } from '@careon/auth';

export function Home({ onNavigate }) {
  const { user, isAuthenticated } = useAuth();
  const [quickTrackToken, setQuickTrackToken] = useState('');
  const drafts = getLocalDrafts();

  const handleCategorySelect = (catId) => {
    onNavigate(`/report?category=${encodeURIComponent(catId)}`);
  };

  const handleTrackSubmit = (e) => {
    e.preventDefault();
    if (quickTrackToken.trim()) {
      onNavigate(`/track?id=${encodeURIComponent(quickTrackToken.trim())}`);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Offline Drafts Notice (if any) */}
      {drafts.length > 0 && (
        <div
          style={{
            backgroundColor: '#FFFBEB',
            border: '1px solid #FDE68A',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontFamily: typography.fontFamily.sans,
            fontSize: typography.fontSize.sm,
            color: '#92400E',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} />
            <span>
              You have <strong>{drafts.length}</strong> locally saved emergency report draft{drafts.length > 1 ? 's' : ''}.
            </span>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onNavigate('/drafts')}
          >
            Review Drafts
          </Button>
        </div>
      )}

      {/* Primary Emergency SOS Hero */}
      <Card
        variant="emergency"
        padding="lg"
        style={{
          marginBottom: '32px',
          backgroundColor: colors.surface,
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <span
          style={{
            fontSize: typography.fontSize.xs,
            fontWeight: typography.fontWeight.bold,
            color: colors.secondary,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: '8px',
          }}
        >
          Immediate Emergency Response
        </span>
        <h1
          style={{
            fontSize: '2rem',
            fontWeight: typography.fontWeight.bold,
            color: colors.textPrimary,
            margin: '0 0 12px',
            lineHeight: 1.2,
          }}
        >
          Need urgent emergency assistance?
        </h1>
        <p
          style={{
            fontSize: typography.fontSize.base,
            color: colors.textSecondary,
            maxWidth: '560px',
            margin: '0 0 24px',
            lineHeight: 1.5,
          }}
        >
          CareOn connects you directly with regional EMS ambulances, trauma hospitals, and multi-agency emergency operations.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%', maxWidth: '400px' }}>
          <Button
            size="lg"
            variant="primary"
            fullWidth
            onClick={() => onNavigate('/report')}
            style={{
              padding: '18px 24px',
              fontSize: '1.125rem',
              fontWeight: typography.fontWeight.bold,
              letterSpacing: '0.02em',
            }}
          >
            REPORT AN EMERGENCY NOW
          </Button>

          <span style={{ fontSize: typography.fontSize.xs, color: colors.textMuted }}>
            Life-threatening? Dial <strong>112</strong> or <strong>108</strong> immediately.
          </span>
        </div>
      </Card>

      {/* Fast Category Select Grid */}
      <div style={{ marginBottom: '40px' }}>
        <h2
          style={{
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.semibold,
            color: colors.textPrimary,
            marginBottom: '16px',
          }}
        >
          Select Emergency Type
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '12px',
          }}
        >
          {INCIDENT_CATEGORIES.map((cat) => {
            const Icon =
              cat.id === 'Medical'
                ? HeartPulse
                : cat.id === 'Road accident'
                ? Car
                : cat.id === 'Fire'
                ? Flame
                : cat.id === 'Rescue'
                ? ShieldAlert
                : cat.id === 'Disaster / Multiple affected people'
                ? Users
                : AlertTriangle;

            return (
              <Card
                key={cat.id}
                onClick={() => handleCategorySelect(cat.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  padding: '16px',
                  cursor: 'pointer',
                  border: `1px solid ${colors.border}`,
                  transition: 'border-color 0.15s ease',
                }}
              >
                <div
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '8px',
                    backgroundColor: '#FEF2F2',
                    border: '1px solid #FECACA',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: colors.secondary,
                    flexShrink: 0,
                  }}
                >
                  <Icon size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      fontWeight: typography.fontWeight.semibold,
                      color: colors.textPrimary,
                      fontSize: typography.fontSize.base,
                    }}
                  >
                    {cat.label}
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    {cat.defaultHelp}
                  </div>
                </div>
                <ArrowRight size={16} color={colors.textSecondary} />
              </Card>
            );
          })}
        </div>
      </div>

      {/* Quick Track Request Bar */}
      <Card
        padding="md"
        style={{
          marginBottom: '40px',
          backgroundColor: colors.surfaceSubtle,
          border: `1px solid ${colors.border}`,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <h3
              style={{
                margin: 0,
                fontSize: typography.fontSize.base,
                fontWeight: typography.fontWeight.semibold,
                color: colors.textPrimary,
              }}
            >
              Track an Existing Emergency Request
            </h3>
            <p
              style={{
                margin: '4px 0 0',
                fontSize: typography.fontSize.xs,
                color: colors.textSecondary,
              }}
            >
              Enter the incident reference code (e.g. CARE-2026-101) or your secure tracking token.
            </p>
          </div>

          <form
            onSubmit={handleTrackSubmit}
            style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}
          >
            <input
              type="text"
              placeholder="e.g. CARE-2026-101 or token..."
              value={quickTrackToken}
              onChange={(e) => setQuickTrackToken(e.target.value)}
              style={{
                flex: 1,
                minWidth: '220px',
                padding: '10px 14px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                fontSize: typography.fontSize.sm,
                color: colors.textPrimary,
                outline: 'none',
              }}
            />
            <Button type="submit" variant="secondary-red" icon={Search}>
              Track Status
            </Button>
          </form>
        </div>
      </Card>

      {/* Direct Civilian Protocols */}
      <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '24px' }}>
        <h3
          style={{
            fontSize: typography.fontSize.base,
            fontWeight: typography.fontWeight.semibold,
            color: colors.textPrimary,
            marginBottom: '12px',
          }}
        >
          Civilian Emergency Protocols
        </h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '16px',
          }}
        >
          <div style={{ padding: '12px', border: `1px solid ${colors.border}`, borderRadius: '6px' }}>
            <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm, marginBottom: '4px' }}>
              1. Stay Calm & Secure
            </div>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Ensure your immediate physical safety and move away from active hazards before reporting.
            </p>
          </div>
          <div style={{ padding: '12px', border: `1px solid ${colors.border}`, borderRadius: '6px' }}>
            <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm, marginBottom: '4px' }}>
              2. Precise Location
            </div>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              GPS helps responders find you quickly, but landmarks and floor numbers speed up access.
            </p>
          </div>
          <div style={{ padding: '12px', border: `1px solid ${colors.border}`, borderRadius: '6px' }}>
            <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm, marginBottom: '4px' }}>
              3. Keep Lines Open
            </div>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Dispatchers or paramedics may call your phone to verify access details and give first aid advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
