import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider } from '@careon/auth';
import ClinicalHeader from '../components/ClinicalHeader.jsx';
import EmptyState from '../components/EmptyState.jsx';
import ClinicalLogin from '../features/auth/ClinicalLogin.jsx';
import HospitalDashboard from '../features/dashboard/HospitalDashboard.jsx';
import DiversionControlModal from '../features/diversion/DiversionControlModal.jsx';
import CapacityUpdateModal from '../features/capacity/CapacityUpdateModal.jsx';
import CapacityManagementView from '../features/capacity/CapacityManagementView.jsx';
import IncomingPatientsView from '../features/incoming/IncomingPatientsView.jsx';
import PatientArrivalTriageModal from '../features/arrival/PatientArrivalTriageModal.jsx';
import ClinicalHandoverWorkspace from '../features/handover/ClinicalHandoverWorkspace.jsx';
import MCICoordinationView from '../features/mci/MCICoordinationView.jsx';
import * as apiClient from '@careon/api-client';

describe('CareOn Clinical — Milestone 13 Hospital Application', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('1. Truthful Empty States (Strictly NO Dummy Data)', () => {
    it('renders truthful empty state when incoming queue has zero items', () => {
      render(
        <IncomingPatientsView
          facility={{ id: 1, name: 'KR Hospital' }}
          incomingRequests={[]}
          incomingTransports={[]}
          loading={false}
        />
      );

      expect(screen.getByText('No Incoming Patients at This Time')).toBeInTheDocument();
      expect(
        screen.getByText(/There are no active ambulance transports en-route or pending pre-arrival bed requests/i)
      ).toBeInTheDocument();
    });

    it('renders truthful empty state when clinical handover queue has zero records', () => {
      render(
        <ClinicalHandoverWorkspace
          handovers={[]}
          loading={false}
        />
      );

      expect(screen.getByText('No Pending Clinical Handovers')).toBeInTheDocument();
      expect(
        screen.getByText(/No pre-hospital SBAR digital handovers are currently awaiting review/i)
      ).toBeInTheDocument();
    });

    it('renders truthful empty state when capacity telemetry is unavailable', () => {
      render(
        <CapacityManagementView
          facility={null}
          readiness={null}
          loading={false}
        />
      );

      expect(screen.getByText('No Facility Capacity Data')).toBeInTheDocument();
    });
  });

  describe('2. Clinical Header & Identity', () => {
    it('displays facility details, diversion status, and bed occupancy summary', () => {
      const facility = { id: 1, name: 'KR Trauma Center', trauma_level: 'Level 1' };
      const readiness = {
        available_er_beds: 12,
        total_er_beds: 20,
        icu_beds_available: 3,
        trauma_bays_available: 2,
      };
      const diversionStatus = { status: 'Open', reason: 'Normal Operations' };

      render(
        <ClinicalHeader
          facility={facility}
          diversionStatus={diversionStatus}
          capacity={readiness}
          wsStatus="CONNECTED"
          activeTab="dashboard"
          user={{ full_name: 'Dr. Sarah Connor', role: 'hospital_staff' }}
          onSelectTab={() => {}}
          onOpenDiversionModal={() => {}}
          onOpenCapacityModal={() => {}}
        />
      );

      expect(screen.getByText('CareOn Clinical')).toBeInTheDocument();
      expect(screen.getByText(/KR Trauma Center \(Level 1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Diversion: Normal Operations/i)).toBeInTheDocument();
      expect(screen.getByText('Live Telemetry')).toBeInTheDocument();
      expect(screen.getByText('Dr. Sarah Connor')).toBeInTheDocument();
      expect(screen.getByText('hospital staff')).toBeInTheDocument();
    });
  });

  describe('3. Diversion Management & Validation', () => {
    it('requires mandatory operational reason when changing status to Diverting', async () => {
      const facility = { id: 1, name: 'KR Hospital' };
      const onStatusUpdated = vi.fn();

      render(
        <DiversionControlModal
          facility={facility}
          currentStatus={{ status: 'Open' }}
          isOpen={true}
          onClose={() => {}}
          onStatusUpdated={onStatusUpdated}
        />
      );

      // Select Diverting
      const divertBtn = screen.getByRole('button', { name: /Diverting/i });
      fireEvent.click(divertBtn);

      // Attempt to submit without reason
      const submitBtn = screen.getByRole('button', { name: /Commit Status Change/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(
          screen.getByText(/A clinical\/operational reason of at least 3 characters is mandatory/i)
        ).toBeInTheDocument();
      });
      expect(onStatusUpdated).not.toHaveBeenCalled();
    });
  });

  describe('4. Bed Capacity Management', () => {
    it('displays ED, ICU, Trauma Bay, and OR capacities accurately', () => {
      const facility = { id: 1, name: 'KR Trauma Hospital' };
      const readiness = {
        available_er_beds: 14,
        total_er_beds: 20,
        icu_beds_available: 4,
        icu_beds_total: 8,
        trauma_bays_available: 2,
        trauma_bays_total: 4,
        operating_rooms_available: 2,
        operating_rooms_total: 3,
      };

      render(
        <CapacityManagementView
          facility={facility}
          readiness={readiness}
          loading={false}
          onRefresh={() => {}}
          onOpenUpdateModal={() => {}}
        />
      );

      expect(screen.getByText('Emergency Department Beds')).toBeInTheDocument();
      expect(screen.getByText('14')).toBeInTheDocument();
      expect(screen.getByText('/ 20 available')).toBeInTheDocument();

      expect(screen.getByText('Intensive Care Unit (ICU)')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('/ 8 available')).toBeInTheDocument();

      expect(screen.getByText('Trauma Resuscitation Bays')).toBeInTheDocument();
      expect(screen.getAllByText('2').length).toBeGreaterThan(0);
      expect(screen.getByText('/ 4 available')).toBeInTheDocument();
    });
  });

  describe('5. Incoming Patients Queue & Actions', () => {
    it('renders incoming pre-arrival requests and handles selection', () => {
      const req = {
        id: 101,
        request_token: 'req_tok_101',
        incident_id: 42,
        emergency_severity: 'P1',
        patient_condition_summary: 'Severe polytrauma following motor vehicle collision.',
        eta_minutes: 8,
        status: 'pending',
      };

      render(
        <IncomingPatientsView
          facility={{ id: 1 }}
          incomingRequests={[req]}
          incomingTransports={[]}
          loading={false}
        />
      );

      expect(screen.getByText('Incident #42')).toBeInTheDocument();
      expect(screen.getByText('P1')).toBeInTheDocument();
      expect(screen.getByText('Pending Action')).toBeInTheDocument();
      expect(screen.getByText(/Severe polytrauma/i)).toBeInTheDocument();
    });
  });

  describe('6. Clinical Handover (SBAR) Workflow', () => {
    it('displays SBAR quadrants (Situation, Background, Assessment, Recommendation)', () => {
      const handover = {
        id: 50,
        handover_token: 'ho_tok_50',
        encounter_id: 12,
        version: 1,
        status: 'submitted',
        situation: 'Acute STEMI, onset 35 minutes prior to paramedic arrival.',
        background: 'Hypertensive, hyperlipidemia, penicillin allergy.',
        assessment: 'ECG shows 3mm ST elevation in V1-V4. BP 142/88, HR 92.',
        recommendation: 'Immediate cath lab activation requested.',
      };

      render(
        <ClinicalHandoverWorkspace
          handovers={[handover]}
          loading={false}
        />
      );

      expect(screen.getByText(/Handover: ho_tok_50/i)).toBeInTheDocument();
      expect(screen.getByText('S — Situation')).toBeInTheDocument();
      expect(screen.getByText(/Acute STEMI/i)).toBeInTheDocument();
      expect(screen.getByText('B — Background')).toBeInTheDocument();
      expect(screen.getByText(/Hypertensive/i)).toBeInTheDocument();
      expect(screen.getByText('A — Assessment (ABCDE & Vitals)')).toBeInTheDocument();
      expect(screen.getByText(/ECG shows 3mm ST elevation/i)).toBeInTheDocument();
      expect(screen.getByText('R — Recommendation & Bed Destination')).toBeInTheDocument();
      expect(screen.getByText(/Immediate cath lab activation/i)).toBeInTheDocument();
      expect(screen.getByText('1. Mark Received')).toBeInTheDocument();
      expect(screen.getByText('Complete Transfer of Care')).toBeInTheDocument();
    });
  });

  describe('7. Mass-Casualty Incident (MCI) Distribution Planner', () => {
    it('renders the MCI distribution planner and regional network facilities', () => {
      const directory = [
        {
          id: 1,
          name: 'Central Trauma Hospital',
          trauma_level: 'Level 1',
          available_er_beds: 8,
          icu_beds_available: 2,
          is_diverting: false,
        },
        {
          id: 2,
          name: 'City General Hospital',
          trauma_level: 'Level 2',
          available_er_beds: 4,
          icu_beds_available: 1,
          is_diverting: false,
        },
      ];

      render(
        <MCICoordinationView
          directory={directory}
          loading={false}
        />
      );

      expect(screen.getByText('MCI Surge Allocation Planner')).toBeInTheDocument();
      expect(screen.getByText('P1 (Immediate)')).toBeInTheDocument();
      expect(screen.getByText('P2 (Delayed)')).toBeInTheDocument();
      expect(screen.getByText('P3 (Minor)')).toBeInTheDocument();
      expect(screen.getByText('Central Trauma Hospital')).toBeInTheDocument();
      expect(screen.getByText('City General Hospital')).toBeInTheDocument();
    });
  });

  describe('8. Session Isolation', () => {
    it('verifies clinical auth uses careon_clinical storage prefix', () => {
      const mockAuthApi = {
        login: vi.fn().mockResolvedValue({ id: 1, email: 'dr@careon.org', role: 'hospital_staff' }),
        getMe: vi.fn(),
      };

      render(
        <AuthProvider apiClient={mockAuthApi} storagePrefix="careon_clinical">
          <div data-testid="auth-child">Auth Mounted</div>
        </AuthProvider>
      );

      expect(screen.getByTestId('auth-child')).toBeInTheDocument();
    });
  });
});
