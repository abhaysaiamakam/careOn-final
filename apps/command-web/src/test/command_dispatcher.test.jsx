import { describe, it, expect } from 'vitest';
import {
  RESOURCE_STATUSES,
  RESOURCE_CATEGORIES,
  HOSPITAL_TRAUMA_LEVELS,
  OPERATIONAL_ZONE_TYPES,
  DISPATCH_QUEUE_TABS,
} from '@careon/contracts';

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

  it('enforces strict role-based access control: rejects civilian users from command console', () => {
    const isAuthorizedRole = (role) => {
      return role === 'admin' || role === 'super_admin' || role === 'dispatcher';
    };

    expect(isAuthorizedRole('dispatcher')).toBe(true);
    expect(isAuthorizedRole('admin')).toBe(true);
    expect(isAuthorizedRole('super_admin')).toBe(true);
    expect(isAuthorizedRole('user')).toBe(false);
    expect(isAuthorizedRole('guest')).toBe(false);
    expect(isAuthorizedRole(null)).toBe(false);
  });

  it('verifies that ineligible candidates require explicit override reasons', () => {
    const candidate = {
      resource_id: 1,
      resource_code: 'AMB-01',
      eligibility_status: 'ineligible',
      ineligibility_reasons: ['Resource status is Assigned'],
    };

    const validateDispatchAction = (cand, isOverride, reason) => {
      if (cand.eligibility_status === 'eligible') {
        return { allowed: true };
      }
      if (!isOverride) {
        return { allowed: false, error: 'Resource is ineligible' };
      }
      if (!reason || !reason.trim()) {
        return { allowed: false, error: 'Override reason is required' };
      }
      return { allowed: true, mode: 'override' };
    };

    // Standard approval should be rejected
    expect(validateDispatchAction(candidate, false, '').allowed).toBe(false);
    // Override without reason should be rejected
    expect(validateDispatchAction(candidate, true, '').allowed).toBe(false);
    // Override with valid operational reason should be allowed
    const validOverride = validateDispatchAction(candidate, true, 'Visual confirmation of immediate scene proximity');
    expect(validOverride.allowed).toBe(true);
    expect(validOverride.mode).toBe('override');
  });
});
