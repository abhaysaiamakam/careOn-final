import React from 'react';
import { colors, radii, shadows, typography } from '../tokens.js';

export function Card({
  children,
  variant = 'default', // 'default' | 'subtle' | 'emergency' | 'outlined'
  padding = 'md',      // 'none' | 'sm' | 'md' | 'lg'
  onClick,
  className = '',
  style = {},
  ...props
}) {
  const paddingValues = {
    none: '0',
    sm: '12px',
    md: '20px',
    lg: '28px',
  };

  const isClickable = Boolean(onClick);

  const variantStyles = {
    default: {
      backgroundColor: colors.surface,
      border: `1px solid ${colors.border}`,
      boxShadow: shadows.subtle,
    },
    subtle: {
      backgroundColor: colors.surfaceSubtle,
      border: `1px solid ${colors.border}`,
      boxShadow: shadows.none,
    },
    emergency: {
      backgroundColor: colors.surface,
      border: `1px solid ${colors.secondary}`,
      borderLeftWidth: '4px',
      boxShadow: shadows.emergency,
    },
    outlined: {
      backgroundColor: colors.surface,
      border: `1px solid ${colors.border}`,
      boxShadow: shadows.none,
    },
  };

  const cardStyle = {
    borderRadius: radii.md,
    padding: paddingValues[padding],
    boxSizing: 'border-box',
    fontFamily: typography.fontFamily.sans,
    cursor: isClickable ? 'pointer' : 'default',
    transition: isClickable ? 'border-color 0.15s ease, box-shadow 0.15s ease' : 'none',
    ...(variantStyles[variant] || variantStyles.default),
    ...style,
  };

  return (
    <div
      onClick={onClick}
      style={cardStyle}
      className={`careon-card ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
