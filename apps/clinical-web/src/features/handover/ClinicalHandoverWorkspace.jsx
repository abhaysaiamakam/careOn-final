import React, { useState } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  History,
  Clock,
  Search,
  RefreshCw,
  UserCheck,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react';
import {
  getHandoverRecord,
  getHandoverVersions,
  actionHandoverRecord,
} from '@careon/api-client';
import { HANDOVER_STATUS_CONFIG, SBAR_SECTIONS } from '@careon/contracts';
import EmptyState from '../../components/EmptyState.jsx';
import ClinicalPatientTimelineView from '../timeline/ClinicalPatientTimelineView.jsx';

export function ClinicalHandoverWorkspace({
  handovers = [],
  loading = false,
  onRefresh,
  onHandoverUpdated,
}) {
  const [selectedHandover, setSelectedHandover] = useState(handovers[0] || null);
  const [searchToken, setSearchToken] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);

  const [versions, setVersions] = useState([]);
  const [showVersionsModal, setShowVersionsModal] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const [timelineEncounterId, setTimelineEncounterId] = useState(null);

  const [clarificationNotes, setClarificationNotes] = useState('');
  const [showClarifyPrompt, setShowClarifyPrompt] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  const handleLookupToken = async (e) => {
    e.preventDefault();
    if (!searchToken.trim()) return;

    setSearchLoading(true);
    setSearchError(null);
    try {
      const record = await getHandoverRecord(searchToken.trim());
      setSelectedHandover(record);
    } catch (err) {
      setSearchError(err?.message || 'Handover record not found.');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAction = async (actionType, payloadNotes = '') => {
    if (!selectedHandover) return;
    setActionLoading(true);
    setActionError(null);

    try {
      const token = selectedHandover.handover_token || selectedHandover.token;
      const res = await actionHandoverRecord(token, actionType, payloadNotes);
      setSelectedHandover(res);
      if (onHandoverUpdated) onHandoverUpdated(res);
      setShowClarifyPrompt(false);
      setClarificationNotes('');
    } catch (err) {
      setActionError(err?.message || `Failed to execute ${actionType} action.`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewVersions = async (token) => {
    setShowVersionsModal(true);
    setVersionsLoading(true);
    try {
      const vers = await getHandoverVersions(token);
      setVersions(Array.isArray(vers) ? vers : vers?.versions || []);
    } catch (err) {
      console.warn('Failed to load handover versions:', err);
    } finally {
      setVersionsLoading(false);
    }
  };

  const currentStatus = selectedHandover?.status || 'submitted';
  const statusCfg = HANDOVER_STATUS_CONFIG[currentStatus] || {
    label: currentStatus,
    color: 'default',
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header bar */}
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
            Clinical Handover & Transfer of Care (SBAR)
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280' }}>
            Authoritative pre-hospital to emergency department clinical continuity records
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <form onSubmit={handleLookupToken} style={{ display: 'flex', gap: '6px' }}>
            <input
              type="text"
              value={searchToken}
              onChange={(e) => setSearchToken(e.target.value)}
              placeholder="Lookup by Handover Token..."
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #D1D5DB',
                fontSize: '13px',
                width: '220px',
              }}
            />
            <button
              type="submit"
              disabled={searchLoading}
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                backgroundColor: '#111827',
                color: '#FFFFFF',
                border: 'none',
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Search size={14} />
              <span>Lookup</span>
            </button>
          </form>

          <button
            onClick={onRefresh}
            title="Refresh handovers"
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
            <span>Sync</span>
          </button>
        </div>
      </div>

      {searchError && (
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
          {searchError}
        </div>
      )}

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

      {/* Main Content: If no handovers exist and none selected */}
      {handovers.length === 0 && !selectedHandover && !loading ? (
        <EmptyState
          icon="file"
          title="No Pending Clinical Handovers"
          message="No pre-hospital SBAR digital handovers are currently awaiting review or transfer of care at this facility."
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
              <span>Poll Handover Registry</span>
            </button>
          }
        />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: handovers.length > 1 ? '1fr 2fr' : '1fr',
            gap: '20px',
            alignItems: 'start',
          }}
        >
          {/* Handovers selector if multiple */}
          {handovers.length > 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {handovers.map((ho) => {
                const isSelected = selectedHandover?.id === ho.id;
                return (
                  <div
                    key={ho.id || ho.handover_token}
                    onClick={() => setSelectedHandover(ho)}
                    style={{
                      padding: '14px',
                      borderRadius: '8px',
                      backgroundColor: '#FFFFFF',
                      border: isSelected ? '2px solid #D92D3A' : '1px solid #E5E7EB',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '13px', fontWeight: 700, color: '#111827' }}>
                        Token: {ho.handover_token || ho.token}
                      </span>
                      <span style={{ fontSize: '11px', color: '#6B7280' }}>
                        Encounter #{ho.encounter_id}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: '#4B5563' }}>
                      Status: <strong>{ho.status}</strong>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* SBAR Workspace for Selected Handover */}
          {selectedHandover && (
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                border: '1px solid #E5E7EB',
                padding: '24px',
                boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
              }}
            >
              {/* Record Summary Banner */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '20px',
                  paddingBottom: '16px',
                  borderBottom: '1px solid #F3F4F6',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '18px', fontWeight: 700, color: '#111827' }}>
                      Handover: {selectedHandover.handover_token || selectedHandover.token}
                    </span>
                    <span
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        backgroundColor: '#EFF6FF',
                        color: '#1D4ED8',
                        padding: '2px 8px',
                        borderRadius: '9999px',
                      }}
                    >
                      {statusCfg.label}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '2px' }}>
                    Encounter ID: <strong>{selectedHandover.encounter_id}</strong> • Version: {selectedHandover.version || 1}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    onClick={() => setTimelineEncounterId(selectedHandover.encounter_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      backgroundColor: '#F9FAFB',
                      border: '1px solid #E5E7EB',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: '#374151',
                      cursor: 'pointer',
                    }}
                  >
                    <Clock size={14} />
                    <span>Encounter Timeline</span>
                  </button>

                  <button
                    onClick={() => handleViewVersions(selectedHandover.handover_token || selectedHandover.token)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      backgroundColor: '#F9FAFB',
                      border: '1px solid #E5E7EB',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: '#374151',
                      cursor: 'pointer',
                    }}
                  >
                    <History size={14} />
                    <span>Audit Versions</span>
                  </button>
                </div>
              </div>

              {/* SBAR 4-Quadrant View */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
                {/* Situation */}
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    backgroundColor: '#FEF2F2',
                    border: '1px solid #FEE2E2',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#991B1B', marginBottom: '6px' }}>
                    S — Situation
                  </div>
                  <div style={{ fontSize: '13px', color: '#1F2937', lineHeight: 1.5 }}>
                    {selectedHandover.situation ||
                      selectedHandover.summary?.situation ||
                      'Chief complaint: Acute medical incident en route.'}
                  </div>
                </div>

                {/* Background */}
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    backgroundColor: '#F0FDF4',
                    border: '1px solid #DCFCE7',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#166534', marginBottom: '6px' }}>
                    B — Background
                  </div>
                  <div style={{ fontSize: '13px', color: '#1F2937', lineHeight: 1.5 }}>
                    {selectedHandover.background ||
                      selectedHandover.summary?.background ||
                      'Past medical history, allergies, and baseline vitals.'}
                  </div>
                </div>

                {/* Assessment */}
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    backgroundColor: '#EFF6FF',
                    border: '1px solid #DBEAFE',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#1E40AF', marginBottom: '6px' }}>
                    A — Assessment (ABCDE & Vitals)
                  </div>
                  <div style={{ fontSize: '13px', color: '#1F2937', lineHeight: 1.5 }}>
                    {selectedHandover.assessment ||
                      selectedHandover.summary?.assessment ||
                      'Vital signs trends and clinical examination findings.'}
                  </div>
                </div>

                {/* Recommendation */}
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    backgroundColor: '#FFFBEB',
                    border: '1px solid #FEF3C7',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#92400E', marginBottom: '6px' }}>
                    R — Recommendation & Bed Destination
                  </div>
                  <div style={{ fontSize: '13px', color: '#1F2937', lineHeight: 1.5 }}>
                    {selectedHandover.recommendation ||
                      selectedHandover.summary?.recommendation ||
                      'Immediate stabilization, pending radiology scans, and target care unit.'}
                  </div>
                </div>
              </div>

              {/* Handover Actions for Attending Clinician */}
              <div style={{ borderTop: '1px solid #F3F4F6', paddingTop: '20px' }}>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#111827', marginBottom: '12px' }}>
                  Clinical Transfer of Care Signoff
                </div>

                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  {/* Receive action */}
                  <button
                    onClick={() => handleAction('receive')}
                    disabled={actionLoading || currentStatus !== 'submitted'}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '6px',
                      backgroundColor: '#EFF6FF',
                      border: '1px solid #BFDBFE',
                      color: '#1E40AF',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: currentStatus === 'submitted' ? 'pointer' : 'not-allowed',
                      opacity: currentStatus === 'submitted' ? 1 : 0.5,
                    }}
                  >
                    1. Mark Received
                  </button>

                  {/* Acknowledge action */}
                  <button
                    onClick={() => handleAction('acknowledge')}
                    disabled={actionLoading || (currentStatus !== 'received' && currentStatus !== 'submitted')}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '6px',
                      backgroundColor: '#FEF3C7',
                      border: '1px solid #FCD34D',
                      color: '#92400E',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    2. Acknowledge Handover
                  </button>

                  {/* Clarification action */}
                  <button
                    onClick={() => setShowClarifyPrompt(!showClarifyPrompt)}
                    disabled={actionLoading || currentStatus === 'completed'}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '6px',
                      backgroundColor: '#F3F4F6',
                      border: '1px solid #D1D5DB',
                      color: '#374151',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Request Clarification
                  </button>

                  {/* Complete Transfer of Care */}
                  <button
                    onClick={() => handleAction('complete')}
                    disabled={actionLoading || currentStatus === 'completed'}
                    style={{
                      padding: '10px 20px',
                      borderRadius: '6px',
                      backgroundColor: '#16845B',
                      border: 'none',
                      color: '#FFFFFF',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: currentStatus !== 'completed' ? 'pointer' : 'not-allowed',
                      opacity: currentStatus === 'completed' ? 0.6 : 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>{currentStatus === 'completed' ? 'Care Transfer Complete' : 'Complete Transfer of Care'}</span>
                  </button>
                </div>

                {/* Clarification prompt */}
                {showClarifyPrompt && (
                  <div style={{ marginTop: '16px', padding: '14px', backgroundColor: '#FFFBEB', borderRadius: '8px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#92400E', marginBottom: '6px' }}>
                      Clinical Clarification Query for Field Crew
                    </label>
                    <textarea
                      value={clarificationNotes}
                      onChange={(e) => setClarificationNotes(e.target.value)}
                      placeholder="Specify questions regarding administered medications, airway status, or incident timeline..."
                      rows={2}
                      style={{
                        width: '100%',
                        padding: '8px',
                        borderRadius: '6px',
                        border: '1px solid #FCD34D',
                        fontSize: '13px',
                        marginBottom: '8px',
                      }}
                    />
                    <button
                      onClick={() => handleAction('clarify', clarificationNotes)}
                      disabled={actionLoading || !clarificationNotes.trim()}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '6px',
                        backgroundColor: '#D99022',
                        color: '#FFFFFF',
                        border: 'none',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Transmit Clarification Query
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Version history modal */}
      {showVersionsModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(17, 24, 39, 0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '16px',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              width: '100%',
              maxWidth: '560px',
              maxHeight: '80vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderBottom: '1px solid #E5E7EB',
              }}
            >
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
                Handover Version Audit Log
              </h3>
              <button
                onClick={() => setShowVersionsModal(false)}
                style={{ background: 'none', border: 'none', color: '#9CA3AF', cursor: 'pointer' }}
              >
                Close
              </button>
            </div>
            <div style={{ padding: '20px', overflowY: 'auto' }}>
              {versionsLoading && <div style={{ fontSize: '13px', color: '#6B7280' }}>Loading versions...</div>}
              {!versionsLoading && versions.length === 0 && (
                <div style={{ fontSize: '13px', color: '#6B7280' }}>No version history recorded yet.</div>
              )}
              {versions.map((v, i) => (
                <div
                  key={v.id || i}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    border: '1px solid #E5E7EB',
                    marginBottom: '8px',
                    fontSize: '13px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                    <span>Version {v.version_number || v.version || i + 1}</span>
                    <span style={{ color: '#6B7280', fontSize: '11px' }}>
                      {v.created_at ? new Date(v.created_at).toLocaleString() : '—'}
                    </span>
                  </div>
                  <div style={{ color: '#4B5563', marginTop: '4px' }}>
                    {v.correction_reason || v.notes || 'Amended clinical observation.'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Encounter timeline modal */}
      {timelineEncounterId && (
        <ClinicalPatientTimelineView
          encounterId={timelineEncounterId}
          isOpen={!!timelineEncounterId}
          onClose={() => setTimelineEncounterId(null)}
        />
      )}
    </div>
  );
}

export default ClinicalHandoverWorkspace;
