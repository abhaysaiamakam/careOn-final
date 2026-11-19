/**
 * CareOn Responder — Durable Offline Action Journal (M9).
 * Persists pending field operational actions (transitions, assessments, vitals, handovers)
 * durably to localStorage/IndexedDB before acknowledging locally.
 */

const JOURNAL_STORAGE_KEY = 'careon_responder_action_journal_v1';
const DEVICE_ID_KEY = 'careon_responder_device_id_v1';

export const SyncStatus = {
  PENDING: 'PENDING',
  IN_FLIGHT: 'IN_FLIGHT',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  FAILED: 'FAILED',
  CONFLICT: 'CONFLICT',
};

class ActionJournalService {
  constructor() {
    this.actions = this._loadJournal();
    this.listeners = new Set();
    this.monotonicSeq = this.actions.reduce((max, a) => Math.max(max, a.deviceSequenceNumber || 0), 0) + 1;
  }

  _loadJournal() {
    try {
      if (typeof localStorage === 'undefined') return [];
      const raw = localStorage.getItem(JOURNAL_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.error('Failed to load action journal:', e);
      return [];
    }
  }

  _persistJournal() {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(this.actions));
      }
      this._notifyListeners();
    } catch (e) {
      console.error('Failed to persist action journal:', e);
    }
  }

  onJournalChange(callback) {
    this.listeners.add(callback);
    callback(this.getPendingActions());
    return () => this.listeners.delete(callback);
  }

  _notifyListeners() {
    const pending = this.getPendingActions();
    this.listeners.forEach((cb) => {
      try {
        cb(pending);
      } catch (e) {
        console.error('Journal listener error:', e);
      }
    });
  }

  getOrCreateDeviceId() {
    try {
      let id = localStorage.getItem(DEVICE_ID_KEY);
      if (!id) {
        id = `web_resp_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
        localStorage.setItem(DEVICE_ID_KEY, id);
      }
      return id;
    } catch (e) {
      return `temp_dev_${Date.now()}`;
    }
  }

  /**
   * Durably record a field operational action before network transmission.
   * Supports both object syntax: recordAction({ actionType, payload, ... })
   * and positional syntax: recordAction(actionType, payload, { mission_id, encounter_id })
   */
  async recordAction(firstArg, secondArg = {}, thirdArg = {}) {
    let actionType, missionId, encounterId, payload, userId;

    if (typeof firstArg === 'object' && firstArg !== null && firstArg.actionType) {
      actionType = firstArg.actionType;
      missionId = firstArg.missionId || firstArg.mission_id || null;
      encounterId = firstArg.encounterId || firstArg.encounter_id || null;
      payload = firstArg.payload || {};
      userId = firstArg.userId || firstArg.user_id || null;
    } else {
      actionType = firstArg;
      payload = secondArg || {};
      missionId = thirdArg.mission_id || thirdArg.missionId || null;
      encounterId = thirdArg.encounter_id || thirdArg.encounterId || null;
      userId = thirdArg.user_id || thirdArg.userId || null;
    }

    const actionUuid = `act_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
    const nowIso = new Date().toISOString();
    const seqNum = this.monotonicSeq++;
    const devId = this.getOrCreateDeviceId();

    const record = {
      actionUuid,
      action_uuid: actionUuid,
      deviceId: devId,
      device_id: devId,
      userId,
      user_id: userId,
      missionId,
      mission_id: missionId,
      encounterId,
      encounter_id: encounterId,
      actionType,
      action_type: actionType,
      payload,
      clientTimestamp: nowIso,
      client_timestamp: nowIso,
      deviceSequenceNumber: seqNum,
      device_sequence_number: seqNum,
      syncStatus: SyncStatus.PENDING,
      sync_status: SyncStatus.PENDING,
      retryCount: 0,
      retry_count: 0,
      errorMessage: null,
      error_message: null,
      serverAckId: null,
      server_ack_id: null,
    };

    this.actions.push(record);
    this._persistJournal();
    return record;
  }

  getPendingActions() {
    return this.actions.filter((a) => a.syncStatus === SyncStatus.PENDING || a.syncStatus === SyncStatus.FAILED);
  }

  getAllActions() {
    return [...this.actions];
  }

  markInFlight(actionUuids) {
    const set = new Set(actionUuids);
    this.actions.forEach((a) => {
      if (set.has(a.actionUuid)) {
        a.syncStatus = SyncStatus.IN_FLIGHT;
      }
    });
    this._persistJournal();
  }

  markAcknowledged(actionUuid, serverAckId = null) {
    const target = this.actions.find((a) => a.actionUuid === actionUuid || a.action_uuid === actionUuid);
    if (target) {
      target.syncStatus = SyncStatus.ACKNOWLEDGED;
      target.sync_status = SyncStatus.ACKNOWLEDGED;
      target.serverAckId = serverAckId;
      target.syncedAt = new Date().toISOString();
      this._persistJournal();
    }
  }

  markActionsSynced(actionUuids = []) {
    const set = new Set(actionUuids);
    this.actions.forEach((a) => {
      if (set.has(a.actionUuid) || set.has(a.action_uuid)) {
        a.syncStatus = SyncStatus.ACKNOWLEDGED;
        a.sync_status = SyncStatus.ACKNOWLEDGED;
        a.syncedAt = new Date().toISOString();
      }
    });
    this._persistJournal();
  }

  markFailed(actionUuid, errorMsg) {
    const target = this.actions.find((a) => a.actionUuid === actionUuid);
    if (target) {
      target.syncStatus = SyncStatus.FAILED;
      target.retryCount = (target.retryCount || 0) + 1;
      target.errorMessage = errorMsg;
      this._persistJournal();
    }
  }

  clearAcknowledged() {
    this.actions = this.actions.filter((a) => a.syncStatus !== SyncStatus.ACKNOWLEDGED);
    this._persistJournal();
  }
}

export const offlineJournal = new ActionJournalService();
