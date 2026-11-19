import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  CheckCircle2,
  Clock,
  Shield,
  AlertCircle,
  RefreshCw,
  XCircle,
  MapPin,
  Calendar,
} from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  Alert,
  Modal,
  colors,
  typography,
} from '@careon/design-system';
import {
  TRACKING_LIFECYCLE_STEPS,
} from '@careon/contracts';
import {
  trackPublicIncident,
  getIncidentDetails,
  cancelIncident,
} from '@careon/api-client';
import { useAuth } from '@careon/auth';
import { CitizenGoogleMap } from '../components/CitizenGoogleMap.jsx';

export function TrackIncident({ initialId, onNavigate }) {
  const { user, isAuthenticated } = useAuth();
  const [queryInput, setQueryInput] = useState(initialId || '');
  const [currentId, setCurrentId] = useState(initialId || '');
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Cancellation modal
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('Patient stabilized / assistance no longer needed');
  const [cancelDetails, setCancelDetails] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [cancelSuccess, setCancelSuccess] = useState(null);

  const fetchTracking = useCallback(async (idToTrack) => {
    if (!idToTrack || !idToTrack.trim()) return;
    setLoading(true);
    setError(null);

    const clean = idToTrack.trim();
    try {
      // First attempt public tracking endpoint
      try {
        const pubData = await trackPublicIncident(clean);
        setIncident(pubData);
        setLoading(false);
        return;
      } catch (pubErr) {
        // If not found publicly and authenticated, try direct incident details
        if (isAuthenticated && (clean.startsWith('CARE-') || !isNaN(clean))) {
          const directData = await getIncidentDetails(clean);
          setIncident(directData);
          setLoading(false);
          return;
        }
        throw pubErr;
      }
    } catch (err) {
      setError(
        err.status === 404
          ? 'No emergency record was found for this tracking credential. Please check the code and try again.'
          : err.message || 'Failed to load tracking details.'
      );
      setIncident(null);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (initialId) {
      setCurrentId(initialId);
      setQueryInput(initialId);
      fetchTracking(initialId);
    }
  }, [initialId, fetchTracking]);

  // Periodic polling every 10 seconds for live updates
  useEffect(() => {
    if (!currentId || !incident || incident.status === 'Resolved' || incident.status === 'Cancelled') {
      return;
    }
    const interval = setInterval(() => {
      fetchTracking(currentId);
    }, 10000);
    return () => clearInterval(interval);
  }, [currentId, incident, fetchTracking]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (queryInput.trim()) {
      setCurrentId(queryInput.trim());
      fetchTracking(queryInput.trim());
      if (onNavigate) {
        onNavigate(`/track?id=${encodeURIComponent(queryInput.trim())}`);
      }
    }
  };

  const handleConfirmCancel = async () => {
    if (!incident || !incident.id) {
      setError('Cannot cancel: numerical incident id is not exposed in public view.');
      return;
    }
    setCancelling(true);
    try {
      await cancelIncident(incident.id, cancelReason, cancelDetails);
      setShowCancelModal(false);
      setCancelSuccess('Incident cancellation requested successfully.');
      fetchTracking(currentId);
    } catch (e) {
      setError(e.message || 'Failed to cancel incident.');
    } finally {
      setCancelling(false);
    }
  };

  const currentStepIndex = incident
    ? TRACKING_LIFECYCLE_STEPS.findIndex((step) =>
        step.statuses.includes(incident.status)
      )
    : -1;

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '24px 16px' }}>
      <h1
        style={{
          margin: '0 0 8px',
          fontSize: '1.5rem',
          fontWeight: typography.fontWeight.bold,
          color: colors.textPrimary,
        }}
      >
        Track Emergency Incident
      </h1>
      <p style={{ margin: '0 0 24px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        Monitor real-time status, triage updates, and responder milestones.
      </p>

      {/* Search Bar */}
      <Card padding="md" style={{ marginBottom: '24px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Enter tracking code (e.g. CARE-2026-101 or token)..."
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            style={{
              flex: 1,
              minWidth: '240px',
              padding: '10px 14px',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              fontSize: typography.fontSize.base,
              outline: 'none',
            }}
          />
          <Button type="submit" variant="primary" loading={loading} icon={Search}>
            Track Status
          </Button>
        </form>
      </Card>

      {error && (
        <Alert variant="danger" style={{ marginBottom: '20px' }}>
          {error}
        </Alert>
      )}

      {cancelSuccess && (
        <Alert variant="info" style={{ marginBottom: '20px' }}>
          {cancelSuccess}
        </Alert>
      )}

      {/* Incident Details Card */}
      {incident && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card padding="lg">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                flexWrap: 'wrap',
                gap: '12px',
                borderBottom: `1px solid ${colors.border}`,
                paddingBottom: '16px',
                marginBottom: '20px',
              }}
            >
              <div>
                <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Incident Reference
                </span>
                <h2 style={{ margin: '4px 0 0', fontSize: '1.25rem', color: colors.secondary, fontWeight: typography.fontWeight.bold }}>
                  {incident.incident_code || currentId}
                </h2>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Badge
                  variant={
                    ['Dispatched', 'En Route to Scene', 'At Scene', 'Transporting'].includes(incident.status)
                      ? 'emergency'
                      : ['Resolved'].includes(incident.status)
                      ? 'success'
                      : ['Cancelled', 'Rejected'].includes(incident.status)
                      ? 'neutral'
                      : 'warning'
                  }
                >
                  {incident.status}
                </Badge>
                <Button
                  size="sm"
                  variant="tertiary"
                  onClick={() => fetchTracking(currentId)}
                  icon={RefreshCw}
                  title="Refresh status"
                >
                  Refresh
                </Button>
              </div>
            </div>

            {/* Restrained Step Timeline */}
            <div style={{ marginBottom: '32px' }}>
              <div style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textSecondary, marginBottom: '16px', textTransform: 'uppercase' }}>
                Coordination Progress
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {TRACKING_LIFECYCLE_STEPS.map((step, idx) => {
                  const isDone = currentStepIndex > idx;
                  const isCurrent = currentStepIndex === idx;
                  const isFuture = currentStepIndex < idx;

                  return (
                    <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <div
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: typography.fontSize.xs,
                          fontWeight: typography.fontWeight.bold,
                          backgroundColor: isCurrent
                            ? colors.secondary
                            : isDone
                            ? colors.textPrimary
                            : '#F3F4F6',
                          color: isCurrent || isDone ? colors.primary : colors.textSecondary,
                          marginTop: '2px',
                        }}
                      >
                        {isDone ? '✓' : idx + 1}
                      </div>

                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontSize: typography.fontSize.sm,
                            fontWeight: isCurrent ? typography.fontWeight.bold : typography.fontWeight.medium,
                            color: isCurrent
                              ? colors.secondary
                              : isDone
                              ? colors.textPrimary
                              : colors.textSecondary,
                          }}
                        >
                          {step.label}
                        </div>
                        {isCurrent && (
                          <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
                            Current state: <strong>{incident.status}</strong>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Live Interactive Google Map Tracking View */}
            {incident.latitude && incident.longitude && (
              <div style={{ marginBottom: '24px' }}>
                <div style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textSecondary, marginBottom: '8px', textTransform: 'uppercase' }}>
                  Live GPS Tracking
                </div>
                <CitizenGoogleMap
                  center={{ lat: Number(incident.latitude), lng: Number(incident.longitude) }}
                  zoom={15}
                  height="260px"
                  markers={[
                    {
                      id: 'incident-pin',
                      lat: Number(incident.latitude),
                      lng: Number(incident.longitude),
                      type: 'incident',
                      title: incident.location_name || 'Emergency Incident Site',
                    },
                  ]}
                  helperNotice={`📍 Live Emergency Location • ${incident.incident_code || 'Incident'}`}
                />
              </div>
            )}

            {/* Location & Details Summary */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '16px',
                backgroundColor: colors.surfaceSubtle,
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '20px',
              }}
            >
              <div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>Location</div>
                <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, marginTop: '2px' }}>
                  {incident.location_name}
                </div>
              </div>

              <div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>Emergency Category</div>
                <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, marginTop: '2px' }}>
                  {incident.category}
                </div>
              </div>

              <div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>Priority & Verification</div>
                <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, marginTop: '2px' }}>
                  {incident.priority || 'Standard'} ({incident.is_verified ? 'Verified' : 'Unverified'})
                </div>
              </div>

              <div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>Reported At</div>
                <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, marginTop: '2px' }}>
                  {new Date(incident.created_at).toLocaleString()}
                </div>
              </div>
            </div>

            {/* Public Timeline Updates */}
            {incident.updates && incident.updates.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px', fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                  Public Operational Updates
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {incident.updates.map((up, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '10px 12px',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '6px',
                        fontSize: typography.fontSize.xs,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <strong style={{ color: colors.textPrimary }}>{up.status}</strong>
                        <span style={{ color: colors.textMuted }}>{new Date(up.created_at).toLocaleTimeString()}</span>
                      </div>
                      {up.message && <div style={{ color: colors.textSecondary }}>{up.message}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Incident Cancellation Action */}
            {incident.id && !['Resolved', 'Cancelled', 'Rejected'].includes(incident.status) && (
              <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="sm"
                  variant="tertiary"
                  onClick={() => setShowCancelModal(true)}
                  icon={XCircle}
                >
                  Cancel This Request
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Cancellation Modal */}
      <Modal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title="Cancel Emergency Request"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ margin: 0, fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
            Are you sure you wish to cancel this emergency request? Responders and dispatchers will be notified immediately.
          </p>

          <Input
            label="Reason for Cancellation"
            as="select"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          >
            <option value="Patient stabilized / assistance no longer needed">Patient stabilized / assistance no longer needed</option>
            <option value="Private transport arranged to hospital">Private transport arranged to hospital</option>
            <option value="Reported by mistake">Reported by mistake</option>
            <option value="Duplicate report for same incident">Duplicate report for same incident</option>
            <option value="Other">Other</option>
          </Input>

          <Input
            label="Additional Notes (Optional)"
            as="textarea"
            placeholder="Provide any details..."
            value={cancelDetails}
            onChange={(e) => setCancelDetails(e.target.value)}
          />

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <Button variant="secondary" onClick={() => setShowCancelModal(false)}>
              Keep Active
            </Button>
            <Button
              variant="danger"
              onClick={handleConfirmCancel}
              loading={cancelling}
            >
              Confirm Cancellation
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
