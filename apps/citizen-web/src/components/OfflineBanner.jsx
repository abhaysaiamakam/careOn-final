import React, { useState, useEffect } from 'react';
import { AlertCircle, WifiOff } from 'lucide-react';
import { colors, typography } from '@careon/design-system';

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
    }
    function handleOffline() {
      setIsOnline(false);
    }

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (isOnline) return null;

  return (
    <div
      style={{
        backgroundColor: '#FFFBEB',
        borderBottom: '1px solid #FDE68A',
        color: '#92400E',
        padding: '10px 16px',
        fontSize: typography.fontSize.sm,
        fontFamily: typography.fontFamily.sans,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        textAlign: 'center',
        zIndex: 1000,
      }}
    >
      <WifiOff size={16} color="#D99022" />
      <span>
        <strong>You are offline.</strong> Emergency reports submitted will be stored as local drafts until connectivity is restored. For life-threatening emergencies, call <strong>112</strong> or <strong>108</strong> immediately.
      </span>
    </div>
  );
}
