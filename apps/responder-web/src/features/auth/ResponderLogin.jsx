import React, { useState } from 'react';
import {
  ShieldAlert,
  Ambulance,
  Lock,
  Mail,
  AlertTriangle,
  Radio,
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

export function ResponderLogin({ onSuccess }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('m2_responder@careon.org');
  const [password, setPassword] = useState('responder123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const user = await login(email.trim(), password);

      // Verify responder role: only responder, paramedic, dispatcher, or admin allowed
      const allowedRoles = ['responder', 'paramedic', 'dispatcher', 'admin', 'super_admin'];
      if (!user || !allowedRoles.includes(user.role)) {
        setError('Access Denied: The Responder Field Operations application requires an authorized Paramedic or Field Responder credential. Civilian accounts are restricted.');
        return;
      }

      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify responder credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (roleEmail, rolePass = 'Password123!') => {
    setEmail(roleEmail);
    setPassword(rolePass);
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
        backgroundImage: 'radial-gradient(circle at 50% 25%, #1E293B 0%, #0F172A 100%)',
      }}
    >
      <div style={{ width: '100%', maxWidth: '420px' }}>
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '12px',
              backgroundColor: colors.secondary,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 24px rgba(217, 45, 58, 0.4)',
              marginBottom: '14px',
            }}
          >
            <Ambulance size={30} color="#FFFFFF" />
          </div>

          <h1
            style={{
              margin: '0 0 6px',
              fontSize: '1.4rem',
              fontWeight: typography.fontWeight.bold,
              color: '#FFFFFF',
              letterSpacing: '-0.02em',
            }}
          >
            CareOn Responder
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
            Field Operations & Clinical Handover
          </div>
        </div>

        {/* Login Card */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            padding: '28px 24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3)',
          }}
        >
          <div style={{ marginBottom: '18px' }}>
            <h2 style={{ margin: '0 0 4px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
              Responder Sign-In
            </h2>
            <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Authenticate to receive emergency assignments, log live telemetry, and record patient assessments.
            </p>
          </div>

          {error && (
            <div style={{ marginBottom: '16px' }}>
              <Alert variant="danger" icon={ShieldAlert}>
                {error}
              </Alert>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <Input
                label="Responder Email"
                required
                type="email"
                placeholder="paramedic@careon.org"
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
                  marginTop: '6px',
                  padding: '12px',
                  fontWeight: typography.fontWeight.bold,
                  backgroundColor: colors.secondary,
                }}
              >
                Sign In to Field Unit
              </Button>
            </div>
          </form>

          {/* Development Quick-Fill Gated behind import.meta.env.DEV */}
          {import.meta.env.DEV && (
            <div style={{ marginTop: '20px', borderTop: `1px solid ${colors.border}`, paddingTop: '14px' }}>
              <div style={{ fontSize: '11px', color: colors.textSecondary, marginBottom: '8px', textTransform: 'uppercase', fontWeight: 600 }}>
                Development Quick Access:
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => handleQuickFill('m2_responder@careon.org', 'responder123')}
                  style={{
                    flex: 1,
                    background: '#F1F5F9',
                    border: '1px solid #CBD5E1',
                    borderRadius: '6px',
                    padding: '6px 8px',
                    fontSize: '11px',
                    color: '#1E293B',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Primary Paramedic
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickFill('m2_dispatcher@careon.org', 'dispatcher123')}
                  style={{
                    flex: 1,
                    background: '#F1F5F9',
                    border: '1px solid #CBD5E1',
                    borderRadius: '6px',
                    padding: '6px 8px',
                    fontSize: '11px',
                    color: '#1E293B',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Field Dispatcher
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '11px', color: '#64748B' }}>
          Authorized EMS Personnel Only • CareOn Mobile Field v1.12
        </div>
      </div>
    </div>
  );
}
