/**
 * CareOn — Unified Google Maps API Loader & State Management
 * Supports VITE_GOOGLE_MAPS_API_KEY, window.CAREON_GOOGLE_MAPS_API_KEY,
 * and localStorage dynamic persistence for instant activation.
 */
import { useState, useEffect, useCallback } from 'react';

let googleMapsLoadPromise = null;

export function getGoogleMapsApiKey() {
  if (typeof window === 'undefined') return '';
  try {
    const fromEnv = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_GOOGLE_MAPS_API_KEY) || '';
    if (fromEnv) return fromEnv;
  } catch (e) {
    // Ignore meta env errors in non-vite contexts
  }
  if (window.CAREON_GOOGLE_MAPS_API_KEY) {
    return window.CAREON_GOOGLE_MAPS_API_KEY;
  }
  try {
    const stored = localStorage.getItem('careon_google_maps_api_key');
    if (stored) return stored;
  } catch (e) {
    // Ignore localStorage restrictions
  }
  return '';
}

export function setGoogleMapsApiKey(apiKey) {
  if (typeof window === 'undefined') return;
  const trimmed = (apiKey || '').trim();
  window.CAREON_GOOGLE_MAPS_API_KEY = trimmed;
  try {
    if (trimmed) {
      localStorage.setItem('careon_google_maps_api_key', trimmed);
    } else {
      localStorage.removeItem('careon_google_maps_api_key');
    }
  } catch (e) {
    // Ignore
  }
}

export function loadGoogleMapsScript(explicitApiKey = null) {
  if (typeof window === 'undefined') {
    return Promise.resolve(null);
  }

  if (window.google && window.google.maps) {
    return Promise.resolve(window.google.maps);
  }

  const key = explicitApiKey || getGoogleMapsApiKey();
  if (!key) {
    return Promise.reject(new Error('MISSING_API_KEY'));
  }

  if (googleMapsLoadPromise) {
    return googleMapsLoadPromise;
  }

  googleMapsLoadPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById('careon-google-maps-script');
    if (existing) {
      existing.addEventListener('load', () => resolve(window.google.maps));
      existing.addEventListener('error', (err) => {
        googleMapsLoadPromise = null;
        reject(err);
      });
      return;
    }

    const script = document.createElement('script');
    script.id = 'careon-google-maps-script';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=places,geometry,drawing`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      resolve(window.google.maps);
    };

    script.onerror = (err) => {
      googleMapsLoadPromise = null;
      script.remove();
      reject(new Error('Failed to load Google Maps script. Please verify the API key and network connectivity.'));
    };

    document.head.appendChild(script);
  });

  return googleMapsLoadPromise;
}

export function useGoogleMaps(customKey = null) {
  const [apiKey, setApiKeyInternal] = useState(() => customKey || getGoogleMapsApiKey());
  const [isLoaded, setIsLoaded] = useState(() => Boolean(typeof window !== 'undefined' && window.google && window.google.maps));
  const [loadError, setLoadError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const setKeyAndReload = useCallback((newKey) => {
    setGoogleMapsApiKey(newKey);
    setApiKeyInternal(newKey);
    setLoadError(null);
    googleMapsLoadPromise = null;
    const existing = document.getElementById('careon-google-maps-script');
    if (existing) existing.remove();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (window.google && window.google.maps) {
      setIsLoaded(true);
      setLoadError(null);
      return;
    }

    const activeKey = customKey || apiKey;
    if (!activeKey) {
      setIsLoaded(false);
      setLoadError('MISSING_API_KEY');
      return;
    }

    let isMounted = true;
    setIsLoading(true);

    loadGoogleMapsScript(activeKey)
      .then((maps) => {
        if (isMounted) {
          setIsLoaded(true);
          setLoadError(null);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setIsLoaded(false);
          setLoadError(err.message || 'Failed to load Google Maps');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [apiKey, customKey]);

  return {
    isLoaded,
    isLoading,
    loadError,
    apiKey,
    setKeyAndReload,
    google: typeof window !== 'undefined' ? window.google?.maps : null,
  };
}
