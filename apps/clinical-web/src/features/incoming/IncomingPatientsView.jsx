import React, { useState } from 'react';
import {
  Radio,
  Clock,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Bed,
  RefreshCw,
  UserCheck,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import {
  respondIncomingPatientRequest,
  cancelIncomingPatientRequest,
} from '@careon/api-client';
import { INCOMING_REQUEST_STATUS_CONFIG } from '@careon/contracts';
import EmptyState from '../../components/EmptyState.jsx';
import PatientArrivalTriageModal from '../arrival/PatientArrivalTriageModal.jsx';

export function IncomingPatientsView({
  facility,
  incomingRequests = [],
  incomingTransports = [],
  loading = false,
  onRefresh,
  onRequestUpdated,
}) {
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [arrivalModalIncident, setArrivalModalIncident] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  // Modal / Prompt states for Decline & Clarify
  const [declineReason, setDeclineReason] = useState('');
  const [showDeclineForm, setShowDeclineForm] = useState(false);
  const [clarificationNotes, setClarificationNotes] = useState('');
  const [showClarifyForm, setShowClarifyForm] = useState(false);

  // Combine pre-arrival requests and incoming transports
  const totalIncomingCount = incomingRequests.length + incomingTransports.length;

  const handleAcknowledge = async (req) => {
    setActionLoading(true);
    setActionError(null);
    try {
      const token = req.request_token;
      const res = await respondIncomingPatientRequest(token, { action: 'acknowledge' });
      if (onRequestUpdated) onRequestUpdated(res);
      setSelectedRequest((prev) => (prev?.id === req.id ? { ...prev, status: 'acknowledged' } : prev));
    } catch (err) {
      setActionError(err?.message || 'Failed to acknowledge incoming patient.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAccept = async (req, bedType = 'emergency') => {
    setActionLoading(true);
    setActionError(null);
    try {
      const token = req.request_token;
      const res = await respondIncomingPatientRequest(token, {
        action: 'accept',
        reserve_er_bed: bedType === 'emergency',
        reserve_trauma_bay: bedType === 'trauma',
        reserve_icu_bed: bedType === 'icu',
      });
      if (onRequestUpdated) onRequestUpdated(res);
      setSelectedRequest((prev) => (prev?.id === req.id ? { ...prev, status: 'accepted' } : prev));
    } catch (err) {
      setActionError(err?.message || 'Failed to accept patient request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeclineSubmit = async (req) => {
    if (!declineReason || declineReason.trim().length < 3) {
      setActionError('A valid decline reason (minimum 3 characters) is mandatory.');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      const token = req.request_token;
      const res = await respondIncomingPatientRequest(token, {
        action: 'decline',
        reason: declineReason.trim(),
      });
      if (onRequestUpdated) onRequestUpdated(res);
      setShowDeclineForm(false);
      setDeclineReason('');
      setSelectedRequest((prev) => (prev?.id === req.id ? { ...prev, status: 'declined' } : prev));
    } catch (err) {
      setActionError(err?.message || 'Failed to decline patient request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClarifySubmit = async (req) => {
    if (!clarificationNotes || clarificationNotes.trim().length < 3) {
      setActionError('Clarification notes (minimum 3 characters) are mandatory.');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      const token = req.request_token;
      const res = await respondIncomingPatientRequest(token, {
        action: 'clarify',
        clarification_notes: clarificationNotes.trim(),
      });
      if (onRequestUpdated) onRequestUpdated(res);
      setShowClarifyForm(false);
      setClarificationNotes('');
      setSelectedRequest((prev) => (prev?.id === req.id ? { ...prev, status: 'clarifying' } : prev));
    } catch (err) {
      setActionError(err?.message || 'Failed to request clarification.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: '#111827' }}>
            Incoming Ambulances & Pre-Arrival Requests
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280' }}>
            Authoritative pre-arrival hospital notification queue and bed reservation workflow
          </p>
        </div>

        <button
          onClick={onRefresh}
          title="Refresh incoming requests"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: '6px',
            backgroundColor: '#FFFFFF',
            border: '1px solid #E5E7EB',
            fontSize: '13px',
            fontWeight: 500,
            color: '#374151',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} className={loading ? 'clinical-pulse' : ''} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {actionError && (
        <div
          style={{
            padding: '12px',
            borderRadius: '6px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            color: '#991B1B',
            fontSize: '13px',
            marginBottom: '18px',
          }}
        >
          {actionError}
        </div>
      )}

      {/* Main Content: If zero incoming requests, render Truthful EmptyState */}
      {totalIncomingCount === 0 && !loading ? (
        <EmptyState
          icon="inbox"
          title="No Incoming Patients at This Time"
          message="There are no active ambulance transports en-route or pending pre-arrival bed requests for this facility in the central database."
          action={
            <button
              onClick={onRefresh}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                backgroundColor: '#D92D3A',
                color: '#FFFFFF',
                borderRadius: '6px',
                border: 'none',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={14} />
              <span>Poll Real-Time Queue</span>
            </button>
          }
        />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: selectedRequest ? '1.2fr 1.8fr' : '1fr',
            gap: '20px',
            alignItems: 'start',
          }}
        >
          {/* List of Requests */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Active En-Route Transports (M3) */}
            {incomingTransports.map((transport) => {
              const incidentId = transport.incident_id || transport.id;
              return (
                <div
                  key={`transport-${incidentId}`}
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px',
                    padding: '16px',
                    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Radio size={16} color="#D92D3A" className="clinical-pulse" />
                      <span style={{ fontSize: '14px', fontWeight: 700, color: '#111827' }}>
                        Incident #{incidentId}
                      </span>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          backgroundColor: '#EFF6FF',
                          color: '#1D4ED8',
                          padding: '2px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        En-Route Transport
                      </span>
                    </div>

                    <button
                      onClick={() => setArrivalModalIncident(transport)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        backgroundColor: '#16845B',
                        color: '#FFFFFF',
                        border: 'none',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <CheckCircle2 size={14} />
                      <span>Confirm Intake Arrival</span>
                    </button>
                  </div>

                  <div style={{ fontSize: '13px', color: '#4B5563', marginBottom: '8px' }}>
                    <strong>Vehicle / Unit:</strong> {transport.vehicle_id || transport.unit_id || 'Ambulance'} •{' '}
                    <strong>Status:</strong> {transport.status || 'Transporting'}
                  </div>
                </div>
              );
            })}

            {/* Pre-Arrival Requests (M7) */}
            {incomingRequests.map((req) => {
              const statusCfg = INCOMING_REQUEST_STATUS_CONFIG[req.status] || {
                label: req.status,
                bg: '#F3F4F6',
                text: '#374151',
              };
              const isSelected = selectedRequest?.id === req.id;

              return (
                <div
                  key={`req-${req.id}`}
                  onClick={() => setSelectedRequest(req)}
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: isSelected ? '2px solid #D92D3A' : '1px solid #E5E7EB',
                    borderRadius: '8px',
                    padding: '16px',
                    cursor: 'pointer',
                    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                    transition: 'border-color 0.15s ease',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '10px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 700, color: '#111827' }}>
                        Incident #{req.incident_id}
                      </span>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor:
                            req.emergency_severity === 'P1' || req.emergency_severity === 'Critical'
                              ? '#FEE2E2'
                              : '#FEF3C7',
                          color:
                            req.emergency_severity === 'P1' || req.emergency_severity === 'Critical'
                              ? '#991B1B'
                              : '#92400E',
                          padding: '2px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        {req.emergency_severity || 'P2'}
                      </span>
                    </div>

                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        backgroundColor: statusCfg.bg,
                        color: statusCfg.text,
                        padding: '2px 8px',
                        borderRadius: '9999px',
                      }}
                    >
                      {statusCfg.label}
                    </span>
                  </div>

                  <div style={{ fontSize: '13px', color: '#4B5563', marginBottom: '8px' }}>
                    {req.patient_condition_summary || 'Chief complaint not specified in dispatch dispatch'}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '12px',
                      color: '#6B7280',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={13} />
                      <span>
                        ETA: <strong>{req.eta_minutes != null ? `${Math.round(req.eta_minutes)} mins` : 'Pending'}</strong>
                      </span>
                    </div>
                    <ChevronRight size={16} color="#9CA3AF" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Request Detail Drawer */}
          {selectedRequest && (
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
                padding: '24px',
                boxShadow: '0 2px 4px 0 rgba(0, 0, 0, 0.05)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '16px',
                  borderBottom: '1px solid #F3F4F6',
                  paddingBottom: '12px',
                }}
              >
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
                    Incoming Patient Detail
                  </h3>
                  <div style={{ fontSize: '12px', color: '#6B7280' }}>
                    Token: {selectedRequest.request_token}
                  </div>
                </div>
                <button
                  onClick={() => setSelectedRequest(null)}
                  style={{
                    background: 'none',
                    border: 'none',
                    fontSize: '13px',
                    color: '#6B7280',
                    cursor: 'pointer',
                  }}
                >
                  Close
                </button>
              </div>

              {/* Data fields */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
                <div>
                  <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                    Incident Reference
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>
                    #{selectedRequest.incident_id}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                    Triage Acuity
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#D92D3A' }}>
                    {selectedRequest.emergency_severity}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                    Estimated Arrival (ETA)
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>
                    {selectedRequest.eta_minutes != null ? `${selectedRequest.eta_minutes} minutes` : 'In Transit'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                    Deadline
                  </div>
                  <div style={{ fontSize: '13px', color: '#111827' }}>
                    {selectedRequest.acknowledgement_deadline
                      ? new Date(selectedRequest.acknowledgement_deadline).toLocaleTimeString()
                      : 'Active'}
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <div style={{ fontSize: '11px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600, marginBottom: '4px' }}>
                  Clinical Condition Summary
                </div>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    backgroundColor: '#F9FAFB',
                    border: '1px solid #E5E7EB',
                    fontSize: '13px',
                    color: '#374151',
                    lineHeight: 1.5,
                  }}
                >
                  {selectedRequest.patient_condition_summary || 'No pre-arrival clinical summary recorded.'}
                </div>
              </div>

              {/* Action Buttons for Clinical Staff */}
              <div style={{ borderTop: '1px solid #F3F4F6', paddingTop: '18px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '10px' }}>
                  Hospital Response Protocol
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {/* Acknowledge Button */}
                  {selectedRequest.status === 'pending' && (
                    <button
                      onClick={() => handleAcknowledge(selectedRequest)}
                      disabled={actionLoading}
                      style={{
                        padding: '10px',
                        borderRadius: '6px',
                        backgroundColor: '#EFF6FF',
                        border: '1px solid #BFDBFE',
                        color: '#1E40AF',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      <UserCheck size={16} />
                      <span>Acknowledge Notification</span>
                    </button>
                  )}

                  {/* Accept & Reserve Bed Options */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <button
                      onClick={() => handleAccept(selectedRequest, 'emergency')}
                      disabled={actionLoading || selectedRequest.status === 'accepted'}
                      style={{
                        padding: '10px',
                        borderRadius: '6px',
                        backgroundColor: '#16845B',
                        border: 'none',
                        color: '#FFFFFF',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: actionLoading ? 'not-allowed' : 'pointer',
                        opacity: selectedRequest.status === 'accepted' ? 0.6 : 1,
                      }}
                    >
                      Accept & Reserve ED Bed
                    </button>
                    <button
                      onClick={() => handleAccept(selectedRequest, 'trauma')}
                      disabled={actionLoading || selectedRequest.status === 'accepted'}
                      style={{
                        padding: '10px',
                        borderRadius: '6px',
                        backgroundColor: '#D92D3A',
                        border: 'none',
                        color: '#FFFFFF',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: actionLoading ? 'not-allowed' : 'pointer',
                        opacity: selectedRequest.status === 'accepted' ? 0.6 : 1,
                      }}
                    >
                      Accept & Reserve Trauma Bay
                    </button>
                  </div>

                  {/* Clarify & Decline actions */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                    <button
                      onClick={() => {
                        setShowClarifyForm(!showClarifyForm);
                        setShowDeclineForm(false);
                      }}
                      disabled={actionLoading}
                      style={{
                        padding: '8px',
                        borderRadius: '6px',
                        backgroundColor: '#FEF3C7',
                        border: '1px solid #FCD34D',
                        color: '#92400E',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Request Clarification
                    </button>

                    <button
                      onClick={() => {
                        setShowDeclineForm(!showDeclineForm);
                        setShowClarifyForm(false);
                      }}
                      disabled={actionLoading}
                      style={{
                        padding: '8px',
                        borderRadius: '6px',
                        backgroundColor: '#FEE2E2',
                        border: '1px solid #FCA5A5',
                        color: '#991B1B',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Decline Transport
                    </button>
                  </div>

                  {/* Clarify Form inline */}
                  {showClarifyForm && (
                    <div style={{ marginTop: '12px', padding: '12px', backgroundColor: '#FFFBEB', borderRadius: '6px' }}>
                      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#92400E', marginBottom: '4px' }}>
                        Clarification Query for Paramedics
                      </label>
                      <textarea
                        value={clarificationNotes}
                        onChange={(e) => setClarificationNotes(e.target.value)}
                        placeholder="Inquire regarding airway status, IV access, anticoagulation history..."
                        rows={2}
                        style={{
                          width: '100%',
                          padding: '8px',
                          borderRadius: '4px',
                          border: '1px solid #FCD34D',
                          fontSize: '12px',
                          marginBottom: '8px',
                        }}
                      />
                      <button
                        onClick={() => handleClarifySubmit(selectedRequest)}
                        disabled={actionLoading}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '4px',
                          backgroundColor: '#D99022',
                          color: '#FFFFFF',
                          border: 'none',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Transmit Query
                      </button>
                    </div>
                  )}

                  {/* Decline Form inline */}
                  {showDeclineForm && (
                    <div style={{ marginTop: '12px', padding: '12px', backgroundColor: '#FEF2F2', borderRadius: '6px' }}>
                      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#991B1B', marginBottom: '4px' }}>
                        Mandatory Operational Decline Reason
                      </label>
                      <textarea
                        value={declineReason}
                        onChange={(e) => setDeclineReason(e.target.value)}
                        placeholder="CT scanner failure, trauma team fully committed, diversion active..."
                        rows={2}
                        style={{
                          width: '100%',
                          padding: '8px',
                          borderRadius: '4px',
                          border: '1px solid #FCA5A5',
                          fontSize: '12px',
                          marginBottom: '8px',
                        }}
                      />
                      <button
                        onClick={() => handleDeclineSubmit(selectedRequest)}
                        disabled={actionLoading}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '4px',
                          backgroundColor: '#D92D3A',
                          color: '#FFFFFF',
                          border: 'none',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Submit Mandatory Decline
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Arrival intake confirmation modal */}
      {arrivalModalIncident && (
        <PatientArrivalTriageModal
          incident={arrivalModalIncident}
          isOpen={!!arrivalModalIncident}
          onClose={() => setArrivalModalIncident(null)}
          onArrivalConfirmed={() => {
            setArrivalModalIncident(null);
            if (onRefresh) onRefresh();
          }}
        />
      )}
    </div>
  );
}

export default IncomingPatientsView;
