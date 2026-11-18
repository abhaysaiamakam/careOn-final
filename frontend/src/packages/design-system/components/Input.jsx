import React from 'react';
import { colors, typography } from '../tokens';

export default function Input({
  label,
  error = null,
  helperText = null,
  id,
  type = 'text',
  value,
  onChange,
  placeholder = '',
  required = false,
  disabled = false,
  style = {},
  inputStyle = {},
  ...rest
}) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px', ...style }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            color: colors.text.secondary,
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {label}
          {required && <span style={{ color: colors.status.critical }}>*</span>}
        </label>
      )}
      <input
        id={inputId}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '10px 14px',
          borderRadius: '8px',
          backgroundColor: colors.bg.surface,
          border: `1px solid ${error ? colors.status.critical : colors.border.medium}`,
          color: colors.text.primary,
          fontSize: typography.fontSize.sm,
          outline: 'none',
          boxSizing: 'border-box',
          transition: 'border-color 0.15s ease',
          ...inputStyle,
        }}
        {...rest}
      />
      {error && (
        <span style={{ fontSize: typography.fontSize.xs, color: colors.status.critical }}>
          {error}
        </span>
      )}
      {helperText && !error && (
        <span style={{ fontSize: typography.fontSize.xs, color: colors.text.muted }}>
          {helperText}
        </span>
      )}
    </div>
  );
}
