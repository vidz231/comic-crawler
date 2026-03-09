import { useSyncExternalStore, useCallback } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ReadingMode = 'strip' | 'paged';
export type ImageQuality = 'low' | 'medium' | 'high';

export interface ReaderSettings {
  /** Max image width in pixels. Range: 600–1400. Default: 900 */
  imageWidth: number;
  /** Image brightness as a percentage. Range: 50–130. Default: 100 */
  brightness: number;
  /** Fit images to viewport width. Default: true */
  fitWidth: boolean;
  /** Gap between pages in pixels. Range: 0–32. Default: 4 */
  pageGap: number;
  /** Strip (continuous scroll) or paged (one image at a time). Default: 'strip' */
  readingMode: ReadingMode;
  /** Automatically advance to the next chapter when reaching the end. Default: true */
  autoAdvance: boolean;
  /** Image rendering quality. Default: 'high' */
  imageQuality: ImageQuality;
}

export const DEFAULT_SETTINGS: ReaderSettings = {
  imageWidth: 1920,
  brightness: 100,
  fitWidth: true,
  pageGap: 4,
  readingMode: 'strip',
  autoAdvance: true,
  imageQuality: 'high',
};

const STORAGE_KEY = 'reader-settings';

// ── Shared external store ─────────────────────────────────────────────────────
// All components that call useReaderSettings() share the SAME snapshot.
// Updating from any consumer immediately notifies every other consumer.

const listeners = new Set<() => void>();

let currentSettings: ReaderSettings = loadFromStorage();

function loadFromStorage(): ReaderSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<ReaderSettings>) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveToStorage(s: ReaderSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* localStorage unavailable — fail silently */
  }
}

function emitChange(): void {
  for (const fn of listeners) fn();
}

function subscribe(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  return () => listeners.delete(onStoreChange);
}

function getSnapshot(): ReaderSettings {
  return currentSettings;
}

// ── Public mutators (can be used outside React too) ───────────────────────────

export function updateReaderSettings(update: Partial<ReaderSettings>): void {
  currentSettings = { ...currentSettings, ...update };
  saveToStorage(currentSettings);
  emitChange();
}

export function resetReaderSettings(): void {
  currentSettings = DEFAULT_SETTINGS;
  saveToStorage(DEFAULT_SETTINGS);
  emitChange();
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Persists reader display settings to localStorage.
 * All consumers share the same live snapshot via useSyncExternalStore —
 * changing a value in the reader settings panel immediately updates
 * the Settings page and vice-versa.
 */
export function useReaderSettings() {
  const settings = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const setSettings = useCallback((update: Partial<ReaderSettings>) => {
    updateReaderSettings(update);
  }, []);

  const resetSettings = useCallback(() => {
    resetReaderSettings();
  }, []);

  return { settings, setSettings, resetSettings, defaults: DEFAULT_SETTINGS };
}
