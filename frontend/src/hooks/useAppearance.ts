import { useSyncExternalStore, useCallback, useEffect } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type Theme = 'light' | 'dark' | 'oled';

export interface AppearanceSettings {
  theme: Theme;
  /** Text size as a percentage (80–140). Default: 100 */
  textSize: number;
}

const DEFAULT_APPEARANCE: AppearanceSettings = {
  theme: 'dark',
  textSize: 100,
};

const THEME_KEY = 'app-theme';
const TEXT_SIZE_KEY = 'app-text-size';

// ── Shared external store ─────────────────────────────────────────────────────

const listeners = new Set<() => void>();

let current: AppearanceSettings = loadFromStorage();

function loadFromStorage(): AppearanceSettings {
  try {
    const theme = localStorage.getItem(THEME_KEY);
    const size = localStorage.getItem(TEXT_SIZE_KEY);
    return {
      theme: theme === 'light' || theme === 'dark' || theme === 'oled' ? theme : 'dark',
      textSize: size ? Math.max(80, Math.min(140, Number(size))) : 100,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

function saveToStorage(s: AppearanceSettings): void {
  try {
    localStorage.setItem(THEME_KEY, s.theme);
    localStorage.setItem(TEXT_SIZE_KEY, String(s.textSize));
  } catch { /* noop */ }
}

/** Apply appearance to the DOM so CSS picks it up immediately */
function applyToDOM(s: AppearanceSettings): void {
  document.documentElement.setAttribute('data-theme', s.theme);
  document.documentElement.style.fontSize = `${s.textSize}%`;
}

function emitChange(): void {
  for (const fn of listeners) fn();
}

function subscribe(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  return () => listeners.delete(onStoreChange);
}

function getSnapshot(): AppearanceSettings {
  return current;
}

// ── Public mutators ───────────────────────────────────────────────────────────

export function setTheme(theme: Theme): void {
  current = { ...current, theme };
  saveToStorage(current);
  applyToDOM(current);
  emitChange();
}

export function setTextSize(textSize: number): void {
  current = { ...current, textSize };
  saveToStorage(current);
  applyToDOM(current);
  emitChange();
}

// Apply on module load so first paint uses correct theme
applyToDOM(current);

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Global appearance settings (theme + text size).
 * Applies `data-theme` and `font-size` to `<html>`.
 * All consumers stay in sync via useSyncExternalStore.
 */
export function useAppearance() {
  const appearance = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  // Re-apply to DOM whenever the snapshot changes (safety net)
  useEffect(() => {
    applyToDOM(appearance);
  }, [appearance]);

  const updateTheme = useCallback((t: Theme) => setTheme(t), []);
  const updateTextSize = useCallback((v: number) => setTextSize(v), []);

  return {
    theme: appearance.theme,
    textSize: appearance.textSize,
    setTheme: updateTheme,
    setTextSize: updateTextSize,
  };
}
