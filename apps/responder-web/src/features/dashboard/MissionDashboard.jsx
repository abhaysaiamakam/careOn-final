import React from 'react';
import { 
  Activity, 
  AlertTriangle, 
  ArrowRight, 
  CheckCircle2, 
  Clock, 
  MapPin, 
  Navigation, 
  Phone, 
  Shield, 
  Truck, 
  UserCheck,
  Inbox,
  Radio,
  FileText
} from 'lucide-react';
import { Badge, Button, Card } from '@careon/design-system';
import { MISSION_STATUS_CONFIG } from '@careon/contracts';

export function MissionDashboard({
  user,
  vehicle,
  activeMission,
  pendingMissions = [],
  completedMissionsCount = 0,
  gpsStatus,
  syncStatus,
  isAvailable,
  onToggleAvailability,
  onNavigate
}) {
  const activeStatusCfg = activeMission 
    ? MISSION_STATUS_CONFIG[activeMission.status] || { label: activeMission.status, color: 'info' }
    : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Pending Assignment Alert Banner */}
      {pendingMissions.length > 0 && (
        <div className="bg-amber-50 border-2 border-amber-500 rounded-xl p-4 shadow-sm animate-pulse flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-amber-500 text-white rounded-lg">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-amber-900">
                {pendingMissions.length} New Mission Assignment Pending
              </h3>
              <p className="text-sm text-amber-700">
                A mission has been assigned to your unit. Immediate response required.
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="md"
            onClick={() => onNavigate('inbox')}
            className="bg-amber-600 hover:bg-amber-700 text-white font-semibold flex items-center justify-center space-x-2"
          >
            <span>Review Assignment</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Unit & Status Overview Card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="flex items-start space-x-4">
            <div className="w-14 h-14 rounded-xl bg-gray-100 border border-gray-200 flex items-center justify-center text-red-600 flex-shrink-0">
              <Truck className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center space-x-3 flex-wrap">
                <h1 className="text-2xl font-bold text-gray-900">
                  {vehicle?.callsign || vehicle?.plate_number || 'Unit Alpha-1'}
                </h1>
                <Badge variant={isAvailable ? 'success' : 'default'}>
                  {isAvailable ? 'READY / STANDBY' : 'OFFLINE / BUSY'}
                </Badge>
                {vehicle?.vehicle_type && (
                  <span className="text-xs uppercase bg-gray-100 text-gray-600 font-semibold px-2 py-0.5 rounded">
                    {vehicle.vehicle_type}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-1 flex items-center space-x-2">
                <span>Responder: <strong className="text-gray-700">{user?.full_name || 'Paramedic'}</strong></span>
                <span>•</span>
                <span>Role: <strong className="text-gray-700 capitalize">{user?.role || 'Responder'}</strong></span>
                {vehicle?.hospital_affiliation && (
                  <>
                    <span>•</span>
                    <span>Affiliation: <strong className="text-gray-700">{vehicle.hospital_affiliation}</strong></span>
                  </>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <Button
              variant={isAvailable ? 'outline' : 'primary'}
              size="md"
              onClick={onToggleAvailability}
              className="min-h-[44px]"
            >
              {isAvailable ? 'Go Off-Duty / Busy' : 'Set Available (On-Duty)'}
            </Button>
          </div>
        </div>
      </div>

      {/* Active Mission Hero Card */}
      {activeMission ? (
        <div className="bg-white rounded-xl border-2 border-red-500 p-6 shadow-md relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-red-600 text-white text-xs font-bold px-3 py-1 rounded-bl-lg uppercase tracking-wider flex items-center space-x-1">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            <span>Active Mission In Progress</span>
          </div>

          <div className="space-y-4 pt-2">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-semibold text-gray-500">Incident Code:</span>
                  <span className="text-sm font-mono font-bold text-gray-900">
                    {activeMission.incident_code || activeMission.incident_id?.slice(0, 8)}
                  </span>
                  <Badge variant={activeStatusCfg?.color || 'primary'}>
                    {activeStatusCfg?.label || activeMission.status}
                  </Badge>
                </div>
                <h2 className="text-xl font-bold text-gray-900 mt-1">
                  {activeMission.incident?.category || activeMission.incident_category || 'Medical Emergency'}
                </h2>
              </div>

              <Button
                variant="primary"
                size="lg"
                onClick={() => onNavigate('active')}
                className="bg-red-600 hover:bg-red-700 text-white font-bold flex items-center justify-center space-x-2 min-h-[48px] px-6"
              >
                <span>Open Mission Workspace</span>
                <ArrowRight className="w-5 h-5" />
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100">
              <div className="flex items-start space-x-2 text-sm text-gray-600">
                <MapPin className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900">Location</div>
                  <div>{activeMission.incident?.location_address || activeMission.incident_address || 'GPS Coordinates Provided'}</div>
                </div>
              </div>

              <div className="flex items-start space-x-2 text-sm text-gray-600">
                <Clock className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900">Status Duration</div>
                  <div>Active in {activeStatusCfg?.label || activeMission.status}</div>
                </div>
              </div>

              <div className="flex items-start space-x-2 text-sm text-gray-600">
                <Shield className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900">Priority</div>
                  <div className="font-bold text-red-600 uppercase">
                    {activeMission.incident?.priority || activeMission.priority || 'CRITICAL P1'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
          <div className="w-16 h-16 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Unit Ready & Standing By</h2>
          <p className="text-sm text-gray-500 max-w-md mx-auto mt-2">
            No active emergency mission assigned. Live GPS telemetry is broadcasting to Command Dispatch.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button
              variant="outline"
              size="md"
              onClick={() => onNavigate('inbox')}
              className="flex items-center space-x-2"
            >
              <Inbox className="w-4 h-4" />
              <span>Check Assignment Inbox ({pendingMissions.length})</span>
            </Button>
            <Button
              variant="outline"
              size="md"
              onClick={() => onNavigate('history')}
              className="flex items-center space-x-2"
            >
              <FileText className="w-4 h-4" />
              <span>View Completed Shifts</span>
            </Button>
          </div>
        </div>
      )}

      {/* Operational Metrics & Device Health Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Missions Completed */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-500">Missions Today</span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-gray-900 mt-2">{completedMissionsCount}</div>
          <div className="text-xs text-gray-500 mt-1">Logged in operational history</div>
        </div>

        {/* GPS Telemetry */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-500">GPS Telemetry</span>
            <div className={`p-2 rounded-lg ${gpsStatus?.transmitting ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'}`}>
              <MapPin className="w-5 h-5" />
            </div>
          </div>
          <div className="text-sm font-bold text-gray-900 mt-2 truncate">
            {gpsStatus?.latitude ? `${gpsStatus.latitude.toFixed(4)}, ${gpsStatus.longitude.toFixed(4)}` : 'Waiting for GPS fix'}
          </div>
          <div className="text-xs text-gray-500 mt-1 flex items-center space-x-1">
            <span className={`w-2 h-2 rounded-full ${gpsStatus?.transmitting ? 'bg-emerald-500' : 'bg-amber-400'}`} />
            <span>{gpsStatus?.transmitting ? `Interval: 5s • ±${Math.round(gpsStatus?.accuracy || 0)}m` : 'Telemetry Idle'}</span>
          </div>
        </div>

        {/* Offline Sync State */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-500">Local Journal</span>
            <div className="p-2 bg-purple-50 text-purple-600 rounded-lg">
              <Radio className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-gray-900 mt-2">
            {syncStatus?.pendingCount ?? 0}
            <span className="text-xs font-normal text-gray-500 ml-1">queued actions</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {syncStatus?.isOnline ? 'Network Online' : 'Operating Offline'}
          </div>
        </div>

        {/* Dispatch Connection */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-500">Dispatch Link</span>
            <div className="p-2 bg-red-50 text-red-600 rounded-lg">
              <Radio className="w-5 h-5" />
            </div>
          </div>
          <div className="text-sm font-bold text-gray-900 mt-2">
            M4 Real-time Duplex
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Duplex WebSocket channel active
          </div>
        </div>
      </div>
    </div>
  );
}
