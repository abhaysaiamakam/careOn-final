/**
 * CareOn Citizen — Local Emergency Draft Manager
 *
 * CRITICAL SAFETY RULES:
 * 1. A local draft is NEVER an emergency submission.
 * 2. Never claim that emergency services received a request until server acknowledges.
 * 3. Never auto-submit stale drafts without user confirmation.
 */

const STORAGE_KEY = 'careon_citizen_offline_drafts';
const MAX_DRAFT_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

export function getLocalDrafts() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    const now = Date.now();
    return list.map((draft) => {
      const ageMs = now - new Date(draft.updatedAt || draft.createdAt).getTime();
      return {
        ...draft,
        isStale: ageMs > MAX_DRAFT_AGE_MS,
      };
    });
  } catch (e) {
    console.error('Failed to read local drafts:', e);
    return [];
  }
}

export function saveLocalDraft(draftData) {
  try {
    const list = getLocalDrafts();
    const id = draftData.id || `draft_${Date.now()}`;
    const now = new Date().toISOString();

    const existingIdx = list.findIndex((d) => d.id === id);
    const updatedDraft = {
      ...draftData,
      id,
      updatedAt: draftData.updatedAt || now,
      createdAt: draftData.createdAt || now,
      status: 'LOCAL_DRAFT_ONLY',
    };

    let nextList;
    if (existingIdx >= 0) {
      nextList = [...list];
      nextList[existingIdx] = updatedDraft;
    } else {
      nextList = [updatedDraft, ...list];
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextList));
    return updatedDraft;
  } catch (e) {
    console.error('Failed to save local draft:', e);
    throw new Error('Could not save emergency draft locally.');
  }
}

export function deleteLocalDraft(id) {
  try {
    const list = getLocalDrafts();
    const filtered = list.filter((d) => d.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
  } catch (e) {
    console.error('Failed to delete draft:', e);
  }
}

export function getDraftById(id) {
  const list = getLocalDrafts();
  return list.find((d) => d.id === id) || null;
}
