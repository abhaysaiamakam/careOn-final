import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldCheck,
  AlertTriangle,
  PhoneCall,
  PlusCircle,
  Clock,
  User,
  HeartPulse,
  MapPin,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  Activity,
  FileText,
  Users,
  Settings,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import { getCitizenDashboardSummary } from '@careon/api-client';
import { useAuth } from '@careon/auth';
import { getLocalDrafts } from '../services/offlineDrafts.js';

export function CitizenDashboard({ onNavigate }) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const drafts = getLocalDrafts();

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCitizenDashboardSummary();
      setSummary(data);
    } catch (err) {
      console.warn('Failed to load citizen dashboard data:', err);
      setError('Could not sync with CareOn servers. Some emergency details may be cached.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const profile = summary?.profile || {};
  const contacts = summary?.contacts || [];
  const activeIncidents = summary?.active_incidents || [];
  const recentIncidents = summary?.recent_incidents || [];
  const primaryContact = contacts.find((c) => c.is_primary) || contacts[0];
  const readinessScore = profile.readiness_score || (profile.onboarding_completed ? 75 : 30);
  const missingFields = profile.missing_critical_fields || [];

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Offline drafts notification if any */}
      {drafts.length > 0 && (
        <div
          style={{
            background: colors.warningLight || '#FEF3C7',
            border: `1px solid ${colors.warning || '#F59E0B'}`,
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '20px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} color="#D97706" />
            <span style={{ fontSize: typography.fontSize.sm, color: '#92400E', fontWeight: typography.fontWeight.medium }}>
              You have {drafts.length} offline emergency report draft{drafts.length > 1 ? 's' : ''} saved locally.
            </span>
          </div>
          <Button size="xs" variant="outline" onClick={() => onNavigate('/drafts')}>
            Review Drafts
          </Button>
        </div>
      )}

      {/* Incomplete Onboarding Banner */}
      {!loading && !profile.onboarding_completed && (
        <div
          style={{
            background: '#FEE2E2',
            border: `1px solid ${colors.secondary}`,
            borderRadius: '8px',
            padding: '14px 18px',
            marginBottom: '24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertCircle size={22} color={colors.secondary} />
            <div>
              <div style={{ fontWeight: typography.fontWeight.bold, color: '#991B1B', fontSize: typography.fontSize.sm }}>
                Emergency Profile Incomplete ({readinessScore}% ready)
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: '#7F1D1D' }}>
                Complete your safety onboarding so first responders receive your home address and emergency contacts instantly.
              </div>
            </div>
          </div>
          <Button size="sm" variant="primary" onClick={() => onNavigate('/onboarding')}>
            Finish Setup Now
          </Button>
        </div>
      )}

      {/* Top Welcome & Readiness Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
          paddingBottom: '20px',
          borderBottom: `1px solid ${colors.border}`,
          marginBottom: '24px',
        }}
      >
        <div>
          <span style={{ fontSize: typography.fontSize.xs, color: colors.secondary, fontWeight: typography.fontWeight.semibold, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Personal Emergency Service
          </span>
          <h1 style={{ margin: '4px 0 0', fontSize: '1.75rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Welcome back, {user?.name || 'Citizen'}
          </h1>
          <div style={{ fontSize: typography.fontSize.sm, color: colors.textSecondary, marginTop: '4px' }}>
            {user?.phone ? `Verified Phone: ${user.phone}` : 'Account Active'}
          </div>
        </div>

        {/* Readiness Meter Card */}
        <div
          style={{
            background: colors.surface || '#FFFFFF',
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            padding: '12px 16px',
            minWidth: '240px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.medium, color: colors.textSecondary }}>
              Profile Readiness
            </span>
            <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: readinessScore >= 80 ? '#10B981' : colors.secondary }}>
              {readinessScore}%
            </span>
          </div>
          <div style={{ width: '100%', height: '6px', background: '#E5E7EB', borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${readinessScore}%`,
                height: '100%',
                background: readinessScore >= 80 ? '#10B981' : colors.secondary,
                borderRadius: '3px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          {missingFields.length > 0 ? (
            <button
              onClick={() => onNavigate(missingFields.includes('emergency_contacts') ? '/contacts' : '/profile')}
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                marginTop: '6px',
                fontSize: typography.fontSize.xs,
                color: colors.secondary,
                cursor: 'pointer',
                textAlign: 'left',
                textDecoration: 'underline',
              }}
            >
              Missing: {missingFields.map((f) => f.replace(/_/g, ' ')).join(', ')}
            </button>
          ) : (
            <div style={{ fontSize: typography.fontSize.xs, color: '#10B981', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckCircle2 size={12} /> Emergency data complete
            </div>
          )}
        </div>
      </div>

      {/* SECTION B: EMERGENCY PRIORITY HERO */}
      <Card
        padding="lg"
        style={{
          background: '#FFF5F5',
          border: `2px solid ${colors.secondary}`,
          borderRadius: '12px',
          marginBottom: '28px',
          textAlign: 'center',
        }}
      >
        <div style={{ maxWidth: '640px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: typography.fontWeight.bold, color: colors.secondary, marginBottom: '8px' }}>
            Immediate Emergency Assistance
          </h2>
          <p style={{ fontSize: typography.fontSize.sm, color: colors.textSecondary, marginBottom: '20px' }}>
            If you or someone nearby is experiencing a life-threatening medical emergency, trigger an instant response.
          </p>

          {/* Primary SOS Button */}
          <Button
            size="lg"
            variant="primary"
            onClick={() => onNavigate('/report')}
            style={{
              width: '100%',
              maxWidth: '420px',
              padding: '16px 24px',
              fontSize: '1.125rem',
              fontWeight: typography.fontWeight.bold,
              letterSpacing: '0.04em',
              background: colors.secondary,
              boxShadow: '0 4px 14px rgba(217, 45, 58, 0.4)',
              margin: '0 auto 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
            }}
          >
            <AlertTriangle size={24} />
            REQUEST EMERGENCY HELP (SOS)
          </Button>

          {/* Direct Hotlines */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              gap: '12px',
              flexWrap: 'wrap',
              marginTop: '12px',
              marginBottom: '20px',
            }}
          >
            <a
              href="tel:112"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                background: '#FFFFFF',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                color: colors.textPrimary,
                textDecoration: 'none',
                fontSize: typography.fontSize.sm,
                fontWeight: typography.fontWeight.semibold,
              }}
            >
              <PhoneCall size={16} color={colors.secondary} />
              Call 112 (National Emergency)
            </a>
            <a
              href="tel:108"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                background: '#FFFFFF',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                color: colors.textPrimary,
                textDecoration: 'none',
                fontSize: typography.fontSize.sm,
                fontWeight: typography.fontWeight.semibold,
              }}
            >
              <PhoneCall size={16} color={colors.secondary} />
              Call 108 (Ambulance / Medical)
            </a>
          </div>

          {/* Fast-Track Category Chips */}
          <div>
            <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, display: 'block', marginBottom: '8px' }}>
              Quick-select emergency condition:
            </span>
            <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: '8px' }}>
              {[
                { label: 'Cardiac / Unconscious', category: 'CARDIAC' },
                { label: 'Road Accident', category: 'ACCIDENT' },
                { label: 'Severe Bleeding', category: 'TRAUMA' },
                { label: 'Breathing Difficulty', category: 'RESPIRATORY' },
              ].map((chip) => (
                <button
                  key={chip.category}
                  onClick={() => onNavigate(`/report?category=${chip.category}`)}
                  style={{
                    background: '#FFFFFF',
                    border: `1px solid ${colors.border}`,
                    borderRadius: '16px',
                    padding: '6px 12px',
                    fontSize: typography.fontSize.xs,
                    fontWeight: typography.fontWeight.medium,
                    color: colors.textPrimary,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.borderColor = colors.secondary;
                    e.currentTarget.style.color = colors.secondary;
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.borderColor = colors.border;
                    e.currentTarget.style.color = colors.textPrimary;
                  }}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* SECTION C: ACTIVE EMERGENCY STATUS OR CALM STATUS */}
      {activeIncidents.length > 0 ? (
        <div style={{ marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: colors.secondary,
                boxShadow: '0 0 0 4px rgba(217, 45, 58, 0.2)',
                display: 'inline-block',
              }}
            />
            <h2 style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.secondary, margin: 0 }}>
              Active Emergency Missions in Progress ({activeIncidents.length})
            </h2>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeIncidents.map((inc) => (
              <Card
                key={inc.id}
                variant="emergency"
                padding="md"
                onClick={() => onNavigate(`/track?id=${encodeURIComponent(inc.tracking_token || inc.incident_code)}`)}
                style={{
                  cursor: 'pointer',
                  borderLeft: `4px solid ${colors.secondary}`,
                  background: '#FFFFFF',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <Badge variant="danger">{inc.status || 'Active'}</Badge>
                    <span style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                      {inc.incident_code || 'CareOn Mission'}
                    </span>
                    <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                      • {inc.category || 'Emergency'}
                    </span>
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    Reported: {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {inc.address ? ` • ${inc.address}` : ''}
                  </div>
                </div>

                <Button size="sm" variant="secondary" icon={ArrowRight}>
                  Open Live Tracker
                </Button>
              </Card>
            ))}
          </div>
        </div>
      ) : (
        <Card
          padding="md"
          style={{
            marginBottom: '28px',
            border: `1px solid ${colors.border}`,
            background: '#F9FAFB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: '#E0F2FE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <ShieldCheck size={24} color="#0284C7" />
            </div>
            <div>
              <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
                No Active Emergencies
              </div>
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Dispatch networks and responder stations are fully operational. Help is one tap away.
              </div>
            </div>
          </div>
          <Button size="xs" variant="outline" onClick={fetchDashboardData} icon={RefreshCw}>
            Refresh Status
          </Button>
        </Card>
      )}

      {/* SECTION D: PROFILE & SAFETY READINESS SUMMARY */}
      <div style={{ marginBottom: '28px' }}>
        <h2 style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, marginBottom: '14px' }}>
          Personal Safety Profile
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          {/* Card 1: Residential Address */}
          <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MapPin size={18} color={colors.secondary} />
                <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                  Home Address
                </span>
              </div>
              <button
                onClick={() => onNavigate('/profile')}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: typography.fontSize.xs,
                  color: colors.secondary,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                Edit
              </button>
            </div>
            {profile.residential_address ? (
              <div>
                <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                  {profile.residential_address}
                </p>
                <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  {profile.residential_city || ''} {profile.residential_postal_code || ''}
                </span>
              </div>
            ) : (
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                No home address saved. Adding your address helps responders locate you rapidly if incapacitated.
              </div>
            )}
          </Card>

          {/* Card 2: Primary ICE Contact */}
          <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Users size={18} color={colors.secondary} />
                <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                  Primary Emergency Contact (ICE)
                </span>
              </div>
              <button
                onClick={() => onNavigate('/contacts')}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: typography.fontSize.xs,
                  color: colors.secondary,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                Manage ({contacts.length})
              </button>
            </div>
            {primaryContact ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                  <div>
                    <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
                      {primaryContact.full_name}
                    </span>
                    <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginLeft: '6px' }}>
                      ({primaryContact.relationship_type})
                    </span>
                  </div>
                  <a
                    href={`tel:${primaryContact.phone}`}
                    style={{
                      padding: '4px 8px',
                      background: '#F3F4F6',
                      borderRadius: '4px',
                      color: colors.secondary,
                      fontSize: typography.fontSize.xs,
                      textDecoration: 'none',
                      fontWeight: typography.fontWeight.semibold,
                    }}
                  >
                    Call
                  </a>
                </div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
                  {primaryContact.phone}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                No emergency contacts added yet. Add trusted contacts who should be notified in an emergency.
              </div>
            )}
          </Card>

          {/* Card 3: Medical Notes (Unverified Disclaimer) */}
          <Card padding="md" style={{ border: `1px solid ${colors.border}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <HeartPulse size={18} color={colors.secondary} />
                <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                  Self-Reported Health Notes
                </span>
              </div>
              <span style={{ fontSize: '10px', background: '#FEF3C7', color: '#92400E', padding: '2px 6px', borderRadius: '4px', fontWeight: typography.fontWeight.bold }}>
                UNVERIFIED
              </span>
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginBottom: '6px' }}>
              Blood Group: <strong style={{ color: colors.textPrimary }}>{profile.blood_group || 'Not specified'}</strong>
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginBottom: '4px' }}>
              Allergies: <span style={{ color: colors.textPrimary }}>{profile.allergies || 'None declared'}</span>
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Conditions: <span style={{ color: colors.textPrimary }}>{profile.medical_conditions || 'None declared'}</span>
            </div>
          </Card>
        </div>
      </div>

      {/* SECTION E: RECENT EMERGENCY REQUESTS */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h2 style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, margin: 0 }}>
            Recent Requests ({recentIncidents.length})
          </h2>
          <button
            onClick={() => onNavigate('/history')}
            style={{
              background: 'none',
              border: 'none',
              fontSize: typography.fontSize.xs,
              color: colors.secondary,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontWeight: typography.fontWeight.semibold,
            }}
          >
            Full Incident History <ChevronRight size={14} />
          </button>
        </div>

        {recentIncidents.length === 0 ? (
          <Card padding="md" style={{ border: `1px solid ${colors.border}`, textAlign: 'center', padding: '28px 16px' }}>
            <Clock size={28} color={colors.textSecondary} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, color: colors.textPrimary }}>
              No Prior Incidents Recorded
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '4px' }}>
              When you submit emergency requests, your history and responder arrival summaries will appear here.
            </div>
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {recentIncidents.slice(0, 3).map((inc) => (
              <div
                key={inc.id}
                onClick={() => onNavigate(`/track?id=${encodeURIComponent(inc.tracking_token || inc.incident_code)}`)}
                style={{
                  background: '#FFFFFF',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  padding: '12px 16px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
                onMouseOver={(e) => { e.currentTarget.style.background = '#F9FAFB'; }}
                onMouseOut={(e) => { e.currentTarget.style.background = '#FFFFFF'; }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
                      {inc.category || 'Emergency'}
                    </span>
                    <Badge variant={['Resolved', 'Closed'].includes(inc.status) ? 'success' : 'neutral'}>
                      {inc.status}
                    </Badge>
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
                    {inc.address || 'Location registered'} • {new Date(inc.created_at).toLocaleDateString()}
                  </div>
                </div>
                <ChevronRight size={18} color={colors.textSecondary} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SECTION F: QUICK ACCESS ACTIONS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <button
          onClick={() => onNavigate('/contacts')}
          style={{
            background: '#FFFFFF',
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <Users size={20} color={colors.secondary} />
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
              ICE Contacts
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Manage emergency list
            </div>
          </div>
        </button>

        <button
          onClick={() => onNavigate('/profile')}
          style={{
            background: '#FFFFFF',
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <User size={20} color={colors.secondary} />
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
              Medical Profile
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Update health details
            </div>
          </div>
        </button>

        <button
          onClick={() => onNavigate('/drafts')}
          style={{
            background: '#FFFFFF',
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <FileText size={20} color={colors.secondary} />
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
              Offline Drafts
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Cached reports ({drafts.length})
            </div>
          </div>
        </button>

        <button
          onClick={() => onNavigate('/settings')}
          style={{
            background: '#FFFFFF',
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <Settings size={20} color={colors.secondary} />
          <div>
            <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
              Safety Settings
            </div>
            <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Language & preferences
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}
