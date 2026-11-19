import React, { useEffect, useRef } from 'react';
import { useGoogleMaps } from '@careon/design-system';
import { Navigation, MapPin, ExternalLink } from 'lucide-react';

export function MissionMap({
  responderPosition,
  incidentPosition,
  hospitalPosition,
  missionStatus
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const { isLoaded, loadError } = useGoogleMaps();

  // Determine active destination (Hospital or Incident)
  const isHeadingToHospital = [
    'en_route_hospital',
    'arrived_hospital',
    'handover_initiated',
    'handover_completed'
  ].includes(missionStatus);

  const activeDestination = isHeadingToHospital && hospitalPosition
    ? { lat: hospitalPosition.lat, lng: hospitalPosition.lng, label: hospitalPosition.name || 'Hospital' }
    : incidentPosition
    ? { lat: incidentPosition.lat, lng: incidentPosition.lng, label: incidentPosition.address || 'Incident Scene' }
    : null;

  const googleMapsUrl = activeDestination
    ? `https://www.google.com/maps/dir/?api=1&destination=${activeDestination.lat},${activeDestination.lng}`
    : null;

  // Initialize Map
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current || !window.google?.maps) return;

    if (!mapInstanceRef.current) {
      const defaultCenter = responderPosition || incidentPosition || { lat: 12.9716, lng: 77.5946 };
      mapInstanceRef.current = new window.google.maps.Map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: 14,
        disableDefaultUI: false,
        zoomControl: true,
        streetViewControl: false,
        mapTypeControl: false,
        fullscreenControl: false,
        styles: [
          { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] }
        ]
      });
    }
  }, [isLoaded]);

  // Update Markers & Bounds
  useEffect(() => {
    if (!mapInstanceRef.current || !window.google?.maps) return;

    // Clear old markers
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];

    const bounds = new window.google.maps.LatLngBounds();
    let hasPoints = false;

    // Responder Marker
    if (responderPosition?.lat && responderPosition?.lng) {
      const respLatLng = new window.google.maps.LatLng(responderPosition.lat, responderPosition.lng);
      bounds.extend(respLatLng);
      hasPoints = true;

      const responderMarker = new window.google.maps.Marker({
        position: respLatLng,
        map: mapInstanceRef.current,
        title: 'Responder Unit (You)',
        icon: {
          path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: '#2563EB',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
          rotation: responderPosition.heading || 0
        }
      });
      markersRef.current.push(responderMarker);
    }

    // Incident Marker
    if (incidentPosition?.lat && incidentPosition?.lng) {
      const incLatLng = new window.google.maps.LatLng(incidentPosition.lat, incidentPosition.lng);
      bounds.extend(incLatLng);
      hasPoints = true;

      const incidentMarker = new window.google.maps.Marker({
        position: incLatLng,
        map: mapInstanceRef.current,
        title: 'Incident Scene',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#DC2626',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2
        }
      });
      markersRef.current.push(incidentMarker);
    }

    // Hospital Marker
    if (hospitalPosition?.lat && hospitalPosition?.lng) {
      const hospLatLng = new window.google.maps.LatLng(hospitalPosition.lat, hospitalPosition.lng);
      bounds.extend(hospLatLng);
      hasPoints = true;

      const hospMarker = new window.google.maps.Marker({
        position: hospLatLng,
        map: mapInstanceRef.current,
        title: hospitalPosition.name || 'Receiving Hospital',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 9,
          fillColor: '#059669',
          fillOpacity: 1,
          strokeColor: '#FFFFFF',
          strokeWeight: 2
        }
      });
      markersRef.current.push(hospMarker);
    }

    if (hasPoints) {
      if (markersRef.current.length === 1) {
        mapInstanceRef.current.setCenter(bounds.getCenter());
        mapInstanceRef.current.setZoom(15);
      } else {
        mapInstanceRef.current.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
      }
    }
  }, [isLoaded, responderPosition, incidentPosition, hospitalPosition]);

  return (
    <div className="relative w-full h-[320px] sm:h-[400px] rounded-xl overflow-hidden border border-gray-200 bg-gray-100 shadow-sm">
      {/* Map Target Canvas */}
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Fallback if map not loaded */}
      {!isLoaded && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-4 bg-gray-50 text-gray-500">
          <MapPin className="w-8 h-8 text-gray-400 mb-2 animate-bounce" />
          <p className="text-sm font-medium">
            {loadError ? 'Map preview unavailable' : 'Loading operational satellite map...'}
          </p>
          {incidentPosition && (
            <p className="text-xs text-gray-400 mt-1">
              Scene Coordinates: {incidentPosition.lat.toFixed(4)}, {incidentPosition.lng.toFixed(4)}
            </p>
          )}
        </div>
      )}

      {/* External Navigation Floating CTA */}
      {googleMapsUrl && (
        <div className="absolute bottom-3 right-3 z-10">
          <a
            href={googleMapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-2 px-3 py-2 bg-white text-gray-900 text-xs font-bold rounded-lg shadow-md border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <Navigation className="w-4 h-4 text-red-600" />
            <span>Navigate in Google Maps</span>
            <ExternalLink className="w-3 h-3 text-gray-400" />
          </a>
        </div>
      )}

      {/* Destination Indicator Badge */}
      {activeDestination && (
        <div className="absolute top-3 left-3 z-10 bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-lg shadow-sm border border-gray-200 text-xs font-semibold text-gray-800 flex items-center space-x-1.5">
          <span className={`w-2.5 h-2.5 rounded-full ${isHeadingToHospital ? 'bg-emerald-500' : 'bg-red-600'}`} />
          <span>Heading to: {isHeadingToHospital ? 'Hospital' : 'Incident Scene'}</span>
        </div>
      )}
    </div>
  );
}
