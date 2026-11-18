/**
 * CareOn Mobile Synchronization Engine.
 *
 * Orchestrates upload of queued local actions, server change downloads,
 * cursor advancement, and network resilience with exponential backoff.
 */

import { mobileApi } from './api';
import { syncStorage } from './syncStorage';
import { actionJournal, SyncStatus } from './actionJournal';

let isSyncing = false;
let syncInterval = null;
let consecutiveFailures = 0;

export const syncEngine = {
  /**
   * Initialize and start periodic background synchronization when online.
   */
  start(intervalMs = 15000) {
    if (syncInterval) clearInterval(syncInterval);
    syncInterval = setInterval(() => {
      this.syncCycle().catch((err) => {
        console.warn('Sync cycle error:', err.message);
      });
    }, intervalMs);
  },

  stop() {
    if (syncInterval) {
      clearInterval(syncInterval);
      syncInterval = null;
    }
  },

  /**
   * Execute a single synchronization pass (Upload Queued Actions -> Download Changes -> Advance Cursor).
   */
  async syncCycle() {
    if (isSyncing) return;
    isSyncing = true;

    try {
      const devId = await syncStorage.getOrCreateDeviceId();

      // Ensure device registration
      await this.ensureDeviceRegistered(devId);

      // Phase 1: Upload Queued Local Actions
      await this.uploadQueuedActions(devId);

      // Phase 2: Download Authoritative Server Changes
      await this.downloadServerChanges(devId);

      consecutiveFailures = 0;
    } catch (err) {
      consecutiveFailures++;
      const backoffSec = Math.min(60, Math.pow(2, consecutiveFailures));
      console.warn(`Sync failed (attempt ${consecutiveFailures}). Backoff ${backoffSec}s:`, err.message);
      throw err;
    } finally {
      isSyncing = false;
    }
  },

  async ensureDeviceRegistered(deviceId) {
    try {
      await mobileApi.registerDevice({
        device_identifier: deviceId,
        platform: 'mobile',
        app_version: '1.0.0',
        device_model: 'Expo Responder Client',
      });
    } catch (err) {
      // If already registered, that's fine
      if (!err.message.includes('403')) {
        console.warn('Device registration notice:', err.message);
      }
    }
  },

  async uploadQueuedActions(deviceId) {
    const pending = await actionJournal.getPendingActions();
    if (pending.length === 0) return;

    const actionUuids = pending.map((p) => p.actionUuid);
    await actionJournal.markInFlight(actionUuids);

    const batchId = `batch_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
    const batchPayload = {
      device_id: deviceId,
      client_batch_id: batchId,
      actions: pending.map((p) => ({
        action_uuid: p.actionUuid,
        action_type: p.actionType,
        mission_id: p.missionId,
        encounter_id: p.encounterId,
        client_timestamp: p.clientTimestamp,
        device_sequence_number: p.deviceSequenceNumber,
        payload: p.payload,
      })),
    };

    const res = await mobileApi.uploadSyncBatch(batchPayload);

    // Process server receipts
    if (res && res.results) {
      for (const item of res.results) {
        if (item.status === 'ACKNOWLEDGED') {
          await actionJournal.markAcknowledged(item.action_uuid, item.server_ack_id);
        } else if (item.status === 'CONFLICT') {
          await actionJournal.markConflict(item.action_uuid, item.conflict_details);
        } else {
          await actionJournal.markFailed(item.action_uuid, item.error_message || 'Sync error', false);
        }
      }
    }
  },

  async downloadServerChanges(deviceId) {
    const cursor = await syncStorage.getSyncCursor();
    const res = await mobileApi.downloadSyncChanges(deviceId, cursor, 50);

    if (res && res.changes && res.changes.length > 0) {
      // Process incoming changes
      for (const change of res.changes) {
        if (change.entity_type === 'mission') {
          await syncStorage.saveCachedMission(change.data);
        }
      }

      // Safely advance cursor
      await mobileApi.acknowledgeCursor(deviceId, res.next_cursor);
      await syncStorage.setSyncCursor(res.next_cursor);
    }
  },
};
