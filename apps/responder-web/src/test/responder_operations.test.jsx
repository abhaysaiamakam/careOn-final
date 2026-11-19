import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { MissionInbox } from '../features/inbox/MissionInbox.jsx';
import { ActiveMissionWorkspace } from '../features/workspace/ActiveMissionWorkspace.jsx';
import { ClinicalAssessmentModal } from '../features/clinical/ClinicalAssessmentModal.jsx';
import { DigitalHandoverView } from '../features/handover/DigitalHandoverView.jsx';
import { offlineJournal } from '../services/offlineJournal.js';

describe('Responder Operations & Field Contracts Suite', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('1. Mission Inbox & Assignment Workflow', () => {
    const mockPendingMission = {
      id: 'mission-test-101',
      assignment_id: 'mission-test-101',
      status: 'assigned',
      incident: {
        code: 'INC-991',
        category: 'Cardiac Arrest',
        priority: 'CRITICAL',
        description: 'Patient collapsed, CPR in progress by bystander',
        location_address: '100 MG Road, Bengaluru',
        latitude: 12.9716,
        longitude: 77.5946,
        caller_name: 'John Doe',
        caller_phone: '+919876543210',
        dispatch_notes: 'Access via Gate 2, 3rd floor',
      },
    };

    it('renders empty inbox state when there are no assignments', () => {
      render(
        <MissionInbox
          pendingMissions={[]}
          onAcceptMission={vi.fn()}
          onRejectMission={vi.fn()}
        />
      );
      expect(screen.getByText('Inbox is Clear')).toBeInTheDocument();
      expect(screen.getByText(/No incoming emergency mission assignments/i)).toBeInTheDocument();
    });

    it('renders assigned mission with priority badge and caller contact', () => {
      render(
        <MissionInbox
          pendingMissions={[mockPendingMission]}
          onAcceptMission={vi.fn()}
          onRejectMission={vi.fn()}
        />
      );
      expect(screen.getByText('ASSIGNED MISSION')).toBeInTheDocument();
      expect(screen.getByText('Cardiac Arrest')).toBeInTheDocument();
      expect(screen.getByText('100 MG Road, Bengaluru')).toBeInTheDocument();
      expect(screen.getByText('+919876543210')).toBeInTheDocument();
      expect(screen.getByText('Access via Gate 2, 3rd floor')).toBeInTheDocument();
    });

    it('triggers onAcceptMission when Accept CTA is clicked', () => {
      const handleAccept = vi.fn();
      render(
        <MissionInbox
          pendingMissions={[mockPendingMission]}
          onAcceptMission={handleAccept}
          onRejectMission={vi.fn()}
        />
      );
      const acceptBtn = screen.getByText('ACCEPT MISSION & DEPLOY');
      fireEvent.click(acceptBtn);
      expect(handleAccept).toHaveBeenCalledWith('mission-test-101');
    });

    it('opens reject modal and submits rejection with selected reason', async () => {
      const handleReject = vi.fn().mockResolvedValue({});
      render(
        <MissionInbox
          pendingMissions={[mockPendingMission]}
          onAcceptMission={vi.fn()}
          onRejectMission={handleReject}
        />
      );

      const rejectBtn = screen.getByText('Reject Assignment');
      fireEvent.click(rejectBtn);

      expect(screen.getByText('Reject Emergency Assignment')).toBeInTheDocument();
      expect(screen.getByText(/Rejection immediately returns this mission to the dispatch pool/i)).toBeInTheDocument();

      const confirmBtn = screen.getByText('Confirm Rejection');
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(handleReject).toHaveBeenCalledWith('mission-test-101', {
          rejection_reason: 'vehicle_breakdown',
          details: '',
        });
      });
    });
  });

  describe('2. M6 State Transitions in ActiveMissionWorkspace', () => {
    const baseMission = {
      id: 'mission-active-202',
      status: 'accepted',
      incident: {
        code: 'INC-202',
        category: 'Severe Trauma',
        priority: 'P1',
        location_address: 'Indiranagar 100ft Road',
        latitude: 12.978,
        longitude: 77.64,
        description: 'Motor vehicle accident with severe hemorrhage',
      },
    };

    it('renders "DEPART: EN ROUTE TO SCENE" for status=accepted', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'accepted' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('DEPART: EN ROUTE TO SCENE');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'en_route_incident');
    });

    it('renders "MARK ARRIVED AT SCENE" for status=en_route_incident', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'en_route_incident' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('MARK ARRIVED AT SCENE');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'arrived_scene');
    });

    it('renders "MARK PATIENT CONTACT" for status=arrived_scene', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'arrived_scene' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('MARK PATIENT CONTACT');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'patient_contact');
    });

    it('renders "PATIENT LOADED / PICKED UP" for status=patient_contact', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'patient_contact' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('PATIENT LOADED / PICKED UP');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'patient_picked_up');
    });

    it('renders "DEPART: EN ROUTE TO HOSPITAL" for status=patient_picked_up', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'patient_picked_up' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('DEPART: EN ROUTE TO HOSPITAL');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'en_route_hospital');
    });

    it('renders "MARK ARRIVED AT HOSPITAL" for status=en_route_hospital', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'en_route_hospital' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('MARK ARRIVED AT HOSPITAL');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'arrived_hospital');
    });

    it('renders "INITIATE CLINICAL HANDOVER" for status=arrived_hospital', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'arrived_hospital' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('INITIATE CLINICAL HANDOVER');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'handover_initiated');
    });

    it('renders "FINALIZE & COMPLETE MISSION" for status=handover_completed', () => {
      const handleTransition = vi.fn();
      render(
        <ActiveMissionWorkspace
          mission={{ ...baseMission, status: 'handover_completed' }}
          onTransitionStatus={handleTransition}
        />
      );
      const btn = screen.getByText('FINALIZE & COMPLETE MISSION');
      expect(btn).toBeInTheDocument();

      fireEvent.click(btn);
      expect(handleTransition).toHaveBeenCalledWith('mission-active-202', 'completed');
    });
  });

  describe('3. Clinical Assessment & Vitals Recording', () => {
    it('submits vitals payload with converted numbers', async () => {
      const handleSaveVitals = vi.fn().mockResolvedValue({});
      render(
        <ClinicalAssessmentModal
          isOpen={true}
          onClose={vi.fn()}
          onSaveVitals={handleSaveVitals}
        />
      );

      const hrInput = screen.getByPlaceholderText('e.g. 78');
      const spo2Input = screen.getByPlaceholderText('e.g. 98');
      const sysInput = screen.getByPlaceholderText('Sys (120)');
      const diaInput = screen.getByPlaceholderText('Dia (80)');
      const gcsInput = screen.getByPlaceholderText('e.g. 15');

      fireEvent.change(hrInput, { target: { value: '88' } });
      fireEvent.change(spo2Input, { target: { value: '99' } });
      fireEvent.change(sysInput, { target: { value: '125' } });
      fireEvent.change(diaInput, { target: { value: '82' } });
      fireEvent.change(gcsInput, { target: { value: '15' } });

      const saveBtn = screen.getByText('Save Vital Signs');
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(handleSaveVitals).toHaveBeenCalledWith({
          heart_rate: 88,
          spo2: 99,
          systolic_bp: 125,
          diastolic_bp: 82,
          gcs_score: 15,
        });
      });
    });

    it('submits ABCDE assessment successfully', async () => {
      const handleSaveAbcde = vi.fn().mockResolvedValue({});
      render(
        <ClinicalAssessmentModal
          isOpen={true}
          onClose={vi.fn()}
          onSaveAssessment={handleSaveAbcde}
        />
      );

      // Switch to ABCDE tab
      const abcdeTab = screen.getByRole('button', { name: 'ABCDE' });
      fireEvent.click(abcdeTab);

      const saveBtn = screen.getByText('Save ABCDE Assessment');
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(handleSaveAbcde).toHaveBeenCalledWith(
          expect.objectContaining({
            airway_status: 'Patent',
            breathing_status: 'Normal',
            circulation_status: 'Normal pulses, CRT < 2s',
            disability_status: 'Alert (AVPU)',
          })
        );
      });
    });
  });

  describe('4. Digital Handover (M8 SBAR)', () => {
    const mockHospitals = [
      { id: 'hosp-1', name: 'Manipal Hospital HAL', emergency_tier: 'Level 1 Trauma' },
      { id: 'hosp-2', name: 'Apollo Hospital Bannerghatta', emergency_tier: 'Level 2 Trauma' },
    ];

    it('submits structured SBAR handover record', async () => {
      const handleSubmitHandover = vi.fn().mockResolvedValue({
        id: 'handover-rec-1',
        token: 'HND-TOKEN-99',
        status: 'submitted',
      });

      render(
        <DigitalHandoverView
          isOpen={true}
          onClose={vi.fn()}
          mission={{ id: 'm-1', incident: { category: 'Polytrauma', description: 'Fall from height' } }}
          hospitals={mockHospitals}
          onSubmitHandover={handleSubmitHandover}
        />
      );

      const submitBtn = screen.getByText('Submit Digital SBAR Handover');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(handleSubmitHandover).toHaveBeenCalledWith(
          expect.objectContaining({
            hospital_id: 'hosp-1',
            situation: expect.stringContaining('Polytrauma'),
            recommendation: expect.stringContaining('resuscitation bay'),
          })
        );
      });
    });
  });

  describe('5. M9 Offline Action Journaling', () => {
    it('records actions with monotonic sequence numbers and idempotency keys', async () => {
      const act1 = await offlineJournal.recordAction('acknowledge_mission', { action: 'accept' }, { mission_id: 'm-100' });
      const act2 = await offlineJournal.recordAction('transition_mission', { target_status: 'en_route_incident' }, { mission_id: 'm-100' });

      expect(act1.device_sequence_number).toBe(1);
      expect(act2.device_sequence_number).toBe(2);
      expect(act1.action_uuid).toBeDefined();
      expect(act2.action_uuid).toBeDefined();

      const pending = await offlineJournal.getPendingActions();
      expect(pending.length).toBe(2);

      await offlineJournal.markActionsSynced([act1.action_uuid, act2.action_uuid]);
      const remaining = await offlineJournal.getPendingActions();
      expect(remaining.length).toBe(0);
    });
  });
});
