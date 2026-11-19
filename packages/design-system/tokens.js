/**
 * CareOn Design System — Centralized Design Tokens
 * Visual Identity: Simple, Minimalist, Premium White + Red
 *
 * Core Principles:
 * - White dominant (#FFFFFF)
 * - Emergency Red (#D92D3A) for primary emergency actions, highlights, critical states
 * - Charcoal (#222222) for primary typography
 * - Grey (#6B7280) for secondary typography
 * - Light Grey (#F5F5F5) for subtle section separation
 * - Thin Grey borders (#E5E7EB)
 * - Muted Green (#16845B) for success
 * - Muted Amber (#D99022) for warning
 */

export const colors = {
  // Surfaces & Backgrounds
  primary: '#FFFFFF',
  secondary: '#D92D3A',
  background: '#FFFFFF',
  surface: '#FFFFFF',
  surfaceSubtle: '#F5F5F5',
  surfaceHover: '#F9FAFB',

  // Typography
  textPrimary: '#222222',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  textInverse: '#FFFFFF',
  textRed: '#D92D3A',

  // Borders & Dividers
  border: '#E5E7EB',
  borderDark: '#D1D5DB',
  borderRed: '#D92D3A',

  // Semantic Status
  emergency: '#D92D3A',
  critical: '#D92D3A',
  success: '#16845B',
  warning: '#D99022',
  info: '#374151',

  // Semantic Badges
  badgeSuccessBg: '#ECFDF5',
  badgeSuccessText: '#16845B',
  badgeSuccessBorder: '#A7F3D0',

  badgeWarningBg: '#FFFBEB',
  badgeWarningText: '#B45309',
  badgeWarningBorder: '#FDE68A',

  badgeDangerBg: '#FEF2F2',
  badgeDangerText: '#D92D3A',
  badgeDangerBorder: '#FECACA',

  badgeNeutralBg: '#F3F4F6',
  badgeNeutralText: '#374151',
  badgeNeutralBorder: '#E5E7EB',
};

export const typography = {
  fontFamily: {
    sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
  fontSize: {
    xs: '0.75rem',    // 12px
    sm: '0.875rem',   // 14px
    base: '1rem',     // 16px
    lg: '1.125rem',   // 18px
    xl: '1.25rem',    // 20px
    '2xl': '1.5rem',  // 24px
    '3xl': '1.875rem',// 30px
    '4xl': '2.25rem', // 36px
  },
  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
  lineHeight: {
    tight: '1.25',
    normal: '1.5',
    relaxed: '1.625',
  },
};

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
  '3xl': '64px',
};

export const radii = {
  sm: '4px',
  md: '6px',
  lg: '8px',
  full: '9999px',
};

export const shadows = {
  none: 'none',
  subtle: '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)',
  card: '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04)',
  emergency: '0 4px 14px 0 rgba(217, 45, 58, 0.25)',
};
