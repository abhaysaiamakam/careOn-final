import React from 'react';
import { colors, radii, typography } from '../tokens.js';

export function Alert({
  variant = 'info', // 'danger' | 'warning' | 'success' | 'info'
  title,
  children,
  icon: Icon,
  className = '',
  style = {},
  action,
}) {
  const variantStyles = {
    danger: {
      backgroundColor: '#FEF2F2',
      borderColor: '#FCA5A5',
      textColor: colors.secondary,
      titleColor: colors.secondary,
    },
    warning: {
      backgroundColor: '#FFFBEB',
      borderColor: '#FDE68A',
      textColor: '#92400E',
      titleColor: '#78350F',
    },
    success: {
      backgroundColor: '#ECFDF5',
      borderColor: '#A7F3D0',
      textColor: '#065F46',
      titleColor: colors.success,
    },
    info: {
      backgroundColor: '#F9FAFB',
      borderColor: colors.border,
      textColor: colors.textSecondary,
      titleColor: colors.textPrimary,
    },
  };

  const current = variantStyles[variant] || variantStyles.info;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '12px 16px',
        borderRadius: radii.md,
        backgroundColor: current.backgroundColor,
        border: `1px solid ${current.borderColor}`,
        fontFamily: typography.fontFamily.sans,
        fontSize: typography.fontSize.sm,
        color: current.textColor,
        marginBottom: '16px',
        ...style,
      }}
      className={`careon-alert ${className}`}
    >
      {Icon && (
        <div style={{ flexShrink: 0, marginTop: '2px', color: current.titleColor }}>
          <Icon size={18} />
        </div>
      )}
      <div style={{ flex: 1 }}>
        {title && (
          <div style={{ fontWeight: typography.fontWeight.semibold, color: current.titleColor, marginBottom: '2px' }}>
            {title}
          </div>
        )}
        <div>{children}</div>
      </div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  );
}
