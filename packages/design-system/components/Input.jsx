import React from 'react';
import { colors, radii, typography } from '../tokens.js';

export function Input({
  label,
  error,
  helperText,
  required = false,
  fullWidth = true,
  className = '',
  style = {},
  id,
  type = 'text',
  as = 'input', // 'input' | 'textarea' | 'select'
  children,
  ...props
}) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  const containerStyle = {
    display: fullWidth ? 'flex' : 'inline-flex',
    flexDirection: 'column',
    gap: '6px',
    marginBottom: '16px',
    width: fullWidth ? '100%' : 'auto',
    fontFamily: typography.fontFamily.sans,
  };

  const labelStyle = {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.medium,
    color: colors.textPrimary,
  };

  const fieldStyle = {
    width: '100%',
    padding: '10px 14px',
    fontSize: typography.fontSize.base,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    border: `1px solid ${error ? colors.secondary : colors.border}`,
    borderRadius: radii.md,
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: typography.fontFamily.sans,
    transition: 'border-color 0.15s ease',
    ...(as === 'textarea' ? { minHeight: '90px', resize: 'vertical' } : {}),
    ...style,
  };

  const Component = as;

  return (
    <div style={containerStyle} className={`careon-field-group ${className}`}>
      {label && (
        <label htmlFor={inputId} style={labelStyle}>
          {label} {required && <span style={{ color: colors.secondary }}>*</span>}
        </label>
      )}
      <Component
        id={inputId}
        type={as === 'input' ? type : undefined}
        style={fieldStyle}
        {...props}
      >
        {children}
      </Component>
      {error && (
        <span style={{ fontSize: typography.fontSize.xs, color: colors.secondary, fontWeight: typography.fontWeight.medium }}>
          {error}
        </span>
      )}
      {!error && helperText && (
        <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
          {helperText}
        </span>
      )}
    </div>
  );
}
