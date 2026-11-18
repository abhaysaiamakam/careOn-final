import React from 'react';
import { colors, shadows } from '../tokens';

export default function Card({
  children,
  header = null,
  footer = null,
  style = {},
  className = '',
  glowing = false,
  glowColor = shadows.card,
  onClick = null,
}) {
  return (
    <div
      onClick={onClick}
      className={`careon-card ${className}`}
      style={{
        backgroundColor: colors.bg.surface,
        border: `1px solid ${colors.border.subtle}`,
        borderRadius: '12px',
        boxShadow: glowing ? `0 0 20px ${glowColor}` : shadows.card,
        backdropFilter: 'blur(12px)',
        overflow: 'hidden',
        transition: 'border-color 0.2s ease, transform 0.2s ease',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      {header && (
        <div style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${colors.border.subtle}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {header}
        </div>
      )}
      <div style={{ padding: '20px' }}>
        {children}
      </div>
      {footer && (
        <div style={{
          padding: '12px 20px',
          borderTop: `1px solid ${colors.border.subtle}`,
          backgroundColor: 'rgba(0,0,0,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '12px',
        }}>
          {footer}
        </div>
      )}
    </div>
  );
}
