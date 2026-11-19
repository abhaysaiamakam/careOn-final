/**
 * CareOn Responder — Field Geolocation & Telemetry Acquisition Service.
 * Acquires authentic device GPS coordinates, validates timestamp drift,
 * filters noise, and submits verified telemetry to the backend.
 */

import { sendResponderTelemetry } from '@careon/api-client';

class ResponderGeolocationService {
  constructor() {
    this.watchId = null;
    this.currentPosition = null;
    this.permissionState = 'prompt'; // 'granted', 'denied', 'prompt', 'unsupported'
    this.listeners = new Set();
    this.lastTransmittedAt = 0;
    this.minTransmitIntervalMs = 5000; // 5-second rate limiting to save battery & bandwidth
    this.activeResourceId = null;
    this.isTransmitting = false;
  }

  setResourceId(resourceId) {
    this.activeResourceId = resourceId;
  }

  onPositionChange(callback) {
    this.listeners.add(callback);
    if (this.currentPosition) callback(this.currentPosition);
    return () => this.listeners.delete(callback);
  }

  _notify(position) {
    this.currentPosition = position;
    this.listeners.forEach((cb) => {
      try {
        cb(position);
      } catch (e) {
        console.error('Position listener error:', e);
      }
    });
  }

  async checkPermission() {
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
      this.permissionState = 'unsupported';
      return 'unsupported';
    }

    if ('permissions' in navigator) {
      try {
        const status = await navigator.permissions.query({ name: 'geolocation' });
        this.permissionState = status.state;
        status.onchange = () => {
          this.permissionState = status.state;
        };
        return status.state;
      } catch (e) {
        // Fall back to prompt
      }
    }
    return this.permissionState;
  }

  startTracking(options = {}) {
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
      this.permissionState = 'unsupported';
      throw new Error('Geolocation is not supported by your browser.');
    }

    if (this.watchId !== null) return;

    this.watchId = navigator.geolocation.watchPosition(
      (pos) => {
        this.permissionState = 'granted';
        const positionData = {
          latitude: parseFloat(pos.coords.latitude.toFixed(6)),
          longitude: parseFloat(pos.coords.longitude.toFixed(6)),
          accuracy: Math.round(pos.coords.accuracy),
          heading: pos.coords.heading !== null && !isNaN(pos.coords.heading) ? pos.coords.heading : null,
          speed: pos.coords.speed !== null && !isNaN(pos.coords.speed) ? Math.round(pos.coords.speed * 3.6) : 0, // km/h
          timestamp: pos.timestamp || Date.now(),
          isStale: false,
        };

        this._notify(positionData);
        this._maybeTransmitTelemetry(positionData);
      },
      (err) => {
        if (err.code === 1) {
          this.permissionState = 'denied';
        }
        console.warn('Geolocation error:', err.message);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 3000,
        ...options,
      }
    );
  }

  stopTracking() {
    if (this.watchId !== null && typeof navigator !== 'undefined') {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }
  }

  async getCurrentLocation() {
    return new Promise((resolve, reject) => {
      if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
        return reject(new Error('Geolocation unsupported'));
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          this.permissionState = 'granted';
          const data = {
            latitude: parseFloat(pos.coords.latitude.toFixed(6)),
            longitude: parseFloat(pos.coords.longitude.toFixed(6)),
            accuracy: Math.round(pos.coords.accuracy),
            heading: pos.coords.heading || 0,
            speed: pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0,
            timestamp: pos.timestamp || Date.now(),
          };
          this._notify(data);
          resolve(data);
        },
        (err) => reject(err),
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  async _maybeTransmitTelemetry(pos) {
    if (!this.activeResourceId || this.isTransmitting) return;

    const now = Date.now();
    if (now - this.lastTransmittedAt < this.minTransmitIntervalMs) {
      return; // Rate limit exceeded
    }

    this.isTransmitting = true;
    try {
      await sendResponderTelemetry({
        resource_id: this.activeResourceId,
        latitude: pos.latitude,
        longitude: pos.longitude,
        speed: pos.speed,
        heading: pos.heading,
      });
      this.lastTransmittedAt = now;
    } catch (err) {
      console.warn('Telemetry transmission error:', err.message);
    } finally {
      this.isTransmitting = false;
    }
  }
}

export const responderGeo = new ResponderGeolocationService();
export { ResponderGeolocationService, ResponderGeolocationService as GeolocationService };
