import React, { useState } from 'react';
import {
  ShieldAlert,
  Radio,
  Lock,
  Mail,
  ArrowRight,
  AlertTriangle,
  Activity,
  CheckCircle,
} from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { useAuth } from '@careon/auth';

export function CommandLogin({ onSuccess }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('dispatcher@careon.org');
  const [password, setPassword] = useState('Password123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const user = await login(email.trim(), password);

      // Enforce role security: only admin / dispatcher permitted
      if (!user || (user.role !== 'admin' && user.role !== 'super_admin' && user.role !== 'dispatcher')) {
        setError('Access Denied: The Command Centre requires authorized Dispatcher or Administrator credentials. Civilian accounts are restricted.');
        return;
      }

      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify dispatcher credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (roleEmail) => {
    setEmail(roleEmail);
    setPassword('Password123!');
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0F172A',
        padding: '24px 16px',
        backgroundImage: 'radial-gradient(circle at 50% 30%, #1E293B 0%, #0F172A 100%)',
      }}
    >
      <div style={{ width: '100%', maxWidth: '440px' }}>
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div
            style={{
              width: '54px',
              height: '54px',
              borderRadius: '12px',
              backgroundColor: colors.secondary,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 24px rgba(217, 45, 58, 0.4)',
              marginBottom: '16px',
            }}
          >
            <Radio size={28} color="#FFFFFF" />
          </div>

          <h1
            style={{
              margin: '0 0 6px',
              fontSize: '1.5rem',
              fontWeight: typography.fontWeight.bold,
              color: '#FFFFFF',
              letterSpacing: '-0.02em',
            }}
          >
            CareOn Command
          </h1>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: typography.fontSize.xs,
              color: '#94A3B8',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              fontWeight: typography.fontWeight.semibold,
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10B981' }} />
            Emergency Operations Command Centre
          </div>
        </div>

        {/* Login Card */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            padding: '32px 28px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
          }}
        >
          <div style={{ marginBottom: '20px' }}>
            <h2 style={{ margin: '0 0 4px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
              Operator Authentication
            </h2>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Sign in with your authorized dispatcher ID to access the live operations queue, spatial fleet tracking, and hospital coordination.
            </p>
          </div>

          {error && (
            <div style={{ marginBottom: '18px' }}>
              <Alert variant="danger" icon={ShieldAlert}>
                {error}
              </Alert>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <Input
                label="Dispatcher Email"
                required
                type="email"
                placeholder="dispatcher@careon.org"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <Input
                label="Security Password"
                required
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />

              <Button
                type="submit"
                variant="primary"
                fullWidth
                loading={loading}
                icon={Lock}
                style={{
                  marginTop: '8px',
                  padding: '12px',
                  fontWeight: typography.fontWeight.bold,
                  backgroundColor: colors.secondary,
                }}
              >
                Enter Command Console
              </Button>
            </div>
          </form>

          {/* Preset Dispatcher Identity Quick Access (Development Environment Only) */}
          {import.meta.env.DEV && (
            <div style={{ marginTop: '24px', borderTop: `1px solid ${colors.border}`, paddingTop: '16px' }}>
              <div style={{ fontSize: '11px', color: colors.textSecondary, marginBottom: '8px', textTransform: 'uppercase', fontWeight: typography.fontWeight.semibold }}>
                Development Quick Access:
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => handleQuickFill('dispatcher@careon.org')}
                  style={{
                    background: '#F1F5F9',
                    border: '1px solid #CBD5E1',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    fontSize: '11px',
                    color: '#1E293B',
                    cursor: 'pointer',
                    fontWeight: typography.fontWeight.medium,
                  }}
                >
                  Lead Dispatcher (Mysuru)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickFill('admin@careon.org')}
                  style={{
                    background: '#F1F5F9',
                    border: '1px solid #CBD5E1',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    fontSize: '11px',
                    color: '#1E293B',
                    cursor: 'pointer',
                    fontWeight: typography.fontWeight.medium,
                  }}
                >
                  Operations Administrator
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer Notice */}
        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '11px', color: '#64748B' }}>
          Restricted Government & Regional Emergency Response Network • CareOn v1.11
        </div>
      </div>
    </div>
  );
}
