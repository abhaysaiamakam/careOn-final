import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AuthProvider, useAuth } from '@careon/auth';
import { 
  getResponderMe, 
  listResponderMissions, 
  acknowledgeMission, 
  transitionMission, 
  getMissionHistory,
  sendResponderTelemetry,
  listHospitalFacilities,
  createEncounter,
  recordClinicalAssessment,
  recordVitalSigns,
  recordIntervention,
  recordMedication,
  createHandoverRecord,
  submitHandoverRecord
} from '@careon/api-client';

import { ResponderHeader } from './components/ResponderHeader.jsx';
import { ResponderLogin } from './features/auth/ResponderLogin.jsx';
import { MissionDashboard } from './features/dashboard/MissionDashboard.jsx';
import { MissionInbox } from './features/inbox/MissionInbox.jsx';
import { ActiveMissionWorkspace } from './features/workspace/ActiveMissionWorkspace.jsx';
import { MissionHistoryView } from './features/history/MissionHistoryView.jsx';
import { responderWs } from './services/websocket.js';
import { responderGeo } from './services/geolocation.js';
import { syncService } from './services/syncService.js';
import { offlineJournal } from './services/offlineJournal.js';

// Simple synthetic alert tone via Web Audio API
function playAlertChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
    osc.frequency.setValueAtTime(1174.66, ctx.currentTime + 0.15); // D6

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) {
    // Audio autoplay might be suspended by browser
  }
}

function ResponderAppContent() {
  const { user, token, logout, isAuthenticated } = useAuth();
  const [currentView, setCurrentView] = useState('dashboard');
  const [responderProfile, setResponderProfile] = useState(null);
  const [missions, setMissions] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [activeMissionHistory, setActiveMissionHistory] = useState([]);
  const [isAvailable, setIsAvailable] = useState(true);
  const [audioMuted, setAudioMuted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  // Service States
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [gpsStatus, setGpsStatus] = useState({ tracking: false, transmitting: false, latitude: null, longitude: null, accuracy: null });
  const [syncStatus, setSyncStatus] = useState({ isOnline: navigator.onLine, isSyncing: false, pendingCount: 0 });

  // Refs for services
  const wsClientRef = useRef(null);
  const geoServiceRef = useRef(null);
  const syncServiceRef = useRef(null);
  const activeMissionRef = useRef(null);

  // Categorize active vs pending missions
  const pendingMissions = missions.filter((m) => m.status === 'assigned');
  const activeMission = missions.find((m) => [
    'accepted',
    'en_route_incident',
    'arrived_scene',
    'patient_contact',
    'patient_picked_up',
    'en_route_hospital',
    'arrived_hospital',
    'handover_initiated',
    'handover_completed'
  ].includes(m.status));

  activeMissionRef.current = activeMission;

  // 1. Initial Data Fetching
  const fetchAllData = useCallback(async () => {
    if (!token) return;
    try {
      setIsLoading(true);
      const [meRes, missionsRes, hospRes] = await Promise.allSettled([
        getResponderMe(),
        listResponderMissions(),
        listHospitalFacilities()
      ]);

      if (meRes.status === 'fulfilled') {
        setResponderProfile(meRes.value);
      }
      if (missionsRes.status === 'fulfilled') {
        const missionList = Array.isArray(missionsRes.value) ? missionsRes.value : [];
        setMissions(missionList);
      }
      if (hospRes.status === 'fulfilled') {
        const hospList = Array.isArray(hospRes.value) ? hospRes.value : [];
        setHospitals(hospList);
      }
    } catch (err) {
      console.error('Failed to load initial responder data', err);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    }
  }, [isAuthenticated, fetchAllData]);

  // Fetch history when active mission changes
  useEffect(() => {
    if (activeMission?.id || activeMission?.assignment_id) {
      const id = activeMission.id || activeMission.assignment_id;
      getMissionHistory(id)
        .then((hist) => setActiveMissionHistory(Array.isArray(hist) ? hist : []))
        .catch(() => setActiveMissionHistory([]));
    } else {
      setActiveMissionHistory([]);
    }
  }, [activeMission?.id, activeMission?.assignment_id, activeMission?.status]);

  // 2. Initialize Duplex M4 WebSocket Client
  useEffect(() => {
    if (!token) return;

    const unbindStatus = responderWs.onStatusChange((status) => {
      setWsStatus(status.toLowerCase());
    });

    const unbindAssign = responderWs.on('mission_assigned', () => {
      if (!audioMuted) playAlertChime();
      fetchAllData();
      setCurrentView('inbox');
    });

    const unbindUpdate = responderWs.on('mission_updated', () => fetchAllData());
    const unbindCancel = responderWs.on('mission_cancelled', () => fetchAllData());
    const unbindAlert = responderWs.on('dispatch_alert', () => {
      if (!audioMuted) playAlertChime();
      fetchAllData();
    });

    responderWs.connect(token);

    return () => {
      unbindStatus();
      unbindAssign();
      unbindUpdate();
      unbindCancel();
      unbindAlert();
      responderWs.disconnect();
    };
  }, [token, audioMuted, fetchAllData]);

  // 3. Initialize Geolocation Service & Telemetry Loop
  useEffect(() => {
    if (!token) return;

    if (responderProfile?.vehicle?.id) {
      responderGeo.setResourceId(responderProfile.vehicle.id);
    }

    const unbindPosition = responderGeo.onPositionChange(async (pos) => {
      setGpsStatus({
        tracking: true,
        transmitting: true,
        latitude: pos.latitude,
        longitude: pos.longitude,
        accuracy: pos.accuracy,
        heading: pos.heading,
        speed: pos.speed
      });

      // Transmit live telemetry to backend
      try {
        const telemetryPayload = {
          resource_id: responderProfile?.vehicle?.id || undefined,
          latitude: pos.latitude,
          longitude: pos.longitude,
          heading: pos.heading || 0,
          speed: pos.speed || 0,
          accuracy: pos.accuracy,
          mission_id: activeMissionRef.current?.id || activeMissionRef.current?.assignment_id || null,
          incident_id: activeMissionRef.current?.incident_id || null,
          timestamp: new Date().toISOString()
        };

        if (navigator.onLine) {
          await sendResponderTelemetry(telemetryPayload);
        } else {
          await offlineJournal.recordAction('send_telemetry', telemetryPayload, {
            mission_id: telemetryPayload.mission_id
          });
        }
      } catch (e) {
        // Journal silently if network dropped
      }
    });

    try {
      responderGeo.startTracking();
    } catch (e) {
      setGpsStatus((prev) => ({ ...prev, tracking: false, error: e.message }));
    }

    return () => {
      unbindPosition();
      responderGeo.stopTracking();
    };
  }, [token, responderProfile?.vehicle?.id]);

  // 4. Initialize Offline Sync Coordinator
  useEffect(() => {
    const unbindOnline = syncService.onOnlineStateChange((isOnline) => {
      setSyncStatus((prev) => ({ ...prev, isOnline }));
    });

    const unbindJournal = offlineJournal.onJournalChange((pending) => {
      setSyncStatus((prev) => ({ ...prev, pendingCount: pending.length }));
    });

    syncService.startAutoSync(10000);

    return () => {
      unbindOnline();
      unbindJournal();
      syncService.stopAutoSync();
    };
  }, []);

  // 5. Mission Action Handlers
  const handleAcceptMission = async (missionId) => {
    setIsProcessing(true);
    try {
      if (navigator.onLine) {
        await acknowledgeMission(missionId, { action: 'accept' });
      } else {
        await offlineJournal.recordAction('acknowledge_mission', { action: 'accept' }, { mission_id: missionId });
      }

      await fetchAllData();
      setCurrentView('active');
    } catch (err) {
      alert(`Could not accept mission: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRejectMission = async (missionId, payload) => {
    setIsProcessing(true);
    try {
      if (navigator.onLine) {
        await acknowledgeMission(missionId, { action: 'reject', ...payload });
      } else {
        await offlineJournal.recordAction('acknowledge_mission', { action: 'reject', ...payload }, { mission_id: missionId });
      }

      await fetchAllData();
    } catch (err) {
      alert(`Could not reject mission: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTransitionStatus = async (missionId, targetStatus) => {
    setIsProcessing(true);
    try {
      if (navigator.onLine) {
        await transitionMission(missionId, { target_status: targetStatus });
      } else {
        await offlineJournal.recordAction('transition_mission', { target_status: targetStatus }, { mission_id: missionId });
      }

      await fetchAllData();
      if (targetStatus === 'completed') {
        setCurrentView('dashboard');
      }
    } catch (err) {
      throw err;
    } finally {
      setIsProcessing(false);
    }
  };

  // Clinical Handlers
  const ensureEncounterId = async () => {
    if (activeMission?.encounter_id) return activeMission.encounter_id;
    // Create an encounter if not already linked
    const enc = await createEncounter({
      incident_id: activeMission.incident_id,
      chief_complaint: activeMission.incident?.description || activeMission.incident?.category || 'Medical Emergency',
      patient_id: null
    });
    return enc.id || enc.encounter_id;
  };

  const handleSaveVitals = async (payload) => {
    const encId = await ensureEncounterId();
    if (navigator.onLine) {
      return await recordVitalSigns(encId, payload);
    } else {
      return await offlineJournal.recordAction('record_vitals', payload, { encounter_id: encId });
    }
  };

  const handleSaveAssessment = async (payload) => {
    const encId = await ensureEncounterId();
    if (navigator.onLine) {
      return await recordClinicalAssessment(encId, payload);
    } else {
      return await offlineJournal.recordAction('record_assessment', payload, { encounter_id: encId });
    }
  };

  const handleSaveIntervention = async (payload) => {
    const encId = await ensureEncounterId();
    if (navigator.onLine) {
      return await recordIntervention(encId, payload);
    } else {
      return await offlineJournal.recordAction('record_intervention', payload, { encounter_id: encId });
    }
  };

  const handleSaveMedication = async (payload) => {
    const encId = await ensureEncounterId();
    if (navigator.onLine) {
      return await recordMedication(encId, payload);
    } else {
      return await offlineJournal.recordAction('record_medication', payload, { encounter_id: encId });
    }
  };

  const handleSubmitHandover = async (payload) => {
    const encId = await ensureEncounterId();
    const resolvedFacilityId = Number(
      payload.hospital_id ||
      payload.facility_id ||
      activeMission?.destination_hospital_id ||
      selectedDestination?.id
    );
    if (!resolvedFacilityId) {
      throw new Error('A valid receiving facility ID is required for clinical handover.');
    }
    const handoverPayload = {
      encounter_id: encId,
      facility_id: resolvedFacilityId,
      receiving_department: 'Emergency Department',
      outstanding_clinical_concerns: payload.recommendation || null,
    };

    if (navigator.onLine) {
      const created = await createHandoverRecord(handoverPayload);
      const token = created.handover_token || created.token || created.id;
      if (token) {
        return await submitHandoverRecord(token);
      }
      return created;
    } else {
      return await offlineJournal.recordAction('submit_handover', handoverPayload, { encounter_id: encId });
    }
  };

  if (!isAuthenticated) {
    return <ResponderLogin />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      <ResponderHeader
        user={user}
        vehicle={responderProfile?.vehicle}
        currentView={currentView}
        onNavigate={setCurrentView}
        activeMission={activeMission}
        pendingMissionsCount={pendingMissions.length}
        gpsStatus={gpsStatus}
        wsStatus={wsStatus}
        syncStatus={syncStatus}
        audioMuted={audioMuted}
        onToggleAudio={() => setAudioMuted(!audioMuted)}
        onTriggerSync={() => syncServiceRef.current?.triggerImmediateSync()}
        onLogout={logout}
      />

      <main className="flex-1">
        {currentView === 'dashboard' && (
          <MissionDashboard
            user={user}
            vehicle={responderProfile?.vehicle}
            activeMission={activeMission}
            pendingMissions={pendingMissions}
            completedMissionsCount={missions.filter((m) => m.status === 'completed').length}
            gpsStatus={gpsStatus}
            syncStatus={syncStatus}
            isAvailable={isAvailable}
            onToggleAvailability={() => setIsAvailable(!isAvailable)}
            onNavigate={setCurrentView}
          />
        )}

        {currentView === 'inbox' && (
          <MissionInbox
            pendingMissions={pendingMissions}
            onAcceptMission={handleAcceptMission}
            onRejectMission={handleRejectMission}
            responderLocation={gpsStatus}
            isProcessing={isProcessing}
          />
        )}

        {currentView === 'active' && (
          <ActiveMissionWorkspace
            mission={activeMission}
            responderLocation={gpsStatus}
            hospitals={hospitals}
            onTransitionStatus={handleTransitionStatus}
            onSaveAssessment={handleSaveAssessment}
            onSaveVitals={handleSaveVitals}
            onSaveIntervention={handleSaveIntervention}
            onSaveMedication={handleSaveMedication}
            onSubmitHandover={handleSubmitHandover}
            missionHistory={activeMissionHistory}
            isUpdating={isProcessing}
          />
        )}

        {currentView === 'history' && (
          <MissionHistoryView
            missions={missions}
            isLoading={isLoading}
          />
        )}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider storagePrefix="careon_responder">
      <ResponderAppContent />
    </AuthProvider>
  );
}
