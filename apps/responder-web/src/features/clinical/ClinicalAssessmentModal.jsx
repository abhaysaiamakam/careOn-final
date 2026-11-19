import React, { useState } from 'react';
import { 
  Heart, 
  Activity, 
  Thermometer, 
  Wind, 
  Eye, 
  Pill, 
  Check, 
  AlertCircle,
  FileCheck,
  Plus
} from 'lucide-react';
import { Button, Modal } from '@careon/design-system';

const QUICK_INTERVENTIONS = [
  'High-Flow Oxygen 15L NRB',
  'IV Cannula 18G',
  'IV Normal Saline 500ml',
  'C-Spine Immobilization',
  'Pressure Bandage / Hemostatic',
  'Defibrillation (AED)',
  'CPR (Chest Compressions)',
  'Bag-Valve-Mask Ventilation',
  'Splint Applied'
];

export function ClinicalAssessmentModal({
  isOpen,
  onClose,
  encounterId,
  onSaveAssessment,
  onSaveVitals,
  onSaveIntervention,
  onSaveMedication,
  isSaving = false
}) {
  const [activeTab, setActiveTab] = useState('vitals'); // 'vitals' | 'abcde' | 'interventions' | 'meds'
  const [saveSuccess, setSaveSuccess] = useState('');
  const [saveError, setSaveError] = useState('');

  // Vitals State
  const [vitals, setVitals] = useState({
    heart_rate: '',
    systolic_bp: '',
    diastolic_bp: '',
    respiratory_rate: '',
    spo2: '',
    temperature_celsius: '',
    gcs_score: ''
  });

  // ABCDE State
  const [abcde, setAbcde] = useState({
    airway: 'Patent',
    breathing: 'Normal',
    circulation: 'Normal pulses, CRT < 2s',
    disability: 'Alert (AVPU)',
    exposure: 'No major external trauma or burns',
    clinical_notes: ''
  });

  // Intervention State
  const [selectedIntervention, setSelectedIntervention] = useState('');
  const [interventionNotes, setInterventionNotes] = useState('');
  const [interventionsList, setInterventionsList] = useState([]);

  // Medication State
  const [medForm, setMedForm] = useState({
    medication_name: '',
    dosage: '',
    route: 'IV',
    notes: ''
  });
  const [medsList, setMedsList] = useState([]);

  const handleSaveVitals = async (e) => {
    e.preventDefault();
    setSaveError('');
    setSaveSuccess('');

    const payload = {};
    if (vitals.heart_rate) payload.heart_rate = Number(vitals.heart_rate);
    if (vitals.systolic_bp) payload.systolic_bp = Number(vitals.systolic_bp);
    if (vitals.diastolic_bp) payload.diastolic_bp = Number(vitals.diastolic_bp);
    if (vitals.respiratory_rate) payload.respiratory_rate = Number(vitals.respiratory_rate);
    if (vitals.spo2) payload.spo2 = Number(vitals.spo2);
    if (vitals.temperature_celsius) payload.temperature_celsius = Number(vitals.temperature_celsius);
    if (vitals.gcs_score) payload.gcs_score = Number(vitals.gcs_score);

    try {
      await onSaveVitals(payload);
      setSaveSuccess('Vital signs recorded successfully.');
    } catch (err) {
      setSaveError(err.message || 'Failed to record vitals');
    }
  };

  const handleSaveAbcde = async (e) => {
    e.preventDefault();
    setSaveError('');
    setSaveSuccess('');

    try {
      await onSaveAssessment({
        airway_status: abcde.airway,
        breathing_status: abcde.breathing,
        circulation_status: abcde.circulation,
        disability_status: abcde.disability,
        exposure_status: abcde.exposure,
        clinical_notes: abcde.clinical_notes
      });
      setSaveSuccess('ABCDE assessment recorded successfully.');
    } catch (err) {
      setSaveError(err.message || 'Failed to record assessment');
    }
  };

  const handleAddIntervention = async () => {
    if (!selectedIntervention) return;
    setSaveError('');
    setSaveSuccess('');

    try {
      const payload = {
        intervention_type: selectedIntervention,
        details: interventionNotes,
        performed_at: new Date().toISOString()
      };
      await onSaveIntervention(payload);
      setInterventionsList((prev) => [...prev, payload]);
      setSelectedIntervention('');
      setInterventionNotes('');
      setSaveSuccess('Intervention logged.');
    } catch (err) {
      setSaveError(err.message || 'Failed to record intervention');
    }
  };

  const handleAddMedication = async (e) => {
    e.preventDefault();
    if (!medForm.medication_name) return;
    setSaveError('');
    setSaveSuccess('');

    try {
      const payload = {
        medication_name: medForm.medication_name,
        dosage: medForm.dosage,
        route: medForm.route,
        notes: medForm.notes,
        administered_at: new Date().toISOString()
      };
      await onSaveMedication(payload);
      setMedsList((prev) => [...prev, payload]);
      setMedForm({ medication_name: '', dosage: '', route: 'IV', notes: '' });
      setSaveSuccess('Medication administration logged.');
    } catch (err) {
      setSaveError(err.message || 'Failed to record medication');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Field Clinical Record & Patient Care"
    >
      <div className="space-y-4 pt-1">
        {/* Sub-tab navigation */}
        <div className="flex border-b border-gray-200">
          <button
            type="button"
            onClick={() => { setActiveTab('vitals'); setSaveSuccess(''); setSaveError(''); }}
            className={`flex-1 py-2.5 text-center text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'vitals'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Vitals
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('abcde'); setSaveSuccess(''); setSaveError(''); }}
            className={`flex-1 py-2.5 text-center text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'abcde'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            ABCDE
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('interventions'); setSaveSuccess(''); setSaveError(''); }}
            className={`flex-1 py-2.5 text-center text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'interventions'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Interventions
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('meds'); setSaveSuccess(''); setSaveError(''); }}
            className={`flex-1 py-2.5 text-center text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'meds'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Medications
          </button>
        </div>

        {/* Feedback Alerts */}
        {saveSuccess && (
          <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center space-x-2">
            <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{saveSuccess}</span>
          </div>
        )}
        {saveError && (
          <div className="p-2.5 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        {/* 1. Vital Signs Tab */}
        {activeTab === 'vitals' && (
          <form onSubmit={handleSaveVitals} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Heart Rate (BPM)
                </label>
                <div className="relative">
                  <Heart className="w-4 h-4 text-red-500 absolute left-2.5 top-2.5" />
                  <input
                    type="number"
                    value={vitals.heart_rate}
                    onChange={(e) => setVitals({ ...vitals, heart_rate: e.target.value })}
                    placeholder="e.g. 78"
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  SpO2 (%)
                </label>
                <div className="relative">
                  <Wind className="w-4 h-4 text-blue-500 absolute left-2.5 top-2.5" />
                  <input
                    type="number"
                    value={vitals.spo2}
                    onChange={(e) => setVitals({ ...vitals, spo2: e.target.value })}
                    placeholder="e.g. 98"
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Blood Pressure (mmHg)
                </label>
                <div className="flex items-center space-x-1">
                  <input
                    type="number"
                    value={vitals.systolic_bp}
                    onChange={(e) => setVitals({ ...vitals, systolic_bp: e.target.value })}
                    placeholder="Sys (120)"
                    className="w-1/2 px-2 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none text-center"
                  />
                  <span className="text-gray-400">/</span>
                  <input
                    type="number"
                    value={vitals.diastolic_bp}
                    onChange={(e) => setVitals({ ...vitals, diastolic_bp: e.target.value })}
                    placeholder="Dia (80)"
                    className="w-1/2 px-2 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none text-center"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Resp Rate (per min)
                </label>
                <input
                  type="number"
                  value={vitals.respiratory_rate}
                  onChange={(e) => setVitals({ ...vitals, respiratory_rate: e.target.value })}
                  placeholder="e.g. 16"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Temperature (°C)
                </label>
                <div className="relative">
                  <Thermometer className="w-4 h-4 text-amber-500 absolute left-2.5 top-2.5" />
                  <input
                    type="number"
                    step="0.1"
                    value={vitals.temperature_celsius}
                    onChange={(e) => setVitals({ ...vitals, temperature_celsius: e.target.value })}
                    placeholder="e.g. 36.8"
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  GCS Score (3–15)
                </label>
                <input
                  type="number"
                  min="3"
                  max="15"
                  value={vitals.gcs_score}
                  onChange={(e) => setVitals({ ...vitals, gcs_score: e.target.value })}
                  placeholder="e.g. 15"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex justify-end pt-3 border-t border-gray-200">
              <Button
                variant="primary"
                size="md"
                type="submit"
                disabled={isSaving}
                className="bg-red-600 hover:bg-red-700 text-white font-bold"
              >
                Save Vital Signs
              </Button>
            </div>
          </form>
        )}

        {/* 2. ABCDE Primary Assessment Tab */}
        {activeTab === 'abcde' && (
          <form onSubmit={handleSaveAbcde} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                A — Airway
              </label>
              <select
                value={abcde.airway}
                onChange={(e) => setAbcde({ ...abcde, airway: e.target.value })}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm bg-white"
              >
                <option value="Patent">Patent / Clear</option>
                <option value="Partially Obstructed">Partially Obstructed / Stridor</option>
                <option value="Completely Obstructed">Completely Obstructed</option>
                <option value="Intubated / Supraglottic">Advanced Airway In Place</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                B — Breathing
              </label>
              <select
                value={abcde.breathing}
                onChange={(e) => setAbcde({ ...abcde, breathing: e.target.value })}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm bg-white"
              >
                <option value="Normal">Normal Effort & Rate</option>
                <option value="Tachypneic">Tachypneic / Rapid</option>
                <option value="Bradypneic / Shallow">Bradypneic / Shallow</option>
                <option value="Wheezing / Stridor">Wheezing / Crackles</option>
                <option value="Apneic">Apneic (Requiring BVM)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                C — Circulation
              </label>
              <select
                value={abcde.circulation}
                onChange={(e) => setAbcde({ ...abcde, circulation: e.target.value })}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm bg-white"
              >
                <option value="Normal pulses, CRT < 2s">Normal pulses, CRT &lt; 2s</option>
                <option value="Weak rapid pulses, CRT > 2s">Weak rapid pulses, CRT &gt; 2s</option>
                <option value="Severe Bleeding / Hemorrhage">Active External Hemorrhage</option>
                <option value="No central pulse (Arrest)">Pulseless / Cardiac Arrest</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                D — Disability (AVPU)
              </label>
              <select
                value={abcde.disability}
                onChange={(e) => setAbcde({ ...abcde, disability: e.target.value })}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm bg-white"
              >
                <option value="Alert (AVPU)">A — Alert</option>
                <option value="Voice (AVPU)">V — Responds to Voice</option>
                <option value="Pain (AVPU)">P — Responds only to Pain</option>
                <option value="Unresponsive (AVPU)">U — Unresponsive</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                E — Exposure / Environment
              </label>
              <input
                type="text"
                value={abcde.exposure}
                onChange={(e) => setAbcde({ ...abcde, exposure: e.target.value })}
                placeholder="Trauma, burns, rash, temperature extremes"
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Clinical Impression & Notes
              </label>
              <textarea
                rows={2}
                value={abcde.clinical_notes}
                onChange={(e) => setAbcde({ ...abcde, clinical_notes: e.target.value })}
                placeholder="Overall primary assessment impression..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <div className="flex justify-end pt-3 border-t border-gray-200">
              <Button
                variant="primary"
                size="md"
                type="submit"
                disabled={isSaving}
                className="bg-red-600 hover:bg-red-700 text-white font-bold"
              >
                Save ABCDE Assessment
              </Button>
            </div>
          </form>
        )}

        {/* 3. Pre-Hospital Interventions Tab */}
        {activeTab === 'interventions' && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Quick Select Common Interventions
              </label>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_INTERVENTIONS.map((item) => (
                  <button
                    type="button"
                    key={item}
                    onClick={() => setSelectedIntervention(item)}
                    className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                      selectedIntervention === item
                        ? 'bg-red-600 text-white border-red-600'
                        : 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200'
                    }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Selected Intervention
              </label>
              <input
                type="text"
                value={selectedIntervention}
                onChange={(e) => setSelectedIntervention(e.target.value)}
                placeholder="Select above or type custom intervention..."
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Details / Site / Outcome
              </label>
              <input
                type="text"
                value={interventionNotes}
                onChange={(e) => setInterventionNotes(e.target.value)}
                placeholder="e.g. Left antecubital fossa, good flow"
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <Button
              variant="outline"
              size="md"
              type="button"
              onClick={handleAddIntervention}
              disabled={!selectedIntervention || isSaving}
              className="w-full flex items-center justify-center space-x-1"
            >
              <Plus className="w-4 h-4" />
              <span>Log Pre-Hospital Intervention</span>
            </Button>

            {/* List of interventions logged */}
            {interventionsList.length > 0 && (
              <div className="pt-2 border-t border-gray-100">
                <span className="text-xs font-bold text-gray-600 uppercase block mb-1">Logged During Encounter</span>
                <div className="space-y-1">
                  {interventionsList.map((intv, idx) => (
                    <div key={idx} className="p-2 bg-gray-50 rounded text-xs flex justify-between items-center">
                      <span className="font-medium text-gray-900">{intv.intervention_type}</span>
                      <span className="text-gray-500">{new Date(intv.performed_at).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 4. Medications Administered Tab */}
        {activeTab === 'meds' && (
          <form onSubmit={handleAddMedication} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Medication Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={medForm.medication_name}
                onChange={(e) => setMedForm({ ...medForm, medication_name: e.target.value })}
                placeholder="e.g. Aspirin, Epinephrine, Salbutamol"
                required
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Dose & Unit
                </label>
                <input
                  type="text"
                  value={medForm.dosage}
                  onChange={(e) => setMedForm({ ...medForm, dosage: e.target.value })}
                  placeholder="e.g. 300mg, 1mg"
                  className="w-full border border-gray-300 rounded-lg p-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Route
                </label>
                <select
                  value={medForm.route}
                  onChange={(e) => setMedForm({ ...medForm, route: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg p-2 text-sm bg-white"
                >
                  <option value="IV">IV (Intravenous)</option>
                  <option value="IM">IM (Intramuscular)</option>
                  <option value="Oral">Oral (PO)</option>
                  <option value="Sublingual">Sublingual (SL)</option>
                  <option value="Inhalation">Inhalation (Nebulized)</option>
                  <option value="Subcutaneous">Subcutaneous (SC)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Clinical Indication / Notes
              </label>
              <input
                type="text"
                value={medForm.notes}
                onChange={(e) => setMedForm({ ...medForm, notes: e.target.value })}
                placeholder="e.g. Suspected acute coronary syndrome"
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            <Button
              variant="outline"
              size="md"
              type="submit"
              disabled={!medForm.medication_name || isSaving}
              className="w-full flex items-center justify-center space-x-1"
            >
              <Plus className="w-4 h-4" />
              <span>Record Medication Administration</span>
            </Button>

            {/* List of meds logged */}
            {medsList.length > 0 && (
              <div className="pt-2 border-t border-gray-100">
                <span className="text-xs font-bold text-gray-600 uppercase block mb-1">Medications Administered</span>
                <div className="space-y-1">
                  {medsList.map((m, idx) => (
                    <div key={idx} className="p-2 bg-gray-50 rounded text-xs flex justify-between items-center">
                      <span className="font-medium text-gray-900">{m.medication_name} ({m.dosage}) - {m.route}</span>
                      <span className="text-gray-500">{new Date(m.administered_at).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </form>
        )}
      </div>
    </Modal>
  );
}
