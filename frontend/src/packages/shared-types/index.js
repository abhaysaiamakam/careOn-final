/**
 * CareOn Shared Types & Constants.
 */

export const UserRoles = {
  CITIZEN: 'citizen',
  DISPATCHER: 'dispatcher',
  RESPONDER: 'responder',
  HOSPITAL_STAFF: 'hospital_staff',
  ORGANIZATION_ADMIN: 'org_admin',
  SUPER_ADMIN: 'super_admin',
};

export const EmergencyCategories = [
  { id: 'Medical', label: 'Medical Emergency', icon: 'HeartPulse', color: '#ef4444' },
  { id: 'Road accident', label: 'Road Accident', icon: 'CarCrash', color: '#f97316' },
  { id: 'Fire', label: 'Fire & Explosion', icon: 'Flame', color: '#dc2626' },
  { id: 'Rescue', label: 'Rescue / Trapped', icon: 'ShieldAlert', color: '#eab308' },
  { id: 'Disaster / Multiple affected people', label: 'Disaster / Mass Casualty', icon: 'AlertTriangle', color: '#b91c1c' },
  { id: 'Safety / Other', label: 'Safety / General Assistance', icon: 'HelpCircle', color: '#3b82f6' },
];

export const MissionStatuses = {
  ASSIGNED: 'Active',
  ACCEPTED: 'Accepted',
  EN_ROUTE: 'En Route',
  ON_SCENE: 'On Scene',
  TRANSPORTING: 'Transporting',
  AT_HOSPITAL: 'Arrived Hospital',
  COMPLETED: 'Completed',
  REJECTED: 'Rejected',
};

export const BedTypes = {
  ER_BED: 'er_bed',
  ICU_BED: 'icu_bed',
  TRAUMA_BAY: 'trauma_bay',
  OPERATING_ROOM: 'operating_room',
};
