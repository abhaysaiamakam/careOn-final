import React, { useState, useEffect } from 'react';
import AdminDashboard from '../../pages/AdminDashboard';
import AdminLogin from '../../pages/AdminLogin';
import useAuth from '../../auth/useAuth';
import { hospitalApi } from '../../packages/api-client';
import { Activity, ShieldCheck, AlertTriangle, Building2, MapPin, Radio } from 'lucide-react';

export default function DispatcherApp({ onNavigate }) {
  const { isAuthenticated, role, user, logout } = useAuth();
  const [divertedHospitals, setDivertedHospitals] = useState([]);
  const [isLoadingHospitals, setIsLoadingHospitals] = useState(false);

  // Poll hospital diversion status for operational visibility
  useEffect(() => {
    let isMounted = true;
    async function fetchHospitals() {
      try {
        setIsLoadingHospitals(true);
        const data = await hospitalApi.getDirectory();
        if (isMounted && Array.isArray(data)) {
          setDivertedHospitals(data.filter((h) => h.divert_status));
        }
      } catch (err) {
        // Non-blocking for dispatcher console
      } finally {
        if (isMounted) setIsLoadingHospitals(false);
      }
    }

    if (isAuthenticated) {
      fetchHospitals();
      const interval = setInterval(fetchHospitals, 30000);
      return () => {
        isMounted = false;
        clearInterval(interval);
      };
    }
  }, [isAuthenticated]);

  return (
    <div className="dispatcher-app-container" style={{ minHeight: '100vh', backgroundColor: '#0a0e17' }}>
      {/* Dispatcher Command Sub-header */}
      <div style={{
        backgroundColor: '#0f172a',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '10px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            color: '#60a5fa',
            padding: '4px 12px',
            borderRadius: '9999px',
            fontSize: '0.8rem',
            fontWeight: 700,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}>
            <Radio size={14} /> Dispatch Command Centre
          </span>
          <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
            Multi-agency coordination, live triage & spatial fleet operations
          </span>
        </div>

        {/* Real-time Hospital Diversion Alert Bar */}
        {divertedHospitals.length > 0 && (
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#f87171',
            padding: '4px 12px',
            borderRadius: '8px',
            fontSize: '0.8rem',
            fontWeight: 600,
          }}>
            <AlertTriangle size={15} />
            <span>
              {divertedHospitals.length} Hospital{divertedHospitals.length > 1 ? 's' : ''} on Divert:{' '}
              {divertedHospitals.map((h) => h.organization_name).join(', ')}
            </span>
          </div>
        )}
      </div>

      {/* Main Dispatcher Dashboard / Login */}
      <div>
        <AdminDashboard
          lang="en"
          currentUser={user}
          onNavigate={onNavigate}
        />
      </div>
    </div>
  );
}
