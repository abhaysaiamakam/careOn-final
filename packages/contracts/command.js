/**
 * CareOn Dispatcher Command Contracts, Enums & Operational Standards.
 * Aligned with backend M0–M11 architecture.
 */

export const RESOURCE_STATUSES = {
  AVAILABLE: 'Available',
  ASSIGNED: 'Assigned',
  EN_ROUTE: 'En Route',
  ON_SCENE: 'On Scene',
  TRANSPORTING: 'Transporting',
  RETURNING: 'Returning',
  MAINTENANCE: 'Maintenance',
  OFFLINE: 'Offline',
};

export const RESOURCE_CATEGORIES = [
  'Ambulance',
  'Fire Response',
  'Police Patrol',
  'Rescue Team',
  'Medical Team',
  'Shelter / Relief Centre',
];

export const HOSPITAL_TRAUMA_LEVELS = [
  'Level 1',
  'Level 2',
  'Level 3',
  'Community Emergency',
];

export const AGENCY_TYPES = {
  EMS: 'EMS',
  POLICE: 'POLICE',
  FIRE_RESCUE: 'FIRE_RESCUE',
  DISASTER_RESPONSE: 'DISASTER_RESPONSE',
  HOSPITAL: 'HOSPITAL',
  COMMAND_CENTRE: 'COMMAND_CENTRE',
  OTHER: 'OTHER',
};

export const OPERATIONAL_ZONE_TYPES = [
  { id: 'HOT_ZONE', label: 'Hot Zone (Exclusion)', color: '#EF4444' },
  { id: 'WARM_ZONE', label: 'Warm Zone (Decontamination / Access)', color: '#F59E0B' },
  { id: 'COLD_ZONE', label: 'Cold Zone (Support / Command Post)', color: '#10B981' },
  { id: 'TRIAGE_STAGING', label: 'Triage & Staging Area', color: '#6366F1' },
  { id: 'CASUALTY_COLLECTION', label: 'Casualty Collection Point (CCP)', color: '#EC4899' },
];

export const HANDOVER_STATUSES = {
  DRAFT: 'Draft',
  READY: 'Ready for Handover',
  SUBMITTED: 'Submitted',
  RECEIVED: 'Received',
  ACKNOWLEDGED: 'Acknowledged',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
};

export const DISPATCH_QUEUE_TABS = [
  { id: 'ALL', label: 'All Incidents' },
  { id: 'UNASSIGNED', label: 'Awaiting Dispatch' },
  { id: 'CRITICAL', label: 'Critical Triage' },
  { id: 'ACTIVE', label: 'Active Missions' },
  { id: 'MCI', label: 'Mass Casualty (MCI)' },
  { id: 'RESOLVED', label: 'Resolved' },
];
