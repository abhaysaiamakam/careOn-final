import React from 'react';
import { 
  Ambulance, 
  Radio, 
  MapPin, 
  Cloud, 
  CloudOff, 
  RefreshCw, 
  Volume2, 
  VolumeX, 
  LogOut, 
  AlertCircle,
  Clock,
  Inbox,
  LayoutDashboard,
  Activity
} from 'lucide-react';
import { Badge, Button } from '@careon/design-system';

export function ResponderHeader({
  user,
  vehicle,
  currentView,
  onNavigate,
  activeMission,
  pendingMissionsCount = 0,
  gpsStatus,
  wsStatus,
  syncStatus,
  audioMuted,
  onToggleAudio,
  onTriggerSync,
  onLogout
}) {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Left: Brand & Unit info */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-10 h-10 rounded-lg bg-red-600 flex items-center justify-center text-white shadow-sm">
                <Ambulance className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-gray-900 tracking-tight text-lg">CareOn</span>
                  <span className="text-xs uppercase px-1.5 py-0.5 bg-gray-100 text-gray-700 font-semibold rounded tracking-wider">
                    Responder
                  </span>
                </div>
                <div className="text-xs text-gray-500 font-medium">
                  {vehicle ? `${vehicle.callsign || vehicle.plate_number} • ${user?.full_name || 'Unit'}` : (user?.full_name || 'Responder Unit')}
                </div>
              </div>
            </div>

            {/* Navigation Tabs (Desktop & Tablet) */}
            <nav className="hidden md:flex items-center space-x-1 ml-6 border-l border-gray-200 pl-6">
              <button
                type="button"
                onClick={() => onNavigate('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                  currentView === 'dashboard'
                    ? 'bg-red-50 text-red-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <LayoutDashboard className="w-4 h-4" />
                <span>Dashboard</span>
              </button>

              <button
                type="button"
                onClick={() => onNavigate('active')}
                className={`relative px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                  currentView === 'active'
                    ? 'bg-red-50 text-red-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Activity className="w-4 h-4" />
                <span>Active Mission</span>
                {activeMission && (
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping ml-1" />
                )}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('inbox')}
                className={`relative px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                  currentView === 'inbox'
                    ? 'bg-red-50 text-red-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Inbox className="w-4 h-4" />
                <span>Inbox</span>
                {pendingMissionsCount > 0 && (
                  <span className="inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-red-600 rounded-full ml-1">
                    {pendingMissionsCount}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('history')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center space-x-1.5 ${
                  currentView === 'history'
                    ? 'bg-red-50 text-red-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Clock className="w-4 h-4" />
                <span>History</span>
              </button>
            </nav>
          </div>

          {/* Right: Operational Status Indicators */}
          <div className="flex items-center space-x-3">
            {/* GPS Telemetry Pill */}
            <div 
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                gpsStatus?.transmitting
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : gpsStatus?.tracking
                  ? 'bg-amber-50 text-amber-800 border-amber-200'
                  : 'bg-gray-50 text-gray-600 border-gray-200'
              }`}
              title={gpsStatus?.error || (gpsStatus?.accuracy ? `Accuracy: ±${Math.round(gpsStatus.accuracy)}m` : 'GPS Ready')}
            >
              <span className={`w-2 h-2 rounded-full ${gpsStatus?.transmitting ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'}`} />
              <MapPin className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {gpsStatus?.accuracy ? `±${Math.round(gpsStatus.accuracy)}m` : 'GPS'}
              </span>
            </div>

            {/* Offline Sync State */}
            <button
              type="button"
              onClick={onTriggerSync}
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                syncStatus?.isOnline
                  ? syncStatus?.pendingCount > 0
                    ? 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100'
                    : 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100'
                  : 'bg-red-50 text-red-700 border-red-200'
              }`}
              title={syncStatus?.isOnline ? `${syncStatus.pendingCount} queued actions` : 'Offline Mode (Local Journal Active)'}
            >
              {syncStatus?.isOnline ? (
                <>
                  <Cloud className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">
                    {syncStatus.isSyncing ? 'Syncing...' : syncStatus.pendingCount > 0 ? `${syncStatus.pendingCount} queued` : 'Synced'}
                  </span>
                </>
              ) : (
                <>
                  <CloudOff className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Offline</span>
                </>
              )}
            </button>

            {/* M4 WebSocket Live Badge */}
            <div 
              className={`flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium ${
                wsStatus === 'connected'
                  ? 'text-emerald-700 bg-emerald-50'
                  : wsStatus === 'reconnecting'
                  ? 'text-amber-700 bg-amber-50'
                  : 'text-gray-500 bg-gray-100'
              }`}
              title={`M4 WebSocket: ${wsStatus}`}
            >
              <Radio className="w-3.5 h-3.5" />
              <span className="hidden lg:inline capitalize">{wsStatus}</span>
            </div>

            {/* Audio Alert Chime Toggle */}
            <button
              type="button"
              onClick={onToggleAudio}
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title={audioMuted ? 'Unmute Audio Alert Chime' : 'Mute Audio Alert Chime'}
            >
              {audioMuted ? <VolumeX className="w-4 h-4 text-gray-400" /> : <Volume2 className="w-4 h-4 text-emerald-600" />}
            </button>

            {/* Logout */}
            <button
              type="button"
              onClick={onLogout}
              className="p-1.5 rounded-lg text-gray-500 hover:text-red-700 hover:bg-red-50 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Mobile Navigation Bar */}
        <div className="flex md:hidden border-t border-gray-100 py-2 justify-around">
          <button
            type="button"
            onClick={() => onNavigate('dashboard')}
            className={`flex flex-col items-center py-1 px-3 text-xs font-medium ${
              currentView === 'dashboard' ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            <LayoutDashboard className="w-5 h-5 mb-0.5" />
            <span>Dashboard</span>
          </button>

          <button
            type="button"
            onClick={() => onNavigate('active')}
            className={`flex flex-col items-center py-1 px-3 text-xs font-medium relative ${
              currentView === 'active' ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            <Activity className="w-5 h-5 mb-0.5" />
            <span>Mission</span>
            {activeMission && (
              <span className="absolute top-1 right-2 w-2 h-2 rounded-full bg-red-500" />
            )}
          </button>

          <button
            type="button"
            onClick={() => onNavigate('inbox')}
            className={`flex flex-col items-center py-1 px-3 text-xs font-medium relative ${
              currentView === 'inbox' ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            <Inbox className="w-5 h-5 mb-0.5" />
            <span>Inbox</span>
            {pendingMissionsCount > 0 && (
              <span className="absolute top-0 right-2 px-1.5 py-0.2 text-[10px] font-bold text-white bg-red-600 rounded-full">
                {pendingMissionsCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => onNavigate('history')}
            className={`flex flex-col items-center py-1 px-3 text-xs font-medium ${
              currentView === 'history' ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            <Clock className="w-5 h-5 mb-0.5" />
            <span>History</span>
          </button>
        </div>
      </div>
    </header>
  );
}
