import React, { useState, useEffect } from 'react';
import { User, Phone, Mail, ShieldCheck, Heart, Save, CheckCircle } from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { BLOOD_GROUPS } from '@careon/contracts';
import { updateMyProfile } from '@careon/api-client';
import { useAuth } from '@careon/auth';

export function Profile({ onNavigate }) {
  const { user, refreshProfile } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [bloodGroup, setBloodGroup] = useState(localStorage.getItem('careon_citizen_blood_group') || 'O+');
  const [allergies, setAllergies] = useState(localStorage.getItem('careon_citizen_allergies') || '');
  const [medicalNotes, setMedicalNotes] = useState(localStorage.getItem('careon_citizen_medical_notes') || '');

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (user) {
      setName(user.name || '');
      setPhone(user.phone || '');
    }
  }, [user]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      await updateMyProfile({ name: name.trim(), phone: phone.trim() });
      localStorage.setItem('careon_citizen_blood_group', bloodGroup);
      localStorage.setItem('careon_citizen_allergies', allergies);
      localStorage.setItem('careon_citizen_medical_notes', medicalNotes);

      if (refreshProfile) {
        await refreshProfile();
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err) {
      setSaveError(err.message || 'Failed to update citizen profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
        Citizen Profile & Emergency Card
      </h1>
      <p style={{ margin: '0 0 24px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        Keep your callback number, emergency medical summary, and triage details updated for responders.
      </p>

      {saveSuccess && (
        <Alert variant="success" icon={CheckCircle}>
          Profile information updated successfully.
        </Alert>
      )}

      {saveError && (
        <Alert variant="danger">
          {saveError}
        </Alert>
      )}

      <form onSubmit={handleSave}>
        {/* Account Details */}
        <Card padding="lg" style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
              Account Identity
            </h2>
            <Badge variant="neutral">
              Trust Score: {user?.trust_score || 'Standard'}
            </Badge>
          </div>

          <Input
            label="Full Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Input
            label="Verified Phone Number"
            required
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            helperText="Responders and emergency dispatchers reach you on this number."
          />

          <Input
            label="Email Address (Locked)"
            disabled
            value={user?.email || ''}
            helperText="Primary authentication identifier."
          />
        </Card>

        {/* Emergency Medical Information */}
        <Card padding="lg" style={{ marginBottom: '24px' }}>
          <h2 style={{ margin: '0 0 16px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
            Emergency Medical Information
          </h2>

          <Input
            label="Blood Group"
            as="select"
            value={bloodGroup}
            onChange={(e) => setBloodGroup(e.target.value)}
          >
            {BLOOD_GROUPS.map((bg) => (
              <option key={bg} value={bg}>{bg}</option>
            ))}
          </Input>

          <Input
            label="Severe Allergies (e.g. Penicillin, Latex, Peanuts)"
            placeholder="e.g. Penicillin, Aspirin..."
            value={allergies}
            onChange={(e) => setAllergies(e.target.value)}
          />

          <Input
            label="Chronic Medical Conditions & Notes"
            as="textarea"
            placeholder="e.g. Type-1 Diabetic, Cardiac Stent placed 2024, Asthmatic..."
            value={medicalNotes}
            onChange={(e) => setMedicalNotes(e.target.value)}
            helperText="Shared securely with paramedic responders and emergency receiving physicians."
          />
        </Card>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <Button
            type="submit"
            variant="primary"
            loading={saving}
            icon={Save}
          >
            Save Profile
          </Button>
        </div>
      </form>
    </div>
  );
}
