import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin,
  Truck,
  Building2,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  AlertTriangle,
  Flame,
  Radio,
  Compass,
  Key,
  Globe,
} from 'lucide-react';
import { colors, typography, Badge, useGoogleMaps, setGoogleMapsApiKey } from '@careon/design-system';

// Tactical Dark Theme for Google Maps
const TACTICAL_DARK_MAP_STYLES = [
  { elementType: 'geometry', stylers: [{ color: '#1B2434' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#1B2434' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94A3B8' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#E2E8F0' }],
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#64748B' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#14202E' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#27354A' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#1E293B' }],
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#94A3B8' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#3B4D68' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#1E293B' }],
  },
  {
    featureType: 'transit',
    elementType: 'geometry',
    stylers: [{ color: '#1E293B' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#0B132B' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#475569' }],
  },
];

export function OperationsMap({
  incidents = [],
  resources = [],
  hospitals = [],
  zones = [],
  selectedIncident = null,
  onSelectIncident = () => {},
  selectedResource = null,
  onSelectResource = () => {},
  height = '100%',
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({ incidents: [], resources: [], hospitals: [], zones: [] });
  const infoWindowRef = useRef(null);

  const { isLoaded, loadError, setKeyAndReload } = useGoogleMaps();
  const [inputKey, setInputKey] = useState('');
  const [mapType, setMapType] = useState('tactical'); // tactical, satellite, roadmap
  const [layers, setLayers] = useState({
    incidents: true,
    ambulances: true,
    hospitals: true,
    zones: true,
  });

  // Center coordinate reference: Mysuru/Central operations (12.310, 76.650)
  const mapCenter = { lat: 12.310, lng: 76.650 };

  // --- GOOGLE MAPS INSTANTIATION ---
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current || !window.google?.maps) return;
    if (mapInstanceRef.current) return;

    const map = new window.google.maps.Map(mapContainerRef.current, {
      center: mapCenter,
      zoom: 13,
      mapTypeId: 'roadmap',
      disableDefaultUI: true,
      zoomControl: false,
      styles: mapType === 'tactical' ? TACTICAL_DARK_MAP_STYLES : [],
    });

    mapInstanceRef.current = map;
    infoWindowRef.current = new window.google.maps.InfoWindow();

    return () => {
      // Clean up markers
      Object.values(markersRef.current).forEach((layer) => {
        if (Array.isArray(layer)) layer.forEach((item) => item.setMap && item.setMap(null));
      });
      mapInstanceRef.current = null;
    };
  }, [isLoaded]);

  // Update styles when mapType changes
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;
    if (mapType === 'satellite') {
      mapInstanceRef.current.setMapTypeId('satellite');
      mapInstanceRef.current.setOptions({ styles: [] });
    } else if (mapType === 'roadmap') {
      mapInstanceRef.current.setMapTypeId('roadmap');
      mapInstanceRef.current.setOptions({ styles: [] });
    } else {
      mapInstanceRef.current.setMapTypeId('roadmap');
      mapInstanceRef.current.setOptions({ styles: TACTICAL_DARK_MAP_STYLES });
    }
  }, [mapType]);

  // Zoom controls
  const handleZoomIn = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setZoom(mapInstanceRef.current.getZoom() + 1);
    }
  };

  const handleZoomOut = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setZoom(mapInstanceRef.current.getZoom() - 1);
    }
  };

  // Pan to selected incident
  useEffect(() => {
    if (!mapInstanceRef.current || !selectedIncident?.latitude || !selectedIncident?.longitude) return;
    mapInstanceRef.current.panTo({
      lat: Number(selectedIncident.latitude),
      lng: Number(selectedIncident.longitude),
    });
  }, [selectedIncident]);

  // --- RENDER GOOGLE MAPS INCIDENTS ---
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.incidents.forEach((m) => m.setMap(null));
    markersRef.current.incidents = [];

    if (!layers.incidents) return;

    incidents.forEach((inc) => {
      if (!inc.latitude || !inc.longitude) return;

      const isCritical = inc.priority === 'Critical';
      const isSelected = selectedIncident?.id === inc.id;
      const color = isCritical ? '#D92D3A' : inc.priority === 'High' ? '#EA580C' : '#0284C7';

      const marker = new window.google.maps.Marker({
        position: { lat: Number(inc.latitude), lng: Number(inc.longitude) },
        map: mapInstanceRef.current,
        title: `${inc.incident_code || 'Incident'}: ${inc.category}`,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: isSelected ? 11 : isCritical ? 9 : 7,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: isSelected ? '#FDE047' : '#FFFFFF',
          strokeWeight: isSelected ? 3 : 2,
        },
      });

      marker.addListener('click', () => {
        onSelectIncident(inc);
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 200px; color: #0F172A;">
              <div style="font-weight: 800; color: ${color}; font-size: 13px; margin-bottom: 2px;">
                ${inc.category} (${inc.priority} Priority)
              </div>
              <div style="font-weight: 700; margin-bottom: 2px;">
                ${inc.incident_code || `#${inc.id}`}
              </div>
              <div style="color: #475569; font-size: 12px; margin-bottom: 6px;">
                📍 ${inc.location_name || 'Mysuru District'}
              </div>
              <div style="font-size: 11px; color: #64748B; margin-bottom: 8px;">
                Status: <b>${inc.status}</b> | Affected: <b>${inc.affected_people || 1}</b>
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
      });

      markersRef.current.incidents.push(marker);
    });
  }, [incidents, layers.incidents, selectedIncident, isLoaded, onSelectIncident]);

  // --- RENDER GOOGLE MAPS AMBULANCES / FLEET ---
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.resources.forEach((m) => m.setMap(null));
    markersRef.current.resources = [];

    if (!layers.ambulances) return;

    resources.forEach((res) => {
      if (!res.latitude || !res.longitude) return;

      const isAvail = res.status === 'Available';
      const isAssigned = res.status === 'Assigned' || res.status === 'En Route';
      const isSelected = selectedResource?.id === res.id;
      const color = isAvail ? '#10B981' : isAssigned ? '#F59E0B' : '#64748B';

      const marker = new window.google.maps.Marker({
        position: { lat: Number(res.latitude), lng: Number(res.longitude) },
        map: mapInstanceRef.current,
        title: `${res.name} (${res.resource_code})`,
        icon: {
          path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: isSelected ? 8 : 6,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: isSelected ? '#FFFFFF' : '#0F172A',
          strokeWeight: 2,
          rotation: res.heading || 45,
        },
      });

      marker.addListener('click', () => {
        onSelectResource(res);
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 190px; color: #0F172A;">
              <div style="font-weight: 800; color: ${color}; font-size: 13px; margin-bottom: 2px;">
                🚑 ${res.name}
              </div>
              <div style="font-size: 12px; color: #334155;">
                Callsign: <b>${res.resource_code}</b> (${res.capabilities || 'Standard ALS'})
              </div>
              <div style="font-size: 12px; color: #475569; margin-bottom: 6px;">
                Status: <b style="color: ${color};">${res.status}</b>
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
      });

      markersRef.current.resources.push(marker);
    });
  }, [resources, layers.ambulances, selectedResource, isLoaded, onSelectResource]);

  // --- RENDER GOOGLE MAPS HOSPITALS ---
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.hospitals.forEach((m) => m.setMap(null));
    markersRef.current.hospitals = [];

    if (!layers.hospitals) return;

    hospitals.forEach((h) => {
      if (!h.latitude || !h.longitude) return;

      const isDiverting = Boolean(h.divert_status);
      const color = isDiverting ? '#EF4444' : '#3B82F6';

      const marker = new window.google.maps.Marker({
        position: { lat: Number(h.latitude), lng: Number(h.longitude) },
        map: mapInstanceRef.current,
        title: `Hospital: ${h.name}`,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
        },
      });

      marker.addListener('click', () => {
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(`
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; line-height: 1.4; min-width: 200px; color: #0F172A;">
              <div style="font-weight: 800; color: ${color}; font-size: 13px; margin-bottom: 2px;">
                🏥 ${h.name}
              </div>
              <div style="font-size: 12px; color: #334155;">
                Trauma Level: <b>${h.trauma_level || 'Level I'}</b>
              </div>
              <div style="font-size: 12px; color: ${isDiverting ? '#EF4444' : '#10B981'}; font-weight: 700; margin-top: 4px;">
                ${isDiverting ? '⚠️ STATUS: DIVERSION ACTIVE' : '✓ RECEIVING EMERGENCY PATIENTS'}
              </div>
            </div>
          `);
          infoWindowRef.current.open(mapInstanceRef.current, marker);
        }
      });

      markersRef.current.hospitals.push(marker);
    });
  }, [hospitals, layers.hospitals, isLoaded]);

  // --- RENDER GOOGLE MAPS OPERATIONAL ZONES (M11) ---
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    markersRef.current.zones.forEach((c) => c.setMap(null));
    markersRef.current.zones = [];

    if (!layers.zones) return;

    zones.forEach((z) => {
      const lat = Number(z.center_latitude || 12.316);
      const lng = Number(z.center_longitude || 76.650);
      const isHot = z.zone_type === 'HOT_ZONE';
      const color = isHot ? '#EF4444' : '#F59E0B';

      const circle = new window.google.maps.Circle({
        map: mapInstanceRef.current,
        center: { lat, lng },
        radius: Number(z.radius_meters || (isHot ? 300 : 700)),
        fillColor: color,
        fillOpacity: isHot ? 0.25 : 0.15,
        strokeColor: color,
        strokeWeight: 2,
        strokeOpacity: 0.8,
      });

      markersRef.current.zones.push(circle);
    });
  }, [zones, layers.zones, isLoaded]);

  // Fallback SVG coordinate projector for offline/pending key preview
  const project = (lat, lon) => {
    const latSpan = 0.12;
    const lonSpan = 0.16;
    const x = ((lon - (mapCenter.lng - lonSpan / 2)) / lonSpan) * 800;
    const y = (((mapCenter.lat + latSpan / 2) - lat) / latSpan) * 500;
    return { x: Math.max(20, Math.min(780, x)), y: Math.max(20, Math.min(480, y)) };
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: height,
        minHeight: '380px',
        backgroundColor: '#0F172A',
        borderRadius: '8px',
        overflow: 'hidden',
        border: '1px solid #1E293B',
      }}
    >
      {/* Map Control Toolbar */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '12px',
          zIndex: 20,
          display: 'flex',
          gap: '6px',
          backgroundColor: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '6px 10px',
          borderRadius: '6px',
          border: '1px solid #334155',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginRight: '4px' }}>
          <Layers size={13} /> LAYERS:
        </span>
        <button
          onClick={() => setLayers((prev) => ({ ...prev, incidents: !prev.incidents }))}
          style={{
            background: layers.incidents ? 'rgba(217, 45, 58, 0.2)' : 'transparent',
            border: `1px solid ${layers.incidents ? colors.secondary : '#334155'}`,
            borderRadius: '4px',
            color: layers.incidents ? '#FCA5A5' : '#64748B',
            fontSize: '11px',
            padding: '3px 8px',
            cursor: 'pointer',
          }}
        >
          Incidents ({incidents.length})
        </button>
        <button
          onClick={() => setLayers((prev) => ({ ...prev, ambulances: !prev.ambulances }))}
          style={{
            background: layers.ambulances ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
            border: `1px solid ${layers.ambulances ? '#10B981' : '#334155'}`,
            borderRadius: '4px',
            color: layers.ambulances ? '#6EE7B7' : '#64748B',
            fontSize: '11px',
            padding: '3px 8px',
            cursor: 'pointer',
          }}
        >
          Fleet ({resources.length})
        </button>
        <button
          onClick={() => setLayers((prev) => ({ ...prev, hospitals: !prev.hospitals }))}
          style={{
            background: layers.hospitals ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
            border: `1px solid ${layers.hospitals ? '#3B82F6' : '#334155'}`,
            borderRadius: '4px',
            color: layers.hospitals ? '#93C5FD' : '#64748B',
            fontSize: '11px',
            padding: '3px 8px',
            cursor: 'pointer',
          }}
        >
          Hospitals ({hospitals.length})
        </button>

        {/* Tactical / Satellite Style Switcher */}
        {isLoaded && (
          <div style={{ marginLeft: '8px', borderLeft: '1px solid #334155', paddingLeft: '8px', display: 'flex', gap: '4px' }}>
            <button
              onClick={() => setMapType('tactical')}
              style={{
                background: mapType === 'tactical' ? '#334155' : 'transparent',
                border: 'none',
                borderRadius: '3px',
                color: mapType === 'tactical' ? '#FFFFFF' : '#94A3B8',
                fontSize: '10px',
                padding: '2px 6px',
                cursor: 'pointer',
              }}
            >
              Tactical
            </button>
            <button
              onClick={() => setMapType('satellite')}
              style={{
                background: mapType === 'satellite' ? '#334155' : 'transparent',
                border: 'none',
                borderRadius: '3px',
                color: mapType === 'satellite' ? '#FFFFFF' : '#94A3B8',
                fontSize: '10px',
                padding: '2px 6px',
                cursor: 'pointer',
              }}
            >
              Satellite
            </button>
          </div>
        )}
      </div>

      {/* Zoom Controls */}
      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          zIndex: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          style={{
            width: '32px',
            height: '32px',
            backgroundColor: '#1E293B',
            border: '1px solid #334155',
            borderRadius: '4px',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          style={{
            width: '32px',
            height: '32px',
            backgroundColor: '#1E293B',
            border: '1px solid #334155',
            borderRadius: '4px',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          <ZoomOut size={16} />
        </button>
      </div>

      {/* Live Google Maps Container */}
      <div
        ref={mapContainerRef}
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          inset: 0,
          visibility: isLoaded ? 'visible' : 'hidden',
        }}
      />

      {/* Fallback / Activation Overlay when Google Maps Key is Pending */}
      {!isLoaded && (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
          {/* Tactical SVG HUD Canvas (fallback preview so dispatchers can work immediately) */}
          <svg viewBox="0 0 800 500" style={{ width: '100%', height: '100%', display: 'block' }}>
            <defs>
              <pattern id="cmdgrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="800" height="500" fill="#0B132B" />
            <rect width="800" height="500" fill="url(#cmdgrid)" />

            {/* Major District Highway Corridor */}
            <path d="M 60 420 Q 250 300 400 240 T 740 80" fill="none" stroke="#1E293B" strokeWidth="6" />
            <path d="M 60 420 Q 250 300 400 240 T 740 80" fill="none" stroke="#334155" strokeWidth="2" strokeDasharray="4 4" />

            {/* Zones */}
            {layers.zones && zones.map((z, idx) => {
              const pt = project(z.center_latitude || 12.316, z.center_longitude || 76.650);
              const r = Math.max(30, (z.radius_meters || 500) / 25);
              return (
                <circle
                  key={`zone-${idx}`}
                  cx={pt.x}
                  cy={pt.y}
                  r={r}
                  fill={z.zone_type === 'HOT_ZONE' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)'}
                  stroke={z.zone_type === 'HOT_ZONE' ? '#EF4444' : '#F59E0B'}
                  strokeWidth="1.5"
                  strokeDasharray="6 3"
                />
              );
            })}

            {/* Hospitals */}
            {layers.hospitals && hospitals.map((h) => {
              const pt = project(h.latitude || 12.314, h.longitude || 76.649);
              return (
                <g key={`hosp-${h.id}`}>
                  <rect x={pt.x - 10} y={pt.y - 10} width="20" height="20" rx="3" fill="#1E3A8A" stroke="#3B82F6" strokeWidth="1.5" />
                  <path d={`M ${pt.x} ${pt.y - 5} L ${pt.x} ${pt.y + 5} M ${pt.x - 5} ${pt.y} L ${pt.x + 5} ${pt.y}`} stroke="#FFFFFF" strokeWidth="2" />
                </g>
              );
            })}

            {/* Ambulances */}
            {layers.ambulances && resources.map((r) => {
              const pt = project(r.latitude || 12.316, r.longitude || 76.631);
              const color = r.status === 'Available' ? '#10B981' : '#F59E0B';
              return (
                <g key={`res-${r.id}`} onClick={() => onSelectResource(r)} style={{ cursor: 'pointer' }}>
                  <circle cx={pt.x} cy={pt.y} r="8" fill="#0F172A" stroke={color} strokeWidth="2" />
                  <circle cx={pt.x} cy={pt.y} r="3" fill={color} />
                </g>
              );
            })}

            {/* Incidents */}
            {layers.incidents && incidents.map((inc) => {
              const pt = project(inc.latitude || 12.316, inc.longitude || 76.658);
              const isSelected = selectedIncident?.id === inc.id;
              const color = inc.priority === 'Critical' ? '#D92D3A' : '#EA580C';
              return (
                <g key={`inc-${inc.id}`} onClick={() => onSelectIncident(inc)} style={{ cursor: 'pointer' }}>
                  <circle cx={pt.x} cy={pt.y} r={isSelected ? 10 : 7} fill={color} stroke="#FFFFFF" strokeWidth="2" />
                </g>
              );
            })}
          </svg>

          {/* Quick Activation Card Banner */}
          <div
            style={{
              position: 'absolute',
              top: '60px',
              left: '50%',
              transform: 'translateX(-50%)',
              backgroundColor: 'rgba(15, 23, 42, 0.92)',
              backdropFilter: 'blur(10px)',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '12px 18px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              maxWidth: '460px',
              width: '90%',
              zIndex: 30,
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#F8FAFC', fontSize: '13px', fontWeight: 600 }}>
              <Globe size={16} color="#38BDF8" />
              <span>Google Maps Integration Ready</span>
            </div>
            <p style={{ margin: 0, fontSize: '11px', color: '#94A3B8', textAlign: 'center', lineHeight: 1.4 }}>
              Set <code style={{ color: '#38BDF8' }}>VITE_GOOGLE_MAPS_API_KEY</code> in environment, or enter key below to switch from tactical HUD to live Google Maps tiles.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (inputKey.trim()) setKeyAndReload(inputKey.trim());
              }}
              style={{ display: 'flex', gap: '6px', width: '100%', marginTop: '4px' }}
            >
              <input
                type="text"
                placeholder="Google Maps API Key (AIzaSy...)"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                style={{
                  flex: 1,
                  padding: '6px 10px',
                  borderRadius: '4px',
                  backgroundColor: '#1E293B',
                  border: '1px solid #475569',
                  color: '#FFFFFF',
                  fontSize: '12px',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  backgroundColor: colors.secondary,
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Key size={12} /> Activate
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Legend & Status Overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: '12px',
          left: '12px',
          backgroundColor: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '6px 12px',
          borderRadius: '6px',
          border: '1px solid #334155',
          display: 'flex',
          gap: '12px',
          fontSize: '11px',
          color: '#94A3B8',
          zIndex: 20,
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#D92D3A' }} /> Critical Incident
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981' }} /> Available Ambulance
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#3B82F6' }} /> Hospital Center
        </span>
        <span style={{ marginLeft: 'auto', color: isLoaded ? '#34D399' : '#F59E0B', fontWeight: 600 }}>
          {isLoaded ? '● Google Maps Live' : '○ Google Maps Ready'}
        </span>
      </div>
    </div>
  );
}
