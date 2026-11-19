/**
 * CareOn Responder — M9 Offline Synchronization Service.
 * Orchestrates background batch upload of queued actions,
 * status receipt handling, and network recovery.
 */

import { uploadSyncBatch, registerSyncDevice } from '@careon/api-client';
import { offlineJournal, SyncStatus } from './offlineJournal.js';

class SyncCoordinatorService {
  constructor() {
    this.isSyncing = false;
    this.syncInterval = null;
    this.consecutiveFailures = 0;
    this.isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
    this.onlineListeners = new Set();

    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        this.isOnline = true;
        this._notifyOnlineState();
        this.syncNow();
      });
      window.addEventListener('offline', () => {
        this.isOnline = false;
        this._notifyOnlineState();
      });
    }
  }

  onOnlineStateChange(callback) {
    this.onlineListeners.add(callback);
    callback(this.isOnline);
    return () => this.onlineListeners.delete(callback);
  }

  _notifyOnlineState() {
    this.onlineListeners.forEach((cb) => {
      try {
        cb(this.isOnline);
      } catch (e) {
        console.error('Online state listener error:', e);
      }
    });
  }

  startAutoSync(intervalMs = 15000) {
    if (this.syncInterval) clearInterval(this.syncInterval);
    this.syncInterval = setInterval(() => {
      if (this.isOnline) {
        this.syncNow().catch((err) => {
          console.warn('Auto-sync cycle caught error:', err.message);
        });
      }
    }, intervalMs);
  }

  stopAutoSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  async syncNow() {
    if (this.isSyncing || !this.isOnline) return;

    const pending = offlineJournal.getPendingActions();
    if (pending.length === 0) return;

    this.isSyncing = true;
    const deviceId = offlineJournal.getOrCreateDeviceId();
    const actionUuids = pending.map((p) => p.actionUuid);

    offlineJournal.markInFlight(actionUuids);

    try {
      // 1. Ensure device registration
      try {
        await registerSyncDevice({
          device_identifier: deviceId,
          platform: 'web_pwa',
          app_version: '1.12.0',
        });
      } catch (e) {
        // Device may already be registered
      }

      // 2. Prepare SyncUploadBatchRequest
      const batchId = `batch_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
      const payload = {
        device_id: deviceId,
        client_batch_id: batchId,
        actions: pending.map((p) => ({
          action_uuid: p.actionUuid,
          action_type: p.actionType,
          mission_id: p.missionId || undefined,
          encounter_id: p.encounterId || undefined,
          client_timestamp: p.clientTimestamp,
          device_sequence_number: p.deviceSequenceNumber || 1,
          payload: p.payload || {},
        })),
      };

      const result = await uploadSyncBatch(payload);

      // 3. Process individual action receipts
      if (result && Array.isArray(result.receipts)) {
        result.receipts.forEach((receipt) => {
          if (receipt.status === 'ACKNOWLEDGED') {
            offlineJournal.markAcknowledged(receipt.action_uuid, receipt.server_ack_id);
          } else {
            offlineJournal.markFailed(receipt.action_uuid, receipt.error_message || 'Sync failed');
          }
        });
      } else {
        // Mark all acknowledged if no specific receipts returned
        actionUuids.forEach((uuid) => offlineJournal.markAcknowledged(uuid));
      }

      this.consecutiveFailures = 0;
    } catch (err) {
      this.consecutiveFailures += 1;
      actionUuids.forEach((uuid) => offlineJournal.markFailed(uuid, err.message));
      console.warn(`Sync failed (attempt ${this.consecutiveFailures}):`, err.message);
    } finally {
      this.isSyncing = false;
    }
  }
}

export const syncService = new SyncCoordinatorService();
export { SyncCoordinatorService, SyncCoordinatorService as OfflineSyncService };
