import React, { useEffect, useRef, useState, useCallback } from 'react';
import { MapPin, Navigation, AlertTriangle, ShieldCheck, RefreshCw, Key, Check } from 'lucide-react';

let googleMapsScriptPromise = null;

function getActiveApiKey() {
  if (typeof window === 'undefined') return '';
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_GOOGLE_MAPS_API_KEY) {
      return import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
    }
  } catch (e) {}
  if (window.CAREON_GOOGLE_MAPS_API_KEY) return window.CAREON_GOOGLE_MAPS_API_KEY;
  try {
    return localStorage.getItem('careon_google_maps_api_key') || '';
  } catch (e) {}
  return '';
}

function loadGoogleMaps(apiKey) {
  if (typeof window === 'undefined') return Promise.resolve(null);
  if (window.google && window.google.maps) return Promise.resolve(window.google.maps);

  const key = apiKey || getActiveApiKey();
  if (!key) return Promise.reject(new Error('MISSING_API_KEY'));

  if (googleMapsScriptPromise) return googleMapsScriptPromise;

  googleMapsScriptPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById('careon-gmaps-script');
    if (existing) {
      existing.addEventListener('load', () => resolve(window.google.maps));
      existing.addEventListener('error', (err) => {
        googleMapsScriptPromise = null;
        reject(err);
      });
      return;
    }

    const script = document.createElement('script');
    script.id = 'careon-gmaps-script';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=places,geometry,drawing`;
    script.async = true;
    script.defer = true;

    script.onload = () => resolve(window.google.maps);
    script.onerror = (err) => {
      googleMapsScriptPromise = null;
      script.remove();
      reject(new Error('Google Maps script load failed.'));
    };

    document.head.appendChild(script);
  });

  return googleMapsScriptPromise;
}

export default function GoogleMap({
  incidents = [],
  resources = [],
  providers = [],
  center = [12.3052, 76.6552], // Default: Mysuru, Karnataka, India
  zoom = 13,
  isSimulationActive = false,
  onMarkerSelect,
  selectable = false,
  selectedLocation = null,
  onLocationSelect,
  height = '420px',
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({ incidents: [], resources: [], providers: [], selection: null });
  const infoWindowRef = useRef(null);

  const [apiKey, setApiKey] = useState(getActiveApiKey);
  const [inputKey, setInputKey] = useState('');
  const [mapLoaded, setMapLoaded] = useState(() => Boolean(typeof window !== 'undefined' && window.google?.maps));
  const [loadError, setLoadError] = useState(null);
  const [activeSimulationStep, setActiveSimulationStep] = useState(0);

  // Initialize or reload Google Maps when key changes
  const activateApiKey = (newKey) => {
    const cleanKey = (newKey || '').trim();
    if (!cleanKey) return;
    window.CAREON_GOOGLE_MAPS_API_KEY = cleanKey;
    try {
      localStorage.setItem('careon_google_maps_api_key', cleanKey);
    } catch (e) {}
    setApiKey(cleanKey);
    googleMapsScriptPromise = null;
    const existing = document.getElementById('careon-gmaps-script');
    if (existing) existing.remove();
    setLoadError(null);
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (window.google?.maps) {
      setMapLoaded(true);
      return;
    }

    const currentKey = apiKey || getActiveApiKey();
    if (!currentKey) {
      setMapLoaded(false);
      setLoadError('MISSING_API_KEY');
      return;
    }

    loadGoogleMaps(currentKey)
      .then(() => {
        setMapLoaded(true);
        setLoadError(null);
      })
      .catch((err) => {
        setMapLoaded(false);
        setLoadError(err.message || 'Failed to load Google Maps');
      });
  }, [apiKey]);

  // Simulation movement timer
  useEffect(() => {
    let interval = null;
    if (isSimulationActive) {
      interval = setInterval(() => {
        setActiveSimulationStep((prev) => (prev + 1) % 10);
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isSimulationActive]);

  // Create Google Map instance once script is ready and container is mounted
  useEffect(() => {
    if (!mapLoaded || !mapContainerRef.current || !window.google?.maps) return;
    if (mapInstanceRef.current) return;

    const [lat, lng] = Array.isArray(center) ? center : [12.3052, 76.6552];

    const map = new window.google.maps.Map(mapContainerRef.current, {
      center: { lat, lng },
      zoom: zoom,
      mapTypeId: 'roadmap',
      zoomControl: true,
      mapTypeControl: true,
      scaleControl: true,
      streetViewControl: false,
      rotateControl: false,
      fullscreenControl: true,
      styles: [
        { featureType: 'poi.business', stylers: [{ visibility: 'simplified' }] },
        { featureType: 'transit', stylers: [{ visibility: 'simplified' }] },
      ],
    });

    mapInstanceRef.current = map;
    infoWindowRef.current = new window.google.maps.InfoWindow();

    if (selectable) {
      map.addListener('click', (e) => {
        const clickedLat = Number(e.latLng.lat().toFixed(6));
        const clickedLng = Number(e.latLng.lng().toFixed(6));

        // Use Google Geocoder if available
        if (window.google?.maps?.Geocoder) {
          const geocoder = new window.google.maps.Geocoder();
          geocoder.geocode({ location: { lat: clickedLat, lng: clickedLng } }, (results, status) => {
            let addr = `Coordinates: ${clickedLat.toFixed(4)}, ${clickedLng.toFixed(4)}`;
            if (status === 'OK' && results && results[0]) {
              addr = results[0].formatted_address;
            }
            onLocationSelect?.({
              latitude: clickedLat,
              longitude: clickedLng,
              location_name: addr,
            });
          });
        } else {
          onLocationSelect?.({
            latitude: clickedLat,
            longitude: clickedLng,
            location_name: `Coordinates: ${clickedLat.toFixed(4)}, ${clickedLng.toFixed(4)}`,
          });
        }
      });
    }

    return () => {
      // Clear markers on unmount
      Object.values(markersRef.current).forEach((m) => {
        if (Array.isArray(m)) m.forEach((item) => item.setMap(null));
        else if (m) m.setMap(null);
      });
      mapInstanceRef.current = null;
    };
  }, [mapLoaded, selectable]);

  // Pan map if center changes
  useEffect(() => {
    if (mapInstanceRef.current && center && Array.isArray(center) && center.length === 2) {
      mapInstanceRef.current.panTo({ lat: center[0], lng: center[1] });
    }
  }, [center]);

  // Render Selection Marker
  useEffect(() => {
    if (!mapInstanceRef.current || !selectable || !window.google?.maps) return;

    if (markersRef.current.selection) {
      markersRef.current.selection.setMap(null);
      markersRef.current.selection = null;
    }

    if (selectedLocation?.latitude && selectedLocation?.longitude) {
      const pos = { lat: Number(selectedLocation.latitude), lng: Number(selectedLocation.longitude) };

      const marker = new window.google.maps.Marker({
        position: pos,
        map: mapInstanceRef.current,
        draggable: true,
        animation: window.google.maps.Animation.DROP,
        title: 'Selected Emergency Location',
        icon: {
          path: window.google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: '#D92D3A',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
      });

      marker.addListener('dragend', (e) => {
        const lat = Number(e.latLng.lat().toFixed(6));
        const lng = Number(e.latLng.lng().toFixed(6));
        onLocationSelect?.({
          latitude: lat,
          longitude: lng,
          location_name: `Selected: ${lat.toFixed(4)}, ${lng.toFixed(4)}`,
        });
      });

      markersRef.current.selection = marker;
      mapInstanceRef.current.panTo(pos);
    }
  }, [selectedLocation, selectable, onLocationSelect]);

  // Render Incidents Markers
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.incidents.forEach((m) => m.setMap(null));
    markersRef.current.incidents = [];

    incidents.forEach((inc) => {
      if (!inc.latitude || !inc.longitude) return;

      const isCritical = inc.priority === 'Critical';
      const color = isCritical ? '#D92D3A' : inc.priority === 'High' ? '#EA580C' : '#0284C7';

      const marker = new window.google.maps.Marker({
        position: { lat: Number(inc.latitude), lng: Number(inc.longitude) },
        map: mapInstanceRef.current,
        title: `${inc.incident_code || 'Incident'}: ${inc.category}`,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: isCritical ? 9 : 7,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
      });

      marker.addListener('click', () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 200px;">
              <div style="font-weight: 800; color: ${color}; font-size: 13px; margin-bottom: 2px;">
                ${inc.category} (${inc.priority} Priority)
              </div>
              <div style="font-weight: 700; color: #0F172A; margin-bottom: 2px;">
                ${inc.incident_code || 'INC'}
              </div>
              <div style="color: #475569; font-size: 12px; margin-bottom: 4px;">
                📍 ${inc.location_name || 'Mysuru Region'}
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 11px; color: #64748B; border-top: 1px solid #E2E8F0; padding-top: 4px; margin-top: 4px;">
                <span>Status: <b>${inc.status}</b></span>
                <span>People: <b>${inc.affected_people || 1}</b></span>
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
        onMarkerSelect?.({ type: 'incident', item: inc });
      });

      markersRef.current.incidents.push(marker);
    });
  }, [incidents, mapLoaded, onMarkerSelect]);

  // Render Resources Markers
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.resources.forEach((m) => m.setMap(null));
    markersRef.current.resources = [];

    resources.forEach((res) => {
      if (!res.latitude || !res.longitude) return;

      let lat = Number(res.latitude);
      let lng = Number(res.longitude);

      if (isSimulationActive && res.status === 'Assigned') {
        lat += activeSimulationStep * 0.0006;
        lng -= activeSimulationStep * 0.0006;
      }

      const isAvail = res.status === 'Available';
      const isAssigned = res.status === 'Assigned' || res.status === 'En Route';
      const color = isAvail ? '#10B981' : isAssigned ? '#2563EB' : '#64748B';

      const marker = new window.google.maps.Marker({
        position: { lat, lng },
        map: mapInstanceRef.current,
        title: `${res.name} (${res.resource_code})`,
        icon: {
          path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
          rotation: 45,
        },
      });

      marker.addListener('click', () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 190px;">
              <div style="font-weight: 800; color: ${color}; font-size: 13px; margin-bottom: 2px;">
                🚑 ${res.name}
              </div>
              <div style="font-size: 12px; color: #334155;">
                Code: <b>${res.resource_code}</b> (${res.category || 'EMS'})
              </div>
              <div style="font-size: 12px; color: #475569;">
                Base: ${res.location_name || 'Mysuru Station'}
              </div>
              <div style="margin-top: 4px; font-size: 11px; font-weight: 700; color: ${color};">
                Status: ${res.status}
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
        onMarkerSelect?.({ type: 'resource', item: res });
      });

      markersRef.current.resources.push(marker);
    });
  }, [resources, isSimulationActive, activeSimulationStep, mapLoaded, onMarkerSelect]);

  // Render Providers Markers
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.providers.forEach((m) => m.setMap(null));
    markersRef.current.providers = [];

    providers.forEach((prov) => {
      if (!prov.latitude || !prov.longitude) return;

      const marker = new window.google.maps.Marker({
        position: { lat: Number(prov.latitude), lng: Number(prov.longitude) },
        map: mapInstanceRef.current,
        title: `Hospital: ${prov.name}`,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: '#8B5CF6',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
      });

      marker.addListener('click', () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 190px;">
              <div style="font-weight: 800; color: #7C3AED; font-size: 13px; margin-bottom: 2px;">
                🏥 ${prov.name}
              </div>
              <div style="font-size: 12px; color: #334155;">
                Type: <b>${prov.provider_type || 'Hospital'}</b>
              </div>
              <div style="font-size: 12px; color: #475569;">
                Address: ${prov.address || 'Mysuru'}
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
        onMarkerSelect?.({ type: 'provider', item: prov });
      });

      markersRef.current.providers.push(marker);
    });
  }, [providers, mapLoaded, onMarkerSelect]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {/* Simulation Movement Banner */}
      {isSimulationActive && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            zIndex: 10,
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            color: '#FFFFFF',
            padding: '6px 14px',
            borderRadius: 20,
            fontSize: '12px',
            fontWeight: 700,
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#10B981' }} />
          <span>Google Maps Fleet Simulation (Step {activeSimulationStep + 1}/10)</span>
        </div>
      )}

      {/* Selectable Location Banner */}
      {selectable && (
        <div
          style={{
            background: '#F0FDF4',
            border: '1px solid #BBF7D0',
            padding: '8px 12px',
            borderRadius: '8px 8px 0 0',
            fontSize: '12px',
            fontWeight: 600,
            color: '#166534',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>📍 Click map or drag marker to pinpoint exact emergency GPS coordinates</span>
          <span style={{ fontSize: '11px', color: '#64748B' }}>Google Maps Geocoding Active</span>
        </div>
      )}

      {/* Google Maps Container */}
      <div
        ref={mapContainerRef}
        style={{
          height: height,
          width: '100%',
          borderRadius: selectable ? '0 0 10px 10px' : '10px',
          border: '1px solid #CBD5E1',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          backgroundColor: '#F1F5F9',
          position: 'relative',
        }}
      >
        {/* If Google Maps API key is not yet set, provide instant activation interface & preview */}
        {!mapLoaded && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: '#F8FAFC',
              borderRadius: '8px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '24px',
              textAlign: 'center',
              zIndex: 5,
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                backgroundColor: '#EFF6FF',
                border: '1px solid #BFDBFE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '12px',
                color: '#2563EB',
              }}
            >
              <MapPin size={24} />
            </div>

            <h3 style={{ margin: '0 0 6px', fontSize: '16px', fontWeight: 700, color: '#0F172A' }}>
              Google Maps Ready
            </h3>
            <p style={{ margin: '0 0 16px', fontSize: '13px', color: '#64748B', maxWidth: '420px', lineHeight: 1.4 }}>
              Set <code style={{ backgroundColor: '#E2E8F0', padding: '2px 6px', borderRadius: '4px' }}>VITE_GOOGLE_MAPS_API_KEY</code> in your environment, or paste your API key below to activate Google Maps instantly.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                activateApiKey(inputKey);
              }}
              style={{ display: 'flex', gap: '8px', width: '100%', maxWidth: '400px' }}
            >
              <input
                type="text"
                placeholder="Enter Google Maps API Key (AIzaSy...)"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '13px',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#D92D3A',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Key size={14} /> Activate
              </button>
            </form>

            {/* Offline/Pending interactive fallback grid */}
            <div
              style={{
                marginTop: '16px',
                padding: '8px 14px',
                backgroundColor: '#FFFFFF',
                border: '1px dashed #CBD5E1',
                borderRadius: '6px',
                fontSize: '11px',
                color: '#64748B',
                display: 'flex',
                gap: '12px',
                alignItems: 'center',
              }}
            >
              <span>Incidents Queued: <b>{incidents.length}</b></span>
              <span>Ambulances: <b>{resources.length}</b></span>
              <span>Hospitals: <b>{providers.length}</b></span>
              <span>Target: <b>Mysuru (12.3052° N, 76.6552° E)</b></span>
            </div>
          </div>
        )}
      </div>

      {/* Map Legend */}
      <div
        style={{
          display: 'flex',
          gap: '14px',
          marginTop: '10px',
          fontSize: '12px',
          fontWeight: 600,
          color: '#475569',
          flexWrap: 'wrap',
          alignItems: 'center',
          background: '#F8FAFC',
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid #E2E8F0',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#D92D3A' }} />
          Emergency Incidents
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: '#10B981' }} />
          Available Fleet
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: '#2563EB' }} />
          Dispatched Units
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#8B5CF6' }} />
          Partner Hospitals & Facilities
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748B' }}>
          Google Maps Platform • Mysuru Region
        </span>
      </div>
    </div>
  );
}
