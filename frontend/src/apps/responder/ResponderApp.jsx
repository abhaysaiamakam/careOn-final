import React, { useState, useEffect } from 'react';
import { responderApi } from '../../packages/api-client';
import useAuth from '../../auth/useAuth';
import {
  Navigation,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
  AlertOctagon,
  Phone,
  Shield,
  Radio,
  Send,
  Users,
  Ambulance,
  RefreshCw,
} from 'lucide-react';

export default function ResponderApp() {
  const { user, isAuthenticated } = useAuth();
  const [profile, setProfile] = useState(null);
  const [missions, setMissions] = useState([]);
  const [activeMission, setActiveMission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [gpsActive, setGpsActive] = useState(true);
  const [lastGpsSync, setLastGpsSync] = useState(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const profData = await responderApi.getProfile();
      setProfile(profData);
      setActiveMission(profData.active_mission || null);

      const mData = await responderApi.getMissions();
      setMissions(Array.isArray(mData) ? mData : []);
    } catch (err) {
      setError(err.message || 'Failed to load responder operational data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, []);

  // Periodic simulated or live GPS telemetry
  useEffect(() => {
    if (!gpsActive || !profile?.assigned_resource) return;

    const pushLocation = async () => {
      try {
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            async (pos) => {
              await responderApi.sendTelemetry(pos.coords.latitude, pos.coords.longitude, pos.coords.speed);
              setLastGpsSync(new Date().toLocaleTimeString());
            },
            async () => {
              // Fallback to slight jitter around current resource coordinates for dev
              const lat = profile.assigned_resource.latitude + (Math.random() - 0.5) * 0.001;
              const lon = profile.assigned_resource.longitude + (Math.random() - 0.5) * 0.001;
              await responderApi.sendTelemetry(lat, lon);
              setLastGpsSync(new Date().toLocaleTimeString());
            }
          );
        }
      } catch (err) {
        // non-blocking
      }
    };

    pushLocation();
    const gpsInterval = setInterval(pushLocation, 20000);
    return () => clearInterval(gpsInterval);
  }, [gpsActive, profile]);

  const handleAccept = async (assignmentId) => {
    try {
      setIsUpdating(true);
      const res = await responderApi.acceptMission(assignmentId);
      setActiveMission(res);
      await loadData();
    } catch (err) {
      alert(`Could not accept mission: ${err.message}`);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleReject = async () => {
    if (!activeMission) return;
    try {
      setIsUpdating(true);
      await responderApi.rejectMission(activeMission.id, rejectReason || 'Unit unavailable');
      setRejectModalOpen(false);
      setRejectReason('');
      setActiveMission(null);
      await loadData();
    } catch (err) {
      alert(`Could not reject mission: ${err.message}`);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleStatusAdvance = async (newStatus, notes = '') => {
    if (!activeMission) return;
    try {
      setIsUpdating(true);
      const updated = await responderApi.updateStatus(activeMission.id, newStatus, notes);
      if (newStatus === 'Completed') {
        setActiveMission(null);
      } else {
        setActiveMission(updated);
      }
      await loadData();
    } catch (err) {
      alert(`Could not update mission status: ${err.message}`);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div style={{
      maxWidth: '600px',
      margin: '0 auto',
      minHeight: '100vh',
      backgroundColor: '#090d16',
      color: '#f8fafc',
      padding: '16px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Mobile Top App Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        backgroundColor: '#111827',
        borderRadius: '12px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        marginBottom: '16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: '#ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}>
            <Ambulance size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {profile?.assigned_resource?.code || 'UNIT-01'}
              <span style={{
                fontSize: '0.7rem',
                backgroundColor: 'rgba(16, 185, 129, 0.2)',
                color: '#34d399',
                padding: '2px 8px',
                borderRadius: '999px',
                fontWeight: 600,
              }}>
                ON DUTY
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              {profile?.user?.name || user?.name || 'Field Responder'} • {profile?.assigned_resource?.name || 'Emergency Unit'}
            </div>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          style={{
            backgroundColor: '#1f2937',
            border: 'none',
            color: '#94a3b8',
            padding: '8px',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* GPS Status Pill */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 14px',
        backgroundColor: '#0f172a',
        borderRadius: '8px',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        fontSize: '0.8rem',
        marginBottom: '16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8' }}>
          <Radio size={14} />
          <span>Telemetry Active: {lastGpsSync ? `Synced at ${lastGpsSync}` : 'Sharing coordinates'}</span>
        </div>
        <button
          onClick={() => setGpsActive(!gpsActive)}
          style={{
            background: 'none',
            border: 'none',
            color: gpsActive ? '#34d399' : '#94a3b8',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {gpsActive ? 'GPS ON' : 'GPS PAUSED'}
        </button>
      </div>

      {/* Active Mission Alert Section */}
      {activeMission ? (
        <div style={{
          backgroundColor: '#131c2e',
          borderRadius: '16px',
          border: '2px solid #ef4444',
          boxShadow: '0 0 24px rgba(239, 68, 68, 0.25)',
          padding: '20px',
          marginBottom: '20px',
        }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{
                backgroundColor: '#ef4444',
                color: '#fff',
                fontSize: '0.75rem',
                fontWeight: 800,
                padding: '4px 8px',
                borderRadius: '6px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}>
                DISPATCH MISSION
              </span>
              <h2 style={{ margin: '8px 0 2px 0', fontSize: '1.25rem', fontWeight: 800 }}>
                {activeMission.title}
              </h2>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                Incident: {activeMission.incident_code} • {activeMission.category}
              </div>
            </div>
            <span style={{
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '0.75rem',
              fontWeight: 700,
            }}>
              {activeMission.priority}
            </span>
          </div>

          {/* Location details */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#1e293b',
            padding: '10px 14px',
            borderRadius: '10px',
            marginBottom: '14px',
            fontSize: '0.85rem',
          }}>
            <MapPin size={18} style={{ color: '#ef4444', flexShrink: 0 }} />
            <div style={{ flex: 1, fontWeight: 600 }}>{activeMission.location_name}</div>
            <a
              href={`https://maps.google.com/?q=${activeMission.latitude},${activeMission.longitude}`}
              target="_blank"
              rel="noreferrer"
              style={{
                color: '#38bdf8',
                fontSize: '0.75rem',
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              NAVIGATE →
            </a>
          </div>

          {/* Mission description */}
          <div style={{
            backgroundColor: 'rgba(0,0,0,0.2)',
            padding: '12px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            color: '#cbd5e1',
            marginBottom: '16px',
            lineHeight: 1.4,
          }}>
            <p style={{ margin: '0 0 6px 0', fontWeight: 600 }}>Situation:</p>
            {activeMission.description}
            <div style={{ marginTop: '8px', fontSize: '0.75rem', color: '#94a3b8' }}>
              Required: {activeMission.help_required} • {activeMission.affected_people} affected
            </div>
          </div>

          {/* Mission Status Timeline */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '8px', fontWeight: 600 }}>
              CURRENT MISSION STAGE: <span style={{ color: '#38bdf8' }}>{activeMission.status.toUpperCase()}</span>
            </div>
            <div style={{ display: 'flex', gap: '4px', height: '6px', borderRadius: '3px', overflow: 'hidden', backgroundColor: '#334155' }}>
              <div style={{ flex: 1, backgroundColor: ['Active', 'Accepted', 'En Route', 'On Scene', 'Transporting', 'Completed'].includes(activeMission.status) ? '#10b981' : '#334155' }} />
              <div style={{ flex: 1, backgroundColor: ['Accepted', 'En Route', 'On Scene', 'Transporting', 'Completed'].includes(activeMission.status) ? '#10b981' : '#334155' }} />
              <div style={{ flex: 1, backgroundColor: ['En Route', 'On Scene', 'Transporting', 'Completed'].includes(activeMission.status) ? '#10b981' : '#334155' }} />
              <div style={{ flex: 1, backgroundColor: ['On Scene', 'Transporting', 'Completed'].includes(activeMission.status) ? '#10b981' : '#334155' }} />
              <div style={{ flex: 1, backgroundColor: ['Transporting', 'Completed'].includes(activeMission.status) ? '#10b981' : '#334155' }} />
            </div>
          </div>

          {/* Lifecycle Action Buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeMission.status === 'Active' && (
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => handleAccept(activeMission.id)}
                  disabled={isUpdating}
                  style={{
                    flex: 2,
                    backgroundColor: '#10b981',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '14px',
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                >
                  <CheckCircle2 size={18} /> ACCEPT MISSION
                </button>
                <button
                  onClick={() => setRejectModalOpen(true)}
                  disabled={isUpdating}
                  style={{
                    flex: 1,
                    backgroundColor: '#1f2937',
                    color: '#f87171',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '10px',
                    padding: '14px',
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  DECLINE
                </button>
              </div>
            )}

            {activeMission.status === 'Accepted' && (
              <button
                onClick={() => handleStatusAdvance('En Route')}
                disabled={isUpdating}
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '14px',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <Navigation size={18} /> START MOVING: EN ROUTE
              </button>
            )}

            {activeMission.status === 'En Route' && (
              <button
                onClick={() => handleStatusAdvance('On Scene')}
                disabled={isUpdating}
                style={{
                  backgroundColor: '#f59e0b',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '14px',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <MapPin size={18} /> ARRIVED ON SCENE
              </button>
            )}

            {activeMission.status === 'On Scene' && (
              <button
                onClick={() => handleStatusAdvance('Transporting')}
                disabled={isUpdating}
                style={{
                  backgroundColor: '#8b5cf6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '14px',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <Ambulance size={18} /> TRANSPORTING TO HOSPITAL
              </button>
            )}

            {activeMission.status === 'Transporting' && (
              <button
                onClick={() => handleStatusAdvance('Completed', 'Handover acknowledged')}
                disabled={isUpdating}
                style={{
                  backgroundColor: '#10b981',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '14px',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <CheckCircle2 size={18} /> HANDOVER COMPLETE / CLEAR
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          backgroundColor: '#111827',
          borderRadius: '16px',
          border: '1px dashed rgba(255, 255, 255, 0.1)',
          padding: '40px 20px',
          textAlign: 'center',
          marginBottom: '24px',
        }}>
          <CheckCircle2 size={44} style={{ color: '#10b981', margin: '0 auto 12px auto' }} />
          <h3 style={{ margin: '0 0 6px 0', fontSize: '1.1rem', fontWeight: 700 }}>
            No Active Dispatch Missions
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
            Unit is in service and standing by for emergency dispatch assignments.
          </p>
        </div>
      )}

      {/* Decline Reason Modal */}
      {rejectModalOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: '#1e293b',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '400px',
            width: '100%',
          }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', fontWeight: 700 }}>
              Decline Emergency Dispatch
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 16px 0' }}>
              Please provide the operational reason why this unit cannot acknowledge:
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Mechanical issue, road block, out of medical oxygen..."
              style={{
                width: '100%',
                height: '80px',
                backgroundColor: '#0f172a',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                color: '#fff',
                padding: '10px',
                fontSize: '0.85rem',
                marginBottom: '16px',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setRejectModalOpen(false)}
                style={{
                  backgroundColor: 'transparent',
                  color: '#94a3b8',
                  border: 'none',
                  padding: '8px 14px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                style={{
                  backgroundColor: '#ef4444',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px 16px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Confirm Decline
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Recent Missions Log */}
      <div>
        <h4 style={{ margin: '0 0 12px 0', fontSize: '0.9rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Mission Log & Assignments
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {missions.map((m) => (
            <div
              key={m.id}
              style={{
                backgroundColor: '#111827',
                borderRadius: '10px',
                padding: '12px 16px',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{m.incident_code} - {m.category}</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{m.location_name}</div>
              </div>
              <span style={{
                fontSize: '0.75rem',
                padding: '3px 8px',
                borderRadius: '6px',
                fontWeight: 600,
                backgroundColor: m.status === 'Completed' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                color: m.status === 'Completed' ? '#34d399' : '#60a5fa',
              }}>
                {m.status}
              </span>
            </div>
          ))}
          {missions.length === 0 && (
            <div style={{ color: '#64748b', fontSize: '0.8rem', textAlign: 'center', padding: '16px' }}>
              No past missions recorded for this unit.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
