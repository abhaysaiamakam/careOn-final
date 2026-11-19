import React, { useState } from 'react';
import { MapPin, Navigation, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { Button, Input, Card, Badge, typography, colors } from '@careon/design-system';
import { acquireCurrentLocation, reverseGeocode } from '../services/geolocation.js';
import { CitizenGoogleMap } from './CitizenGoogleMap.jsx';

export function EmergencyLocationPicker({
  locationName,
  latitude,
  longitude,
  onChange,
}) {
  const [loadingGps, setLoadingGps] = useState(false);
  const [gpsError, setGpsError] = useState(null);
  const [gpsAccuracy, setGpsAccuracy] = useState(null);
  const [geocodingPin, setGeocodingPin] = useState(false);

  const handleAcquireGps = async () => {
    setLoadingGps(true);
    setGpsError(null);
    try {
      const pos = await acquireCurrentLocation();
      setGpsAccuracy(pos.accuracy);

      // Trigger reverse geocoding to suggest address if empty or update coordinates
      const addr = await reverseGeocode(pos.latitude, pos.longitude);
      onChange({
        latitude: pos.latitude,
        longitude: pos.longitude,
        locationName: locationName || addr,
      });
    } catch (err) {
      setGpsError(err.message || 'Could not acquire GPS position.');
    } finally {
      setLoadingGps(false);
    }
  };

  const handleMapPinChange = async ({ lat, lng }) => {
    setGeocodingPin(true);
    try {
      const addr = await reverseGeocode(lat, lng);
      onChange({
        latitude: lat,
        longitude: lng,
        locationName: addr || locationName,
      });
    } catch (e) {
      onChange({
        latitude: lat,
        longitude: lng,
        locationName,
      });
    } finally {
      setGeocodingPin(false);
    }
  };

  const currentLat = typeof latitude === 'number' && latitude !== 0 ? latitude : 12.3052;
  const currentLng = typeof longitude === 'number' && longitude !== 0 ? longitude : 76.6552;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <Button
          type="button"
          size="sm"
          variant="secondary-red"
          onClick={handleAcquireGps}
          loading={loadingGps}
          icon={Navigation}
        >
          {loadingGps ? 'Acquiring GPS Position...' : 'Use My Current Location'}
        </Button>

        {gpsAccuracy !== null && (
          <Badge variant="success" size="sm">
            GPS Accurate to ±{gpsAccuracy}m
          </Badge>
        )}
      </div>

      {gpsError && (
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FECACA',
            borderRadius: '6px',
            fontSize: typography.fontSize.xs,
            color: colors.secondary,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <AlertCircle size={14} />
          <span>{gpsError} Please enter your address or tap the map below.</span>
        </div>
      )}

      {/* Interactive Google Map Location Picker */}
      <CitizenGoogleMap
        center={{ lat: currentLat, lng: currentLng }}
        zoom={latitude && longitude ? 16 : 14}
        height="220px"
        selectable={true}
        selectedPin={{ lat: currentLat, lng: currentLng }}
        onPinChange={handleMapPinChange}
        helperNotice={
          geocodingPin
            ? 'Updating address from Google Maps pin...'
            : '📍 Click map or drag pin to position exact emergency location'
        }
      />

      <Input
        label="Emergency Location / Street Address / Landmark"
        required
        placeholder="e.g. KR Circle, Near Mysore Palace North Gate"
        value={locationName}
        onChange={(e) => onChange({ locationName: e.target.value, latitude, longitude })}
        helperText="Be as specific as possible (building name, floor, cross street, or landmarks)."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <Input
          label="Latitude"
          type="number"
          step="any"
          value={latitude || ''}
          onChange={(e) =>
            onChange({
              locationName,
              latitude: parseFloat(e.target.value) || 0,
              longitude,
            })
          }
          helperText="WGS84 Coordinate"
        />
        <Input
          label="Longitude"
          type="number"
          step="any"
          value={longitude || ''}
          onChange={(e) =>
            onChange({
              locationName,
              latitude,
              longitude: parseFloat(e.target.value) || 0,
            })
          }
          helperText="WGS84 Coordinate"
        />
      </div>
    </div>
  );
}
