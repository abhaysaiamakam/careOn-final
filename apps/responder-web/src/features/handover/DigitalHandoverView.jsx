import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Send, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  FileText, 
  ShieldCheck, 
  Bed, 
  UserCheck 
} from 'lucide-react';
import { Button, Badge, Modal } from '@careon/design-system';

export function DigitalHandoverView({
  isOpen,
  onClose,
  mission,
  hospitals = [],
  onSubmitHandover,
  existingHandover = null,
  isSubmitting = false
}) {
  const [selectedHospitalId, setSelectedHospitalId] = useState('');
  const [situation, setSituation] = useState('');
  const [background, setBackground] = useState('');
  const [assessment, setAssessment] = useState('');
  const [recommendation, setRecommendation] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [handoverRecord, setHandoverRecord] = useState(existingHandover);

  // Initialize defaults from mission if available
  useEffect(() => {
    if (mission) {
      const incident = mission.incident || {};
      if (!situation) {
        setSituation(`Patient presenting with ${incident.category || 'medical emergency'}. ${incident.description || ''}`.trim());
      }
      if (!recommendation) {
        setRecommendation('Immediate trauma / emergency resuscitation bay evaluation requested.');
      }
      if (mission.destination_hospital_id) {
        setSelectedHospitalId(mission.destination_hospital_id);
      } else if (hospitals.length > 0 && !selectedHospitalId) {
        setSelectedHospitalId(hospitals[0].id || hospitals[0].facility_id);
      }
    }
  }, [mission, hospitals]);

  useEffect(() => {
    if (existingHandover) {
      setHandoverRecord(existingHandover);
    }
  }, [existingHandover]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    if (!selectedHospitalId) {
      setErrorMsg('Please select a receiving hospital facility');
      return;
    }
    if (!situation.trim() || !recommendation.trim()) {
      setErrorMsg('Situation and Recommendation fields are required for SBAR');
      return;
    }

    try {
      const payload = {
        hospital_id: selectedHospitalId,
        situation: situation.trim(),
        background: background.trim(),
        assessment: assessment.trim(),
        recommendation: recommendation.trim(),
        sbar_payload: {
          situation: situation.trim(),
          background: background.trim(),
          assessment: assessment.trim(),
          recommendation: recommendation.trim()
        }
      };
      const res = await onSubmitHandover(payload);
      setHandoverRecord(res);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to submit digital handover');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Digital Patient Handover (M8 SBAR)"
    >
      <div className="space-y-4 pt-1 max-h-[75vh] overflow-y-auto pr-1">
        {/* Status Banner if Handover is Submitted */}
        {handoverRecord ? (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <h4 className="font-bold text-emerald-900 text-sm">
                  Digital Handover Submitted
                </h4>
              </div>
              <Badge variant="success">
                {handoverRecord.status || 'SUBMITTED'}
              </Badge>
            </div>

            <div className="text-xs text-emerald-800 space-y-1 font-mono">
              <div>Token: {handoverRecord.handover_token || handoverRecord.token || 'HANDOVER-TX-ACTIVE'}</div>
              <div>Hospital ID: {handoverRecord.hospital_id || selectedHospitalId}</div>
              <div>Submitted At: {new Date(handoverRecord.created_at || Date.now()).toLocaleTimeString()}</div>
            </div>

            {handoverRecord.receiving_bed && (
              <div className="p-2.5 bg-white rounded-lg border border-emerald-100 flex items-center space-x-2 text-xs text-gray-800 font-medium">
                <Bed className="w-4 h-4 text-emerald-600" />
                <span>Assigned Trauma Bay / Bed: <strong>{handoverRecord.receiving_bed}</strong></span>
              </div>
            )}

            <p className="text-xs text-emerald-700">
              Receiving clinical team has received pre-arrival telemetry and clinical SBAR packet.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Hospital Selection */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Receiving Hospital Facility <span className="text-red-500">*</span>
              </label>
              <select
                value={selectedHospitalId}
                onChange={(e) => setSelectedHospitalId(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg p-2.5 text-sm bg-white focus:ring-2 focus:ring-red-500 focus:outline-none"
              >
                <option value="">Select Hospital Facility...</option>
                {hospitals.map((h) => (
                  <option key={h.id || h.facility_id} value={h.id || h.facility_id}>
                    {h.name || h.hospital_name || 'Emergency Medical Center'} {h.emergency_tier ? `(${h.emergency_tier})` : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* S - Situation */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                S — Situation (Chief Complaint & Presentation) <span className="text-red-500">*</span>
              </label>
              <textarea
                rows={2}
                value={situation}
                onChange={(e) => setSituation(e.target.value)}
                required
                placeholder="State the immediate clinical emergency and presenting condition..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            {/* B - Background */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                B — Background (Medical History, Allergies, Onset)
              </label>
              <textarea
                rows={2}
                value={background}
                onChange={(e) => setBackground(e.target.value)}
                placeholder="Cardiac history, diabetic, NKDA, medications taken..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            {/* A - Assessment */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                A — Assessment (Clinical Findings & Pre-Hospital Trend)
              </label>
              <textarea
                rows={2}
                value={assessment}
                onChange={(e) => setAssessment(e.target.value)}
                placeholder="Vitals trend, GCS, suspected clinical diagnosis..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            {/* R - Recommendation */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                R — Recommendation (Immediate Facility Requirements) <span className="text-red-500">*</span>
              </label>
              <textarea
                rows={2}
                value={recommendation}
                onChange={(e) => setRecommendation(e.target.value)}
                required
                placeholder="Trauma bay, surgical consult, CT scan, ICU resuscitation..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            {errorMsg && (
              <div className="p-2.5 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200">
              <Button
                variant="outline"
                size="md"
                onClick={onClose}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                type="submit"
                disabled={isSubmitting}
                className="bg-red-600 hover:bg-red-700 text-white font-bold flex items-center space-x-2"
              >
                <Send className="w-4 h-4" />
                <span>Submit Digital SBAR Handover</span>
              </Button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
}
