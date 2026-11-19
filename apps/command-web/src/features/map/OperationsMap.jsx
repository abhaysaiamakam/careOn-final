import React, { useState } from 'react';
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
} from 'lucide-react';
import { colors, typography, Badge } from '@careon/design-system';

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
  const [zoom, setZoom] = useState(1);
  const [layers, setLayers] = useState({
    incidents: true,
    ambulances: true,
    hospitals: true,
    zones: true,
  });

  // Center coordinate reference: Mysuru/Central operations (12.310, 76.650)
  const mapCenter = { lat: 12.310, lon: 76.650 };
  const latSpan = 0.12 / zoom;
  const lonSpan = 0.16 / zoom;

  // Project geographic coords to SVG coordinate space (800x500)
  const project = (lat, lon) => {
    const x = ((lon - (mapCenter.lon - lonSpan / 2)) / lonSpan) * 800;
    const y = (((mapCenter.lat + latSpan / 2) - lat) / latSpan) * 500;
    return { x: Math.max(20, Math.min(780, x)), y: Math.max(20, Math.min(480, y)) };
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'Critical': return '#D92D3A';
      case 'High': return '#EA580C';
      case 'Medium': return '#0284C7';
      default: return '#64748B';
    }
  };

  const getResourceStatusColor = (status) => {
    switch (status) {
      case 'Available': return '#10B981';
      case 'Assigned':
      case 'En Route': return '#F59E0B';
      default: return '#64748B';
    }
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
        }}
      >
        <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginRight: '6px' }}>
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
          onClick={() => setZoom((z) => Math.min(z + 0.3, 2.5))}
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
          onClick={() => setZoom((z) => Math.max(z - 0.3, 0.8))}
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

      {/* SVG Interactive Canvas */}
      <svg
        viewBox="0 0 800 500"
        style={{ width: '100%', height: '100%', display: 'block' }}
      >
        {/* Background Grid Lines (Tactical HUD) */}
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="800" height="500" fill="#0B132B" />
        <rect width="800" height="500" fill="url(#grid)" />

        {/* Major District Highway Corridor Overlay */}
        <path
          d="M 60 420 Q 250 300 400 240 T 740 80"
          fill="none"
          stroke="#1E293B"
          strokeWidth="6"
        />
        <path
          d="M 60 420 Q 250 300 400 240 T 740 80"
          fill="none"
          stroke="#334155"
          strokeWidth="2"
          strokeDasharray="4 4"
        />

        {/* Operational Zones (M11) */}
        {layers.zones && zones.map((z, idx) => {
          const pt = project(z.center_latitude || 12.316, z.center_longitude || 76.650);
          const r = Math.max(30, (z.radius_meters || 500) / 25);
          return (
            <g key={`zone-${idx}`}>
              <circle
                cx={pt.x}
                cy={pt.y}
                r={r}
                fill={z.zone_type === 'HOT_ZONE' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)'}
                stroke={z.zone_type === 'HOT_ZONE' ? '#EF4444' : '#F59E0B'}
                strokeWidth="1.5"
                strokeDasharray="6 3"
              />
              <text x={pt.x} y={pt.y - r - 4} fill="#CBD5E1" fontSize="10" textAnchor="middle" fontWeight="bold">
                {z.zone_name || 'Operational Zone'}
              </text>
            </g>
          );
        })}

        {/* Hospital Facility Nodes */}
        {layers.hospitals && hospitals.map((h) => {
          const pt = project(h.latitude || 12.314, h.longitude || 76.649);
          return (
            <g
              key={`hosp-${h.id}`}
              style={{ cursor: 'pointer' }}
              onClick={() => {}}
            >
              <rect
                x={pt.x - 12}
                y={pt.y - 12}
                width="24"
                height="24"
                rx="4"
                fill="#1E3A8A"
                stroke={h.divert_status ? '#EF4444' : '#3B82F6'}
                strokeWidth="2"
              />
              <path
                d={`M ${pt.x} ${pt.y - 6} L ${pt.x} ${pt.y + 6} M ${pt.x - 6} ${pt.y} L ${pt.x + 6} ${pt.y}`}
                stroke="#FFFFFF"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <text
                x={pt.x}
                y={pt.y + 20}
                fill="#93C5FD"
                fontSize="9"
                textAnchor="middle"
                fontWeight="600"
              >
                {h.name?.split(' ')[0] || 'Hospital'}
              </text>
            </g>
          );
        })}

        {/* Resources / Ambulances */}
        {layers.ambulances && resources.map((r) => {
          const pt = project(r.latitude || 12.316, r.longitude || 76.631);
          const isSelected = selectedResource?.id === r.id;
          const statusColor = getResourceStatusColor(r.status);
          return (
            <g
              key={`res-${r.id}`}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelectResource(r)}
            >
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isSelected ? 14 : 10}
                fill="#0F172A"
                stroke={statusColor}
                strokeWidth={isSelected ? 3 : 2}
              />
              <circle
                cx={pt.x}
                cy={pt.y}
                r="4"
                fill={statusColor}
              />
              <text
                x={pt.x}
                y={pt.y - 12}
                fill="#F8FAFC"
                fontSize="9"
                textAnchor="middle"
                fontWeight="bold"
              >
                {r.resource_code || 'AMB'}
              </text>
            </g>
          );
        })}

        {/* Active Incidents */}
        {layers.incidents && incidents.map((inc) => {
          const pt = project(inc.latitude || 12.316, inc.longitude || 76.658);
          const isSelected = selectedIncident?.id === inc.id;
          const prioColor = getPriorityColor(inc.priority);
          return (
            <g
              key={`inc-${inc.id}`}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelectIncident(inc)}
            >
              {/* Pulsing ring for critical/selected */}
              {(inc.priority === 'Critical' || isSelected) && (
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r="20"
                  fill="none"
                  stroke={prioColor}
                  strokeWidth="1.5"
                  opacity="0.4"
                >
                  <animate
                    attributeName="r"
                    values="14;24;14"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.8;0.1;0.8"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Pin body */}
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isSelected ? 10 : 8}
                fill={prioColor}
                stroke="#FFFFFF"
                strokeWidth="2"
              />

              <text
                x={pt.x}
                y={pt.y + 16}
                fill="#FFFFFF"
                fontSize="10"
                textAnchor="middle"
                fontWeight="bold"
                style={{ textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
              >
                {inc.incident_code || `#${inc.id}`}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend & Quick Stats Overlay */}
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
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#D92D3A' }} /> Critical Incident
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981' }} /> Ambulance Available
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#3B82F6' }} /> Hospital Facility
        </span>
      </div>
    </div>
  );
}
