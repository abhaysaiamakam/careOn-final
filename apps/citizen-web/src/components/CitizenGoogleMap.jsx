import React, { useEffect, useRef, useState } from 'react';
import { MapPin, Navigation, Key, Globe, Check } from 'lucide-react';
import { colors, typography, useGoogleMaps } from '@careon/design-system';

export function CitizenGoogleMap({
  center = { lat: 12.3052, lng: 76.6552 }, // Default: Mysuru
  zoom = 14,
  height = '240px',
  selectable = false,
  selectedPin = null, // { lat, lng }
  onPinChange = null, // (newPos: { lat, lng }) => void
  markers = [], // [{ id, lat, lng, type: 'incident'|'ambulance'|'hospital', title, label }]
  polylinePath = null, // [{ lat, lng }, ...]
  helperNotice = null,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersMapRef = useRef(new Map());
  const selectionMarkerRef = useRef(null);
  const polylineRef = useRef(null);

  const { isLoaded, loadError, setKeyAndReload } = useGoogleMaps();
  const [inputKey, setInputKey] = useState('');

  const centerLat = typeof center?.lat === 'number' ? center.lat : Array.isArray(center) ? center[0] : 12.3052;
  const centerLng = typeof center?.lng === 'number' ? center.lng : Array.isArray(center) ? center[1] : 76.6552;

  // Initialize Map when Google Maps script is loaded
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current || !window.google?.maps) return;
    if (mapInstanceRef.current) return;

    const map = new window.google.maps.Map(mapContainerRef.current, {
      center: { lat: centerLat, lng: centerLng },
      zoom: zoom,
      mapTypeId: 'roadmap',
      zoomControl: true,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      styles: [
        { featureType: 'poi.business', stylers: [{ visibility: 'simplified' }] },
        { featureType: 'transit', stylers: [{ visibility: 'simplified' }] },
      ],
    });

    mapInstanceRef.current = map;

    if (selectable && onPinChange) {
      map.addListener('click', (e) => {
        const lat = Number(e.latLng.lat().toFixed(6));
        const lng = Number(e.latLng.lng().toFixed(6));
        onPinChange({ lat, lng });
      });
    }

    return () => {
      if (selectionMarkerRef.current) selectionMarkerRef.current.setMap(null);
      markersMapRef.current.forEach((m) => m.setMap(null));
      markersMapRef.current.clear();
      if (polylineRef.current) polylineRef.current.setMap(null);
      mapInstanceRef.current = null;
    };
  }, [isLoaded, selectable]);

  // Update center when changed
  useEffect(() => {
    if (mapInstanceRef.current && typeof centerLat === 'number' && typeof centerLng === 'number') {
      mapInstanceRef.current.panTo({ lat: centerLat, lng: centerLng });
    }
  }, [centerLat, centerLng]);

  // Update selection marker
  useEffect(() => {
    if (!mapInstanceRef.current || !selectable || !window.google?.maps) return;

    if (selectionMarkerRef.current) {
      selectionMarkerRef.current.setMap(null);
      selectionMarkerRef.current = null;
    }

    if (selectedPin && selectedPin.lat && selectedPin.lng) {
      const pos = { lat: Number(selectedPin.lat), lng: Number(selectedPin.lng) };

      const marker = new window.google.maps.Marker({
        position: pos,
        map: mapInstanceRef.current,
        draggable: true,
        animation: window.google.maps.Animation.DROP,
        title: 'Emergency Incident Location',
        icon: {
          path: window.google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: colors.secondary,
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
      });

      marker.addListener('dragend', (e) => {
        const lat = Number(e.latLng.lat().toFixed(6));
        const lng = Number(e.latLng.lng().toFixed(6));
        onPinChange?.({ lat, lng });
      });

      selectionMarkerRef.current = marker;
      mapInstanceRef.current.panTo(pos);
    }
  }, [selectedPin, selectable, onPinChange]);

  // Update general markers (incidents, ambulances, hospitals)
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersMapRef.current.forEach((m) => m.setMap(null));
    markersMapRef.current.clear();

    markers.forEach((item) => {
      if (!item.lat || !item.lng) return;

      const isAmbulance = item.type === 'ambulance';
      const isHospital = item.type === 'hospital';
      const color = isAmbulance ? '#2563EB' : isHospital ? '#8B5CF6' : colors.secondary;

      const marker = new window.google.maps.Marker({
        position: { lat: Number(item.lat), lng: Number(item.lng) },
        map: mapInstanceRef.current,
        title: item.title || item.type,
        icon: {
          path: isAmbulance
            ? window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW
            : window.google.maps.SymbolPath.CIRCLE,
          scale: isAmbulance ? 6 : 7,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
          rotation: item.heading || 0,
        },
      });

      markersMapRef.current.set(item.id || `${item.lat}-${item.lng}`, marker);
    });
  }, [markers, isLoaded]);

  // Update Polyline route
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }

    if (polylinePath && polylinePath.length >= 2) {
      const poly = new window.google.maps.Polyline({
        path: polylinePath,
        geodesic: true,
        strokeColor: colors.secondary,
        strokeOpacity: 0.85,
        strokeWeight: 4,
        map: mapInstanceRef.current,
      });
      polylineRef.current = poly;
    }
  }, [polylinePath, isLoaded]);

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: height,
        borderRadius: '8px',
        overflow: 'hidden',
        border: '1px solid #E5E7EB',
        backgroundColor: '#F9FAFB',
      }}
    >
      {/* Helper Banner */}
      {helperNotice && (
        <div
          style={{
            position: 'absolute',
            top: '8px',
            left: '8px',
            right: '8px',
            zIndex: 10,
            backgroundColor: 'rgba(255, 255, 255, 0.94)',
            backdropFilter: 'blur(6px)',
            padding: '6px 10px',
            borderRadius: '6px',
            border: '1px solid #E5E7EB',
            fontSize: typography.fontSize.xs,
            fontWeight: typography.fontWeight.medium,
            color: colors.textSecondary,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
          }}
        >
          <span>{helperNotice}</span>
          <span style={{ fontSize: '10px', color: isLoaded ? '#10B981' : '#F59E0B', fontWeight: 600 }}>
            {isLoaded ? '● Google Maps Active' : '○ Google Maps Ready'}
          </span>
        </div>
      )}

      {/* Map DOM Element */}
      <div
        ref={mapContainerRef}
        style={{
          width: '100%',
          height: '100%',
          visibility: isLoaded ? 'visible' : 'hidden',
        }}
      />

      {/* If Google Maps API key is not yet set, display clean configuration & preview card */}
      {!isLoaded && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: '#F9FAFB',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            textAlign: 'center',
            zIndex: 5,
          }}
        >
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: '#FEF2F2',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '10px',
              color: colors.secondary,
            }}
          >
            <MapPin size={20} />
          </div>

          <div style={{ fontSize: typography.fontSize.sm, fontWeight: typography.fontWeight.bold, color: colors.textPrimary, marginBottom: '4px' }}>
            Google Maps Integration
          </div>
          <p style={{ margin: '0 0 12px', fontSize: typography.fontSize.xs, color: colors.textSecondary, maxWidth: '360px', lineHeight: 1.4 }}>
            Set <code style={{ backgroundColor: '#F3F4F6', padding: '1px 4px', borderRadius: '3px' }}>VITE_GOOGLE_MAPS_API_KEY</code> or paste key below to activate live Google Maps.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (inputKey.trim()) setKeyAndReload(inputKey.trim());
            }}
            style={{ display: 'flex', gap: '6px', width: '100%', maxWidth: '340px' }}
          >
            <input
              type="text"
              placeholder="Google Maps API Key (AIzaSy...)"
              value={inputKey}
              onChange={(e) => setInputKey(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid #D1D5DB',
                fontSize: typography.fontSize.xs,
                outline: 'none',
              }}
            />
            <button
              type="submit"
              style={{
                padding: '6px 12px',
                backgroundColor: colors.secondary,
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                fontSize: typography.fontSize.xs,
                fontWeight: typography.fontWeight.semibold,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Key size={12} /> Activate
            </button>
          </form>

          {/* Location details fallback pill */}
          <div
            style={{
              marginTop: '12px',
              padding: '4px 10px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E5E7EB',
              borderRadius: '16px',
              fontSize: '11px',
              color: colors.textSecondary,
            }}
          >
            📍 Coordinates: <b>{centerLat.toFixed(4)}, {centerLng.toFixed(4)}</b>
          </div>
        </div>
      )}
    </div>
  );
}
