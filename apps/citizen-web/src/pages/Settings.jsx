import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Bell,
  MapPin,
  Database,
  Trash2,
  CheckCircle2,
  Download,
  AlertTriangle,
  LogOut,
  RefreshCw,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import {
  isStandalone,
  promptInstall,
  requestPushPermission,
  subscribeInstallState,
} from '../services/pwa.js';
import { acquireCurrentLocation } from '../services/geolocation.js';
import { useAuth } from '@careon/auth';

export function Settings({ onNavigate }) {
  const { user, logout, isAuthenticated } = useAuth();
  const [canInstall, setCanInstall] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [pushStatus, setPushStatus] = useState('checking');
  const [locationStatus, setLocationStatus] = useState('Checking...');
  const [cacheCleared, setCacheCleared] = useState(false);

  useEffect(() => {
    setIsInstalled(isStandalone());
    const unsub = subscribeInstallState((installable) => setCanInstall(installable));

    if ('Notification' in window) {
      setPushStatus(Notification.permission);
    } else {
      setPushStatus('unsupported');
    }

    if ('geolocation' in navigator) {
      if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then((result) => {
          setLocationStatus(result.state);
          result.onchange = () => setLocationStatus(result.state);
        }).catch(() => {
          setLocationStatus('available');
        });
      } else {
        setLocationStatus('available');
      }
    } else {
      setLocationStatus('unsupported');
    }

    return unsub;
  }, []);

  const handleRequestPush = async () => {
    const res = await requestPushPermission();
    setPushStatus(res.permission);
  };

  const handleTestGps = async () => {
    setLocationStatus('Acquiring...');
    try {
      const pos = await acquireCurrentLocation();
      setLocationStatus(`Granted (Accuracy ±${pos.accuracy}m)`);
    } catch (e) {
      setLocationStatus(`Denied or unavailable: ${e.message}`);
    }
  };

  const handleClearAppCache = async () => {
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map((n) => caches.delete(n)));
      setCacheCleared(true);
      setTimeout(() => setCacheCleared(false), 3000);
    }
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
        Application Settings & PWA
      </h1>
      <p style={{ margin: '0 0 24px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        Configure installation, background alerts, GPS permissions, and local storage.
      </p>

      {cacheCleared && (
        <Alert variant="success" icon={CheckCircle2}>
          Application cache was cleared. Fresh assets will be downloaded on next reload.
        </Alert>
      )}

      {/* PWA & Mobile Installation */}
      <Card padding="lg" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <Smartphone size={20} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
            Progressive Web App (PWA) Status
          </h2>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
              Installation Mode
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              {isInstalled ? 'Running as standalone installed application.' : 'Running inside web browser.'}
            </div>
          </div>
          <Badge variant={isInstalled ? 'success' : 'neutral'}>
            {isInstalled ? 'Installed / Standalone' : 'Browser Web App'}
          </Badge>
        </div>

        {!isInstalled && (
          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '12px', marginTop: '12px' }}>
            {canInstall ? (
              <Button size="sm" variant="secondary-red" onClick={promptInstall} icon={Download}>
                Install CareOn to Home Screen
              </Button>
            ) : (
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textMuted }}>
                To install, use Chrome / Edge "Install App" or Safari "Add to Home Screen".
              </span>
            )}
          </div>
        )}
      </Card>

      {/* Push Notifications */}
      <Card padding="lg" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <Bell size={20} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
            Emergency Notifications
          </h2>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
              Web Push Notification Permission
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Permits dispatch alerts and ambulance arrival notices.
            </div>
          </div>
          <Badge variant={pushStatus === 'granted' ? 'success' : pushStatus === 'denied' ? 'emergency' : 'warning'}>
            {pushStatus}
          </Badge>
        </div>

        {pushStatus !== 'granted' && pushStatus !== 'unsupported' && (
          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '12px' }}>
            <Button size="sm" variant="secondary" onClick={handleRequestPush}>
              Enable Notifications
            </Button>
          </div>
        )}
      </Card>

      {/* Geolocation Permissions */}
      <Card padding="lg" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <MapPin size={20} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
            GPS & Geolocation Status
          </h2>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
              Browser Location Permission
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Current state: {locationStatus}
            </div>
          </div>
          <Button size="sm" variant="secondary" onClick={handleTestGps}>
            Test GPS Acquisition
          </Button>
        </div>
      </Card>

      {/* Offline Storage & Cache */}
      <Card padding="lg" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <Database size={20} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
            Offline Storage & Cache
          </h2>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
              Local Emergency Drafts
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Manage saved reports waiting for network connectivity.
            </div>
          </div>
          <Button size="sm" variant="secondary" onClick={() => onNavigate('/drafts')}>
            View Drafts
          </Button>
        </div>

        <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
              Service Worker Asset Cache
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Purge cached HTML, scripts, and CSS.
            </div>
          </div>
          <Button size="sm" variant="tertiary" onClick={handleClearAppCache} icon={Trash2}>
            Clear Cache
          </Button>
        </div>
      </Card>

      {/* Account Logout */}
      {isAuthenticated && (
        <Card padding="md" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm }}>
              Signed in as {user?.email}
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Role: {user?.role}
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={logout} icon={LogOut}>
            Sign Out
          </Button>
        </Card>
      )}
    </div>
  );
}
