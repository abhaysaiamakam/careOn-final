import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as apiClient from '@careon/api-client';
import { AuthProvider, useAuth } from '@careon/auth';
import { CommandLogin } from './features/auth/CommandLogin.jsx';
import { CommandHeader } from './components/CommandHeader.jsx';
import { CommandOverview } from './features/overview/CommandOverview.jsx';
import { OperationsMap } from './features/map/OperationsMap.jsx';
import { FleetManagement } from './features/fleet/FleetManagement.jsx';
import { HospitalCoordinationView } from './features/hospitals/HospitalCoordinationView.jsx';
import { MultiAgencyCommandView } from './features/mass-casualty/MultiAgencyCommandView.jsx';
import { PredictiveIntelligenceView } from './features/intelligence/PredictiveIntelligenceView.jsx';
import { AnalyticsView } from './features/analytics/AnalyticsView.jsx';
import { LiveEventFeed } from './components/LiveEventFeed.jsx';
import { commandWs } from './services/websocket.js';
import { colors, typography, Button } from '@careon/design-system';
import { ShieldAlert, LogOut } from 'lucide-react';

function CommandAppShell() {
  const { user, accessToken, isAuthenticated, role, logout } = useAuth();
  const [activeView, setActiveView] = useState('overview'); // overview, map, fleet, hospitals, multi-agency, intelligence, analytics
  const [wsStatus, setWsStatus] = useState('DISCONNECTED');
  const [audioAlertsEnabled, setAudioAlertsEnabled] = useState(true);
  const [events, setEvents] = useState([]);

  // Data states
  const [incidents, setIncidents] = useState([]);
  const [resources, setResources] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [zones, setZones] = useState([]);
  const [shortages, setShortages] = useState({});
  const [loading, setLoading] = useState(true);

  // Selected item states
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [selectedResource, setSelectedResource] = useState(null);

  // Audio Chime Ref using Web Audio API synthesized beep (no external audio asset needed)
  const audioCtxRef = useRef(null);

  const playChime = useCallback(() => {
    if (!audioAlertsEnabled) return;
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5 tone
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.25);
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    } catch (e) {
      // Audio autoplay policy might prevent playback without prior user gesture
    }
  }, [audioAlertsEnabled]);

  // Load live operational data from central PostgreSQL backend
  const loadOperationalData = useCallback(async () => {
    setLoading(true);
    try {
      const [incData, resData, hospData, shortData] = await Promise.all([
        apiClient.listIncidents().catch(() => []),
        apiClient.listResources().catch(() => []),
        apiClient.listHospitalFacilities().catch(() => []),
        apiClient.getShortagesSummary().catch(() => ({ shortages: [] })),
      ]);

      setIncidents(incData || []);
      setResources(resData || []);
      setHospitals(hospData || []);
      setShortages(shortData || {});

      // If an incident was selected, update its reference
      if (selectedIncident) {
        const updated = (incData || []).find((i) => i.id === selectedIncident.id);
        if (updated) setSelectedIncident(updated);
      }
    } catch (err) {
      console.error('Failed to sync command centre data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedIncident]);

  // Initial data load on authentication
  useEffect(() => {
    if (isAuthenticated) {
      loadOperationalData();
    }
  }, [isAuthenticated, loadOperationalData]);

  // M4 Real-Time WebSocket Connection & Event Routing
  useEffect(() => {
    if (!isAuthenticated || !accessToken) return;

    // Connect WebSocket
    commandWs.connect(accessToken);
    const unsubStatus = commandWs.onStatusChange((status) => setWsStatus(status));

    // Handle incoming events
    const unsubEvents = commandWs.on('*', ({ type, data }) => {
      const newEvt = {
        type: type || 'realtime_event',
        data,
        timestamp: new Date().toISOString(),
        text: data?.message || data?.incident_code || JSON.stringify(data),
      };

      setEvents((prev) => [newEvt, ...prev.slice(0, 49)]);

      // Event-specific triggers
      if (type === 'incident_created' || type === 'INCIDENT_CREATED') {
        playChime();
        loadOperationalData();
      } else if (type === 'incident_updated' || type === 'assignment_created') {
        loadOperationalData();
      } else if (type === 'telemetry_updated') {
        // Live responder/vehicle location update
        if (data?.resource_id && data?.latitude && data?.longitude) {
          setResources((prev) =>
            prev.map((r) =>
              r.id === data.resource_id
                ? { ...r, latitude: data.latitude, longitude: data.longitude }
                : r
            )
          );
        }
      }
    });

    return () => {
      unsubStatus();
      unsubEvents();
      commandWs.disconnect();
    };
  }, [isAuthenticated, accessToken, loadOperationalData, playChime]);

  // 1. Unauthenticated View -> Dispatcher Login
  if (!isAuthenticated) {
    return <CommandLogin />;
  }

  // 2. Role Security Check -> Default Deny for unauthorized roles
  const isAuthorizedRole = role === 'admin' || role === 'super_admin' || role === 'dispatcher';
  if (!isAuthorizedRole) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#0F172A',
          padding: '24px',
        }}
      >
        <div style={{ maxWidth: '440px', backgroundColor: '#FFFFFF', borderRadius: '8px', padding: '32px', textAlign: 'center' }}>
          <ShieldAlert size={48} color={colors.secondary} style={{ margin: '0 auto 16px' }} />
          <h2 style={{ margin: '0 0 8px', fontSize: typography.fontSize.lg, fontWeight: 700, color: colors.textPrimary }}>
            Unauthorized Role Access
          </h2>
          <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Logged in as <strong>{user?.email}</strong> with role <code>{role}</code>. The Command Centre is strictly reserved for authorized Emergency Dispatchers and Command Administrators.
          </p>
          <Button variant="primary" fullWidth onClick={logout} icon={LogOut}>
            Sign Out
          </Button>
        </div>
      </div>
    );
  }

  // 3. Authenticated Dispatcher Layout
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', backgroundColor: '#F8FAFC' }}>
      {/* Top Header */}
      <CommandHeader
        activeView={activeView}
        onViewChange={(view) => setActiveView(view)}
        wsStatus={wsStatus}
        audioAlertsEnabled={audioAlertsEnabled}
        onToggleAudioAlerts={() => setAudioAlertsEnabled(!audioAlertsEnabled)}
      />

      {/* Main Feature Viewport */}
      <main style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {activeView === 'overview' && (
          <CommandOverview
            incidents={incidents}
            resources={resources}
            hospitals={hospitals}
            zones={zones}
            shortages={shortages}
            selectedIncident={selectedIncident}
            onSelectIncident={(inc) => setSelectedIncident(inc)}
            selectedResource={selectedResource}
            onSelectResource={(res) => setSelectedResource(res)}
            onCloseIncidentPanel={() => setSelectedIncident(null)}
            onIncidentUpdated={loadOperationalData}
            loading={loading}
          />
        )}

        {activeView === 'map' && (
          <div style={{ height: '100%', padding: '12px' }}>
            <OperationsMap
              incidents={incidents.filter((i) => !['Resolved', 'Cancelled'].includes(i.status))}
              resources={resources}
              hospitals={hospitals}
              zones={zones}
              selectedIncident={selectedIncident}
              onSelectIncident={(inc) => {
                setSelectedIncident(inc);
                setActiveView('overview');
              }}
              selectedResource={selectedResource}
              onSelectResource={(r) => setSelectedResource(r)}
              height="100%"
            />
          </div>
        )}

        {activeView === 'fleet' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <FleetManagement
              resources={resources}
              onRefresh={loadOperationalData}
              loading={loading}
            />
          </div>
        )}

        {activeView === 'hospitals' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <HospitalCoordinationView />
          </div>
        )}

        {activeView === 'multi-agency' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <MultiAgencyCommandView />
          </div>
        )}

        {activeView === 'intelligence' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <PredictiveIntelligenceView />
          </div>
        )}

        {activeView === 'analytics' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <AnalyticsView />
          </div>
        )}
      </main>

      {/* Collapsible Live Real-Time Activity Feed */}
      <LiveEventFeed
        events={events}
        onClear={() => setEvents([])}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider apiClient={apiClient} storagePrefix="careon_command">
      <CommandAppShell />
    </AuthProvider>
  );
}
