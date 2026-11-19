import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  ArrowRight, 
  Check, 
  CheckCircle2, 
  Clock, 
  FileText, 
  Heart, 
  Hospital, 
  MapPin, 
  Navigation, 
  Phone, 
  Send, 
  ShieldAlert, 
  Stethoscope, 
  User, 
  Users 
} from 'lucide-react';
import { Badge, Button } from '@careon/design-system';
import { MISSION_STATUS_CONFIG } from '@careon/contracts';
import { MissionMap } from './MissionMap.jsx';
import { ClinicalAssessmentModal } from '../clinical/ClinicalAssessmentModal.jsx';
import { DigitalHandoverView } from '../handover/DigitalHandoverView.jsx';

// Authoritative next transitions per M6 Responder State Machine
const NEXT_TRANSITIONS = {
  assigned: { target: 'accepted', label: 'ACCEPT MISSION', variant: 'primary' },
  accepted: { target: 'en_route_incident', label: 'DEPART: EN ROUTE TO SCENE', variant: 'primary' },
  en_route_incident: { target: 'arrived_scene', label: 'MARK ARRIVED AT SCENE', variant: 'primary' },
  arrived_scene: { target: 'patient_contact', label: 'MARK PATIENT CONTACT', variant: 'primary' },
  patient_contact: { target: 'patient_picked_up', label: 'PATIENT LOADED / PICKED UP', variant: 'primary' },
  patient_picked_up: { target: 'en_route_hospital', label: 'DEPART: EN ROUTE TO HOSPITAL', variant: 'primary' },
  en_route_hospital: { target: 'arrived_hospital', label: 'MARK ARRIVED AT HOSPITAL', variant: 'primary' },
  arrived_hospital: { target: 'handover_initiated', label: 'INITIATE CLINICAL HANDOVER', variant: 'primary' },
  handover_initiated: { target: 'handover_completed', label: 'CONFIRM HANDOVER COMPLETED', variant: 'primary' },
  handover_completed: { target: 'completed', label: 'FINALIZE & COMPLETE MISSION', variant: 'success' }
};

export function ActiveMissionWorkspace({
  mission,
  responderLocation,
  hospitals = [],
  onTransitionStatus,
  onSaveAssessment,
  onSaveVitals,
  onSaveIntervention,
  onSaveMedication,
  onSubmitHandover,
  missionHistory = [],
  isUpdating = false
}) {
  const [isClinicalModalOpen, setIsClinicalModalOpen] = useState(false);
  const [isHandoverModalOpen, setIsHandoverModalOpen] = useState(false);
  const [transitionError, setTransitionError] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Timer for status duration
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [mission?.status]);

  if (!mission) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <div className="w-16 h-16 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto mb-4">
          <Activity className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">No Active Mission</h2>
        <p className="text-sm text-gray-500 mt-2">
          Your unit is currently on standby. Check the inbox when a new assignment arrives.
        </p>
      </div>
    );
  }

  const incident = mission.incident || {};
  const currentStatus = mission.status || 'assigned';
  const statusCfg = MISSION_STATUS_CONFIG[currentStatus] || { label: currentStatus, color: 'default' };
  const nextAction = NEXT_TRANSITIONS[currentStatus];

  // Coordinates
  const responderCoords = responderLocation?.latitude && responderLocation?.longitude
    ? { lat: responderLocation.latitude, lng: responderLocation.longitude, heading: responderLocation.heading }
    : null;

  const incidentCoords = incident.latitude && incident.longitude
    ? { lat: incident.latitude, lng: incident.longitude, address: incident.location_address }
    : null;

  const destHospital = hospitals.find((h) => (h.id || h.facility_id) === (mission.destination_hospital_id || mission.hospital_id));
  const hospitalCoords = destHospital?.latitude && destHospital?.longitude
    ? { lat: destHospital.latitude, lng: destHospital.longitude, name: destHospital.name }
    : null;

  const handleExecuteTransition = async (targetStatus) => {
    setTransitionError('');
    try {
      await onTransitionStatus(mission.id || mission.assignment_id, targetStatus);
      setElapsedSeconds(0);
    } catch (err) {
      setTransitionError(err.message || 'Failed to update mission status');
    }
  };

  const formatTimer = (totalSec) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* 1. TOP OPERATIONAL STATUS BANNER & PRIMARY TRANSITION ACTION */}
      <div className="bg-white rounded-xl border-2 border-red-500 p-6 shadow-md space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3 flex-wrap">
              <span className="text-xs uppercase px-2 py-0.5 bg-red-100 text-red-800 font-bold rounded tracking-wider">
                ACTIVE FIELD MISSION
              </span>
              <span className="font-mono text-sm font-bold text-gray-800">
                #{incident.code || mission.incident_id?.slice(0, 8)}
              </span>
              <Badge variant={statusCfg.color || 'primary'}>
                {statusCfg.label || currentStatus}
              </Badge>
            </div>

            <h1 className="text-2xl font-black text-gray-900 mt-1">
              {incident.category || mission.incident_category || 'Medical Emergency'}
            </h1>
            <p className="text-sm text-gray-500 flex items-center space-x-2 mt-1">
              <Clock className="w-4 h-4 text-gray-400" />
              <span>Time in current status: <strong className="font-mono text-gray-800">{formatTimer(elapsedSeconds)}</strong></span>
            </p>
          </div>

          {/* Large Primary Action Button */}
          {nextAction && (
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <Button
                variant={nextAction.variant === 'success' ? 'success' : 'primary'}
                size="lg"
                onClick={() => handleExecuteTransition(nextAction.target)}
                disabled={isUpdating}
                className="w-full sm:w-auto min-h-[52px] px-8 text-base font-extrabold shadow-lg bg-red-600 hover:bg-red-700 text-white tracking-wide"
              >
                <span>{nextAction.label}</span>
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          )}
        </div>

        {/* Alternate action: treated on scene without transport */}
        {['arrived_scene', 'patient_contact'].includes(currentStatus) && (
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={() => handleExecuteTransition('completed')}
              disabled={isUpdating}
              className="text-xs text-gray-500 hover:text-gray-900 underline font-medium"
            >
              Patient treated on scene (No transport required / Complete mission)
            </button>
          </div>
        )}

        {transitionError && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{transitionError}</span>
          </div>
        )}
      </div>

      {/* 2. MAP & DISPATCH DETAILS GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive Map & Live Navigation */}
        <div className="lg:col-span-2 space-y-4">
          <MissionMap
            responderPosition={responderCoords}
            incidentPosition={incidentCoords}
            hospitalPosition={hospitalCoords}
            missionStatus={currentStatus}
          />

          {/* Quick Clinical & Handover Action Bar */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex flex-wrap gap-3 items-center justify-between">
            <div className="text-sm font-bold text-gray-800 flex items-center space-x-2">
              <Stethoscope className="w-5 h-5 text-red-600" />
              <span>Field Clinical Care</span>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="md"
                onClick={() => setIsClinicalModalOpen(true)}
                className="flex items-center space-x-2 text-sm font-semibold"
              >
                <Heart className="w-4 h-4 text-red-600" />
                <span>Record Vitals & ABCDE</span>
              </Button>

              <Button
                variant="outline"
                size="md"
                onClick={() => setIsHandoverModalOpen(true)}
                className="flex items-center space-x-2 text-sm font-semibold"
              >
                <Hospital className="w-4 h-4 text-emerald-600" />
                <span>Hospital Handover (SBAR)</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Incident Brief & Access Notes */}
        <div className="space-y-4">
          {/* Incident Details Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <h3 className="font-bold text-gray-900 text-base">Scene & Incident</h3>
              <Badge variant={incident.priority === 'P1' || incident.priority === 'CRITICAL' ? 'danger' : 'warning'}>
                {incident.priority || 'CRITICAL P1'}
              </Badge>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-start space-x-2.5">
                <MapPin className="w-4 h-4 text-red-600 mt-1 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900">Scene Location</div>
                  <div className="text-gray-600">{incident.location_address || incident.address || 'GPS Coordinates Dispatched'}</div>
                  {incident.latitude && incident.longitude && (
                    <div className="text-xs font-mono text-gray-400 mt-0.5">
                      {Number(incident.latitude).toFixed(5)}, {Number(incident.longitude).toFixed(5)}
                    </div>
                  )}
                </div>
              </div>

              {incident.caller_name && (
                <div className="flex items-start space-x-2.5">
                  <User className="w-4 h-4 text-gray-400 mt-1 flex-shrink-0" />
                  <div>
                    <div className="font-semibold text-gray-900">Reporting Caller</div>
                    <div className="text-gray-600">{incident.caller_name}</div>
                  </div>
                </div>
              )}

              {incident.caller_phone && (
                <div className="flex items-start space-x-2.5">
                  <Phone className="w-4 h-4 text-gray-400 mt-1 flex-shrink-0" />
                  <div>
                    <div className="font-semibold text-gray-900">Phone Contact</div>
                    <a href={`tel:${incident.caller_phone}`} className="font-mono text-red-600 font-semibold hover:underline">
                      {incident.caller_phone}
                    </a>
                  </div>
                </div>
              )}

              {incident.description && (
                <div className="pt-2 border-t border-gray-100">
                  <div className="font-semibold text-gray-900 mb-1">Chief Complaint</div>
                  <div className="text-xs text-gray-700 bg-gray-50 p-2.5 rounded-lg border border-gray-100">
                    {incident.description}
                  </div>
                </div>
              )}

              {incident.dispatch_notes && (
                <div>
                  <div className="font-semibold text-gray-900 mb-1">Dispatcher Access Notes</div>
                  <div className="text-xs text-amber-900 bg-amber-50 p-2.5 rounded-lg border border-amber-200">
                    {incident.dispatch_notes}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Receiving Facility Card */}
          {destHospital && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3">
              <div className="flex items-center space-x-2">
                <Hospital className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-gray-900 text-sm">Destination Facility</h3>
              </div>
              <div className="text-sm font-semibold text-gray-900">{destHospital.name}</div>
              <div className="text-xs text-gray-500">{destHospital.address}</div>
              {destHospital.emergency_tier && (
                <Badge variant="success">{destHospital.emergency_tier}</Badge>
              )}
            </div>
          )}

          {/* Mission Timeline / Event Log */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3">
            <h3 className="font-bold text-gray-900 text-sm flex items-center space-x-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <span>Mission Event Timeline</span>
            </h3>

            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {missionHistory.length === 0 ? (
                <div className="text-xs text-gray-400 italic">No events logged yet</div>
              ) : (
                missionHistory.map((evt, idx) => (
                  <div key={idx} className="text-xs border-l-2 border-red-500 pl-2.5 py-0.5 space-y-0.5">
                    <div className="font-bold text-gray-800">
                      {evt.event_type || evt.target_status || evt.action_type || 'Status Update'}
                    </div>
                    <div className="text-gray-500 text-[11px]">
                      {new Date(evt.created_at || evt.timestamp || Date.now()).toLocaleTimeString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Clinical Assessment Modal */}
      <ClinicalAssessmentModal
        isOpen={isClinicalModalOpen}
        onClose={() => setIsClinicalModalOpen(false)}
        encounterId={mission.encounter_id}
        onSaveAssessment={onSaveAssessment}
        onSaveVitals={onSaveVitals}
        onSaveIntervention={onSaveIntervention}
        onSaveMedication={onSaveMedication}
      />

      {/* Handover Modal */}
      <DigitalHandoverView
        isOpen={isHandoverModalOpen}
        onClose={() => setIsHandoverModalOpen(false)}
        mission={mission}
        hospitals={hospitals}
        onSubmitHandover={onSubmitHandover}
      />
    </div>
  );
}
