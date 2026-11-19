import React, { useState, useEffect } from 'react';
import {
  X,
  Phone,
  MapPin,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Send,
  Truck,
  Building2,
  Users,
  ShieldCheck,
  Brain,
  FileText,
  Activity,
  Layers,
  Edit2,
  ChevronDown,
  RefreshCw,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  Input,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import {
  assessIncident,
  recommendDispatchResources,
  approveDispatchAssignment,
  overrideDispatchAssignment,
  updateIncidentStatus,
  updateIncidentPriority,
  recommendReceivingHospitals,
  createIncomingPatientRequest,
  listMutualAidPartners,
  inviteIncidentCollaboration,
  listIncidentEncounters,
} from '@careon/api-client';

export function IncidentCommandPanel({
  incident,
  onClose,
  onIncidentUpdated = () => {},
}) {
  const [activeTab, setActiveTab] = useState('dispatch'); // dispatch, assessment, hospital, multiagency, handover
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // M5 Assessment State
  const [assessment, setAssessment] = useState(null);
  const [assessmentLoading, setAssessmentLoading] = useState(false);

  // M5 Recommendations State
  const [recommendations, setRecommendations] = useState(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  // Override Modal State
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  // Hospital Recommendation State
  const [hospitalsRec, setHospitalsRec] = useState([]);
  const [hospitalLoading, setHospitalLoading] = useState(false);

  // Multi-Agency State
  const [partners, setPartners] = useState([]);
  const [collaborations, setCollaborations] = useState([]);

  // Handover State
  const [encounters, setEncounters] = useState([]);
  const [hospitalRouting, setHospitalRouting] = useState(false);

  const notify = (msg, isErr = false) => {
    if (isErr) {
      setErrorMsg(msg);
      setTimeout(() => setErrorMsg(null), 6000);
    } else {
      setActionMsg(msg);
      setTimeout(() => setActionMsg(null), 4000);
    }
  };

  // Load recommendations whenever incident changes
  useEffect(() => {
    if (incident?.id) {
      loadDispatchData();
    }
  }, [incident?.id]);

  const loadDispatchData = async () => {
    if (!incident) return;
    setRecommendationsLoading(true);
    try {
      const data = await recommendDispatchResources(incident.id);
      setRecommendations(data);
      if (data.assessment) {
        setAssessment(data.assessment);
      }
      if (data.top_recommendation) {
        setSelectedCandidate(data.top_recommendation);
      } else if (data.ranked_candidates && data.ranked_candidates.length > 0) {
        const eligible = data.ranked_candidates.find((c) => c.eligibility_status === 'eligible');
        setSelectedCandidate(eligible || data.ranked_candidates[0]);
      }
    } catch (err) {
      console.warn('Failed to load dispatch recommendations:', err);
    } finally {
      setRecommendationsLoading(false);
    }
  };

  const handleRunAssessment = async () => {
    setAssessmentLoading(true);
    try {
      const data = await assessIncident(incident.id);
      setAssessment(data);
      notify('Triage assessment updated.');
    } catch (err) {
      notify(err.message || 'Assessment failed.', true);
    } finally {
      setAssessmentLoading(false);
    }
  };

  const handleApproveAssignment = async () => {
    if (!selectedCandidate) {
      notify('Select a resource candidate to dispatch.', true);
      return;
    }

    setLoading(true);
    try {
      await approveDispatchAssignment({
        incident_id: incident.id,
        resource_id: selectedCandidate.resource_id,
        eta_minutes: selectedCandidate.eta_minutes || 5.0,
      });
      notify(`Dispatched ${selectedCandidate.resource_code || 'Ambulance'} to incident.`);
      onIncidentUpdated();
      loadDispatchData();
    } catch (err) {
      notify(err.message || 'Dispatch approval rejected by safety rules.', true);
    } finally {
      setLoading(false);
    }
  };

  const handleManualOverride = async () => {
    if (!selectedCandidate || !overrideReason.trim()) {
      notify('Justification reason is required for manual dispatch override.', true);
      return;
    }

    setLoading(true);
    try {
      await overrideDispatchAssignment({
        incident_id: incident.id,
        resource_id: selectedCandidate.resource_id,
        override_reason: overrideReason.trim(),
      });
      notify(`Manual override approved for ${selectedCandidate.resource_code}.`);
      setShowOverrideModal(false);
      setOverrideReason('');
      onIncidentUpdated();
      loadDispatchData();
    } catch (err) {
      notify(err.message || 'Override failed.', true);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus) => {
    try {
      await updateIncidentStatus(incident.id, newStatus, 'Dispatcher console manual transition');
      notify(`Incident marked as ${newStatus}`);
      onIncidentUpdated();
    } catch (err) {
      notify(err.message || 'Status transition failed.', true);
    }
  };

  const handlePriorityChange = async (newPriority) => {
    try {
      await updateIncidentPriority(incident.id, newPriority, 'Dispatcher priority update');
      notify(`Priority updated to ${newPriority}`);
      onIncidentUpdated();
    } catch (err) {
      notify(err.message || 'Priority change failed.', true);
    }
  };

  const loadHospitals = async () => {
    setHospitalLoading(true);
    try {
      const data = await recommendReceivingHospitals(incident.id);
      setHospitalsRec(data || []);
    } catch (err) {
      console.warn('Failed to load hospital recommendations:', err);
    } finally {
      setHospitalLoading(false);
    }
  };

  const handleRouteHospital = async (hospital) => {
    if (!incident) return;
    setHospitalRouting(true);
    try {
      await createIncomingPatientRequest({
        facility_id: hospital.facility_id,
        incident_id: incident.id,
        emergency_severity: incident.priority || 'High',
        patient_condition_summary: `${incident.title || ''}: ${incident.description || ''}`.trim(),
        eta_minutes: hospital.eta_minutes || 10,
        eta_source: hospital.eta_source || 'OSRM Road Network',
      });
      notify(`Pre-arrival notification sent to ${hospital.facility_name}. Awaiting hospital confirmation.`);
      loadHospitals();
    } catch (err) {
      console.error('Failed to route hospital:', err);
      notify(err.message || 'Failed to send pre-arrival notification', true);
    } finally {
      setHospitalRouting(false);
    }
  };

  const loadMultiAgency = async () => {
    try {
      const data = await listMutualAidPartners();
      setPartners(data || []);
    } catch (err) {
      console.warn('Failed to load mutual aid partners:', err);
    }
  };

  const loadHandover = async () => {
    try {
      const data = await listIncidentEncounters(incident.id);
      setEncounters(data || []);
    } catch (err) {
      console.warn('Failed to load handover encounters:', err);
    }
  };

  if (!incident) {
    return (
      <div style={{ padding: '32px 16px', textAlign: 'center', color: colors.textSecondary }}>
        Select an incident from the queue or map to inspect details and dispatch resources.
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: '#FFFFFF',
        borderLeft: `1px solid ${colors.border}`,
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: `1px solid ${colors.border}`,
          backgroundColor: '#0F172A',
          color: '#FFFFFF',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: '#FFFFFF' }}>
              {incident.incident_code || `#${incident.id}`}
            </span>
            <Badge variant={incident.priority === 'Critical' ? 'danger' : 'warning'}>
              {incident.priority}
            </Badge>
            <Badge variant="neutral">
              {incident.status}
            </Badge>
          </div>
          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px' }}>
            {incident.category} • Reported: {new Date(incident.created_at).toLocaleTimeString()}
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#94A3B8',
            cursor: 'pointer',
            padding: '4px',
          }}
        >
          <X size={18} />
        </button>
      </div>

      {actionMsg && (
        <div style={{ padding: '8px 16px' }}>
          <Alert variant="success" icon={CheckCircle2}>
            {actionMsg}
          </Alert>
        </div>
      )}

      {errorMsg && (
        <div style={{ padding: '8px 16px' }}>
          <Alert variant="danger" icon={AlertTriangle}>
            {errorMsg}
          </Alert>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: `1px solid ${colors.border}`,
          backgroundColor: '#F8FAFC',
          overflowX: 'auto',
        }}
      >
        {[
          { id: 'dispatch', label: 'Dispatch', icon: Truck },
          { id: 'assessment', label: 'Triage Assessment', icon: Brain },
          { id: 'hospital', label: 'Hospital Coordination', icon: Building2 },
          { id: 'multiagency', label: 'Multi-Agency / MCI', icon: Users },
          { id: 'handover', label: 'Handover', icon: FileText },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id === 'hospital') loadHospitals();
                if (tab.id === 'multiagency') loadMultiAgency();
                if (tab.id === 'handover') loadHandover();
              }}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                padding: '10px 8px',
                fontSize: '11px',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? colors.secondary : colors.textSecondary,
                borderBottom: isActive ? `2px solid ${colors.secondary}` : '2px solid transparent',
                background: isActive ? '#FFFFFF' : 'transparent',
                borderLeft: 'none',
                borderRight: 'none',
                borderTop: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main Tab Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {/* TAB 1: INTELLIGENT DISPATCH (M5) */}
        {activeTab === 'dispatch' && (
          <div>
            {/* Citizen Caller & Location Summary */}
            <div style={{ backgroundColor: '#F8FAFC', borderRadius: '6px', border: `1px solid ${colors.border}`, padding: '12px', marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', marginBottom: '8px' }}>
                Incident Location & Caller
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '6px' }}>
                <MapPin size={15} color={colors.secondary} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ fontSize: typography.fontSize.xs, fontWeight: 600, color: colors.textPrimary }}>
                    {incident.location_name || 'Registered Coordinates'}
                  </div>
                  <div style={{ fontSize: '11px', color: colors.textSecondary }}>
                    GPS: {incident.latitude?.toFixed(5)}, {incident.longitude?.toFixed(5)}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid #E2E8F0`, paddingTop: '8px', marginTop: '8px' }}>
                <div style={{ fontSize: '11px', color: colors.textSecondary }}>
                  Caller: <strong>{incident.contact_name || 'Citizen'}</strong> ({incident.contact_phone || 'Direct'})
                </div>
                {incident.contact_phone && (
                  <a
                    href={`tel:${incident.contact_phone}`}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: colors.secondary,
                      textDecoration: 'none',
                      padding: '2px 6px',
                      backgroundColor: '#FEE2E2',
                      borderRadius: '4px',
                    }}
                  >
                    <Phone size={11} /> Dial
                  </a>
                )}
              </div>
            </div>

            {/* M5 Ranked Candidates */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: colors.textPrimary, textTransform: 'uppercase' }}>
                  Ranked Resource Candidates ({recommendations?.ranked_candidates?.length || 0})
                </div>
                <button
                  onClick={loadDispatchData}
                  style={{ background: 'none', border: 'none', color: colors.secondary, fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <RefreshCw size={11} /> Recalculate
                </button>
              </div>

              {recommendationsLoading ? (
                <div style={{ textAlign: 'center', padding: '24px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  Computing spatial distance, route ETA, and capability matches...
                </div>
              ) : !recommendations?.ranked_candidates?.length ? (
                <div style={{ padding: '20px', textAlign: 'center', border: '1px dashed #CBD5E1', borderRadius: '6px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  No resources currently registered in spatial radius.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {recommendations.ranked_candidates.map((cand) => {
                    const isSelected = selectedCandidate?.resource_id === cand.resource_id;
                    const isEligible = cand.eligibility_status === 'eligible';
                    return (
                      <div
                        key={cand.resource_id}
                        onClick={() => setSelectedCandidate(cand)}
                        style={{
                          border: isSelected ? `2px solid ${colors.secondary}` : `1px solid ${colors.border}`,
                          borderRadius: '6px',
                          padding: '10px',
                          backgroundColor: isSelected ? '#FFF5F5' : '#FFFFFF',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                              {cand.resource_code}
                            </span>
                            <span style={{ fontSize: '11px', color: colors.textSecondary }}>
                              {cand.resource_name}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: isEligible ? '#DCFCE7' : '#F1F5F9',
                                color: isEligible ? '#15803D' : '#64748B',
                              }}
                            >
                              {cand.eligibility_status?.toUpperCase()}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: colors.textSecondary, marginBottom: '4px' }}>
                          <span>ETA: <strong style={{ color: colors.textPrimary }}>{cand.eta_minutes || 5} min</strong> ({cand.distance_km || 1.5} km)</span>
                          <span>Routing: {cand.eta_source || 'OSRM'}</span>
                        </div>

                        {/* Ineligibility Reason warnings */}
                        {cand.ineligibility_reasons?.length > 0 && (
                          <div style={{ fontSize: '10px', color: '#B91C1C', marginTop: '4px', lineHeight: 1.3 }}>
                            ⚠️ {cand.ineligibility_reasons.join(' • ')}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Dispatch Action Buttons */}
            <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '16px', display: 'flex', gap: '10px' }}>
              <Button
                variant="primary"
                fullWidth
                loading={loading}
                disabled={!selectedCandidate || selectedCandidate.eligibility_status !== 'eligible'}
                onClick={handleApproveAssignment}
                icon={Send}
                style={{ backgroundColor: colors.secondary }}
              >
                Approve Dispatch ({selectedCandidate?.resource_code || 'Select'})
              </Button>

              <Button
                variant="outline"
                disabled={!selectedCandidate}
                onClick={() => setShowOverrideModal(true)}
              >
                Manual Override
              </Button>
            </div>
          </div>
        )}

        {/* TAB 2: TRIAGE ASSESSMENT (M5) */}
        {activeTab === 'assessment' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary }}>
                Decision-Support Triage & Severity
              </h3>
              <Button size="xs" variant="primary" loading={assessmentLoading} onClick={handleRunAssessment}>
                Run Assessment
              </Button>
            </div>

            {assessment ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontSize: '11px', color: colors.textSecondary }}>Recommended Priority</span>
                    <Badge variant={assessment.recommended_priority === 'Critical' ? 'danger' : 'warning'}>
                      {assessment.recommended_priority}
                    </Badge>
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textPrimary, lineHeight: 1.4 }}>
                    {assessment.explanation}
                  </div>
                </Card>

                {assessment.required_capabilities?.length > 0 && (
                  <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
                    <div style={{ fontSize: '11px', fontWeight: 700, color: colors.textSecondary, marginBottom: '6px' }}>
                      Required Capabilities:
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {assessment.required_capabilities.map((c) => (
                        <span key={c} style={{ fontSize: '10px', background: '#E2E8F0', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                          {c}
                        </span>
                      ))}
                    </div>
                  </Card>
                )}

                {assessment.missing_information?.length > 0 && (
                  <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', padding: '10px', borderRadius: '6px', fontSize: '11px', color: '#92400E' }}>
                    <strong>Information Gaps:</strong>
                    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                      {assessment.missing_information.map((m, idx) => (
                        <li key={idx}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '24px', color: colors.textSecondary, fontSize: typography.fontSize.xs }}>
                No automated assessment loaded. Click "Run Assessment" above.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: HOSPITAL COORDINATION (M7) */}
        {activeTab === 'hospital' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary }}>
                Receiving Hospital Facilities (M7)
              </h3>
              <Button size="xs" variant="outline" onClick={loadHospitals}>
                Refresh
              </Button>
            </div>

            {hospitalLoading ? (
              <div style={{ textAlign: 'center', padding: '24px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Evaluating hospital capacity and trauma levels...
              </div>
            ) : hospitalsRec.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', border: '1px dashed #CBD5E1', borderRadius: '6px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                No hospital recommendations available.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {hospitalsRec.map((h, idx) => (
                  <Card key={idx} padding="md" style={{ border: `1px solid ${h.is_designated ? colors.primary : colors.border}`, backgroundColor: h.is_designated ? '#F8FAFC' : '#FFFFFF' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                          {h.facility_name}
                        </span>
                        {h.is_designated && (
                          <Badge variant="primary">Designated Intake</Badge>
                        )}
                        {h.has_confirmed && (
                          <Badge variant="success">Confirmed Pre-Arrival</Badge>
                        )}
                      </div>
                      <Badge variant={h.operating_status === 'diverted' || h.divert_status ? 'danger' : 'success'}>
                        {h.operating_status === 'diverted' || h.divert_status ? 'ON DIVERT' : 'OPEN'}
                      </Badge>
                    </div>

                    <div style={{ fontSize: '11px', color: colors.textSecondary, marginBottom: '6px' }}>
                      Trauma: <strong>{h.trauma_level || 'Level 1 Trauma'}</strong> • Travel ETA: <strong>{h.eta_minutes || 10} min</strong> ({h.eta_source || 'OSRM'})
                    </div>

                    <div style={{ fontSize: '11px', color: colors.textSecondary, marginBottom: '8px' }}>
                      ER Bays: <strong>{h.er_beds_available ?? h.available_er_beds ?? 'N/A'}</strong> • ICU: <strong>{h.icu_beds_available ?? 'N/A'}</strong> • Incoming: <strong>{h.incoming_patients_count ?? 0}</strong> • Freshness: <em>{h.capacity_freshness || 'Verified'}</em>
                    </div>

                    {h.routing_warning && (
                      <div style={{ padding: '6px 8px', borderRadius: '4px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', color: '#991B1B', fontSize: '11px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <AlertTriangle size={12} /> {h.routing_warning}
                      </div>
                    )}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px' }}>
                      <Button
                        size="sm"
                        variant={h.requires_override ? 'danger' : 'primary'}
                        disabled={hospitalRouting}
                        onClick={() => handleRouteHospital(h)}
                      >
                        {hospitalRouting ? 'Transmitting...' : (h.requires_override ? 'Manual Override & Route' : 'Route & Send Pre-Arrival Notification')}
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: MULTI-AGENCY COMMAND (M11) */}
        {activeTab === 'multiagency' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary }}>
                Mutual Aid & Partner Agencies (M11)
              </h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {partners.map((p) => (
                <Card key={p.organization_id} padding="md" style={{ border: `1px solid ${colors.border}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                      {p.organization_name}
                    </span>
                    <Badge variant="neutral">{p.agency_type}</Badge>
                  </div>
                  <div style={{ fontSize: '11px', color: colors.textSecondary }}>
                    TAC Radio: <strong>{p.radio_channel || 'DIRECT'}</strong> • Hotline: <strong>{p.dispatch_hotline || '100'}</strong>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: CLINICAL HANDOVER (M8) */}
        {activeTab === 'handover' && (
          <div>
            <h3 style={{ margin: '0 0 12px', fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary }}>
              Digital Clinical Handover (M8)
            </h3>

            {encounters.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', border: '1px dashed #CBD5E1', borderRadius: '6px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                No active clinical encounter submitted for this incident yet. Handover records are populated once paramedics arrive on scene.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {encounters.map((enc) => (
                  <Card key={enc.id} padding="md" style={{ border: `1px solid ${colors.border}` }}>
                    <div style={{ fontSize: typography.fontSize.xs, fontWeight: 700 }}>
                      Encounter #{enc.id} ({enc.status})
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Manual Override Dialog */}
      {showOverrideModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '8px',
              maxWidth: '440px',
              width: '100%',
              padding: '20px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.3)',
            }}
          >
            <h3 style={{ margin: '0 0 8px', fontSize: typography.fontSize.base, fontWeight: 700, color: colors.textPrimary }}>
              Manual Dispatch Override
            </h3>
            <p style={{ margin: '0 0 14px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              You are manually assigning <strong>{selectedCandidate?.resource_code}</strong> despite automated recommendation ranking or eligibility flags. Enter a mandatory audit reason.
            </p>

            <textarea
              required
              rows={3}
              placeholder="e.g. Field commander verbal order; vehicle is in direct visual proximity to scene."
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '6px',
                border: `1px solid ${colors.border}`,
                fontSize: typography.fontSize.xs,
                fontFamily: 'inherit',
                marginBottom: '16px',
                boxSizing: 'border-box',
              }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <Button variant="outline" size="sm" onClick={() => setShowOverrideModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                loading={loading}
                disabled={!overrideReason.trim()}
                onClick={handleManualOverride}
                style={{ backgroundColor: colors.secondary }}
              >
                Confirm Override
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
