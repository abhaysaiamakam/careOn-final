import React, { useState } from 'react';
import { MapPin, Navigation, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { Button, Input, Card, Badge, typography, colors } from '@careon/design-system';
import { acquireCurrentLocation, reverseGeocode } from '../services/geolocation.js';

export function EmergencyLocationPicker({
  locationName,
  latitude,
  longitude,
  onChange,
}) {
  const [loadingGps, setLoadingGps] = useState(false);
  const [gpsError, setGpsError] = useState(null);
  const [gpsAccuracy, setGpsAccuracy] = useState(null);

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
          <span>{gpsError} Please enter your address or landmark below.</span>
        </div>
      )}

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
