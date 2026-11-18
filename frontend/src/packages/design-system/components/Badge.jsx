import React from 'react';
import { colors, typography } from '../tokens';

export default function Badge({
  children,
  variant = 'neutral', // 'critical' | 'warning' | 'success' | 'info' | 'neutral'
  size = 'sm',         // 'xs' | 'sm' | 'md'
  style = {},
  className = '',
}) {
  const variantStyles = {
    critical: {
      backgroundColor: 'rgba(239, 68, 68, 0.15)',
      color: colors.status.critical,
      border: '1px solid rgba(239, 68, 68, 0.35)',
    },
    warning: {
      backgroundColor: 'rgba(245, 158, 11, 0.15)',
      color: colors.status.warning,
      border: '1px solid rgba(245, 158, 11, 0.35)',
    },
    success: {
      backgroundColor: 'rgba(16, 185, 129, 0.15)',
      color: colors.status.success,
      border: '1px solid rgba(16, 185, 129, 0.35)',
    },
    info: {
      backgroundColor: 'rgba(59, 130, 246, 0.15)',
      color: colors.status.info,
      border: '1px solid rgba(59, 130, 246, 0.35)',
    },
    neutral: {
      backgroundColor: 'rgba(148, 163, 184, 0.12)',
      color: colors.text.secondary,
      border: '1px solid rgba(148, 163, 184, 0.25)',
    },
  };

  const sizeStyles = {
    xs: { padding: '2px 6px', fontSize: '0.7rem' },
    sm: { padding: '3px 8px', fontSize: typography.fontSize.xs },
    md: { padding: '5px 12px', fontSize: typography.fontSize.sm },
  };

  return (
    <span
      className={`careon-badge ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        borderRadius: '9999px',
        fontWeight: typography.fontWeight.semibold,
        letterSpacing: '0.02em',
        textTransform: 'uppercase',
        lineHeight: 1,
        ...variantStyles[variant],
        ...sizeStyles[size],
        ...style,
      }}
    >
      {children}
    </span>
  );
}
