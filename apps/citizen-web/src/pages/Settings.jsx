import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Bell,
  MapPin,
  Lock,
  Globe,
  LogOut,
  CheckCircle2,
  Download,
  AlertCircle,
  ExternalLink,
  Shield,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { PREFERRED_LANGUAGES } from '@careon/contracts';
import {
  isStandalone,
  promptInstall,
  requestPushPermission,
  subscribeInstallState,
} from '../services/pwa.js';
import { acquireCurrentLocation } from '../services/geolocation.js';
import { getCitizenProfile, updateCitizenProfile } from '@careon/api-client';
import { useAuth } from '@careon/auth';

export function Settings({ onNavigate }) {
  const { user, logout, isAuthenticated } = useAuth();
  const [canInstall, setCanInstall] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [pushStatus, setPushStatus] = useState('checking');
  const [locationStatus, setLocationStatus] = useState('Checking...');
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [consentDataSharing, setConsentDataSharing] = useState(true);
  const [savingMsg, setSavingMsg] = useState(null);

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

    // Load citizen profile settings
    getCitizenProfile()
      .then((prof) => {
        if (prof) {
          setSelectedLanguage(prof.preferred_language || 'en');
          setConsentDataSharing(prof.consent_data_sharing_emergency !== false);
        }
      })
      .catch(() => {});

    return unsub;
  }, []);

  const handleLanguageChange = async (newLang) => {
    setSelectedLanguage(newLang);
    try {
      await updateCitizenProfile({ preferred_language: newLang });
      setSavingMsg('Language preference updated.');
      setTimeout(() => setSavingMsg(null), 3000);
    } catch (e) {
      console.warn('Failed to save language:', e);
    }
  };

  const handleConsentToggle = async (checked) => {
    setConsentDataSharing(checked);
    try {
      await updateCitizenProfile({ consent_data_sharing_emergency: checked });
      setSavingMsg('Privacy preference updated.');
      setTimeout(() => setSavingMsg(null), 3000);
    } catch (e) {
      console.warn('Failed to save consent:', e);
    }
  };

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

  const handleInstallClick = async () => {
    const outcome = await promptInstall();
    if (outcome === 'accepted') {
      setCanInstall(false);
      setIsInstalled(true);
    }
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ margin: '0 0 6px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
        Safety & Application Settings
      </h1>
      <p style={{ margin: '0 0 24px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        Customize emergency alert channels, language, privacy consent, and device integration.
      </p>

      {savingMsg && (
        <div style={{ marginBottom: '16px' }}>
          <Alert variant="success" icon={CheckCircle2}>
            {savingMsg}
          </Alert>
        </div>
      )}

      {/* PWA App Installation Guidance */}
      <Card padding="md" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Smartphone size={20} color={colors.secondary} />
            </div>
            <div>
              <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                {isInstalled ? 'CareOn Emergency App Installed' : 'Install for Fast Home Screen Access'}
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                {isInstalled
                  ? 'Running as a standalone Progressive Web Application on your device.'
                  : 'Install CareOn to your home screen for rapid 1-tap SOS launching without a browser bar.'}
              </div>
            </div>
          </div>

          {!isInstalled && canInstall && (
            <Button size="sm" variant="primary" onClick={handleInstallClick} icon={Download}>
              Install App
            </Button>
          )}

          {isInstalled && (
            <Badge variant="success">Installed</Badge>
          )}
        </div>
      </Card>

      {/* Language Preference */}
      <Card padding="md" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Globe size={18} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Preferred Language
          </h2>
        </div>
        <p style={{ margin: '0 0 12px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
          Emergency instructions and dispatch notifications will be rendered in your chosen language.
        </p>

        <select
          value={selectedLanguage}
          onChange={(e) => handleLanguageChange(e.target.value)}
          style={{
            width: '100%',
            maxWidth: '320px',
            padding: '10px 12px',
            borderRadius: '6px',
            border: `1px solid ${colors.border}`,
            fontSize: typography.fontSize.sm,
            background: '#FFFFFF',
          }}
        >
          {PREFERRED_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label} ({lang.native})
            </option>
          ))}
        </select>
      </Card>

      {/* Device Permissions: GPS & Notifications */}
      <Card padding="md" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
        <h2 style={{ margin: '0 0 16px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
          Device Emergency Capabilities
        </h2>

        {/* GPS Permission */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '14px', borderBottom: `1px solid ${colors.border}`, marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <MapPin size={18} color={colors.secondary} />
            <div>
              <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, color: colors.textPrimary }}>
                High-Accuracy GPS Location
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Status: <strong>{locationStatus}</strong>
              </div>
            </div>
          </div>
          <Button size="xs" variant="outline" onClick={handleTestGps}>
            Test GPS Accuracy
          </Button>
        </div>

        {/* Notification Permission */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Bell size={18} color={colors.secondary} />
            <div>
              <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, color: colors.textPrimary }}>
                Emergency Push Notifications
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Real-time ambulance dispatch, ETA, and triage updates. Status: <strong>{pushStatus}</strong>
              </div>
            </div>
          </div>

          {pushStatus !== 'granted' && (
            <Button size="xs" variant="primary" onClick={handleRequestPush}>
              Enable Notifications
            </Button>
          )}
          {pushStatus === 'granted' && (
            <Badge variant="success">Enabled</Badge>
          )}
        </div>
      </Card>

      {/* Privacy & Emergency Data Sharing */}
      <Card padding="md" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Lock size={18} color={colors.secondary} />
          <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Privacy & Emergency Data Sharing
          </h2>
        </div>
        <p style={{ margin: '0 0 14px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
          Control how your registered home address and health notes are accessed during missions.
        </p>

        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: typography.fontSize.sm, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={consentDataSharing}
            onChange={(e) => handleConsentToggle(e.target.checked)}
            style={{ width: '16px', height: '16px', marginTop: '3px', accentColor: colors.secondary }}
          />
          <div>
            <span style={{ fontWeight: typography.fontWeight.medium, color: colors.textPrimary }}>
              Share profile with verified responders during active emergencies
            </span>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
              When enabled, paramedics assigned to your emergency will see your blood group, allergies, address notes, and primary ICE contact.
            </div>
          </div>
        </label>
      </Card>

      {/* Account & Session */}
      {isAuthenticated && (
        <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                Account Session ({user?.name || user?.email || 'Logged In'})
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Role: Citizen Civilian • Safe logout terminates session tokens
              </div>
            </div>

            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                logout();
                onNavigate('/login');
              }}
              icon={LogOut}
            >
              Sign Out
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
