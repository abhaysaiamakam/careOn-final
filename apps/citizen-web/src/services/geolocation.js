/**
 * CareOn Citizen — Geolocation Acquisition & Reverse Geocoding
 */

export function acquireCurrentLocation(options = {}) {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      return reject(new Error('Geolocation is not supported by your browser.'));
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: parseFloat(pos.coords.latitude.toFixed(6)),
          longitude: parseFloat(pos.coords.longitude.toFixed(6)),
          accuracy: Math.round(pos.coords.accuracy),
          timestamp: pos.timestamp,
        });
      },
      (err) => {
        let msg = 'Failed to obtain GPS position.';
        if (err.code === 1) {
          msg = 'Location permission was denied. Please allow location access or type your address manually.';
        } else if (err.code === 2) {
          msg = 'Location position unavailable. Ensure GPS is enabled.';
        } else if (err.code === 3) {
          msg = 'Location request timed out. Please enter address manually.';
        }
        const error = new Error(msg);
        error.code = err.code;
        reject(error);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 5000,
        ...options,
      }
    );
  });
}

export async function reverseGeocode(latitude, longitude) {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`,
      {
        headers: {
          'Accept-Language': 'en',
          'User-Agent': 'CareOn-Citizen-PWA/1.0',
        },
      }
    );
    if (!res.ok) throw new Error('Geocoding service unavailable');
    const data = await res.json();
    if (data && data.display_name) {
      return data.display_name;
    }
  } catch (e) {
    console.warn('Reverse geocode failed or rate-limited, falling back to coordinates:', e);
  }
  return `Near Lat: ${latitude.toFixed(4)}, Lon: ${longitude.toFixed(4)}`;
}
