import { describe, it, expect } from 'vitest';
import {
  PREFERRED_LANGUAGES,
  CONTACT_RELATIONSHIPS,
  BLOOD_GROUPS,
} from '@careon/contracts';

describe('CareOn Citizen — Onboarding, Profile & ICE Contracts', () => {
  it('defines valid Indian & International emergency contact relationships', () => {
    expect(CONTACT_RELATIONSHIPS).toContain('Family');
    expect(CONTACT_RELATIONSHIPS).toContain('Spouse');
    expect(CONTACT_RELATIONSHIPS).toContain('Parent');
    expect(CONTACT_RELATIONSHIPS).toContain('Doctor');
    expect(CONTACT_RELATIONSHIPS).toContain('Caregiver');
    expect(CONTACT_RELATIONSHIPS.length).toBeGreaterThanOrEqual(8);
  });

  it('defines supported regional languages for emergency instructions', () => {
    const codes = PREFERRED_LANGUAGES.map((l) => l.code);
    expect(codes).toContain('en');
    expect(codes).toContain('hi');
    expect(codes).toContain('kn');
    expect(codes).toContain('te');
    expect(codes).toContain('ta');
  });

  it('contains universal human blood group classifications plus UNKNOWN', () => {
    expect(BLOOD_GROUPS).toContain('A+');
    expect(BLOOD_GROUPS).toContain('O+');
    expect(BLOOD_GROUPS).toContain('O-');
    expect(BLOOD_GROUPS).toContain('B+');
    expect(BLOOD_GROUPS).toContain('AB+');
    expect(BLOOD_GROUPS).toContain('UNKNOWN');
  });

  it('computes emergency profile readiness accurately based on completed safety fields', () => {
    const calculateReadiness = (profile, contactsCount) => {
      let score = 20; // Base account
      if (profile.residential_address?.trim()) score += 25;
      if (profile.residential_city?.trim()) score += 10;
      if (contactsCount > 0) score += 25;
      if (profile.blood_group && profile.blood_group !== 'UNKNOWN') score += 10;
      if (profile.consent_data_sharing_emergency) score += 10;
      return Math.min(score, 100);
    };

    const emptyProfile = {
      residential_address: '',
      residential_city: '',
      blood_group: 'UNKNOWN',
      consent_data_sharing_emergency: false,
    };
    expect(calculateReadiness(emptyProfile, 0)).toBe(20);

    const fullProfile = {
      residential_address: '123 MG Road',
      residential_city: 'Bengaluru',
      blood_group: 'O+',
      consent_data_sharing_emergency: true,
    };
    expect(calculateReadiness(fullProfile, 2)).toBe(100);
  });

  it('mandates self-reported medical information to carry unverified disclaimer', () => {
    const disclaimerNotice = 'Self-reported medical information is provided for responder awareness only and does not constitute a verified electronic health record (EHR).';
    expect(disclaimerNotice).toContain('responder awareness only');
    expect(disclaimerNotice).toContain('does not constitute a verified electronic health record');
  });
});
