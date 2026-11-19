import React from 'react';
import { colors, radii, typography } from '../tokens.js';

export function Button({
  children,
  variant = 'primary', // 'primary' | 'secondary' | 'secondary-red' | 'tertiary' | 'danger'
  size = 'md',        // 'sm' | 'md' | 'lg'
  disabled = false,
  loading = false,
  fullWidth = false,
  icon: Icon,
  iconPosition = 'left',
  onClick,
  type = 'button',
  className = '',
  style = {},
  ...props
}) {
  const baseStyle = {
    display: fullWidth ? 'flex' : 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    width: fullWidth ? '100%' : 'auto',
    fontFamily: typography.fontFamily.sans,
    fontWeight: typography.fontWeight.medium,
    borderRadius: radii.md,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    transition: 'all 0.15s ease',
    textDecoration: 'none',
    boxSizing: 'border-box',
    border: '1px solid transparent',
  };

  const sizeStyles = {
    sm: {
      padding: '6px 12px',
      fontSize: typography.fontSize.sm,
      lineHeight: '1.25',
    },
    md: {
      padding: '10px 18px',
      fontSize: typography.fontSize.base,
      lineHeight: '1.5',
    },
    lg: {
      padding: '14px 24px',
      fontSize: typography.fontSize.lg,
      lineHeight: '1.5',
      fontWeight: typography.fontWeight.semibold,
    },
  };

  const variantStyles = {
    primary: {
      backgroundColor: colors.secondary,
      borderColor: colors.secondary,
      color: colors.primary,
    },
    secondary: {
      backgroundColor: colors.surface,
      borderColor: colors.border,
      color: colors.textPrimary,
    },
    'secondary-red': {
      backgroundColor: colors.surface,
      borderColor: colors.secondary,
      color: colors.secondary,
    },
    tertiary: {
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      color: colors.textSecondary,
      paddingLeft: '8px',
      paddingRight: '8px',
    },
    'tertiary-red': {
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      color: colors.secondary,
      paddingLeft: '8px',
      paddingRight: '8px',
    },
    danger: {
      backgroundColor: colors.secondary,
      borderColor: colors.secondary,
      color: colors.primary,
    },
  };

  const computedStyle = {
    ...baseStyle,
    ...sizeStyles[size],
    ...(variantStyles[variant] || variantStyles.primary),
    ...style,
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      style={computedStyle}
      className={`careon-btn ${className}`}
      {...props}
    >
      {loading ? (
        <span style={{ display: 'inline-block', width: '16px', height: '16px', border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} />
      ) : (
        <>
          {Icon && iconPosition === 'left' && <Icon size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />}
          {children}
          {Icon && iconPosition === 'right' && <Icon size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />}
        </>
      )}
    </button>
  );
}
