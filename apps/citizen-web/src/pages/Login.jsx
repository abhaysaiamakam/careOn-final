import React, { useState } from 'react';
import { LogIn, ArrowRight, ShieldCheck, Heart, AlertTriangle } from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { getCitizenProfile } from '@careon/api-client';
import { useAuth } from '@careon/auth';

export function Login({ onNavigate }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('citizen@careon.org');
  const [password, setPassword] = useState('Password123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email.trim(), password);

      // Check onboarding status
      try {
        const prof = await getCitizenProfile();
        if (prof && !prof.onboarding_completed) {
          onNavigate('/onboarding');
          return;
        }
      } catch (profErr) {
        console.warn('Could not check onboarding status:', profErr);
      }

      onNavigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '440px', margin: '40px auto', padding: '0 16px' }}>
      {/* Emergency SOS Bypass Banner */}
      <div
        style={{
          background: '#FEF2F2',
          border: `1px solid ${colors.secondary}`,
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={18} color={colors.secondary} />
          <span style={{ fontSize: typography.fontSize.xs, color: '#991B1B', fontWeight: typography.fontWeight.semibold }}>
            Experiencing a live emergency?
          </span>
        </div>
        <Button size="xs" variant="primary" onClick={() => onNavigate('/report')}>
          Report SOS Now
        </Button>
      </div>

      <Card padding="lg">
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '8px',
              backgroundColor: colors.secondary,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: colors.primary,
              fontWeight: typography.fontWeight.bold,
              fontSize: '24px',
              marginBottom: '12px',
            }}
          >
            +
          </div>
          <h1 style={{ margin: '0 0 6px', fontSize: '1.35rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Citizen Sign In
          </h1>
          <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Access emergency tracking, history, and family ICE contacts.
          </p>
        </div>

        {error && (
          <Alert variant="danger" style={{ marginBottom: '16px' }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <Input
            label="Email Address"
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Input
            label="Password"
            required
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button
            type="submit"
            variant="primary"
            fullWidth
            loading={loading}
            icon={LogIn}
            style={{ marginTop: '8px', marginBottom: '16px' }}
          >
            Sign In
          </Button>
        </form>

        <div style={{ textAlign: 'center', borderTop: `1px solid ${colors.border}`, paddingTop: '16px' }}>
          <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Need a citizen account?{' '}
            <button
              onClick={() => onNavigate('/register')}
              style={{
                background: 'none',
                border: 'none',
                color: colors.secondary,
                fontWeight: typography.fontWeight.bold,
                cursor: 'pointer',
                padding: 0,
              }}
            >
              Register here
            </button>
          </span>
        </div>
      </Card>
    </div>
  );
}
