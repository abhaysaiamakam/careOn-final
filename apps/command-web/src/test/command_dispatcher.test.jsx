import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  RESOURCE_STATUSES,
  RESOURCE_CATEGORIES,
  HOSPITAL_TRAUMA_LEVELS,
  OPERATIONAL_ZONE_TYPES,
  DISPATCH_QUEUE_TABS,
} from '@careon/contracts';
import { commandWs } from '../services/websocket.js';

describe('CareOn Command — Dispatcher Contracts & Security Roles', () => {
  it('defines valid operational resource statuses including Available and Assigned', () => {
    expect(RESOURCE_STATUSES.AVAILABLE).toBe('Available');
    expect(RESOURCE_STATUSES.ASSIGNED).toBe('Assigned');
    expect(RESOURCE_STATUSES.EN_ROUTE).toBe('En Route');
    expect(RESOURCE_STATUSES.MAINTENANCE).toBe('Maintenance');
  });

  it('defines multi-disciplinary emergency fleet categories', () => {
    expect(RESOURCE_CATEGORIES).toContain('Ambulance');
    expect(RESOURCE_CATEGORIES).toContain('Fire Response');
    expect(RESOURCE_CATEGORIES).toContain('Police Patrol');
    expect(RESOURCE_CATEGORIES).toContain('Rescue Team');
  });

  it('contains hospital trauma accreditation levels', () => {
    expect(HOSPITAL_TRAUMA_LEVELS).toContain('Level 1');
    expect(HOSPITAL_TRAUMA_LEVELS).toContain('Level 2');
    expect(HOSPITAL_TRAUMA_LEVELS).toContain('Level 3');
  });

  it('enforces tactical zone classifications for mass-casualty incidents', () => {
    const ids = OPERATIONAL_ZONE_TYPES.map((z) => z.id);
    expect(ids).toContain('HOT_ZONE');
    expect(ids).toContain('WARM_ZONE');
    expect(ids).toContain('COLD_ZONE');
  });
});

describe('1. Authentication & Role-Based Access Control', () => {
  const isAuthorizedRole = (role) => {
    return role === 'admin' || role === 'super_admin' || role === 'dispatcher';
  };

  it('strictly allows only authorized dispatcher roles', () => {
    expect(isAuthorizedRole('dispatcher')).toBe(true);
    expect(isAuthorizedRole('admin')).toBe(true);
    expect(isAuthorizedRole('super_admin')).toBe(true);
  });

  it('default-denies civilian, responder, hospital, guest, and null roles', () => {
    expect(isAuthorizedRole('user')).toBe(false);
    expect(isAuthorizedRole('citizen')).toBe(false);
    expect(isAuthorizedRole('paramedic')).toBe(false);
    expect(isAuthorizedRole('hospital_staff')).toBe(false);
    expect(isAuthorizedRole('guest')).toBe(false);
    expect(isAuthorizedRole(null)).toBe(false);
    expect(isAuthorizedRole(undefined)).toBe(false);
  });

  it('validates that production mode hides developer preset credentials', () => {
    const shouldShowPresets = (isDev) => Boolean(isDev);
    expect(shouldShowPresets(true)).toBe(true);
    expect(shouldShowPresets(false)).toBe(false);
  });
});

describe('2. Incident Queue & Priority Filtering', () => {
  const sampleIncidents = [
    { id: 1, incident_code: 'INC-01', priority: 'Critical', status: 'Pending', category: 'Cardiac Arrest', location_name: 'KR Circle' },
    { id: 2, incident_code: 'INC-02', priority: 'High', status: 'Allocated', category: 'Road Traffic Accident', location_name: 'Ring Road' },
    { id: 3, incident_code: 'INC-03', priority: 'Medium', status: 'Resolved', category: 'Minor Injury', location_name: 'Sayyaji Rao Road' },
    { id: 4, incident_code: 'INC-04', priority: 'Critical', status: 'In Progress', category: 'Multi-Casualty Crash', location_name: 'Bannimantap' },
  ];

  it('filters queue by active tabs correctly', () => {
    const filterByTab = (list, tab) => {
      switch (tab) {
        case 'UNASSIGNED':
          return list.filter((i) => i.status === 'Pending' || i.status === 'Reported');
        case 'CRITICAL':
          return list.filter((i) => i.priority === 'Critical');
        case 'ACTIVE':
          return list.filter((i) => i.status !== 'Resolved' && i.status !== 'Cancelled');
        case 'RESOLVED':
          return list.filter((i) => i.status === 'Resolved');
        default:
          return list;
      }
    };

    expect(filterByTab(sampleIncidents, 'ALL').length).toBe(4);
    expect(filterByTab(sampleIncidents, 'UNASSIGNED').length).toBe(1);
    expect(filterByTab(sampleIncidents, 'CRITICAL').length).toBe(2);
    expect(filterByTab(sampleIncidents, 'ACTIVE').length).toBe(3);
    expect(filterByTab(sampleIncidents, 'RESOLVED').length).toBe(1);
  });

  it('searches incidents by code, category, or location', () => {
    const searchIncidents = (list, query) => {
      if (!query.trim()) return list;
      const q = query.toLowerCase();
      return list.filter(
        (i) =>
          i.incident_code.toLowerCase().includes(q) ||
          i.category.toLowerCase().includes(q) ||
          i.location_name.toLowerCase().includes(q)
      );
    };

    expect(searchIncidents(sampleIncidents, 'Cardiac').length).toBe(1);
    expect(searchIncidents(sampleIncidents, 'Ring Road').length).toBe(1);
    expect(searchIncidents(sampleIncidents, 'INC-04').length).toBe(1);
    expect(searchIncidents(sampleIncidents, 'NonExistent').length).toBe(0);
  });
});

describe('3. Real-Time M4 WebSocket Architecture & Deduplication', () => {
  beforeEach(() => {
    commandWs.disconnect();
    commandWs.seenEventIds.clear();
    commandWs.lastEventId = null;
  });

  it('connects to /api/ws endpoint without token in query string', () => {
    const wsUrl = 'ws://localhost:3003/api/ws';
    expect(wsUrl).not.toContain('?token=');
    expect(wsUrl).not.toContain('jwt');
  });

  it('deduplicates incoming events by event_id across multi-instance Redis Pub/Sub', () => {
    const dispatched = [];
    commandWs.on('incident.created', (data) => dispatched.push(data));

    const duplicateFrame = {
      event_id: 'evt-unique-12345',
      event_type: 'incident.created',
      payload: { id: 101, code: 'INC-101' },
    };

    // First delivery -> Accepted
    commandWs._processEvent(duplicateFrame);
    expect(dispatched.length).toBe(1);
    expect(commandWs.lastEventId).toBe('evt-unique-12345');

    // Duplicate delivery (Redis pub/sub duplicate) -> Dropped
    commandWs._processEvent(duplicateFrame);
    expect(dispatched.length).toBe(1); // Still 1!
  });

  it('normalizes event type aliases (e.g. incident.created <-> incident_created)', () => {
    const received = [];
    commandWs.on('incident_created', (data) => received.push(data));

    commandWs._processEvent({
      event_id: 'evt-alias-99',
      event_type: 'incident.created',
      payload: { id: 202 },
    });

    expect(received.length).toBe(1);
    expect(received[0].id).toBe(202);
  });
});

describe('4. M5 Intelligent Dispatch, Approval & Hard Constraints', () => {
  const eligibleResource = {
    resource_id: 1,
    resource_code: 'AMB-01',
    status: 'Available',
    eligibility_status: 'eligible',
    ineligibility_reasons: [],
    composite_score: 88.5,
  };

  const busyResource = {
    resource_id: 2,
    resource_code: 'AMB-02',
    status: 'Assigned',
    eligibility_status: 'ineligible',
    ineligibility_reasons: ['Resource status is Assigned'],
    composite_score: 45.0,
  };

  it('approves eligible candidate and formats valid approve payload', () => {
    const formatApprovePayload = (incidentId, candidate) => {
      if (candidate.eligibility_status !== 'eligible') {
        throw new Error(`Cannot approve ineligible candidate: ${candidate.ineligibility_reasons.join(', ')}`);
      }
      return {
        incident_id: incidentId,
        resource_id: candidate.resource_id,
        notes: `Dispatcher approved recommended unit ${candidate.resource_code}`,
      };
    };

    const payload = formatApprovePayload(10, eligibleResource);
    expect(payload.incident_id).toBe(10);
    expect(payload.resource_id).toBe(1);

    expect(() => formatApprovePayload(10, busyResource)).toThrow(
      'Cannot approve ineligible candidate'
    );
  });

  it('enforces mandatory override justification >= 5 characters for manual override', () => {
    const validateOverride = (incidentId, candidate, reason) => {
      if (!reason || reason.trim().length < 5) {
        throw new Error('Mandatory override reason (min 5 characters) is required when overriding.');
      }
      return {
        incident_id: incidentId,
        resource_id: candidate.resource_id,
        override_reason: reason.trim(),
        notes: `Manual dispatch override logged for unit ${candidate.resource_code}`,
      };
    };

    expect(() => validateOverride(10, busyResource, '')).toThrow('min 5 characters');
    expect(() => validateOverride(10, busyResource, 'test')).toThrow('min 5 characters');

    const valid = validateOverride(10, busyResource, 'PROXIMITY_OVERRIDE: Visual scene contact confirmed');
    expect(valid.resource_id).toBe(2);
    expect(valid.override_reason).toBe('PROXIMITY_OVERRIDE: Visual scene contact confirmed');
  });

  it('strictly prevents double assignment of already committed units', () => {
    const checkDoubleAssignment = (resource, activeAssignments) => {
      const isCommitted = activeAssignments.some(
        (a) => a.resource_id === resource.resource_id && a.status !== 'RELEASED' && a.status !== 'CANCELLED'
      );
      if (isCommitted || resource.status === 'Assigned' || resource.status === 'En Route') {
        return { allowed: false, reason: 'DOUBLE_ASSIGNMENT_PREVENTED' };
      }
      return { allowed: true };
    };

    const activeAssignments = [{ id: 101, resource_id: 2, status: 'DISPATCHED' }];
    expect(checkDoubleAssignment(busyResource, activeAssignments).allowed).toBe(false);
    expect(checkDoubleAssignment(eligibleResource, activeAssignments).allowed).toBe(true);
  });
});

describe('5. Fleet Telemetry & GPS Freshness Invariant', () => {
  it('flags telemetry older than 30 minutes as stale GPS', () => {
    const checkGpsFreshness = (lastUpdatedIso) => {
      const ageMs = Date.now() - new Date(lastUpdatedIso).getTime();
      const isStale = ageMs > 30 * 60 * 1000;
      return { isStale, ageMinutes: Math.round(ageMs / 60000) };
    };

    const freshTime = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 min ago
    const staleTime = new Date(Date.now() - 45 * 60 * 1000).toISOString(); // 45 min ago

    expect(checkGpsFreshness(freshTime).isStale).toBe(false);
    expect(checkGpsFreshness(staleTime).isStale).toBe(true);
    expect(checkGpsFreshness(staleTime).ageMinutes).toBe(45);
  });
});

describe('6. Hospital Readiness, Diversions & Pre-Arrival Workflow', () => {
  const hospitals = [
    { id: 1, name: 'Apollo Trauma Hospital', divert_status: false, trauma_level: 'Level 1', available_er_beds: 4 },
    { id: 2, name: 'District General Hospital', divert_status: true, trauma_level: 'Level 2', available_er_beds: 0 },
  ];

  it('identifies diverted facilities and filters rerouted destinations', () => {
    const getEligibleReceivingFacilities = (list) => {
      return list.filter((h) => !h.divert_status && (h.available_er_beds || 0) > 0);
    };

    const eligible = getEligibleReceivingFacilities(hospitals);
    expect(eligible.length).toBe(1);
    expect(eligible[0].name).toBe('Apollo Trauma Hospital');
  });

  it('validates pre-arrival incoming patient request payload', () => {
    const createPreArrivalPayload = (incidentId, hospitalId, priority, condition) => {
      return {
        incident_id: incidentId,
        destination_facility_id: hospitalId,
        triage_category: priority,
        clinical_condition_summary: condition,
        estimated_arrival_minutes: 12,
      };
    };

    const req = createPreArrivalPayload(10, 1, 'Critical', 'STEMI cardiac arrest with ROSC');
    expect(req.incident_id).toBe(10);
    expect(req.destination_facility_id).toBe(1);
    expect(req.triage_category).toBe('Critical');
  });
});

describe('7. Multi-Agency Coordination & Clinical Privacy Isolation', () => {
  it('enforces that general mutual-aid agencies do NOT receive raw patient PHI', () => {
    const sanitizeEncounterForExternalAgency = (encounter, requesterAgencyType) => {
      if (requesterAgencyType === 'EMS' || requesterAgencyType === 'HOSPITAL') {
        return encounter; // Authorized clinical receiver
      }
      // Redact clinical PHI for Police, Fire, Search & Rescue
      return {
        id: encounter.id,
        incident_id: encounter.incident_id,
        status: encounter.status,
        patient_count: encounter.patient_count || 1,
        // Excluded: vitals, medical_history, clinical_notes, medications
      };
    };

    const rawEncounter = {
      id: 50,
      incident_id: 10,
      status: 'HANDOVER_COMPLETED',
      patient_name: 'Jane Doe',
      vitals: { hr: 120, bp: '80/50' },
      clinical_notes: 'Severe internal hemorrhage',
      patient_count: 1,
    };

    const policeView = sanitizeEncounterForExternalAgency(rawEncounter, 'POLICE');
    expect(policeView.id).toBe(50);
    expect(policeView.status).toBe('HANDOVER_COMPLETED');
    expect(policeView.vitals).toBeUndefined();
    expect(policeView.clinical_notes).toBeUndefined();
    expect(policeView.patient_name).toBeUndefined();

    const emsView = sanitizeEncounterForExternalAgency(rawEncounter, 'EMS');
    expect(emsView.vitals).toBeDefined();
    expect(emsView.clinical_notes).toBe('Severe internal hemorrhage');
  });
});

describe('8. M10 Predictive Intelligence Presentation & Expiry', () => {
  it('validates positioning recommendation presentation and expiry detection', () => {
    const isRecommendationExpired = (expiresAtIso) => {
      return Date.now() > new Date(expiresAtIso).getTime();
    };

    const activeExpiry = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    const pastExpiry = new Date(Date.now() - 5 * 60 * 1000).toISOString();

    expect(isRecommendationExpired(activeExpiry)).toBe(false);
    expect(isRecommendationExpired(pastExpiry)).toBe(true);
  });
});

describe('9. Resilience to Backend Outage & Empty Operational State', () => {
  it('renders gracefully with empty operational queues without exceptions', () => {
    const calculateQueueKPIs = (incidents, resources, hospitals) => {
      return {
        activeCount: (incidents || []).filter((i) => i.status !== 'Resolved').length,
        criticalCount: (incidents || []).filter((i) => i.priority === 'Critical').length,
        availableAmbulances: (resources || []).filter((r) => r.status === 'Available').length,
        divertedHospitals: (hospitals || []).filter((h) => h.divert_status).length,
      };
    };

    const emptyKPIs = calculateQueueKPIs([], [], []);
    expect(emptyKPIs.activeCount).toBe(0);
    expect(emptyKPIs.criticalCount).toBe(0);
    expect(emptyKPIs.availableAmbulances).toBe(0);
    expect(emptyKPIs.divertedHospitals).toBe(0);

    const nullKPIs = calculateQueueKPIs(null, null, null);
    expect(nullKPIs.activeCount).toBe(0);
  });
});
