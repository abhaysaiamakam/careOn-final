import React, { useState } from 'react';
import { 
  AlertTriangle, 
  Check, 
  X, 
  MapPin, 
  Clock, 
  ShieldAlert, 
  Phone, 
  FileText, 
  Navigation, 
  Inbox as InboxIcon,
  HelpCircle
} from 'lucide-react';
import { Badge, Button, Modal } from '@careon/design-system';

const REJECTION_REASONS = [
  { id: 'vehicle_breakdown', label: 'Vehicle Breakdown / Mechanical Failure' },
  { id: 'crew_shortage', label: 'Crew Fatigue / Staffing Shortage' },
  { id: 'supplies_depleted', label: 'Medical Supplies Depleted' },
  { id: 'out_of_radius', label: 'Incident Out of Operating Radius' },
  { id: 'clinical_mismatch', label: 'Incident Exceeds Clinical Capability' },
  { id: 'other', label: 'Other Operational Obstacle' },
];

export function MissionInbox({
  pendingMissions = [],
  onAcceptMission,
  onRejectMission,
  responderLocation,
  isProcessing = false
}) {
  const [selectedMissionForReject, setSelectedMissionForReject] = useState(null);
  const [rejectReason, setRejectReason] = useState('vehicle_breakdown');
  const [rejectDetails, setRejectDetails] = useState('');
  const [rejectError, setRejectError] = useState('');

  const handleOpenReject = (mission) => {
    setSelectedMissionForReject(mission);
    setRejectReason('vehicle_breakdown');
    setRejectDetails('');
    setRejectError('');
  };

  const handleConfirmReject = async () => {
    if (!rejectReason) {
      setRejectError('Please select a valid rejection reason');
      return;
    }
    if (rejectReason === 'other' && !rejectDetails.trim()) {
      setRejectError('Please provide details for the rejection');
      return;
    }

    try {
      await onRejectMission(selectedMissionForReject.id || selectedMissionForReject.assignment_id, {
        rejection_reason: rejectReason,
        details: rejectDetails.trim()
      });
      setSelectedMissionForReject(null);
    } catch (err) {
      setRejectError(err.message || 'Failed to reject mission');
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Mission Inbox</h1>
            {pendingMissions.length > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800">
                {pendingMissions.length} Pending
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Dispatch assignments require prompt acknowledgment to ensure rapid patient response.
          </p>
        </div>
      </div>

      {/* Pending Missions List */}
      {pendingMissions.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-sm">
          <div className="w-16 h-16 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto mb-4">
            <InboxIcon className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">Inbox is Clear</h3>
          <p className="text-sm text-gray-500 max-w-sm mx-auto mt-2">
            No incoming emergency mission assignments. Stay on standby with telemetry enabled.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingMissions.map((mission) => {
            const incident = mission.incident || {};
            const missionId = mission.id || mission.assignment_id;

            return (
              <div 
                key={missionId}
                className="bg-white rounded-xl border-2 border-red-500 p-6 shadow-md transition-shadow hover:shadow-lg space-y-4"
              >
                {/* Mission header */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-gray-100">
                  <div className="flex items-center space-x-3 flex-wrap gap-y-2">
                    <span className="px-3 py-1 rounded bg-red-600 text-white font-bold text-sm tracking-wider uppercase">
                      ASSIGNED MISSION
                    </span>
                    <span className="font-mono text-sm font-semibold text-gray-700">
                      #{incident.code || missionId?.slice(0, 8)}
                    </span>
                    <Badge variant={incident.priority === 'P1' || incident.priority === 'CRITICAL' ? 'danger' : 'warning'}>
                      {incident.priority || 'CRITICAL P1'}
                    </Badge>
                  </div>

                  <div className="flex items-center space-x-2 text-xs text-gray-500">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span>Assigned {new Date(mission.assigned_at || mission.created_at || Date.now()).toLocaleTimeString()}</span>
                  </div>
                </div>

                {/* Main Incident Details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">
                      {incident.category || mission.incident_category || 'Medical Emergency'}
                    </h3>
                    <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                      {incident.description || incident.chief_complaint || 'Caller reports urgent medical distress.'}
                    </p>

                    <div className="mt-3 flex items-start space-x-2 text-sm text-gray-700">
                      <MapPin className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="font-semibold">Scene Address: </span>
                        <span>{incident.location_address || incident.address || 'GPS Coordinates Dispatched'}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3 space-y-2 text-sm border border-gray-100">
                    {incident.caller_name && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Caller:</span>
                        <span className="font-medium text-gray-900">{incident.caller_name}</span>
                      </div>
                    )}
                    {incident.caller_phone && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Contact:</span>
                        <a href={`tel:${incident.caller_phone}`} className="font-mono font-medium text-red-600 hover:underline">
                          {incident.caller_phone}
                        </a>
                      </div>
                    )}
                    {incident.dispatch_notes && (
                      <div className="pt-1 border-t border-gray-200">
                        <span className="text-gray-500 text-xs font-semibold block">Dispatch Instructions:</span>
                        <span className="text-xs text-gray-700">{incident.dispatch_notes}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Primary Response CTAs */}
                <div className="pt-3 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-end gap-3">
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => handleOpenReject(mission)}
                    disabled={isProcessing}
                    className="w-full sm:w-auto min-h-[44px] text-gray-700 hover:text-red-700 hover:bg-red-50 border-gray-300"
                  >
                    <X className="w-4 h-4 mr-2" />
                    <span>Reject Assignment</span>
                  </Button>

                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => onAcceptMission(missionId)}
                    disabled={isProcessing}
                    className="w-full sm:w-auto min-h-[48px] bg-red-600 hover:bg-red-700 text-white font-bold px-8 shadow-sm"
                  >
                    <Check className="w-5 h-5 mr-2" />
                    <span>ACCEPT MISSION & DEPLOY</span>
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Reject Assignment Modal */}
      {selectedMissionForReject && (
        <Modal
          isOpen={Boolean(selectedMissionForReject)}
          onClose={() => setSelectedMissionForReject(null)}
          title="Reject Emergency Assignment"
        >
          <div className="space-y-4 pt-2">
            <div className="p-3 bg-amber-50 rounded-lg text-amber-800 text-sm flex items-start space-x-2">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" />
              <div>
                Rejection immediately returns this mission to the dispatch pool for re-allocation. A valid operational reason is required for dispatch logging.
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">
                Reason for Rejection <span className="text-red-500">*</span>
              </label>
              <select
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2.5 text-sm bg-white focus:ring-2 focus:ring-red-500 focus:outline-none"
              >
                {REJECTION_REASONS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">
                Operational Notes / Explanation
              </label>
              <textarea
                rows={3}
                value={rejectDetails}
                onChange={(e) => setRejectDetails(e.target.value)}
                placeholder="Provide additional context for dispatch command..."
                className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            {rejectError && (
              <div className="text-xs text-red-600 font-semibold">
                {rejectError}
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200">
              <Button
                variant="outline"
                size="md"
                onClick={() => setSelectedMissionForReject(null)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleConfirmReject}
                className="bg-red-600 hover:bg-red-700 text-white font-bold"
              >
                Confirm Rejection
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
