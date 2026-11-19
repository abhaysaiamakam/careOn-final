import React from 'react';
import {
  AlertTriangle,
  Radio,
  Truck,
  Building2,
  Clock,
  ShieldAlert,
  Activity,
  CheckCircle2,
} from 'lucide-react';
import { colors, typography, Badge } from '@careon/design-system';
import { IncidentQueue } from '../incidents/IncidentQueue.jsx';
import { OperationsMap } from '../map/OperationsMap.jsx';
import { IncidentCommandPanel } from '../details/IncidentCommandPanel.jsx';

export function CommandOverview({
  incidents = [],
  resources = [],
  hospitals = [],
  zones = [],
  shortages = {},
  selectedIncident = null,
  onSelectIncident = () => {},
  selectedResource = null,
  onSelectResource = () => {},
  onCloseIncidentPanel = () => {},
  onIncidentUpdated = () => {},
  loading = false,
}) {
  // Real Operational Indicator Calculations
  const activeIncidents = incidents.filter(
    (i) => !['Resolved', 'Cancelled', 'Rejected'].includes(i.status)
  );
  const criticalIncidents = activeIncidents.filter((i) => i.priority === 'Critical');
  const unassignedIncidents = activeIncidents.filter(
    (i) => !['Allocated', 'Dispatched', 'En Route to Scene', 'At Scene', 'Transporting'].includes(i.status)
  );

  const availableAmbulances = resources.filter(
    (r) => r.category === 'Ambulance' && r.status === 'Available'
  );
  const assignedResources = resources.filter((r) => r.status === 'Assigned' || r.status === 'En Route');
  const divertedHospitals = hospitals.filter((h) => h.divert_status);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* SECTION 1: TOP OPERATIONAL KPI STATUS CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '8px',
          padding: '10px 16px',
          backgroundColor: '#0F172A',
          borderBottom: '1px solid #1E293B',
        }}
      >
        {/* Active Incidents */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>Active Missions</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#FFFFFF', marginTop: '2px' }}>
            {activeIncidents.length}
          </div>
        </div>

        {/* Critical Incidents */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: criticalIncidents.length > 0 ? '1px solid #EF4444' : '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: criticalIncidents.length > 0 ? '#FCA5A5' : '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>
            Critical Triage
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: criticalIncidents.length > 0 ? '#EF4444' : '#FFFFFF', marginTop: '2px' }}>
            {criticalIncidents.length}
          </div>
        </div>

        {/* Awaiting Dispatch */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: unassignedIncidents.length > 0 ? '1px solid #F59E0B' : '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: unassignedIncidents.length > 0 ? '#FCD34D' : '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>
            Awaiting Dispatch
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: unassignedIncidents.length > 0 ? '#F59E0B' : '#FFFFFF', marginTop: '2px' }}>
            {unassignedIncidents.length}
          </div>
        </div>

        {/* Available Ambulances */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: availableAmbulances.length === 0 ? '1px solid #EF4444' : '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: availableAmbulances.length > 0 ? '#6EE7B7' : '#FCA5A5', textTransform: 'uppercase', fontWeight: 600 }}>
            Available Ambulances
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: availableAmbulances.length > 0 ? '#10B981' : '#EF4444', marginTop: '2px' }}>
            {availableAmbulances.length}
          </div>
        </div>

        {/* Assigned Fleet */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>Fleet En Route</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#FFFFFF', marginTop: '2px' }}>
            {assignedResources.length}
          </div>
        </div>

        {/* Hospital Diversion Indicator */}
        <div style={{ backgroundColor: '#1E293B', padding: '8px 12px', borderRadius: '6px', border: divertedHospitals.length > 0 ? '1px solid #EF4444' : '1px solid #334155' }}>
          <div style={{ fontSize: '10px', color: divertedHospitals.length > 0 ? '#FCA5A5' : '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>
            Hospital Diverts
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: divertedHospitals.length > 0 ? '#EF4444' : '#FFFFFF', marginTop: '2px' }}>
            {divertedHospitals.length}
          </div>
        </div>
      </div>

      {/* Critical Operational Banner if Divert or Shortage Active */}
      {divertedHospitals.length > 0 && (
        <div
          style={{
            backgroundColor: '#FEF2F2',
            borderBottom: '1px solid #FCA5A5',
            padding: '6px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            color: '#991B1B',
            fontWeight: 600,
          }}
        >
          <AlertTriangle size={14} color="#DC2626" />
          <span>
            HOSPITAL ADVISORY: {divertedHospitals.map((h) => h.name).join(', ')} currently on DIVERSION. Reroute incoming trauma and emergency cases.
          </span>
        </div>
      )}

      {/* SECTION 2: 3-PANE OPERATIONS COMMAND CENTRE */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Pane A: Left Incident Queue (340px) */}
        <div style={{ width: '340px', minWidth: '300px', height: '100%' }}>
          <IncidentQueue
            incidents={incidents}
            selectedIncident={selectedIncident}
            onSelectIncident={onSelectIncident}
            loading={loading}
          />
        </div>

        {/* Pane B: Center Operations Map (Flex 1) */}
        <div style={{ flex: 1, height: '100%', position: 'relative', overflow: 'hidden' }}>
          <OperationsMap
            incidents={activeIncidents}
            resources={resources}
            hospitals={hospitals}
            zones={zones}
            selectedIncident={selectedIncident}
            onSelectIncident={onSelectIncident}
            selectedResource={selectedResource}
            onSelectResource={onSelectResource}
            height="100%"
          />
        </div>

        {/* Pane C: Right Incident Details & Dispatch Panel (420px) */}
        {selectedIncident && (
          <div style={{ width: '420px', minWidth: '380px', height: '100%' }}>
            <IncidentCommandPanel
              incident={selectedIncident}
              onClose={onCloseIncidentPanel}
              onIncidentUpdated={onIncidentUpdated}
            />
          </div>
        )}
      </div>
    </div>
  );
}
