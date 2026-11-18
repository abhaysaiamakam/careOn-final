import React from 'react';
import { colors, typography } from '../tokens';

export default function Button({
  children,
  variant = 'primary', // 'primary' | 'danger' | 'secondary' | 'outline' | 'ghost'
  size = 'md',        // 'sm' | 'md' | 'lg'
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  style = {},
  className = '',
  icon: Icon = null,
  ...rest
}) {
  const sizeStyles = {
    sm: { padding: '6px 12px', fontSize: typography.fontSize.xs, height: '32px' },
    md: { padding: '8px 16px', fontSize: typography.fontSize.sm, height: '40px' },
    lg: { padding: '12px 24px', fontSize: typography.fontSize.base, height: '48px' },
  };

  const variantStyles = {
    primary: {
      backgroundColor: colors.brand.primary,
      color: '#ffffff',
      border: 'none',
      boxShadow: '0 2px 8px rgba(59, 130, 246, 0.4)',
    },
    danger: {
      backgroundColor: colors.status.critical,
      color: '#ffffff',
      border: 'none',
      boxShadow: '0 2px 8px rgba(239, 68, 68, 0.4)',
    },
    secondary: {
      backgroundColor: colors.bg.elevated,
      color: colors.text.primary,
      border: `1px solid ${colors.border.subtle}`,
    },
    outline: {
      backgroundColor: 'transparent',
      color: colors.text.primary,
      border: `1px solid ${colors.border.medium}`,
    },
    ghost: {
      backgroundColor: 'transparent',
      color: colors.text.secondary,
      border: 'none',
    },
  };

  const computedStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    borderRadius: '8px',
    fontWeight: typography.fontWeight.semibold,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    transition: 'all 0.18s ease-in-out',
    fontFamily: typography.fontFamily.sans,
    textDecoration: 'none',
    ...sizeStyles[size],
    ...variantStyles[variant],
    ...style,
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      style={computedStyle}
      className={`careon-btn ${className}`}
      {...rest}
    >
      {loading && (
        <span style={{
          display: 'inline-block',
          width: '14px',
          height: '14px',
          border: '2px solid rgba(255, 255, 255, 0.3)',
          borderTopColor: '#ffffff',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
      )}
      {Icon && !loading && <Icon size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />}
      {children}
    </button>
  );
}
