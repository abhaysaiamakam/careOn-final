import React from 'react';
import { colors, radii, typography } from '../tokens.js';

export function Badge({
  children,
  variant = 'neutral', // 'emergency' | 'critical' | 'success' | 'warning' | 'info' | 'neutral'
  size = 'md',        // 'sm' | 'md'
  className = '',
  style = {},
  ...props
}) {
  const variantStyles = {
    emergency: {
      backgroundColor: colors.badgeDangerBg,
      color: colors.badgeDangerText,
      borderColor: colors.badgeDangerBorder,
    },
    critical: {
      backgroundColor: colors.badgeDangerBg,
      color: colors.badgeDangerText,
      borderColor: colors.badgeDangerBorder,
    },
    success: {
      backgroundColor: colors.badgeSuccessBg,
      color: colors.badgeSuccessText,
      borderColor: colors.badgeSuccessBorder,
    },
    warning: {
      backgroundColor: colors.badgeWarningBg,
      color: colors.badgeWarningText,
      borderColor: colors.badgeWarningBorder,
    },
    info: {
      backgroundColor: '#EFF6FF',
      color: '#1D4ED8',
      borderColor: '#BFDBFE',
    },
    neutral: {
      backgroundColor: colors.badgeNeutralBg,
      color: colors.badgeNeutralText,
      borderColor: colors.badgeNeutralBorder,
    },
  };

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: size === 'sm' ? '2px 8px' : '4px 10px',
    fontSize: size === 'sm' ? typography.fontSize.xs : typography.fontSize.sm,
    fontWeight: typography.fontWeight.medium,
    lineHeight: '1.25',
    borderRadius: radii.full,
    border: '1px solid',
    fontFamily: typography.fontFamily.sans,
    whiteSpace: 'nowrap',
    ...(variantStyles[variant] || variantStyles.neutral),
    ...style,
  };

  return (
    <span style={badgeStyle} className={`careon-badge ${className}`} {...props}>
      {children}
    </span>
  );
}
