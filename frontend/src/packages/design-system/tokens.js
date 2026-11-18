/**
 * CareOn Design System — Tokens & Theming.
 * 
 * Cinematic Emergency & Operations Palette:
 * - Slate/Navy deep backgrounds with subtle glassmorphic blur
 * - High-contrast emergency accents: Crimson/Coral (Critical), Amber (Warning), Emerald (Active/Resolved), Cobalt (Information)
 * - Accessible contrast ratios for field mobile conditions & dark-mode dispatcher rooms
 */

export const colors = {
  // Backgrounds
  bg: {
    base: '#0a0e17',
    surface: '#111827',
    elevated: '#1f2937',
    glass: 'rgba(17, 24, 39, 0.85)',
    glassHover: 'rgba(31, 41, 55, 0.9)',
    overlay: 'rgba(5, 8, 15, 0.75)',
  },
  // Text
  text: {
    primary: '#f8fafc',
    secondary: '#94a3b8',
    muted: '#64748b',
    inverse: '#0f172a',
  },
  // Emergency Accents
  status: {
    critical: '#ef4444',     // Critical / Emergency
    criticalGlow: 'rgba(239, 68, 68, 0.35)',
    warning: '#f59e0b',      // High priority / Caution
    warningGlow: 'rgba(245, 158, 11, 0.35)',
    success: '#10b981',      // Resolved / Available / Healthy
    successGlow: 'rgba(16, 185, 129, 0.35)',
    info: '#3b82f6',         // In transit / En route / Info
    infoGlow: 'rgba(59, 130, 246, 0.35)',
  },
  // Borders
  border: {
    subtle: 'rgba(255, 255, 255, 0.08)',
    medium: 'rgba(255, 255, 255, 0.16)',
    active: '#3b82f6',
    danger: '#ef4444',
  },
  // Brand
  brand: {
    primary: '#3b82f6',
    primaryHover: '#2563eb',
    secondary: '#8b5cf6',
    accent: '#06b6d4',
  },
};

export const typography = {
  fontFamily: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
  fontSize: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
    '4xl': '2.25rem',
  },
  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800',
  },
};

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
};

export const shadows = {
  card: '0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 0 1px 1px rgba(255, 255, 255, 0.05)',
  emergency: '0 0 25px rgba(239, 68, 68, 0.45)',
  glow: '0 0 20px rgba(59, 130, 246, 0.3)',
};
