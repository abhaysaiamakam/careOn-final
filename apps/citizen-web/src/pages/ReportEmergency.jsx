import React, { useState, useEffect } from 'react';
import {
  HeartPulse,
  MapPin,
  Users,
  Info,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Save,
  Send,
  PhoneCall,
  ShieldAlert,
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
  INCIDENT_CATEGORIES,
} from '@careon/contracts';
import { reportIncident, verifyIncidentOtp } from '@careon/api-client';
import { useAuth } from '@careon/auth';
import { saveLocalDraft, deleteLocalDraft, getDraftById } from '../services/offlineDrafts.js';
import { EmergencyLocationPicker } from '../components/EmergencyLocationPicker.jsx';

const STEPS = [
  { title: '1. What Happened?' },
  { title: '2. Location' },
  { title: '3. Affected People' },
  { title: '4. Hazards & Notes' },
  { title: '5. Review & Submit' },
];

export function ReportEmergency({ onNavigate, initialDraftId, initialCategory }) {
  const { user } = useAuth();

  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState({
    category: initialCategory || 'Medical',
    description: '',
    help_required: 'Ambulance & Paramedic',
    location_name: '',
    latitude: 12.3052,
    longitude: 76.6552,
    affected_people: 1,
    contact_name: user?.name || '',
    contact_phone: user?.phone || '',
    additional_details: '',
    is_disaster: false,
    disaster_details: '',
    patient_conscious: true,
    patient_breathing: true,
  });

  const [draftId, setDraftId] = useState(initialDraftId || null);
  const [draftSavedNotice, setDraftSavedNotice] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Server response state
  const [confirmedIncident, setConfirmedIncident] = useState(null);
  const [otpInput, setOtpInput] = useState('');
  const [otpVerifying, setOtpVerifying] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);
  const [otpError, setOtpError] = useState(null);

  // Load draft if specified
  useEffect(() => {
    if (initialDraftId) {
      const draft = getDraftById(initialDraftId);
      if (draft) {
        setFormData((prev) => ({ ...prev, ...draft }));
        setDraftId(draft.id);
      }
    }
  }, [initialDraftId]);

  // Sync category default help text
  useEffect(() => {
    const matched = INCIDENT_CATEGORIES.find((c) => c.id === formData.category);
    if (matched && !formData.help_required) {
      setFormData((prev) => ({ ...prev, help_required: matched.defaultHelp }));
    }
  }, [formData.category]);

  const updateField = (field, val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleSaveDraft = () => {
    try {
      const saved = saveLocalDraft({
        ...formData,
        id: draftId,
      });
      setDraftId(saved.id);
      setDraftSavedNotice(true);
      setTimeout(() => setDraftSavedNotice(false), 3000);
    } catch (e) {
      setSubmitError('Failed to save draft locally.');
    }
  };

  const validateStep = () => {
    if (currentStep === 0) {
      if (!formData.category) return 'Please select an emergency category.';
      if (!formData.description || formData.description.trim().length < 5) {
        return 'Please provide a brief description (minimum 5 characters).';
      }
    }
    if (currentStep === 1) {
      if (!formData.location_name || formData.location_name.trim().length < 2) {
        return 'Please enter or acquire the emergency location.';
      }
    }
    if (currentStep === 2) {
      if (!formData.contact_name || formData.contact_name.trim().length < 2) {
        return 'Contact name is required so responders can identify the reporter.';
      }
      if (!formData.contact_phone || formData.contact_phone.trim().length < 8) {
        return 'A valid contact phone number is required (min 8 digits).';
      }
    }
    return null;
  };

  const handleNext = () => {
    const err = validateStep();
    if (err) {
      setSubmitError(err);
      return;
    }
    setSubmitError(null);
    setCurrentStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const handleBack = () => {
    setSubmitError(null);
    setCurrentStep((s) => Math.max(s - 1, 0));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);

    // Prepare payload for backend POST /api/incidents
    const payload = {
      category: formData.category,
      description: formData.description.trim(),
      location_name: formData.location_name.trim(),
      latitude: formData.latitude,
      longitude: formData.longitude,
      affected_people: parseInt(formData.affected_people, 10) || 1,
      help_required: formData.help_required || 'Emergency Assistance',
      contact_name: formData.contact_name.trim(),
      contact_phone: formData.contact_phone.trim(),
      additional_details: [
        formData.additional_details,
        `Patient conscious: ${formData.patient_conscious ? 'Yes' : 'No'}`,
        `Patient breathing: ${formData.patient_breathing ? 'Yes' : 'No'}`,
      ]
        .filter(Boolean)
        .join(' | '),
      is_disaster: formData.is_disaster,
      disaster_details: formData.disaster_details || null,
    };

    try {
      const serverResp = await reportIncident(payload);
      setConfirmedIncident(serverResp);

      // Clean up local draft if it was saved
      if (draftId) {
        deleteLocalDraft(draftId);
      }
    } catch (err) {
      if (err.isNetworkError || !navigator.onLine) {
        // Automatically offer local draft persistence
        handleSaveDraft();
        setSubmitError(
          'Network connection unavailable. Your emergency report has been preserved as a LOCAL DRAFT. Dial 112 or 108 immediately!'
        );
      } else {
        setSubmitError(err.message || 'Failed to submit emergency report.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!confirmedIncident || !otpInput.trim()) return;
    setOtpVerifying(true);
    setOtpError(null);
    try {
      await verifyIncidentOtp(confirmedIncident.id, otpInput.trim());
      setOtpVerified(true);
    } catch (e) {
      setOtpError('Invalid verification code. Enter code 123456 or the code sent to your phone.');
    } finally {
      setOtpVerifying(false);
    }
  };

  // If server confirmed, show confirmation view
  if (confirmedIncident) {
    return (
      <div style={{ maxWidth: '640px', margin: '0 auto', padding: '32px 16px' }}>
        <Card variant="emergency" padding="lg">
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                backgroundColor: '#ECFDF5',
                border: '2px solid #10B981',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: colors.success,
                marginBottom: '16px',
              }}
            >
              <CheckCircle2 size={32} />
            </div>
            <h1
              style={{
                margin: '0 0 8px',
                fontSize: '1.5rem',
                fontWeight: typography.fontWeight.bold,
                color: colors.textPrimary,
              }}
            >
              Emergency Report Received by Server
            </h1>
            <p style={{ margin: 0, fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
              Your report has been logged and queued for regional emergency dispatch evaluation.
            </p>
          </div>

          <div
            style={{
              backgroundColor: colors.surfaceSubtle,
              border: `1px solid ${colors.border}`,
              borderRadius: '8px',
              padding: '16px',
              marginBottom: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Incident Reference Code:
              </span>
              <strong style={{ fontSize: typography.fontSize.base, color: colors.secondary, letterSpacing: '0.05em' }}>
                {confirmedIncident.incident_code}
              </strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Current Status:
              </span>
              <Badge variant="warning">{confirmedIncident.status}</Badge>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Category & Priority:
              </span>
              <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
                {confirmedIncident.category} ({confirmedIncident.priority || 'Triage Pending'})
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Location:
              </span>
              <span style={{ fontSize: typography.fontSize.sm, textAlign: 'right' }}>
                {confirmedIncident.location_name}
              </span>
            </div>
          </div>

          {/* OTP Verification Box */}
          {!otpVerified && !confirmedIncident.is_verified && (
            <div
              style={{
                border: `1px dashed ${colors.borderDark}`,
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '20px',
              }}
            >
              <h4 style={{ margin: '0 0 6px', fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                Phone Contact Verification
              </h4>
              <p style={{ margin: '0 0 12px', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                Enter the 6-digit confirmation code sent to {formData.contact_phone} (Demo Code: <strong>123456</strong>):
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="123456"
                  value={otpInput}
                  onChange={(e) => setOtpInput(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    border: `1px solid ${colors.border}`,
                    borderRadius: '6px',
                    fontSize: typography.fontSize.base,
                    letterSpacing: '0.2em',
                    textAlign: 'center',
                    fontWeight: typography.fontWeight.bold,
                  }}
                />
                <Button
                  size="sm"
                  variant="secondary-red"
                  onClick={handleVerifyOtp}
                  loading={otpVerifying}
                >
                  Verify
                </Button>
              </div>
              {otpError && (
                <div style={{ marginTop: '6px', fontSize: typography.fontSize.xs, color: colors.secondary }}>
                  {otpError}
                </div>
              )}
            </div>
          )}

          {otpVerified && (
            <Alert variant="success" title="Phone Verified">
              Your contact phone number has been verified. Dispatchers can reach you directly.
            </Alert>
          )}

          <div
            style={{
              padding: '12px',
              backgroundColor: '#FEF2F2',
              borderRadius: '6px',
              marginBottom: '24px',
              fontSize: typography.fontSize.xs,
              color: colors.secondary,
              lineHeight: 1.5,
            }}
          >
            <strong>OPERATIONAL NOTICE:</strong> Responders are evaluated and assigned according to severity triage. Do not leave the location unless instructed by emergency operators.
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Button
              variant="primary"
              fullWidth
              onClick={() => onNavigate(`/track?id=${encodeURIComponent(confirmedIncident.tracking_token || confirmedIncident.incident_code)}`)}
            >
              Go to Live Tracking
            </Button>
            <Button
              variant="secondary"
              fullWidth
              onClick={() => onNavigate('/')}
            >
              Return Home
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <h1
          style={{
            margin: 0,
            fontSize: '1.5rem',
            fontWeight: typography.fontWeight.bold,
            color: colors.textPrimary,
          }}
        >
          Report an Emergency
        </h1>
        <Button
          type="button"
          size="sm"
          variant="tertiary"
          onClick={handleSaveDraft}
          icon={Save}
        >
          Save Draft
        </Button>
      </div>

      {draftSavedNotice && (
        <Alert variant="info" style={{ marginBottom: '12px' }}>
          Draft saved locally to your device. Note: Local drafts are not received by emergency services until submitted.
        </Alert>
      )}

      {submitError && (
        <Alert variant="danger" style={{ marginBottom: '16px' }}>
          {submitError}
        </Alert>
      )}

      <StepIndicator
        steps={STEPS}
        currentStep={currentStep}
        onStepClick={(idx) => setCurrentStep(idx)}
      />

      <Card padding="lg" style={{ marginBottom: '24px' }}>
        {/* STEP 1: WHAT HAPPENED */}
        {currentStep === 0 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 16px' }}>
              Step 1: What type of emergency is this?
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px', marginBottom: '20px' }}>
              {INCIDENT_CATEGORIES.map((cat) => {
                const isSelected = formData.category === cat.id;
                return (
                  <div
                    key={cat.id}
                    onClick={() => {
                      updateField('category', cat.id);
                      updateField('help_required', cat.defaultHelp);
                    }}
                    style={{
                      padding: '12px',
                      borderRadius: '6px',
                      border: `1px solid ${isSelected ? colors.secondary : colors.border}`,
                      backgroundColor: isSelected ? '#FEF2F2' : colors.surface,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm, color: isSelected ? colors.secondary : colors.textPrimary }}>
                      {cat.label}
                    </div>
                  </div>
                );
              })}
            </div>

            <Input
              label="Describe What Happened"
              as="textarea"
              required
              placeholder="e.g. Elderly person collapsed, unresponsive, pale skin, shallow breathing..."
              value={formData.description}
              onChange={(e) => updateField('description', e.target.value)}
              helperText="Include key symptoms, visible injuries, vehicle types, or fire intensity."
            />

            <Input
              label="Assistance Requested"
              value={formData.help_required}
              onChange={(e) => updateField('help_required', e.target.value)}
              placeholder="e.g. Ambulance & Paramedics"
            />
          </div>
        )}

        {/* STEP 2: WHERE DID IT HAPPEN */}
        {currentStep === 1 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 16px' }}>
              Step 2: Emergency Location
            </h2>
            <EmergencyLocationPicker
              locationName={formData.location_name}
              latitude={formData.latitude}
              longitude={formData.longitude}
              onChange={({ locationName, latitude, longitude }) => {
                updateField('location_name', locationName);
                updateField('latitude', latitude);
                updateField('longitude', longitude);
              }}
            />
          </div>
        )}

        {/* STEP 3: WHO NEEDS HELP */}
        {currentStep === 2 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 16px' }}>
              Step 3: Patient & Contact Details
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <Input
                label="Number of Patients Affected"
                type="number"
                min="1"
                max="100"
                value={formData.affected_people}
                onChange={(e) => updateField('affected_people', parseInt(e.target.value, 10) || 1)}
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.medium }}>
                  Patient Condition Checks:
                </span>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: typography.fontSize.sm, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={formData.patient_conscious}
                    onChange={(e) => updateField('patient_conscious', e.target.checked)}
                  />
                  Patient is conscious
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: typography.fontSize.sm, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={formData.patient_breathing}
                    onChange={(e) => updateField('patient_breathing', e.target.checked)}
                  />
                  Patient is breathing
                </label>
              </div>
            </div>

            <Input
              label="Reporter / Contact Name"
              required
              placeholder="Your full name"
              value={formData.contact_name}
              onChange={(e) => updateField('contact_name', e.target.value)}
            />

            <Input
              label="Callback Phone Number"
              required
              type="tel"
              placeholder="e.g. 9876543210"
              value={formData.contact_phone}
              onChange={(e) => updateField('contact_phone', e.target.value)}
              helperText="Dispatchers or paramedics will use this number to contact you directly."
            />
          </div>
        )}

        {/* STEP 4: HAZARDS & NOTES */}
        {currentStep === 3 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 16px' }}>
              Step 4: Additional Hazards & Access Notes
            </h2>

            <Input
              label="Access Codes, Building, or Floor Notes"
              as="textarea"
              placeholder="e.g. 2nd Floor, Apt 204, Ring bell, Gate code 1234, Guard aware..."
              value={formData.additional_details}
              onChange={(e) => updateField('additional_details', e.target.value)}
            />

            <div
              style={{
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                padding: '16px',
                backgroundColor: colors.surfaceSubtle,
                marginBottom: '16px',
              }}
            >
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontWeight: typography.fontWeight.semibold }}>
                <input
                  type="checkbox"
                  checked={formData.is_disaster}
                  onChange={(e) => updateField('is_disaster', e.target.checked)}
                />
                Is this a mass casualty incident or widespread disaster?
              </label>

              {formData.is_disaster && (
                <div style={{ marginTop: '12px' }}>
                  <Input
                    label="Disaster Details"
                    placeholder="Describe scale, structural danger, trapped individuals..."
                    value={formData.disaster_details}
                    onChange={(e) => updateField('disaster_details', e.target.value)}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 5: REVIEW & SUBMIT */}
        {currentStep === 4 && (
          <div>
            <h2 style={{ fontSize: typography.fontSize.lg, fontWeight: typography.fontWeight.semibold, margin: '0 0 16px' }}>
              Step 5: Review Emergency Details
            </h2>

            <div
              style={{
                backgroundColor: colors.surfaceSubtle,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                marginBottom: '20px',
                fontSize: typography.fontSize.sm,
              }}
            >
              <div>
                <strong>Category:</strong> {formData.category} ({formData.help_required})
              </div>
              <div>
                <strong>Description:</strong> {formData.description}
              </div>
              <div>
                <strong>Location:</strong> {formData.location_name} (Coordinates: {formData.latitude}, {formData.longitude})
              </div>
              <div>
                <strong>Patients:</strong> {formData.affected_people} | Conscious: {formData.patient_conscious ? 'Yes' : 'No'} | Breathing: {formData.patient_breathing ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Reporter:</strong> {formData.contact_name} ({formData.contact_phone})
              </div>
              {formData.additional_details && (
                <div>
                  <strong>Access Notes:</strong> {formData.additional_details}
                </div>
              )}
            </div>

            <div
              style={{
                padding: '12px',
                backgroundColor: '#FEF2F2',
                border: '1px solid #FECACA',
                borderRadius: '6px',
                fontSize: typography.fontSize.xs,
                color: colors.secondary,
                marginBottom: '20px',
              }}
            >
              <strong>CONFIRMATION:</strong> By clicking submit, you confirm that this is a genuine emergency report. Dispatchers will review and assign emergency units immediately.
            </div>
          </div>
        )}

        {/* Navigation Step Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: `1px solid ${colors.border}`,
            paddingTop: '16px',
            marginTop: '8px',
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
              onClick={() => onNavigate('/')}
            >
              Cancel
            </Button>
          )}

          {currentStep < STEPS.length - 1 ? (
            <Button
              type="button"
              variant="primary"
              onClick={handleNext}
              icon={ArrowRight}
              iconPosition="right"
            >
              Continue
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              onClick={handleSubmit}
              loading={isSubmitting}
              icon={Send}
              style={{ padding: '12px 28px', fontSize: typography.fontSize.base }}
            >
              SUBMIT EMERGENCY REPORT
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
