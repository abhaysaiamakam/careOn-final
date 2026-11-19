/**
 * Offline Drafts & Sync Contracts.
 *
 * CRITICAL SAFETY REQUIREMENT:
 * A locally saved emergency draft is NOT a submitted emergency.
 * Drafts must never claim to have been received by emergency services.
 * Stale drafts (> 24 hours) must be explicitly flagged and cannot be auto-submitted.
 */

export const DRAFT_STATUSES = {
  LOCAL_ONLY: 'LOCAL_ONLY',
  EXPIRED: 'EXPIRED',
  SUBMITTED: 'SUBMITTED',
};

export const MAX_DRAFT_AGE_HOURS = 24;
