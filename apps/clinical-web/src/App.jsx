import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from '@careon/auth';
import * as apiClient from '@careon/api-client';
import {
  listHospitalFacilities,
  getHospitalReadiness,
  getIncomingTransports,
  listIncomingPatientRequests,
  getHospitalDirectory,
  getFacilityDiversion,
} from '@careon/api-client';
import clinicalWs from './services/websocket.js';
import ClinicalHeader from './components/ClinicalHeader.jsx';
import ClinicalLogin from './features/auth/ClinicalLogin.jsx';
import HospitalDashboard from './features/dashboard/HospitalDashboard.jsx';
import IncomingPatientsView from './features/incoming/IncomingPatientsView.jsx';
import CapacityManagementView from './features/capacity/CapacityManagementView.jsx';
import CapacityUpdateModal from './features/capacity/CapacityUpdateModal.jsx';
import DiversionControlModal from './features/diversion/DiversionControlModal.jsx';
import ClinicalHandoverWorkspace from './features/handover/ClinicalHandoverWorkspace.jsx';
import MCICoordinationView from './features/mci/MCICoordinationView.jsx';

function ClinicalPortal() {
  const { user, accessToken, isAuthenticated, isLoading, logout } = useAuth();

  // Navigation tab state
  const [activeTab, setActiveTab] = useState('dashboard');

  // Facilities & Operational telemetry state
  const [facilities, setFacilities] = useState([]);
  const [selectedFacility, setSelectedFacility] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [diversionStatus, setDiversionStatus] = useState(null);
  const [incomingRequests, setIncomingRequests] = useState([]);
  const [incomingTransports, setIncomingTransports] = useState([]);
  const [handovers, setHandovers] = useState([]);
  const [directory, setDirectory] = useState([]);

  // Telemetry status
  const [loading, setLoading] = useState(false);
  const [wsStatus, setWsStatus] = useState('DISCONNECTED');

  // Modals state
  const [showDiversionModal, setShowDiversionModal] = useState(false);
  const [showCapacityModal, setShowCapacityModal] = useState(false);

  // Monitor WebSocket status
  useEffect(() => {
    const unsub = clinicalWs.onStatusChange((status) => {
      setWsStatus(status);
    });
    return unsub;
  }, []);

  // Connect WebSocket when authenticated
  useEffect(() => {
    if (isAuthenticated && accessToken) {
      clinicalWs.connect(accessToken);
    } else {
      clinicalWs.disconnect();
    }
  }, [isAuthenticated, accessToken]);

  // Fetch live telemetry from backend
  const fetchTelemetry = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);

    try {
      // 1. Fetch facilities
      const facs = await listHospitalFacilities().catch(() => []);
      const facList = Array.isArray(facs) ? facs : facs?.items || [];
      setFacilities(facList);

      let currentFac = selectedFacility;
      if (!currentFac && facList.length > 0) {
        currentFac = facList[0];
        setSelectedFacility(facList[0]);
      }

      // 2. Fetch readiness
      const r = await getHospitalReadiness().catch(() => null);
      if (r) {
        setReadiness(r);
        setDiversionStatus({
          status: r.divert_status ? 'Diverting' : 'Open',
          reason: r.divert_reason,
          is_diverting: r.divert_status,
        });
      }

      // 3. If facility exists, fetch facility-specific diversion
      if (currentFac?.id) {
        const div = await getFacilityDiversion(currentFac.id).catch(() => null);
        if (div) {
          setDiversionStatus(div);
        }
      }

      // 4. Fetch incoming transports & requests
      const transports = await getIncomingTransports().catch(() => []);
      setIncomingTransports(Array.isArray(transports) ? transports : transports?.items || []);

      const reqs = await listIncomingPatientRequests(
        currentFac?.id ? { facility_id: currentFac.id } : {}
      ).catch(() => []);
      setIncomingRequests(Array.isArray(reqs) ? reqs : reqs?.items || []);

      // 5. Fetch hospital directory for MCI
      const dir = await getHospitalDirectory().catch(() => []);
      setDirectory(Array.isArray(dir) ? dir : dir?.items || []);
    } catch (err) {
      console.error('Failed to load clinical operational telemetry:', err);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, selectedFacility]);

  // Initial fetch
  useEffect(() => {
    if (isAuthenticated) {
      fetchTelemetry();
    }
  }, [isAuthenticated, fetchTelemetry]);

  // WebSocket event subscriptions for real-time updates
  useEffect(() => {
    if (!isAuthenticated) return;

    // Incoming patient request events
    const unsubReq = clinicalWs.on('hospital.incoming_patient_requested', (event) => {
      fetchTelemetry();
    });
    const unsubAck = clinicalWs.on('hospital.incoming_patient_acknowledged', (event) => {
      fetchTelemetry();
    });
    const unsubAcc = clinicalWs.on('hospital.incoming_patient_accepted', (event) => {
      fetchTelemetry();
    });
    const unsubDec = clinicalWs.on('hospital.incoming_patient_declined', (event) => {
      fetchTelemetry();
    });
    const unsubTimeout = clinicalWs.on('hospital.response_timeout', () => {
      fetchTelemetry();
    });

    // Capacity & Diversion events
    const unsubCap = clinicalWs.on('hospital.capacity_updated', () => {
      fetchTelemetry();
    });
    const unsubDiv = clinicalWs.on('hospital.diversion_changed', () => {
      fetchTelemetry();
    });
    const unsubReadiness = clinicalWs.on('hospital.readiness_changed', () => {
      fetchTelemetry();
    });
    const unsubArr = clinicalWs.on('hospital.patient_arrival_confirmed', () => {
      fetchTelemetry();
    });

    // Handover events
    const unsubHoSubmit = clinicalWs.on('handover.document_submitted', (event) => {
      fetchTelemetry();
    });
    const unsubHoRec = clinicalWs.on('handover.received', () => {
      fetchTelemetry();
    });
    const unsubHoComp = clinicalWs.on('handover.completed', () => {
      fetchTelemetry();
    });

    return () => {
      unsubReq();
      unsubAck();
      unsubAcc();
      unsubDec();
      unsubTimeout();
      unsubCap();
      unsubDiv();
      unsubReadiness();
      unsubArr();
      unsubHoSubmit();
      unsubHoRec();
      unsubHoComp();
    };
  }, [isAuthenticated, fetchTelemetry]);

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#F9FAFB',
          color: '#4B5563',
          fontSize: '14px',
          fontWeight: 600,
        }}
      >
        Initializing CareOn Clinical Session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <ClinicalLogin onLoginSuccess={() => fetchTelemetry()} />;
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#F9FAFB' }}>
      {/* Universal Top Header */}
      <ClinicalHeader
        facility={selectedFacility}
        facilities={facilities}
        onSelectFacility={(fac) => {
          setSelectedFacility(fac);
          fetchTelemetry();
        }}
        diversionStatus={diversionStatus}
        onOpenDiversionModal={() => setShowDiversionModal(true)}
        onOpenCapacityModal={() => setShowCapacityModal(true)}
        capacity={readiness}
        wsStatus={wsStatus}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        user={user}
        onLogout={logout}
        pendingIncomingCount={incomingRequests.length + incomingTransports.length}
        pendingHandoverCount={handovers.length}
      />

      {/* Main View Router */}
      <main>
        {activeTab === 'dashboard' && (
          <HospitalDashboard
            facility={selectedFacility}
            diversionStatus={diversionStatus}
            capacity={readiness}
            readiness={readiness}
            incomingRequests={incomingRequests}
            incomingTransports={incomingTransports}
            handovers={handovers}
            onNavigateTab={setActiveTab}
            onOpenDiversionModal={() => setShowDiversionModal(true)}
            onOpenCapacityModal={() => setShowCapacityModal(true)}
            onRefresh={fetchTelemetry}
          />
        )}

        {activeTab === 'incoming' && (
          <IncomingPatientsView
            facility={selectedFacility}
            incomingRequests={incomingRequests}
            incomingTransports={incomingTransports}
            loading={loading}
            onRefresh={fetchTelemetry}
            onRequestUpdated={() => fetchTelemetry()}
          />
        )}

        {activeTab === 'capacity' && (
          <CapacityManagementView
            facility={selectedFacility}
            readiness={readiness}
            loading={loading}
            onRefresh={fetchTelemetry}
            onOpenUpdateModal={() => setShowCapacityModal(true)}
          />
        )}

        {activeTab === 'handover' && (
          <ClinicalHandoverWorkspace
            handovers={handovers}
            loading={loading}
            onRefresh={fetchTelemetry}
            onHandoverUpdated={() => fetchTelemetry()}
          />
        )}

        {activeTab === 'mci' && (
          <MCICoordinationView
            facilities={facilities}
            directory={directory}
            loading={loading}
            onRefresh={fetchTelemetry}
          />
        )}
      </main>

      {/* Diversion Status Change Modal */}
      <DiversionControlModal
        facility={selectedFacility}
        currentStatus={diversionStatus}
        isOpen={showDiversionModal}
        onClose={() => setShowDiversionModal(false)}
        onStatusUpdated={(updated) => {
          setDiversionStatus(updated);
          fetchTelemetry();
        }}
      />

      {/* Bed Capacity Inventory Update Modal */}
      <CapacityUpdateModal
        facility={selectedFacility}
        readiness={readiness}
        isOpen={showCapacityModal}
        onClose={() => setShowCapacityModal(false)}
        onCapacityUpdated={(updated) => {
          setReadiness((prev) => ({ ...prev, ...updated }));
          fetchTelemetry();
        }}
      />
    </div>
  );
}

export function App() {
  return (
    <AuthProvider apiClient={apiClient} storagePrefix="careon_clinical">
      <ClinicalPortal />
    </AuthProvider>
  );
}

export default App;
