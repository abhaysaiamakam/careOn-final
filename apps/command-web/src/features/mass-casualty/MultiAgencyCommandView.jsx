import React, { useState, useEffect } from 'react';
import {
  Users,
  Shield,
  Radio,
  Flame,
  Building2,
  AlertTriangle,
  Plus,
  Send,
  RefreshCw,
  Clock,
  Layers,
  CheckCircle,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import {
  listMutualAidPartners,
  listIncidents,
  listIncidentCollaborations,
  listAgencyTasks,
  createAgencyTask,
  listOperationalZones,
} from '@careon/api-client';
import { OPERATIONAL_ZONE_TYPES } from '@careon/contracts';

export function MultiAgencyCommandView() {
  const [partners, setPartners] = useState([]);
  const [mciIncidents, setMciIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskAgency, setNewTaskAgency] = useState('POLICE');
  const [actionMsg, setActionMsg] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [partnerData, incidentData] = await Promise.all([
        listMutualAidPartners().catch(() => []),
        listIncidents().catch(() => []),
      ]);
      setPartners(partnerData || []);

      // Filter to MCI / Disasters or high priority incidents
      const mcis = (incidentData || []).filter(
        (i) => i.is_disaster || (i.affected_people || 1) >= 2 || i.priority === 'Critical'
      );
      setMciIncidents(mcis);
      if (mcis.length > 0 && !selectedIncident) {
        setSelectedIncident(mcis[0]);
      }
    } catch (e) {
      console.warn('Failed to load multi-agency data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedIncident?.id) {
      loadIncidentMciDetails(selectedIncident.id);
    }
  }, [selectedIncident?.id]);

  const loadIncidentMciDetails = async (incidentId) => {
    try {
      const [taskData, zoneData] = await Promise.all([
        listAgencyTasks(incidentId).catch(() => []),
        listOperationalZones(incidentId).catch(() => []),
      ]);
      setTasks(taskData || []);
      setZones(zoneData || []);
    } catch (e) {
      console.warn('Failed to load MCI details:', e);
    }
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || !selectedIncident) return;
    try {
      await createAgencyTask(selectedIncident.id, {
        task_title: newTaskTitle.trim(),
        target_agency_type: newTaskAgency,
        priority: 'HIGH',
      });
      setNewTaskTitle('');
      setActionMsg(`Agency task dispatched to ${newTaskAgency}.`);
      loadIncidentMciDetails(selectedIncident.id);
      setTimeout(() => setActionMsg(null), 3000);
    } catch (err) {
      alert(`Failed to create agency task: ${err.message}`);
    }
  };

  return (
    <div style={{ padding: '20px 24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Unified Incident Command & Multi-Agency MCI (M11)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Inter-agency mutual aid coordination between EMS, Police, Fire & Rescue, and Receiving Hospital Triages under National Incident Management Standards.
          </p>
        </div>

        <Button size="sm" variant="outline" onClick={loadData} loading={loading} icon={RefreshCw}>
          Refresh Command
        </Button>
      </div>

      {actionMsg && (
        <div style={{ marginBottom: '16px', background: '#ECFDF5', border: '1px solid #A7F3D0', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: '#065F46' }}>
          ✓ {actionMsg}
        </div>
      )}

      {/* Mutual Aid Signatories Banner */}
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', marginBottom: '10px' }}>
          Registered Mutual Aid Signatory Agencies ({partners.length})
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
          {partners.map((p) => (
            <div
              key={p.organization_id}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '6px',
                border: `1px solid ${colors.border}`,
                padding: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                  {p.organization_name}
                </span>
                <Badge variant="neutral">{p.agency_type}</Badge>
              </div>
              <div style={{ fontSize: '11px', color: colors.textSecondary }}>
                Jurisdiction: {p.jurisdiction}
              </div>
              <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '10px', color: '#475569' }}>
                <span>TAC Radio: <strong>{p.radio_channel}</strong></span>
                <span>Direct: <strong>{p.dispatch_hotline}</strong></span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main MCI Operations Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '16px', minHeight: '400px' }}>
        {/* Left: Active MCI Incidents */}
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: '8px', border: `1px solid ${colors.border}`, padding: '16px' }}>
          <h3 style={{ margin: '0 0 12px', fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary }}>
            MCI / Disaster Missions ({mciIncidents.length})
          </h3>

          {mciIncidents.length === 0 ? (
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, textAlign: 'center', padding: '24px 0' }}>
              No active mass-casualty or disaster declarations in progress.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {mciIncidents.map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => setSelectedIncident(inc)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '6px',
                    border: `1px solid ${selectedIncident?.id === inc.id ? colors.secondary : colors.border}`,
                    backgroundColor: selectedIncident?.id === inc.id ? '#FEF2F2' : '#F8FAFC',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <strong style={{ fontSize: typography.fontSize.xs, color: colors.textPrimary }}>
                      {inc.incident_code}
                    </strong>
                    <Badge variant="danger">{inc.priority}</Badge>
                  </div>
                  <div style={{ fontSize: '11px', color: colors.textPrimary, fontWeight: 500 }}>
                    {inc.category} • {inc.affected_people || 1} Casualties
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Selected MCI Workspace */}
        {selectedIncident ? (
          <div style={{ backgroundColor: '#FFFFFF', borderRadius: '8px', border: `1px solid ${colors.border}`, padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: `1px solid ${colors.border}`, paddingBottom: '14px', marginBottom: '16px' }}>
              <div>
                <span style={{ fontSize: '10px', color: colors.secondary, fontWeight: 700, textTransform: 'uppercase' }}>
                  Unified Command Post
                </span>
                <h2 style={{ margin: '2px 0 0', fontSize: typography.fontSize.base, fontWeight: 700, color: colors.textPrimary }}>
                  {selectedIncident.incident_code}: {selectedIncident.title || selectedIncident.location_name}
                </h2>
                <div style={{ fontSize: '11px', color: colors.textSecondary, marginTop: '2px' }}>
                  Location: {selectedIncident.location_name} • Reported Casualties: {selectedIncident.affected_people || 1}
                </div>
              </div>

              <Badge variant="danger">UNIFIED COMMAND ACTIVE</Badge>
            </div>

            {/* Tactical Operational Zones */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', marginBottom: '8px' }}>
                Operational Perimeters & Tactical Zones:
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {OPERATIONAL_ZONE_TYPES.map((zone) => (
                  <div
                    key={zone.id}
                    style={{
                      borderLeft: `4px solid ${zone.color}`,
                      backgroundColor: '#F8FAFC',
                      padding: '6px 12px',
                      borderRadius: '4px',
                      fontSize: '11px',
                    }}
                  >
                    <span style={{ fontWeight: 600, color: colors.textPrimary }}>{zone.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Agency Task Delegation */}
            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', marginBottom: '8px' }}>
                Cross-Agency Tasks & Orders ({tasks.length}):
              </div>

              <form onSubmit={handleCreateTask} style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                <input
                  type="text"
                  required
                  placeholder="Order (e.g. Establish perimeter cordon on Sayyaji Rao Rd; set up triage CCP)"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: `1px solid ${colors.border}`,
                    fontSize: typography.fontSize.xs,
                  }}
                />
                <select
                  value={newTaskAgency}
                  onChange={(e) => setNewTaskAgency(e.target.value)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: `1px solid ${colors.border}`,
                    fontSize: typography.fontSize.xs,
                    backgroundColor: '#FFFFFF',
                  }}
                >
                  <option value="POLICE">Police</option>
                  <option value="FIRE_RESCUE">Fire & Rescue</option>
                  <option value="EMS">EMS</option>
                  <option value="HOSPITAL">Hospital</option>
                </select>
                <Button type="submit" size="sm" variant="primary" icon={Send} style={{ backgroundColor: colors.secondary }}>
                  Dispatch Task
                </Button>
              </form>

              {tasks.length === 0 ? (
                <div style={{ fontSize: '11px', color: colors.textSecondary, textAlign: 'center', padding: '16px', background: '#F8FAFC', borderRadius: '6px' }}>
                  No agency tasks delegated yet. Use the form above to assign tactical missions to mutual-aid partners.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {tasks.map((t) => (
                    <div
                      key={t.id}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: '#F8FAFC',
                        borderRadius: '6px',
                        border: `1px solid ${colors.border}`,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '11px',
                      }}
                    >
                      <div>
                        <strong>[{t.target_agency_type}]</strong> {t.task_title}
                      </div>
                      <Badge variant="neutral">{t.status || 'PENDING'}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ padding: '40px', textAlign: 'center', color: colors.textSecondary, backgroundColor: '#FFFFFF', borderRadius: '8px', border: `1px solid ${colors.border}` }}>
            Select an incident to view or establish Unified Command.
          </div>
        )}
      </div>
    </div>
  );
}
