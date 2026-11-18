/**
 * CareOn Mobile Durable Storage Service.
 *
 * Provides persistent, crash-resilient storage for the Action Journal
 * and cached offline mission data.
 * Uses SecureStore for tokens/device IDs and resilient local storage.
 */

import * as SecureStore from 'expo-secure-store';

const DEVICE_ID_KEY = 'careon_device_identifier';
const CURSOR_KEY = 'careon_sync_cursor';
const JOURNAL_PREFIX = 'careon_journal_';
const CACHED_MISSION_KEY = 'careon_cached_mission';
const CACHED_CHANGES_KEY = 'careon_cached_changes';

export const syncStorage = {
  /**
   * Get or initialize a stable, persistent device installation identifier.
   */
  async getOrCreateDeviceId() {
    try {
      let devId = await SecureStore.getItemAsync(DEVICE_ID_KEY);
      if (!devId) {
        devId = `dev_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
        await SecureStore.setItemAsync(DEVICE_ID_KEY, devId, {
          keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        });
      }
      return devId;
    } catch (err) {
      console.warn('SecureStore deviceId error, falling back:', err);
      return `dev_fallback_${Date.now()}`;
    }
  },

  async getSyncCursor() {
    try {
      return (await SecureStore.getItemAsync(CURSOR_KEY)) || '0';
    } catch (err) {
      return '0';
    }
  },

  async setSyncCursor(cursor) {
    try {
      await SecureStore.setItemAsync(CURSOR_KEY, String(cursor));
    } catch (err) {
      console.warn('Failed to save cursor:', err);
    }
  },

  async saveCachedMission(mission) {
    try {
      await SecureStore.setItemAsync(CACHED_MISSION_KEY, JSON.stringify(mission));
    } catch (err) {
      console.warn('Failed to save cached mission:', err);
    }
  },

  async getCachedMission() {
    try {
      const data = await SecureStore.getItemAsync(CACHED_MISSION_KEY);
      return data ? JSON.parse(data) : null;
    } catch (err) {
      return null;
    }
  },

  async saveActionRecord(actionUuid, record) {
    try {
      await SecureStore.setItemAsync(
        `${JOURNAL_PREFIX}${actionUuid}`,
        JSON.stringify(record)
      );
    } catch (err) {
      console.warn(`Failed to persist action ${actionUuid}:`, err);
    }
  },

  async getActionRecord(actionUuid) {
    try {
      const val = await SecureStore.getItemAsync(`${JOURNAL_PREFIX}${actionUuid}`);
      return val ? JSON.parse(val) : null;
    } catch (err) {
      return null;
    }
  },

  async removeActionRecord(actionUuid) {
    try {
      await SecureStore.deleteItemAsync(`${JOURNAL_PREFIX}${actionUuid}`);
    } catch (err) {
      console.warn(`Failed to delete action ${actionUuid}:`, err);
    }
  },
};
