import React, { useState, useEffect } from 'react';
import {
  Users,
  Phone,
  Plus,
  Trash2,
  Edit2,
  Star,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Heart,
  PhoneCall,
  ShieldAlert,
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
import { CONTACT_RELATIONSHIPS } from '@careon/contracts';
import {
  listCitizenContacts,
  createCitizenContact,
  updateCitizenContact,
  deleteCitizenContact,
} from '@careon/api-client';

export function EmergencyContacts({ onNavigate }) {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Form State
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [fullName, setFullName] = useState('');
  const [relationshipType, setRelationshipType] = useState('Spouse');
  const [phone, setPhone] = useState('');
  const [secondaryPhone, setSecondaryPhone] = useState('');
  const [email, setEmail] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [canAuthorizeTreatment, setCanAuthorizeTreatment] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchContacts = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCitizenContacts();
      setContacts(data || []);
    } catch (err) {
      console.warn('Failed to load contacts:', err);
      setError('Could not retrieve emergency contacts from server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContacts();
  }, []);

  const resetForm = () => {
    setFullName('');
    setRelationshipType('Spouse');
    setPhone('');
    setSecondaryPhone('');
    setEmail('');
    setIsPrimary(contacts.length === 0);
    setCanAuthorizeTreatment(false);
    setEditingId(null);
    setShowForm(false);
  };

  const handleStartEdit = (contact) => {
    setEditingId(contact.id);
    setFullName(contact.full_name);
    setRelationshipType(contact.relationship_type || 'Family');
    setPhone(contact.phone);
    setSecondaryPhone(contact.secondary_phone || '');
    setEmail(contact.email || '');
    setIsPrimary(Boolean(contact.is_primary));
    setCanAuthorizeTreatment(Boolean(contact.can_authorize_medical_treatment));
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!fullName.trim() || !phone.trim()) {
      setError('Name and phone number are required.');
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload = {
      full_name: fullName.trim(),
      relationship_type: relationshipType,
      phone: phone.trim(),
      secondary_phone: secondaryPhone.trim() || null,
      email: email.trim() || null,
      is_primary: isPrimary || contacts.length === 0,
      can_authorize_medical_treatment: canAuthorizeTreatment,
    };

    try {
      if (editingId) {
        await updateCitizenContact(editingId, payload);
        setSuccessMsg(`Updated contact ${fullName}.`);
      } else {
        await createCitizenContact(payload);
        setSuccessMsg(`Added ${fullName} to emergency contacts.`);
      }
      resetForm();
      await fetchContacts();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || 'Failed to save contact.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (contactId, name) => {
    if (!window.confirm(`Are you sure you want to remove ${name} from your emergency contacts?`)) {
      return;
    }
    try {
      await deleteCitizenContact(contactId);
      setSuccessMsg(`Removed ${name}.`);
      await fetchContacts();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to remove contact.');
    }
  };

  const handleSetPrimary = async (contact) => {
    try {
      await updateCitizenContact(contact.id, { is_primary: true });
      setSuccessMsg(`${contact.full_name} is now your primary emergency contact.`);
      await fetchContacts();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to update primary contact.');
    }
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '24px' }}>
        <div>
          <h1 style={{ margin: '0 0 6px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            In Case of Emergency (ICE) Contacts
          </h1>
          <p style={{ margin: 0, fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
            Notified when you trigger an emergency. Paramedics can reach them if you are incapacitated.
          </p>
        </div>

        {!showForm && contacts.length < 5 && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            icon={Plus}
          >
            Add Contact
          </Button>
        )}
      </div>

      {successMsg && (
        <div style={{ marginBottom: '16px' }}>
          <Alert variant="success" icon={CheckCircle}>
            {successMsg}
          </Alert>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: '16px' }}>
          <Alert variant="danger" icon={AlertCircle}>
            {error}
          </Alert>
        </div>
      )}

      {/* Add / Edit Form Modal/Card */}
      {showForm && (
        <Card padding="lg" style={{ marginBottom: '24px', border: `2px solid ${colors.secondary}`, background: '#FFFFFF' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ margin: 0, fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
              {editingId ? 'Edit Emergency Contact' : 'Add New Emergency Contact'}
            </h2>
            <button
              onClick={resetForm}
              style={{ background: 'none', border: 'none', color: colors.textSecondary, fontSize: typography.fontSize.sm, cursor: 'pointer' }}
            >
              Cancel
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                <Input
                  label="Contact Full Name"
                  required
                  placeholder="e.g. Maya Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />

                <div>
                  <label style={{ display: 'block', fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.semibold, color: colors.textPrimary, marginBottom: '6px' }}>
                    Relationship
                  </label>
                  <select
                    value={relationshipType}
                    onChange={(e) => setRelationshipType(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      border: `1px solid ${colors.border}`,
                      fontSize: typography.fontSize.sm,
                      background: '#FFFFFF',
                    }}
                  >
                    {CONTACT_RELATIONSHIPS.map((rel) => (
                      <option key={rel} value={rel}>
                        {rel}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                <Input
                  label="Mobile Phone Number"
                  required
                  type="tel"
                  placeholder="+91 98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />

                <Input
                  label="Secondary Phone (Optional)"
                  type="tel"
                  placeholder="+91 98765 00000"
                  value={secondaryPhone}
                  onChange={(e) => setSecondaryPhone(e.target.value)}
                />
              </div>

              <Input
                label="Email Address (Optional)"
                type="email"
                placeholder="contact@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <div style={{ background: '#F9FAFB', padding: '12px', borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: typography.fontSize.sm, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isPrimary}
                    onChange={(e) => setIsPrimary(e.target.checked)}
                    style={{ width: '16px', height: '16px', accentColor: colors.secondary }}
                  />
                  <span style={{ fontWeight: typography.fontWeight.semibold, color: colors.textPrimary }}>
                    Designate as Primary ICE Contact
                  </span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: typography.fontSize.sm, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={canAuthorizeTreatment}
                    onChange={(e) => setCanAuthorizeTreatment(e.target.checked)}
                    style={{ width: '16px', height: '16px', accentColor: colors.secondary }}
                  />
                  <span style={{ color: colors.textSecondary }}>
                    Authorized to make medical decisions if I am unconscious
                  </span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                <Button type="button" variant="outline" onClick={resetForm}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" loading={submitting}>
                  {editingId ? 'Update Contact' : 'Save Contact'}
                </Button>
              </div>
            </div>
          </form>
        </Card>
      )}

      {/* Contacts List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '36px 0' }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px', color: colors.secondary }} />
          <div style={{ fontSize: typography.fontSize.sm, color: colors.textSecondary }}>Loading emergency contacts...</div>
        </div>
      ) : contacts.length === 0 ? (
        <Card padding="lg" style={{ textAlign: 'center', border: '1px dashed #D1D5DB', padding: '40px 20px' }}>
          <ShieldAlert size={40} color={colors.secondary} style={{ margin: '0 auto 12px', opacity: 0.8 }} />
          <h3 style={{ margin: '0 0 6px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            No Emergency Contacts Configured
          </h3>
          <p style={{ margin: '0 0 18px', fontSize: typography.fontSize.sm, color: colors.textSecondary, maxWidth: '420px', marginLeft: 'auto', marginRight: 'auto' }}>
            In an emergency, responders and hospital triage teams will not know who to contact on your behalf.
          </p>
          <Button
            size="md"
            variant="primary"
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            icon={Plus}
          >
            Add Primary Emergency Contact
          </Button>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, textTransform: 'uppercase', fontWeight: typography.fontWeight.semibold }}>
              Configured Contacts ({contacts.length} / 5)
            </span>
          </div>

          {contacts.map((contact) => (
            <Card
              key={contact.id}
              padding="md"
              style={{
                border: contact.is_primary ? `2px solid ${colors.secondary}` : `1px solid ${colors.border}`,
                background: '#FFFFFF',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
                      {contact.full_name}
                    </span>
                    <Badge variant="neutral">{contact.relationship_type}</Badge>
                    {contact.is_primary && (
                      <Badge variant="danger">
                        PRIMARY ICE
                      </Badge>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: typography.fontSize.sm, color: colors.textPrimary, fontWeight: typography.fontWeight.medium }}>
                      {contact.phone}
                    </span>
                    {contact.secondary_phone && (
                      <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                        Alt: {contact.secondary_phone}
                      </span>
                    )}
                    {contact.email && (
                      <span style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                        {contact.email}
                      </span>
                    )}
                  </div>

                  {contact.can_authorize_medical_treatment && (
                    <div style={{ fontSize: '11px', color: '#047857', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle size={12} /> Authorized for proxy medical decisions
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <a
                    href={`tel:${contact.phone}`}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      background: '#FEE2E2',
                      color: colors.secondary,
                      textDecoration: 'none',
                      fontSize: typography.fontSize.xs,
                      fontWeight: typography.fontWeight.bold,
                    }}
                  >
                    <PhoneCall size={14} />
                    Call
                  </a>

                  {!contact.is_primary && (
                    <button
                      onClick={() => handleSetPrimary(contact)}
                      title="Set as Primary ICE"
                      style={{
                        background: 'none',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '6px',
                        padding: '6px 8px',
                        fontSize: typography.fontSize.xs,
                        color: colors.textSecondary,
                        cursor: 'pointer',
                      }}
                    >
                      Make Primary
                    </button>
                  )}

                  <button
                    onClick={() => handleStartEdit(contact)}
                    title="Edit contact"
                    style={{
                      background: 'none',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '6px',
                      padding: '6px 8px',
                      color: colors.textSecondary,
                      cursor: 'pointer',
                    }}
                  >
                    <Edit2 size={14} />
                  </button>

                  <button
                    onClick={() => handleDelete(contact.id, contact.full_name)}
                    title="Delete contact"
                    style={{
                      background: 'none',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '6px',
                      padding: '6px 8px',
                      color: '#EF4444',
                      cursor: 'pointer',
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
