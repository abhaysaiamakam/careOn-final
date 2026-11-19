/**
 * CareOn Incident Contracts & Enums.
 * Aligned with backend models and schemas (M0-M11).
 */

export const INCIDENT_CATEGORIES = [
  { id: 'Medical', label: 'Medical Emergency', icon: 'HeartPulse', defaultHelp: 'Ambulance & Paramedic' },
  { id: 'Road accident', label: 'Road Traffic Accident', icon: 'Car', defaultHelp: 'Ambulance & Traffic Police' },
  { id: 'Fire', label: 'Fire & Rescue', icon: 'Flame', defaultHelp: 'Fire Engine & Rescue' },
  { id: 'Rescue', label: 'Trapped / Structural Collapse', icon: 'ShieldAlert', defaultHelp: 'Disaster Rescue Team' },
  { id: 'Disaster / Multiple affected people', label: 'Mass Casualty / Disaster', icon: 'Users', defaultHelp: 'Multi-Agency Emergency Response' },
  { id: 'Safety / Other', label: 'Other Urgent Assistance', icon: 'AlertTriangle', defaultHelp: 'Emergency Responder' },
];

export const INCIDENT_PRIORITIES = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

export const INCIDENT_STATUSES = {
  RECEIVED: 'Received',
  VERIFICATION_PENDING: 'Verification Pending',
  VERIFIED: 'Verified',
  ALLOCATED: 'Allocated',
  DISPATCHED: 'Dispatched',
  EN_ROUTE_TO_SCENE: 'En Route to Scene',
  AT_SCENE: 'At Scene',
  TRANSPORTING: 'Transporting',
  AT_HOSPITAL: 'At Hospital',
  RESOLVED: 'Resolved',
  CANCELLED: 'Cancelled',
  REJECTED: 'Rejected',
};

export const TRACKING_LIFECYCLE_STEPS = [
  { key: 'RECEIVED', label: 'Emergency Received', statuses: ['Received', 'Verification Pending'] },
  { key: 'VERIFIED', label: 'Triage & Verified', statuses: ['Verified', 'Allocated'] },
  { key: 'DISPATCHED', label: 'Responders Dispatched', statuses: ['Dispatched', 'En Route to Scene'] },
  { key: 'ON_SCENE', label: 'Responders on Scene', statuses: ['At Scene', 'Transporting'] },
  { key: 'HOSPITAL', label: 'Receiving Hospital Intake', statuses: ['At Hospital'] },
  { key: 'RESOLVED', label: 'Mission Completed', statuses: ['Resolved'] },
];
