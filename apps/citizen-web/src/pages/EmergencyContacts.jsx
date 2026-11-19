import React, { useState, useEffect } from 'react';
import { User, Phone, Plus, Trash2, Heart, Save, CheckCircle } from 'lucide-react';
import {
  Button,
  Card,
  Input,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';

const STORAGE_KEY = 'careon_citizen_ice_contacts';

export function EmergencyContacts() {
  const [contacts, setContacts] = useState([]);
  const [name, setName] = useState('');
  const [relationship, setRelationship] = useState('Family');
  const [phone, setPhone] = useState('');
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setContacts(JSON.parse(raw));
      } else {
        // Default seed contacts for demo
        setContacts([
          { id: 'c1', name: 'Dr. Ramesh Singh (Father)', relationship: 'Father', phone: '+91 98450 12345' },
          { id: 'c2', name: 'Sunita Singh (Mother)', relationship: 'Mother', phone: '+91 98450 54321' },
        ]);
      }
    } catch (e) {
      // ignore
    }
  }, []);

  const saveToStorage = (updatedList) => {
    setContacts(updatedList);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedList));
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  const handleAddContact = (e) => {
    e.preventDefault();
    if (!name.trim() || !phone.trim()) return;

    const newContact = {
      id: `c_${Date.now()}`,
      name: name.trim(),
      relationship,
      phone: phone.trim(),
    };

    saveToStorage([...contacts, newContact]);
    setName('');
    setPhone('');
  };

  const handleDelete = (id) => {
    saveToStorage(contacts.filter((c) => c.id !== id));
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
        In Case of Emergency (ICE) Contacts
      </h1>
      <p style={{ margin: '0 0 24px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        These contacts are alerted when you report an emergency, and paramedics can reach them if you are incapacitated.
      </p>

      {savedSuccess && (
        <Alert variant="success" icon={CheckCircle}>
          Emergency contacts updated.
        </Alert>
      )}

      {/* Add Contact Card */}
      <Card padding="md" style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: '0 0 16px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
          Add Emergency Contact
        </h2>
        <form onSubmit={handleAddContact}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <Input
              label="Contact Full Name"
              required
              placeholder="e.g. Priya Sharma"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Input
              label="Relationship"
              as="select"
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
            >
              <option value="Spouse">Spouse / Partner</option>
              <option value="Parent">Parent</option>
              <option value="Sibling">Sibling</option>
              <option value="Child">Child</option>
              <option value="Friend">Friend</option>
              <option value="Guardian">Guardian</option>
              <option value="Other">Other</option>
            </Input>
          </div>

          <Input
            label="Phone Number"
            required
            type="tel"
            placeholder="e.g. +91 98765 43210"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="submit" variant="secondary-red" icon={Plus}>
              Add Contact
            </Button>
          </div>
        </form>
      </Card>

      {/* Existing Contacts List */}
      <h2 style={{ margin: '0 0 12px', fontSize: typography.fontSize.base, fontWeight: typography.fontWeight.semibold }}>
        Registered Contacts ({contacts.length})
      </h2>

      {contacts.length === 0 ? (
        <Card padding="md" style={{ textAlign: 'center', color: colors.textSecondary }}>
          No emergency contacts added yet. Add at least one family member or guardian.
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {contacts.map((c) => (
            <Card
              key={c.id}
              padding="sm"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong style={{ fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                    {c.name}
                  </strong>
                  <Badge variant="neutral" size="sm">
                    {c.relationship}
                  </Badge>
                </div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary, marginTop: '2px' }}>
                  {c.phone}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <a
                  href={`tel:${c.phone}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '6px 10px',
                    backgroundColor: colors.surfaceSubtle,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '4px',
                    color: colors.textPrimary,
                    fontSize: typography.fontSize.xs,
                    textDecoration: 'none',
                  }}
                >
                  <Phone size={12} color={colors.secondary} /> Call
                </a>

                <button
                  onClick={() => handleDelete(c.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: colors.textSecondary,
                    cursor: 'pointer',
                    padding: '6px',
                  }}
                  title="Remove contact"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
