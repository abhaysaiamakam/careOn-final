import React from 'react';
import { ShieldCheck, PhoneCall, Heart } from 'lucide-react';
import { colors, typography } from '@careon/design-system';

export function CitizenFooter({ onNavigate }) {
  return (
    <footer
      style={{
        backgroundColor: colors.surfaceSubtle,
        borderTop: `1px solid ${colors.border}`,
        padding: '32px 16px',
        marginTop: 'auto',
        fontFamily: typography.fontFamily.sans,
      }}
    >
      <div
        style={{
          maxWidth: '1120px',
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ fontWeight: typography.fontWeight.bold, color: colors.textPrimary, fontSize: typography.fontSize.base }}>
                CareOn Citizen
              </span>
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textMuted }}>
                PWA v1.0.0
              </span>
            </div>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Intelligent civilian emergency coordination & life-support coordination system.
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: colors.surface,
              padding: '8px 16px',
              borderRadius: '6px',
              border: `1px solid ${colors.border}`,
            }}
          >
            <PhoneCall size={16} color={colors.secondary} />
            <span style={{ fontSize: typography.fontSize.xs, color: colors.textPrimary }}>
              National Emergency Hotlines: <strong>112</strong> (Unified) / <strong>108</strong> (Ambulance)
            </span>
          </div>
        </div>

        <div
          style={{
            borderTop: `1px solid ${colors.border}`,
            paddingTop: '16px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: typography.fontSize.xs,
            color: colors.textMuted,
            gap: '12px',
          }}
        >
          <div>
            © {new Date().getFullYear()} CareOn Emergency Coordination Operating System. All rights reserved.
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <span style={{ cursor: 'pointer' }} onClick={() => onNavigate && onNavigate('/settings')}>
              Settings & PWA
            </span>
            <span style={{ cursor: 'pointer' }} onClick={() => onNavigate && onNavigate('/track')}>
              Public Tracking
            </span>
            <span>Encrypted End-to-End</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
