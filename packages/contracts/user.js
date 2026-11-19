/**
 * CareOn User, Citizen Profile & Emergency Contacts Contracts.
 */

export const USER_ROLES = {
  USER: 'user',
  ADMIN: 'admin',
  SUPER_ADMIN: 'super_admin',
};

export const BLOOD_GROUPS = [
  'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'UNKNOWN',
];

export const PREFERRED_LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
];

export const CONTACT_RELATIONSHIPS = [
  'Family',
  'Spouse',
  'Parent',
  'Child',
  'Sibling',
  'Friend',
  'Doctor',
  'Caregiver',
  'Guardian',
  'Colleague',
  'Other',
];
