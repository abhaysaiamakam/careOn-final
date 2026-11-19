import React, { useState, useEffect } from 'react';
import {
  User,
  Phone,
  Mail,
  ShieldCheck,
  Heart,
  Save,
  CheckCircle,
  AlertCircle,
  MapPin,
  Lock,
  ArrowRight,
  RefreshCw,
  Info,
} from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { BLOOD_GROUPS, PREFERRED_LANGUAGES } from '@careon/contracts';
import { getCitizenProfile, updateCitizenProfile, updateMyProfile } from '@careon/api-client';
import { useAuth } from '@careon/auth';

export function Profile({ onNavigate }) {
  const { user, refreshProfile } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Form State
  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [preferredLanguage, setPreferredLanguage] = useState('en');
  const [residentialAddress, setResidentialAddress] = useState('');
  const [residentialCity, setResidentialCity] = useState('');
  const [residentialState, setResidentialState] = useState('');
  const [residentialPostalCode, setResidentialPostalCode] = useState('');
  const [addressLandmark, setAddressLandmark] = useState('');
  const [accessInstructions, setAccessInstructions] = useState('');
  const [bloodGroup, setBloodGroup] = useState('UNKNOWN');
  const [allergies, setAllergies] = useState('');
  const [medicalConditions, setMedicalConditions] = useState('');
  const [currentMedications, setCurrentMedications] = useState('');
  const [emergencyNotes, setEmergencyNotes] = useState('');
  const [isOrganDonor, setIsOrganDonor] = useState(false);
  const [consentDataSharing, setConsentDataSharing] = useState(true);
  const [readinessScore, setReadinessScore] = useState(0);

  const loadData = async () => {
    setLoading(true);
    setSaveError(null);
    try {
      const data = await getCitizenProfile();
      if (data) {
        setResidentialAddress(data.residential_address || '');
        setResidentialCity(data.residential_city || '');
        setResidentialState(data.residential_state || '');
        setResidentialPostalCode(data.residential_postal_code || '');
        setAddressLandmark(data.address_landmark || '');
        setAccessInstructions(data.access_instructions || '');
        setPreferredLanguage(data.preferred_language || 'en');
        setBloodGroup(data.blood_group || 'UNKNOWN');
        setAllergies(data.allergies || '');
        setMedicalConditions(data.medical_conditions || '');
        setCurrentMedications(data.current_medications || '');
        setEmergencyNotes(data.emergency_notes || '');
        setIsOrganDonor(Boolean(data.is_organ_donor));
        setConsentDataSharing(data.consent_data_sharing_emergency !== false);
        setReadinessScore(data.readiness_score || 0);
      }
    } catch (err) {
      console.warn('Failed to load citizen profile:', err);
      setSaveError('Could not load current profile from server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      setName(user.name || '');
      setPhone(user.phone || '');
    }
    loadData();
  }, [user]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      // 1. Update basic user account info if modified
      if (name.trim() !== (user?.name || '') || phone.trim() !== (user?.phone || '')) {
        await updateMyProfile({ name: name.trim(), phone: phone.trim() });
        if (refreshProfile) await refreshProfile();
      }

      // 2. Update extended citizen profile in PostgreSQL
      const updated = await updateCitizenProfile({
        residential_address: residentialAddress.trim(),
        residential_city: residentialCity.trim(),
        residential_state: residentialState.trim(),
        residential_postal_code: residentialPostalCode.trim(),
        address_landmark: addressLandmark.trim(),
        access_instructions: accessInstructions.trim(),
        preferred_language: preferredLanguage,
        blood_group: bloodGroup,
        allergies: allergies.trim(),
        medical_conditions: medicalConditions.trim(),
        current_medications: currentMedications.trim(),
        emergency_notes: emergencyNotes.trim(),
        is_organ_donor: isOrganDonor,
        consent_data_sharing_emergency: consentDataSharing,
      });

      if (updated) {
        setReadinessScore(updated.readiness_score || 85);
      }

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 5000);
    } catch (err) {
      setSaveError(err.message || 'Failed to save profile changes.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: '680px', margin: '40px auto', textAlign: 'center', padding: '24px' }}>
        <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 12px', color: colors.secondary }} />
        <p style={{ fontSize: typography.fontSize.sm, color: colors.textSecondary }}>Loading emergency profile...</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '24px' }}>
        <div>
          <h1 style={{ margin: '0 0 6px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Citizen Profile & Safety Record
          </h1>
          <p style={{ margin: 0, fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
            Stored securely on CareOn servers to assist responders during emergency dispatch.
          </p>
        </div>

        <div style={{ background: '#F3F4F6', padding: '6px 12px', borderRadius: '6px', textAlign: 'right' }}>
          <div style={{ fontSize: '11px', color: colors.textSecondary, textTransform: 'uppercase', fontWeight: typography.fontWeight.semibold }}>
            Safety Readiness
          </div>
          <div style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: readinessScore >= 80 ? '#10B981' : colors.secondary }}>
            {readinessScore}% Complete
          </div>
        </div>
      </div>

      {saveSuccess && (
        <div style={{ marginBottom: '20px' }}>
          <Alert variant="success" icon={CheckCircle}>
            Emergency profile updated and saved to CareOn database successfully.
          </Alert>
        </div>
      )}

      {saveError && (
        <div style={{ marginBottom: '20px' }}>
          <Alert variant="danger">
            {saveError}
          </Alert>
        </div>
      )}

      <form onSubmit={handleSave}>
        {/* Section 1: Account & Contact Identity */}
        <Card padding="lg" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
          <h2 style={{ margin: '0 0 16px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={18} color={colors.secondary} />
            1. Identity & Contact Details
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Input
              label="Full Legal Name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. John Doe"
            />

            <Input
              label="Primary Callback Phone"
              required
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 98765 43210"
              helperText="Dispatchers will use this number to coordinate arrival."
            />

            <div>
              <label style={{ display: 'block', fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary, marginBottom: '6px' }}>
                Preferred Language
              </label>
              <select
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${colors.border}`,
                  fontSize: typography.fontSize.sm,
                  background: '#FFFFFF',
                }}
              >
                {PREFERRED_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.label} ({lang.native})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </Card>

        {/* Section 2: Residential Address & Dispatch Access */}
        <Card padding="lg" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
          <h2 style={{ margin: '0 0 16px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={18} color={colors.secondary} />
            2. Residential & Dispatch Address
          </h2>
          <p style={{ margin: '0 0 14px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Responders rely on this address if you trigger emergency help from your home without GPS.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Input
              label="Street Address / Building"
              value={residentialAddress}
              onChange={(e) => setResidentialAddress(e.target.value)}
              placeholder="Apartment, Street, House Number"
            />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
              <Input
                label="City"
                value={residentialCity}
                onChange={(e) => setResidentialCity(e.target.value)}
                placeholder="City"
              />
              <Input
                label="State / Province"
                value={residentialState}
                onChange={(e) => setResidentialState(e.target.value)}
                placeholder="State"
              />
              <Input
                label="Postal / PIN Code"
                value={residentialPostalCode}
                onChange={(e) => setResidentialPostalCode(e.target.value)}
                placeholder="Postal Code"
              />
            </div>

            <Input
              label="Prominent Landmark"
              value={addressLandmark}
              onChange={(e) => setAddressLandmark(e.target.value)}
              placeholder="e.g. Opposite City Hospital gate #2"
            />

            <div>
              <label style={{ display: 'block', fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary, marginBottom: '6px' }}>
                Building Access / Entry Details
              </label>
              <textarea
                value={accessInstructions}
                onChange={(e) => setAccessInstructions(e.target.value)}
                rows={2}
                placeholder="e.g. 4th floor, Elevator available, security code #1234, dog inside"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${colors.border}`,
                  fontSize: typography.fontSize.sm,
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>
        </Card>

        {/* Section 3: Self-Reported Medical Info (UNVERIFIED DISCLAIMER) */}
        <Card padding="lg" style={{ marginBottom: '20px', border: `1px solid ${colors.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Heart size={18} color={colors.secondary} />
              3. Self-Reported Health Profile
            </h2>
            <span style={{ fontSize: '10px', background: '#FEF3C7', color: '#92400E', padding: '2px 8px', borderRadius: '4px', fontWeight: typography.fontWeight.bold }}>
              UNVERIFIED RECORD
            </span>
          </div>

          <div
            style={{
              background: '#FFFBEB',
              border: '1px solid #FDE68A',
              borderRadius: '6px',
              padding: '10px 12px',
              fontSize: typography.fontSize.xs,
              color: '#92400E',
              marginBottom: '16px',
              display: 'flex',
              gap: '8px',
            }}
          >
            <Info size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Disclaimer:</strong> Self-reported medical information is provided for responder awareness only and does not constitute a verified electronic health record (EHR). In critical situations, medical teams perform independent clinical verification.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary, marginBottom: '6px' }}>
                Blood Group (Self-Reported)
              </label>
              <select
                value={bloodGroup}
                onChange={(e) => setBloodGroup(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${colors.border}`,
                  fontSize: typography.fontSize.sm,
                  background: '#FFFFFF',
                }}
              >
                {BLOOD_GROUPS.map((bg) => (
                  <option key={bg} value={bg}>
                    {bg}
                  </option>
                ))}
              </select>
            </div>

            <Input
              label="Known Allergies (Medications, Latex, Food)"
              value={allergies}
              onChange={(e) => setAllergies(e.target.value)}
              placeholder="e.g. Penicillin, Sulfa drugs, Peanuts"
            />

            <Input
              label="Chronic Medical Conditions"
              value={medicalConditions}
              onChange={(e) => setMedicalConditions(e.target.value)}
              placeholder="e.g. Type 2 Diabetes, Hypertension, Asthma"
            />

            <Input
              label="Current Regular Medications"
              value={currentMedications}
              onChange={(e) => setCurrentMedications(e.target.value)}
              placeholder="e.g. Metformin 500mg, Lisinopril 10mg"
            />

            <div>
              <label style={{ display: 'block', fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary, marginBottom: '6px' }}>
                Special Medical Instructions / Emergency Notes
              </label>
              <textarea
                value={emergencyNotes}
                onChange={(e) => setEmergencyNotes(e.target.value)}
                rows={2}
                placeholder="e.g. Pacemaker implanted, severe mobility limitations"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${colors.border}`,
                  fontSize: typography.fontSize.sm,
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: typography.fontSize.sm, cursor: 'pointer', marginTop: '4px' }}>
              <input
                type="checkbox"
                checked={isOrganDonor}
                onChange={(e) => setIsOrganDonor(e.target.checked)}
                style={{ width: '16px', height: '16px', accentColor: colors.secondary }}
              />
              <span style={{ color: colors.textPrimary, fontWeight: typography.fontWeight.medium }}>
                Registered Organ Donor
              </span>
            </label>
          </div>
        </Card>

        {/* Section 4: Privacy & Consent */}
        <Card padding="lg" style={{ marginBottom: '24px', border: `1px solid ${colors.border}` }}>
          <h2 style={{ margin: '0 0 12px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lock size={18} color={colors.secondary} />
            4. Emergency Dispatch Consent
          </h2>

          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: typography.fontSize.xs, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={consentDataSharing}
              onChange={(e) => setConsentDataSharing(e.target.checked)}
              style={{ width: '16px', height: '16px', marginTop: '2px', accentColor: colors.secondary }}
            />
            <span style={{ color: colors.textSecondary, lineHeight: 1.5 }}>
              I authorize CareOn to transmit my address, self-reported health notes, and primary emergency contact to authorized dispatchers, paramedics, and receiving hospital triage units when an emergency is active.
            </span>
          </label>
        </Card>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <Button
            type="button"
            variant="outline"
            onClick={() => onNavigate('/contacts')}
            icon={ArrowRight}
          >
            Manage ICE Contacts
          </Button>

          <Button
            type="submit"
            variant="primary"
            loading={saving}
            icon={Save}
          >
            Save Emergency Profile
          </Button>
        </div>
      </form>
    </div>
  );
}
