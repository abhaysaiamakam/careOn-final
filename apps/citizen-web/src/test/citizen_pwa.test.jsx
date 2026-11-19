import { describe, it, expect, beforeEach } from 'vitest';
import fs from 'fs';
import path from 'path';

import {
  INCIDENT_CATEGORIES,
  INCIDENT_STATUSES,
  TRACKING_LIFECYCLE_STEPS,
  MAX_DRAFT_AGE_HOURS,
} from '@careon/contracts';

import {
  getLocalDrafts,
  saveLocalDraft,
  deleteLocalDraft,
  getDraftById,
} from '../services/offlineDrafts.js';

describe('CareOn Citizen — Contracts & Constants', () => {
  it('defines the required civilian emergency incident categories', () => {
    const ids = INCIDENT_CATEGORIES.map((c) => c.id);
    expect(ids).toContain('Medical');
    expect(ids).toContain('Road accident');
    expect(ids).toContain('Fire');
    expect(ids).toContain('Rescue');
    expect(ids).toContain('Disaster / Multiple affected people');
    expect(ids).toContain('Safety / Other');
  });

  it('defines tracking progression milestones aligned with operational statuses', () => {
    expect(TRACKING_LIFECYCLE_STEPS.length).toBeGreaterThanOrEqual(5);
    const keys = TRACKING_LIFECYCLE_STEPS.map((s) => s.key);
    expect(keys).toContain('RECEIVED');
    expect(keys).toContain('DISPATCHED');
    expect(keys).toContain('ON_SCENE');
    expect(keys).toContain('RESOLVED');
  });
});

describe('CareOn Citizen — Offline Drafts Manager (Safety Checks)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('saves an incomplete emergency report as a local draft without submitting', () => {
    const draft = saveLocalDraft({
      category: 'Medical',
      description: 'Breathing difficulty, elderly patient',
      location_name: 'Mysore Palace North Gate',
      latitude: 12.3052,
      longitude: 76.6552,
      affected_people: 1,
    });

    expect(draft.id).toBeDefined();
    expect(draft.status).toBe('LOCAL_DRAFT_ONLY');

    const retrieved = getDraftById(draft.id);
    expect(retrieved).not.toBeNull();
    expect(retrieved.description).toBe('Breathing difficulty, elderly patient');
    expect(retrieved.isStale).toBe(false);
  });

  it('marks local drafts older than 24 hours as stale to prevent auto-submission', () => {
    const oldTimestamp = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
    const draft = saveLocalDraft({
      category: 'Fire',
      description: 'Kitchen fire',
      location_name: 'Gokulam 3rd Stage',
      createdAt: oldTimestamp,
      updatedAt: oldTimestamp,
    });

    const drafts = getLocalDrafts();
    const staleDraft = drafts.find((d) => d.id === draft.id);
    expect(staleDraft).toBeDefined();
    expect(staleDraft.isStale).toBe(true);
  });

  it('safely deletes local drafts after review or server submission', () => {
    const draft = saveLocalDraft({
      category: 'Road accident',
      description: 'Minor collision',
      location_name: 'Ring Road',
    });

    expect(getLocalDrafts().length).toBe(1);
    deleteLocalDraft(draft.id);
    expect(getLocalDrafts().length).toBe(0);
  });
});

describe('CareOn Citizen — PWA Manifest & Service Worker Specification', () => {
  const publicDir = path.resolve(__dirname, '../../public');

  it('contains a valid W3C Web App Manifest matching PWA Builder standards', () => {
    const manifestPath = path.join(publicDir, 'manifest.webmanifest');
    expect(fs.existsSync(manifestPath)).toBe(true);

    const raw = fs.readFileSync(manifestPath, 'utf8');
    const manifest = JSON.parse(raw);

    // Required PWA Builder manifest properties
    expect(manifest.name).toBe('CareOn Citizen');
    expect(manifest.short_name).toBe('CareOn');
    expect(manifest.start_url).toBe('/');
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBe('#D92D3A');
    expect(manifest.background_color).toBe('#FFFFFF');
    expect(Array.isArray(manifest.icons)).toBe(true);

    // Verify 192x192, 512x512, and maskable icons
    const iconSizes = manifest.icons.map((i) => i.sizes);
    expect(iconSizes).toContain('192x192');
    expect(iconSizes).toContain('512x512');

    const hasMaskable = manifest.icons.some((i) => i.purpose === 'maskable');
    expect(hasMaskable).toBe(true);
  });

  it('has production service worker with app shell caching and sensitive API bypass', () => {
    const swPath = path.join(publicDir, 'sw.js');
    expect(fs.existsSync(swPath)).toBe(true);

    const swSource = fs.readFileSync(swPath, 'utf8');
    expect(swSource).toContain('careon-citizen-v1');
    expect(swSource).toContain('/offline.html');
    expect(swSource).toContain('/manifest.webmanifest');
    expect(swSource).toContain("pathname.startsWith('/api/')"); // Strictly bypasses API cache
    expect(swSource).toContain('addEventListener(\'push\'');
    expect(swSource).toContain('addEventListener(\'notificationclick\'');
  });

  it('contains fallback offline.html for safe offline navigation', () => {
    const offlinePath = path.join(publicDir, 'offline.html');
    expect(fs.existsSync(offlinePath)).toBe(true);

    const content = fs.readFileSync(offlinePath, 'utf8');
    expect(content).toContain('You are currently offline');
    expect(content).toContain('112');
    expect(content).toContain('108');
  });
});
