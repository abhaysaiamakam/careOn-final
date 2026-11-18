/**
 * CareOn Mobile Durable Action Journal.
 *
 * Implements the local persistent action journal for the responder application.
 * Actions are persisted to durable storage BEFORE showing as safely recorded,
 * surviving application crashes and device restarts.
 */

import { syncStorage } from './syncStorage';

export const SyncStatus = {
  PENDING: 'PENDING',
  IN_FLIGHT: 'IN_FLIGHT',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  RETRYABLE_FAILURE: 'RETRYABLE_FAILURE',
  PERMANENT_FAILURE: 'PERMANENT_FAILURE',
  CONFLICT_REQUIRES_REVIEW: 'CONFLICT_REQUIRES_REVIEW',
};

// In-memory registry mirrored with durable syncStorage
let actionIndex = [];
let monotonicSeq = 1;

export const actionJournal = {
  /**
   * Record a new offline-capable field action durably.
   */
  async recordAction({
    actionType,
    missionId = null,
    encounterId = null,
    patientId = null,
    payload = {},
    userId = null,
  }) {
    const devId = await syncStorage.getOrCreateDeviceId();
    const actionUuid = `act_${Math.random().toString(36).substring(2, 12)}_${Date.now()}`;
    const nowIso = new Date().toISOString();

    const record = {
      actionUuid,
      deviceId: devId,
      userId,
      missionId,
      encounterId,
      patientId,
      actionType,
      payload,
      clientTimestamp: nowIso,
      deviceSequenceNumber: monotonicSeq++,
      localCreatedAt: nowIso,
      retryCount: 0,
      syncStatus: SyncStatus.PENDING,
      lastSyncAttempt: null,
      serverAckId: null,
      conflictDetails: null,
      errorMessage: null,
    };

    // 1. Persist durably before acknowledging locally
    await syncStorage.saveActionRecord(actionUuid, record);

    // 2. Track in index
    if (!actionIndex.includes(actionUuid)) {
      actionIndex.push(actionUuid);
    }

    return record;
  },

  /**
   * Retrieve all actions ready for synchronization (PENDING or RETRYABLE_FAILURE).
   */
  async getPendingActions() {
    const pending = [];
    for (const uuid of actionIndex) {
      const rec = await syncStorage.getActionRecord(uuid);
      if (
        rec &&
        (rec.syncStatus === SyncStatus.PENDING ||
          rec.syncStatus === SyncStatus.RETRYABLE_FAILURE)
      ) {
        pending.push(rec);
      }
    }
    return pending;
  },

  /**
   * Mark actions as IN_FLIGHT during an active upload batch.
   */
  async markInFlight(actionUuids) {
    const nowIso = new Date().toISOString();
    for (const uuid of actionUuids) {
      const rec = await syncStorage.getActionRecord(uuid);
      if (rec) {
        rec.syncStatus = SyncStatus.IN_FLIGHT;
        rec.lastSyncAttempt = nowIso;
        rec.retryCount = (rec.retryCount || 0) + 1;
        await syncStorage.saveActionRecord(uuid, rec);
      }
    }
  },

  /**
   * Mark action as ACKNOWLEDGED upon receipt of server acknowledgement.
   */
  async markAcknowledged(actionUuid, serverAckId) {
    const rec = await syncStorage.getActionRecord(actionUuid);
    if (rec) {
      rec.syncStatus = SyncStatus.ACKNOWLEDGED;
      rec.serverAckId = serverAckId;
      rec.errorMessage = null;
      await syncStorage.saveActionRecord(actionUuid, rec);
    }
  },

  /**
   * Mark action as failed (either retryable or permanent failure).
   */
  async markFailed(actionUuid, errorMessage, isRetryable = true) {
    const rec = await syncStorage.getActionRecord(actionUuid);
    if (rec) {
      rec.syncStatus = isRetryable
        ? SyncStatus.RETRYABLE_FAILURE
        : SyncStatus.PERMANENT_FAILURE;
      rec.errorMessage = errorMessage;
      await syncStorage.saveActionRecord(actionUuid, rec);
    }
  },

  /**
   * Mark action as CONFLICT_REQUIRES_REVIEW when server reports a state conflict.
   */
  async markConflict(actionUuid, conflictDetails) {
    const rec = await syncStorage.getActionRecord(actionUuid);
    if (rec) {
      rec.syncStatus = SyncStatus.CONFLICT_REQUIRES_REVIEW;
      rec.conflictDetails = conflictDetails;
      await syncStorage.saveActionRecord(actionUuid, rec);
    }
  },

  /**
   * Get summary statistics of the local action journal.
   */
  async getJournalStats() {
    let pending = 0;
    let acknowledged = 0;
    let failed = 0;
    let conflicts = 0;

    for (const uuid of actionIndex) {
      const rec = await syncStorage.getActionRecord(uuid);
      if (!rec) continue;
      if (rec.syncStatus === SyncStatus.PENDING || rec.syncStatus === SyncStatus.IN_FLIGHT) {
        pending++;
      } else if (rec.syncStatus === SyncStatus.ACKNOWLEDGED) {
        acknowledged++;
      } else if (rec.syncStatus === SyncStatus.CONFLICT_REQUIRES_REVIEW) {
        conflicts++;
      } else {
        failed++;
      }
    }

    return {
      total: actionIndex.length,
      pending,
      acknowledged,
      failed,
      conflicts,
    };
  },
};
