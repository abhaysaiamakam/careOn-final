import React from 'react';
import { colors } from '../tokens';

export function StatusIndicator({
  status = 'active', // 'critical' | 'warning' | 'active' | 'offline'
  label = null,
  pulse = true,
}) {
  const colorMap = {
    critical: colors.status.critical,
    warning: colors.status.warning,
    active: colors.status.success,
    offline: colors.text.muted,
  };

  const activeColor = colorMap[status] || colors.status.info;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
      <span
        style={{
          position: 'relative',
          display: 'inline-flex',
          width: '10px',
          height: '10px',
        }}
      >
        {pulse && (
          <span
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              backgroundColor: activeColor,
              opacity: 0.75,
              animation: 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite',
            }}
          />
        )}
        <span
          style={{
            position: 'relative',
            display: 'inline-block',
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: activeColor,
          }}
        />
      </span>
      {label && (
        <span style={{ fontSize: '0.85rem', color: colors.text.secondary, fontWeight: 500 }}>
          {label}
        </span>
      )}
    </span>
  );
}

export function LoadingState({ message = 'Loading emergency operations...' }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        gap: '16px',
        color: colors.text.muted,
      }}
    >
      <div
        style={{
          width: '36px',
          height: '36px',
          border: `3px solid ${colors.border.subtle}`,
          borderTopColor: colors.brand.primary,
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <span style={{ fontSize: '0.9rem', color: colors.text.secondary }}>{message}</span>
    </div>
  );
}

export function EmptyState({
  icon: Icon = null,
  title = 'No records found',
  description = 'Everything is currently clear.',
  action = null,
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '56px 24px',
        textAlign: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.01)',
        borderRadius: '12px',
        border: `1px dashed ${colors.border.subtle}`,
      }}
    >
      {Icon && (
        <div style={{ color: colors.text.muted, marginBottom: '16px' }}>
          <Icon size={40} strokeWidth={1.5} />
        </div>
      )}
      <h4 style={{ margin: '0 0 8px 0', color: colors.text.primary, fontSize: '1.1rem', fontWeight: 600 }}>
        {title}
      </h4>
      <p style={{ margin: '0 0 20px 0', color: colors.text.muted, fontSize: '0.875rem', maxWidth: '380px' }}>
        {description}
      </p>
      {action}
    </div>
  );
}
