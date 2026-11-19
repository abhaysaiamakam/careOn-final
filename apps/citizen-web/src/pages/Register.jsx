import React, { useState } from 'react';
import { UserPlus, ArrowRight, AlertTriangle, ShieldCheck } from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { useAuth } from '@careon/auth';

export function Register({ onNavigate }) {
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        password,
        confirm_password: confirmPassword,
        role: 'user',
      });
      // Route new citizens immediately to first-time safety onboarding wizard
      onNavigate('/onboarding');
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '480px', margin: '40px auto', padding: '0 16px' }}>
      {/* Emergency Bypass Notice */}
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
            Need immediate help?
          </span>
        </div>
        <Button size="xs" variant="primary" onClick={() => onNavigate('/report')}>
          Report SOS Now
        </Button>
      </div>

      <Card padding="lg">
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <h1 style={{ margin: '0 0 6px', fontSize: '1.35rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Create Citizen Safety Account
          </h1>
          <p style={{ margin: 0, fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Register to keep callback records and emergency ICE contacts organized.
          </p>
        </div>

        {error && (
          <Alert variant="danger" style={{ marginBottom: '16px' }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <Input
            label="Full Name"
            required
            placeholder="e.g. Ramesh Kumar"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Input
            label="Email Address"
            required
            type="email"
            placeholder="ramesh@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Input
            label="Mobile Phone Number"
            required
            type="tel"
            placeholder="e.g. 9845012345"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            helperText="Responders and dispatchers will call this number during emergencies."
          />

          <Input
            label="Password"
            required
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Input
            label="Confirm Password"
            required
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />

          <Button
            type="submit"
            variant="primary"
            fullWidth
            loading={loading}
            icon={UserPlus}
            style={{ marginTop: '12px', marginBottom: '16px' }}
          >
            Create Account & Continue
          </Button>
        </form>

        <div style={{ textAlign: 'center', borderTop: `1px solid ${colors.border}`, paddingTop: '16px' }}>
          <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Already have an account?{' '}
            <button
              onClick={() => onNavigate('/login')}
              style={{
                background: 'none',
                border: 'none',
                color: colors.secondary,
                fontWeight: typography.fontWeight.bold,
                cursor: 'pointer',
                padding: 0,
              }}
            >
              Sign in here
            </button>
          </span>
        </div>
      </Card>
    </div>
  );
}
