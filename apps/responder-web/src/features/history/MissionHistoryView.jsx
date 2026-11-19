import React, { useState } from 'react';
import { 
  Clock, 
  Search, 
  CheckCircle2, 
  XCircle, 
  MapPin, 
  Hospital, 
  Calendar, 
  FileText,
  ChevronRight
} from 'lucide-react';
import { Badge, Button, Modal } from '@careon/design-system';

export function MissionHistoryView({
  missions = [],
  isLoading = false
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMission, setSelectedMission] = useState(null);

  // Filter completed or terminal missions
  const historyMissions = missions.filter((m) => ['completed', 'cancelled', 'rejected'].includes(m.status));

  const filtered = historyMissions.filter((m) => {
    const inc = m.incident || {};
    const text = `${m.id} ${inc.code || ''} ${inc.category || ''} ${inc.location_address || ''}`.toLowerCase();
    return text.includes(searchTerm.toLowerCase());
  });

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Title & Search bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Mission History</h1>
          <p className="text-sm text-gray-500 mt-1">
            Archived logs of completed emergency responses and patient handovers.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by code or type..."
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none bg-white"
          />
        </div>
      </div>

      {/* Missions List */}
      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-sm">
          <div className="w-16 h-16 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">No Past Missions Found</h3>
          <p className="text-sm text-gray-500 max-w-sm mx-auto mt-2">
            {searchTerm ? 'No missions match your search query.' : 'Completed missions from your shifts will appear here.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((mission) => {
            const incident = mission.incident || {};
            const isCompleted = mission.status === 'completed';

            return (
              <div
                key={mission.id || mission.assignment_id}
                onClick={() => setSelectedMission(mission)}
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:border-red-400 cursor-pointer transition-all flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-gray-500">
                      #{incident.code || mission.id?.slice(0, 8)}
                    </span>
                    <Badge variant={isCompleted ? 'success' : 'default'}>
                      {mission.status.toUpperCase()}
                    </Badge>
                    <span className="text-xs text-gray-400">
                      {new Date(mission.created_at || Date.now()).toLocaleDateString()}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-gray-900">
                    {incident.category || mission.incident_category || 'Emergency Callout'}
                  </h3>

                  <div className="flex items-center space-x-4 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center space-x-1">
                      <MapPin className="w-3.5 h-3.5 text-gray-400" />
                      <span>{incident.location_address || 'Scene location'}</span>
                    </span>
                    {mission.destination_hospital_name && (
                      <span className="flex items-center space-x-1">
                        <Hospital className="w-3.5 h-3.5 text-gray-400" />
                        <span>{mission.destination_hospital_name}</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end sm:self-center">
                  <span className="text-xs font-semibold text-red-600 hidden sm:inline">View Summary</span>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Mission Detail Modal */}
      {selectedMission && (
        <Modal
          isOpen={Boolean(selectedMission)}
          onClose={() => setSelectedMission(null)}
          title={`Mission Summary #${selectedMission.incident?.code || selectedMission.id?.slice(0, 8)}`}
        >
          <div className="space-y-4 pt-2 text-sm">
            <div className="flex justify-between items-center pb-2 border-b border-gray-100">
              <span className="text-gray-500">Status</span>
              <Badge variant={selectedMission.status === 'completed' ? 'success' : 'default'}>
                {selectedMission.status.toUpperCase()}
              </Badge>
            </div>

            <div>
              <span className="font-semibold text-gray-700 block mb-1">Category & Symptoms</span>
              <p className="text-gray-900 font-medium">
                {selectedMission.incident?.category || 'Medical Emergency'}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                {selectedMission.incident?.description || 'No additional description provided.'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-100">
              <div>
                <span className="text-xs text-gray-500 block">Assigned At</span>
                <span className="font-medium text-gray-900 text-xs">
                  {new Date(selectedMission.assigned_at || selectedMission.created_at || Date.now()).toLocaleTimeString()}
                </span>
              </div>
              <div>
                <span className="text-xs text-gray-500 block">Completed At</span>
                <span className="font-medium text-gray-900 text-xs">
                  {selectedMission.completed_at ? new Date(selectedMission.completed_at).toLocaleTimeString() : 'N/A'}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-gray-100">
              <span className="text-xs text-gray-500 block">Scene Location</span>
              <span className="font-medium text-gray-900 text-xs">
                {selectedMission.incident?.location_address || 'GPS Coordinates Recorded'}
              </span>
            </div>

            <div className="flex justify-end pt-3 border-t border-gray-200">
              <Button
                variant="outline"
                size="md"
                onClick={() => setSelectedMission(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
