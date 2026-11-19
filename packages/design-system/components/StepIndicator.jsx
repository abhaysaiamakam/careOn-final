import React from 'react';
import { colors, radii, typography } from '../tokens.js';

export function StepIndicator({
  steps = [],
  currentStep = 0,
  onStepClick,
  className = '',
  style = {},
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
        padding: '12px 0 20px',
        borderBottom: `1px solid ${colors.border}`,
        marginBottom: '24px',
        fontFamily: typography.fontFamily.sans,
        overflowX: 'auto',
        ...style,
      }}
      className={`careon-step-indicator ${className}`}
    >
      {steps.map((step, idx) => {
        const isCurrent = idx === currentStep;
        const isPast = idx < currentStep;
        const isFuture = idx > currentStep;

        return (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'center',
              flex: 1,
              minWidth: 'fit-content',
              cursor: isPast && onStepClick ? 'pointer' : 'default',
            }}
            onClick={() => isPast && onStepClick && onStepClick(idx)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: radii.full,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: typography.fontSize.sm,
                  fontWeight: typography.fontWeight.semibold,
                  backgroundColor: isCurrent
                    ? colors.secondary
                    : isPast
                    ? colors.textPrimary
                    : colors.surfaceSubtle,
                  color: isCurrent || isPast ? colors.primary : colors.textSecondary,
                  border: isFuture ? `1px solid ${colors.border}` : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                {isPast ? '✓' : idx + 1}
              </div>
              <span
                style={{
                  fontSize: typography.fontSize.sm,
                  fontWeight: isCurrent ? typography.fontWeight.semibold : typography.fontWeight.normal,
                  color: isCurrent
                    ? colors.secondary
                    : isPast
                    ? colors.textPrimary
                    : colors.textSecondary,
                  whiteSpace: 'nowrap',
                }}
              >
                {step.title || step}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: '2px',
                  backgroundColor: isPast ? colors.textPrimary : colors.border,
                  margin: '0 12px',
                  minWidth: '16px',
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
