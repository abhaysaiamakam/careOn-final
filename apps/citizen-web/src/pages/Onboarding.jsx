import React, { useState, useEffect } from 'react';
import {
  Shield,
  User,
  MapPin,
  Heart,
  Phone,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Navigation,
  Plus,
  Trash2,
  Lock,
  Globe,
  Info,
} from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  StepIndicator,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import {
  BLOOD_GROUPS,
  PREFERRED_LANGUAGES,
  CONTACT_RELATIONSHIPS,
} from '@careon/contracts';
import {
  getCitizenProfile,
  updateCitizenProfile,
  completeCitizenOnboarding,
  listCitizenContacts,
  createCitizenContact,
  deleteCitizenContact,
} from '@careon/api-client';
import { useAuth } from '@careon/auth';
import { acquireCurrentLocation, reverseGeocode } from '../services/geolocation.js';

const ONBOARDING_STEPS = [
  { title: '1. Personal' },
  { title: '2. Address' },
  { title: '3. Contacts' },
  { title: '4. Medical' },
  { title: '5. Consent' },
];

export function Onboarding({ onNavigate }) {
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [locationDetecting, setLocationDetecting] = useState(false);
  const [locationSuccess, setLocationSuccess] = useState(null);

  // Form State
  const [formData, setFormData] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    dob: '',
    preferred_language: 'en',
    profile_photo_url: '',
    residential_address: '',
    city: 'Mysuru',
    state: 'Karnataka',
    pincode: '',
    landmark: '',
    home_latitude: null,
    home_longitude: null,
    blood_group: '',
    allergies: '',
    medical_conditions: '',
    medications: '',
    accessibility_needs: '',
    consent_data_sharing: true,
    consent_emergency_contact: true,
  });

  // Emergency contacts list for Step 3
  const [contacts, setContacts] = useState([]);
  const [newContactName, setNewContactName] = useState('');
  const [newContactRel, setNewContactRel] = useState('Parent');
  const [newContactPhone, setNewContactPhone] = useState('');
  const [newContactPrimary, setNewContactPrimary] = useState(true);

  // Load existing profile & contacts on mount
  useEffect(() => {
    async function loadData() {
      try {
        const [profile, contactList] = await Promise.all([
          getCitizenProfile(),
          listCitizenContacts(),
        ]);
        setFormData({
          name: profile.name || user?.name || '',
          phone: profile.phone || user?.phone || '',
          dob: profile.dob || '',
          preferred_language: profile.preferred_language || 'en',
          profile_photo_url: profile.profile_photo_url || '',
          residential_address: profile.residential_address || '',
          city: profile.city || 'Mysuru',
          state: profile.state || 'Karnataka',
          pincode: profile.pincode || '',
          landmark: profile.landmark || '',
          home_latitude: profile.home_latitude || null,
          home_longitude: profile.home_longitude || null,
          blood_group: profile.blood_group || '',
          allergies: profile.allergies || '',
          medical_conditions: profile.medical_conditions || '',
          medications: profile.medications || '',
          accessibility_needs: profile.accessibility_needs || '',
          consent_data_sharing: profile.consent_data_sharing ?? true,
          consent_emergency_contact: profile.consent_emergency_contact ?? true,
        });
        setContacts(contactList || []);

        // Resume at saved step if incomplete
        if (profile.onboarding_step && profile.onboarding_step > 1 && profile.onboarding_step <= 5) {
          setCurrentStep(profile.onboarding_step - 1);
        }
      } catch (e) {
        console.warn('Failed to load initial onboarding profile:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [user]);

  const updateField = (field, val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleAcquireLocation = async () => {
    setLocationDetecting(true);
    setLocationSuccess(null);
    setError(null);
    try {
      const pos = await acquireCurrentLocation();
      updateField('home_latitude', pos.latitude);
      updateField('home_longitude', pos.longitude);
      const addr = await reverseGeocode(pos.latitude, pos.longitude);
      if (addr && !formData.residential_address) {
        updateField('residential_address', addr);
      }
      setLocationSuccess(`Acquired coordinates (±${pos.accuracy}m accuracy).`);
    } catch (err) {
      setError(`Location access: ${err.message}. You can enter your address manually.`);
    } finally {
      setLocationDetecting(false);
    }
  };

  const handleAddContact = async (e) => {
    e.preventDefault();
    if (!newContactName.trim() || !newContactPhone.trim()) return;
    try {
      const created = await createCitizenContact({
        name: newContactName.trim(),
        relationship_type: newContactRel,
        phone: newContactPhone.trim(),
        is_primary: newContactPrimary || contacts.length === 0,
      });
      setContacts([...contacts, created]);
      setNewContactName('');
      setNewContactPhone('');
    } catch (err) {
      setError(err.message || 'Failed to save emergency contact.');
    }
  };

  const handleDeleteContact = async (contactId) => {
    try {
      await deleteCitizenContact(contactId);
      setContacts(contacts.filter((c) => c.id !== contactId));
    } catch (err) {
      setError(err.message || 'Failed to remove emergency contact.');
    }
  };

  const saveCurrentStep = async (nextStepIndex) => {
    setSaving(true);
    setError(null);
    try {
      await updateCitizenProfile({
        ...formData,
        onboarding_step: nextStepIndex + 1,
      });
      setCurrentStep(nextStepIndex);
    } catch (err) {
      setError(err.message || 'Failed to save onboarding progress.');
    } finally {
      setSaving(false);
    }
  };

  const handleNext = () => {
    // Validation for step 1
    if (currentStep === 0) {
      if (!formData.name.trim()) {
        setError('Full name is required.');
        return;
      }
    }
    saveCurrentStep(Math.min(currentStep + 1, ONBOARDING_STEPS.length - 1));
  };

  const handleBack = () => {
    setError(null);
    setCurrentStep((s) => Math.max(s - 1, 0));
  };

  const handleCompleteOnboarding = async () => {
    setSaving(true);
    setError(null);
    try {
      // 1. Save all profile details
      await updateCitizenProfile({
        ...formData,
        onboarding_step: 5,
      });
      // 2. Mark onboarding completed in database
      await completeCitizenOnboarding();
      onNavigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Failed to complete setup.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: '680px', margin: '40px auto', padding: '0 16px', textAlign: 'center' }}>
        <Card padding="lg" style={{ color: colors.textSecondary }}>
          Preparing your CareOn emergency profile...
        </Card>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '32px 16px' }}>
      {/* Top Urgent Emergency Shortcut — Always Accessible */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          backgroundColor: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: '8px',
          marginBottom: '24px',
          fontSize: typography.fontSize.xs,
          color: colors.secondary,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <AlertTriangle size={15} />
          <span>In active danger right now? Do not wait to finish setup.</span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <a
            href="tel:112"
            style={{
              color: colors.secondary,
              fontWeight: typography.fontWeight.bold,
              textDecoration: 'none',
              padding: '2px 8px',
              backgroundColor: '#FFFFFF',
              borderRadius: '4px',
              border: '1px solid #FECACA',
            }}
          >
            Call 112
          </a>
          <button
            onClick={() => onNavigate('/report')}
            style={{
              background: colors.secondary,
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              padding: '2px 8px',
              fontWeight: typography.fontWeight.semibold,
              cursor: 'pointer',
            }}
          >
            Report SOS
          </button>
        </div>
      </div>

      {/* Welcoming Header */}
      <div style={{ marginBottom: '24px', textAlign: 'center' }}>
        <h1
          style={{
            margin: '0 0 6px',
            fontSize: '1.75rem',
            fontWeight: typography.fontWeight.bold,
            color: colors.textPrimary,
            letterSpacing: '-0.02em',
          }}
        >
          Welcome to CareOn
        </h1>
        <p style={{ margin: 0, fontSize: typography.fontSize.base, color: colors.textSecondary }}>
          Let's prepare your emergency profile so responders know how to reach and assist you.
        </p>
      </div>

      {error && (
        <Alert variant="danger" style={{ marginBottom: '20px' }}>
          {error}
        </Alert>
      )}

      {/* Step Indicator */}
      <StepIndicator
        steps={ONBOARDING_STEPS}
        currentStep={currentStep}
        onStepClick={(idx) => {
          if (idx < currentStep) setCurrentStep(idx);
        }}
      />

      <Card padding="lg">
        {/* STEP 1: PERSONAL INFORMATION */}
        {currentStep === 0 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 8px' }}>
              Step 1: Personal Information
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Your verified identity ensures emergency dispatches can confirm civilian calls.
            </p>

            <Input
              label="Full Legal Name"
              required
              value={formData.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="e.g. Aastha Singh"
            />

            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium, color: colors.textPrimary }}>
                  Contact Phone Number
                </label>
                <Badge variant="success" size="sm">
                  Verified Contact
                </Badge>
              </div>
              <input
                type="text"
                readOnly
                disabled
                value={formData.phone}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: colors.surfaceSubtle,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '6px',
                  color: colors.textSecondary,
                  fontSize: typography.fontSize.base,
                  boxSizing: 'border-box',
                }}
              />
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textMuted, marginTop: '4px', display: 'block' }}>
                Primary phone number authenticated with your CareOn account.
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Input
                label="Date of Birth (Optional)"
                type="date"
                value={formData.dob}
                onChange={(e) => updateField('dob', e.target.value)}
                helperText="Helps paramedics determine pediatric or geriatric triage."
              />

              <Input
                label="Preferred Language"
                as="select"
                value={formData.preferred_language}
                onChange={(e) => updateField('preferred_language', e.target.value)}
              >
                {PREFERRED_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.label}
                  </option>
                ))}
              </Input>
            </div>
          </div>
        )}

        {/* STEP 2: ADDRESS AND LOCATION */}
        {currentStep === 1 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 8px' }}>
              Step 2: Address & Residential Location
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Your home location allows emergency operators to pre-stage response when calls originate from home.
            </p>

            <div
              style={{
                backgroundColor: colors.surfaceSubtle,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                padding: '14px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div>
                <strong style={{ fontSize: typography.fontSize.sm, color: colors.textPrimary, display: 'block' }}>
                  Pinpoint Residential GPS Coordinate
                </strong>
                <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  Foreground location is requested once. We never track your device in the background.
                </span>
              </div>
              <Button
                size="sm"
                variant="secondary-red"
                onClick={handleAcquireLocation}
                loading={locationDetecting}
                icon={Navigation}
              >
                Detect My GPS
              </Button>
            </div>

            {locationSuccess && (
              <Alert variant="success" icon={CheckCircle2} style={{ marginBottom: '16px' }}>
                {locationSuccess}
              </Alert>
            )}

            <Input
              label="Street Address / Building / Flat"
              placeholder="e.g. 14B, 3rd Cross, Gokulam 3rd Stage"
              value={formData.residential_address}
              onChange={(e) => updateField('residential_address', e.target.value)}
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Input
                label="City"
                value={formData.city}
                onChange={(e) => updateField('city', e.target.value)}
              />
              <Input
                label="PIN Code"
                placeholder="570002"
                value={formData.pincode}
                onChange={(e) => updateField('pincode', e.target.value)}
              />
            </div>

            <Input
              label="Prominent Landmark"
              placeholder="e.g. Opposite Post Office, Near Big Banyan Tree"
              value={formData.landmark}
              onChange={(e) => updateField('landmark', e.target.value)}
              helperText="Critical for ambulance drivers navigating residential lanes at night."
            />
          </div>
        )}

        {/* STEP 3: EMERGENCY CONTACTS */}
        {currentStep === 2 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 8px' }}>
              Step 3: Trusted In-Case-of-Emergency (ICE) Contacts
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              ICE contacts are notified if you submit an emergency report or are found incapacitated.
            </p>

            {/* Existing added contacts */}
            {contacts.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                {contacts.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px',
                      backgroundColor: colors.surfaceSubtle,
                      border: `1px solid ${colors.border}`,
                      borderRadius: '6px',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong style={{ fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                          {c.name}
                        </strong>
                        <Badge variant="neutral" size="sm">
                          {c.relationship_type}
                        </Badge>
                        {c.is_primary && (
                          <Badge variant="emergency" size="sm">
                            Primary ICE
                          </Badge>
                        )}
                      </div>
                      <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
                        {c.phone}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteContact(c.id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.textSecondary, padding: '4px' }}
                      title="Remove contact"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add contact mini-form */}
            <div style={{ border: `1px dashed ${colors.borderDark}`, borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
              <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.semibold, display: 'block', marginBottom: '12px' }}>
                Add Contact Person
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <Input
                  label="Contact Name"
                  placeholder="e.g. Sunita Singh"
                  value={newContactName}
                  onChange={(e) => setNewContactName(e.target.value)}
                />
                <Input
                  label="Relationship"
                  as="select"
                  value={newContactRel}
                  onChange={(e) => setNewContactRel(e.target.value)}
                >
                  {CONTACT_RELATIONSHIPS.map((rel) => (
                    <option key={rel} value={rel}>{rel}</option>
                  ))}
                </Input>
              </div>

              <Input
                label="Mobile Phone"
                type="tel"
                placeholder="+91 98450 54321"
                value={newContactPhone}
                onChange={(e) => setNewContactPhone(e.target.value)}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: typography.fontSize.xs, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={newContactPrimary}
                    onChange={(e) => setNewContactPrimary(e.target.checked)}
                  />
                  Designate as primary contact
                </label>
                <Button
                  size="sm"
                  variant="secondary-red"
                  onClick={handleAddContact}
                  icon={Plus}
                >
                  Save Contact
                </Button>
              </div>
            </div>

            <div style={{ fontSize: typography.fontSize.xs, color: colors.textMuted }}>
              * You can add up to 10 contacts. You can also skip this step and add contacts later.
            </div>
          </div>
        )}

        {/* STEP 4: OPTIONAL MEDICAL PROFILE */}
        {currentStep === 3 && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: 0 }}>
                Step 4: Optional Medical Information
              </h2>
              <Badge variant="warning" size="sm">
                Optional
              </Badge>
            </div>

            {/* Explicit unverified medical status notice */}
            <Alert variant="info" icon={Info} style={{ marginBottom: '20px' }}>
              <strong>CLINICAL TRANSPARENCY:</strong> Information entered here is civilian-reported and labeled as <strong>UNVERIFIED</strong>. It provides early operational clues to paramedics and trauma doctors, but is not a substitute for clinical diagnostics.
            </Alert>

            <Input
              label="Blood Group (Optional)"
              as="select"
              value={formData.blood_group}
              onChange={(e) => updateField('blood_group', e.target.value)}
            >
              <option value="">-- Select Blood Group (Optional) --</option>
              {BLOOD_GROUPS.map((bg) => (
                <option key={bg} value={bg}>{bg}</option>
              ))}
            </Input>

            <Input
              label="Known Severe Allergies (Optional)"
              placeholder="e.g. Penicillin, Latex, Peanuts, Aspirin..."
              value={formData.allergies}
              onChange={(e) => updateField('allergies', e.target.value)}
              helperText="Alerts paramedics before administering standard pain or stabilization medications."
            />

            <Input
              label="Pre-existing Medical Conditions (Optional)"
              as="textarea"
              placeholder="e.g. Type-2 Diabetes, Cardiac Stent (2023), Hypertension, Epilepsy..."
              value={formData.medical_conditions}
              onChange={(e) => updateField('medical_conditions', e.target.value)}
            />

            <Input
              label="Daily Medications & Dosages (Optional)"
              placeholder="e.g. Metformin 500mg, Ecosprin 75mg daily..."
              value={formData.medications}
              onChange={(e) => updateField('medications', e.target.value)}
            />

            <Input
              label="Accessibility & Special Communication Needs (Optional)"
              placeholder="e.g. Wheelchair user, Hearing impaired, Non-verbal in distress..."
              value={formData.accessibility_needs}
              onChange={(e) => updateField('accessibility_needs', e.target.value)}
            />
          </div>
        )}

        {/* STEP 5: REVIEW AND CONSENT */}
        {currentStep === 4 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 8px' }}>
              Step 5: Review & Consent
            </h2>
            <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
              Review your stored profile and authorize secure sharing with regional emergency responders.
            </p>

            {/* Summary Box */}
            <div
              style={{
                backgroundColor: colors.surfaceSubtle,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                fontSize: typography.fontSize.sm,
              }}
            >
              <div>
                <strong>Citizen:</strong> {formData.name} ({formData.phone}) • Language: {formData.preferred_language.toUpperCase()}
              </div>

              <div>
                <strong>Residential Address:</strong> {formData.residential_address || 'Not specified'} {formData.city && `, ${formData.city}`} {formData.pincode && `- ${formData.pincode}`}
              </div>

              <div>
                <strong>ICE Emergency Contacts:</strong> {contacts.length > 0 ? `${contacts.length} registered (${contacts.map((c) => c.name).join(', ')})` : 'None registered'}
              </div>

              <div>
                <strong>Medical Summary:</strong> Blood Group: {formData.blood_group || 'Not specified'} | Allergies: {formData.allergies || 'None recorded'} | Conditions: {formData.medical_conditions || 'None recorded'}
              </div>
            </div>

            {/* Consents */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: typography.fontSize.xs, cursor: 'pointer', lineHeight: 1.5 }}>
                <input
                  type="checkbox"
                  checked={formData.consent_data_sharing}
                  onChange={(e) => updateField('consent_data_sharing', e.target.checked)}
                  style={{ marginTop: '2px' }}
                />
                <span>
                  <strong>Emergency Responder Data Sharing:</strong> I consent to CareOn sharing my address, contacts, and unverified medical notes with dispatched ambulance paramedics, trauma centers, and verified operations personnel during active emergencies.
                </span>
              </label>

              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: typography.fontSize.xs, cursor: 'pointer', lineHeight: 1.5 }}>
                <input
                  type="checkbox"
                  checked={formData.consent_emergency_contact}
                  onChange={(e) => updateField('consent_emergency_contact', e.target.checked)}
                  style={{ marginTop: '2px' }}
                />
                <span>
                  <strong>Emergency Contact Authorization:</strong> I authorize CareOn to reach out to my listed ICE contacts if I am involved in a reported emergency.
                </span>
              </label>
            </div>

            <Alert variant="success" icon={Shield}>
              All profile information can be edited or revoked at any time in <strong>My Profile</strong>.
            </Alert>
          </div>
        )}

        {/* Step Navigation Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: `1px solid ${colors.border}`,
            paddingTop: '20px',
            marginTop: '16px',
          }}
        >
          {currentStep > 0 ? (
            <Button
              type="button"
              variant="secondary"
              onClick={handleBack}
              icon={ArrowLeft}
            >
              Back
            </Button>
          ) : (
            <Button
              type="button"
              variant="tertiary"
              onClick={() => onNavigate('/dashboard')}
            >
              Skip Setup for Now
            </Button>
          )}

          {currentStep < ONBOARDING_STEPS.length - 1 ? (
            <div style={{ display: 'flex', gap: '8px' }}>
              {currentStep > 0 && (
                <Button
                  type="button"
                  variant="tertiary"
                  onClick={() => saveCurrentStep(currentStep + 1)}
                >
                  Skip Step
                </Button>
              )}
              <Button
                type="button"
                variant="primary"
                onClick={handleNext}
                loading={saving}
                icon={ArrowRight}
                iconPosition="right"
              >
                Save & Continue
              </Button>
            </div>
          ) : (
            <Button
              type="button"
              variant="primary"
              onClick={handleCompleteOnboarding}
              loading={saving}
              icon={CheckCircle2}
              style={{ padding: '12px 28px', fontSize: typography.fontSize.base }}
            >
              Complete Setup & Go to Dashboard
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
