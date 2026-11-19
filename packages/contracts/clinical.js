/**
 * CareOn Milestone 13 — Clinical & Hospital Coordination Contracts.
 * Authoritative types, status enums, triage priorities, and SBAR handover contracts.
 */

export const INCOMING_REQUEST_STATUSES = {
  PENDING: 'pending',
  ACKNOWLEDGED: 'acknowledged',
  ACCEPTED: 'accepted',
  DECLINED: 'declined',
  CLARIFYING: 'clarifying',
  CANCELLED: 'cancelled',
  TIMEOUT: 'timeout',
};

export const INCOMING_REQUEST_STATUS_CONFIG = {
  pending: { label: 'Pending Action', color: 'danger', bg: '#FEE2E2', text: '#991B1B' },
  acknowledged: { label: 'Acknowledged', color: 'warning', bg: '#FEF3C7', text: '#92400E' },
  accepted: { label: 'Accepted / Bed Reserved', color: 'success', bg: '#D1FAE5', text: '#065F46' },
  declined: { label: 'Declined', color: 'default', bg: '#F3F4F6', text: '#374151' },
  clarifying: { label: 'Clarification Needed', color: 'warning', bg: '#FEF3C7', text: '#92400E' },
  needs_clarification: { label: 'Clarification Needed', color: 'warning', bg: '#FEF3C7', text: '#92400E' },
  cancelled: { label: 'Mission Cancelled', color: 'default', bg: '#F3F4F6', text: '#6B7280' },
  timeout: { label: 'Response Timed Out', color: 'danger', bg: '#FEE2E2', text: '#991B1B' },
};

export const HANDOVER_STATUSES = {
  DRAFT: 'draft',
  SUBMITTED: 'submitted',
  RECEIVED: 'received',
  ACKNOWLEDGED: 'acknowledged',
  CLARIFICATION_REQUESTED: 'clarification_requested',
  CORRECTED: 'corrected',
  COMPLETED: 'completed',
};

export const HANDOVER_STATUS_CONFIG = {
  draft: { label: 'Draft', color: 'default' },
  submitted: { label: 'Submitted (Pre-Arrival)', color: 'warning' },
  received: { label: 'Intake Received', color: 'info' },
  acknowledged: { label: 'Clinician Acknowledged', color: 'primary' },
  clarification_requested: { label: 'Clarification Requested', color: 'warning' },
  corrected: { label: 'Version Amended', color: 'info' },
  completed: { label: 'Care Transferred', color: 'success' },
};

export const BED_CATEGORIES = {
  EMERGENCY: 'Emergency Department',
  ICU: 'Intensive Care Unit (ICU)',
  TRAUMA: 'Trauma Resuscitation Bay',
  OPERATING_ROOM: 'Operating Room / Surgical Suite',
};

export const TRIAGE_PRIORITIES = {
  P1: { label: 'P1 — Resuscitation (Immediate)', color: 'danger', code: 'P1' },
  P2: { label: 'P2 — Emergent (Within 15 mins)', color: 'warning', code: 'P2' },
  P3: { label: 'P3 — Urgent (Within 30 mins)', color: 'info', code: 'P3' },
  P4: { label: 'P4 — Less Urgent (Within 60 mins)', color: 'default', code: 'P4' },
};

export const SBAR_SECTIONS = [
  { key: 'situation', label: 'S — Situation', placeholder: 'Presenting chief complaint, mechanism of injury, acute clinical concern...' },
  { key: 'background', label: 'B — Background', placeholder: 'Medical history, allergies, baseline functional status, medications...' },
  { key: 'assessment', label: 'A — Assessment', placeholder: 'Vital signs trend, ABCDE findings, diagnostic interpretation...' },
  { key: 'recommendation', label: 'R — Recommendation', placeholder: 'Immediate specialty team needs, required room/bed, planned interventions...' },
];

export const HOSPITAL_ROLES = {
  HOSPITAL_STAFF: 'hospital_staff',
  ORG_ADMIN: 'org_admin',
  SUPER_ADMIN: 'super_admin',
  DISPATCHER: 'dispatcher',
};
