/**
 * Platform Secure Storage Service.
 * 
 * Safely persists refresh tokens and credentials using platform keychain / keystore.
 * Never uses unencrypted localStorage or plaintext file storage.
 */

import * as SecureStore from 'expo-secure-store';

const REFRESH_TOKEN_KEY = 'careon_secure_refresh_token';
const ACCESS_TOKEN_KEY = 'careon_secure_access_token';
const USER_KEY = 'careon_secure_user';

export const secureStorage = {
  async saveRefreshToken(token) {
    try {
      await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
    } catch (error) {
      console.warn('SecureStore save failed:', error);
    }
  },

  async getRefreshToken() {
    try {
      return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    } catch (error) {
      console.warn('SecureStore read failed:', error);
      return null;
    }
  },

  async clearTokens() {
    try {
      await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
      await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
      await SecureStore.deleteItemAsync(USER_KEY);
    } catch (error) {
      console.warn('SecureStore clear failed:', error);
    }
  },
};
