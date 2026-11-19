import React, { useState, useEffect } from 'react';
import { Download, X, Smartphone, Info } from 'lucide-react';
import { Button, Card, typography, colors } from '@careon/design-system';
import { subscribeInstallState, promptInstall, isStandalone } from '../services/pwa.js';

export function InstallPrompt() {
  const [canInstall, setCanInstall] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [showIosInstructions, setShowIosInstructions] = useState(false);

  useEffect(() => {
    // Check if already running standalone
    if (isStandalone()) {
      return;
    }

    // Check iOS Safari
    const isIos =
      /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isSafari =
      /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent);

    if (isIos && isSafari) {
      setShowIosInstructions(true);
    }

    return subscribeInstallState((installable) => {
      setCanInstall(installable);
    });
  }, []);

  if (dismissed || isStandalone()) return null;

  if (canInstall) {
    return (
      <div
        style={{
          padding: '8px 16px',
          backgroundColor: '#F9FAFB',
          borderBottom: `1px solid ${colors.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontFamily: typography.fontFamily.sans,
          fontSize: typography.fontSize.sm,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Smartphone size={16} color={colors.secondary} />
          <span>Install CareOn Citizen for fast home-screen SOS access.</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Button size="sm" variant="secondary-red" onClick={promptInstall} icon={Download}>
            Install App
          </Button>
          <button
            onClick={() => setDismissed(true)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: colors.textSecondary }}
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    );
  }

  if (showIosInstructions) {
    return (
      <div
        style={{
          padding: '8px 16px',
          backgroundColor: '#F9FAFB',
          borderBottom: `1px solid ${colors.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontFamily: typography.fontFamily.sans,
          fontSize: typography.fontSize.xs,
          color: colors.textSecondary,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Info size={14} color={colors.secondary} />
          <span>iOS Tip: Tap Share &gt; "Add to Home Screen" to install CareOn as a mobile app.</span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.textSecondary }}
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return null;
}
