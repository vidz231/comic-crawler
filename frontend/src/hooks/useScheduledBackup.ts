import { useState, useEffect, useCallback } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type BackupFrequency = 'daily' | 'weekly' | 'monthly';

export interface ScheduledBackupSettings {
  enabled: boolean;
  frequency: BackupFrequency;
  lastRun: string | null;  // ISO string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'scheduled-backup';

const FREQUENCY_MS: Record<BackupFrequency, number> = {
  daily:   24 * 60 * 60 * 1000,
  weekly:  7 * 24 * 60 * 60 * 1000,
  monthly: 30 * 24 * 60 * 60 * 1000,
};

// ── Storage helpers ─────────────────────────────────────────────────────────

function loadSettings(): ScheduledBackupSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { enabled: false, frequency: 'weekly', lastRun: null };
    return JSON.parse(raw) as ScheduledBackupSettings;
  } catch {
    return { enabled: false, frequency: 'weekly', lastRun: null };
  }
}

function saveSettings(s: ScheduledBackupSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* fail silently */
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Manages scheduled backup settings. Checks on mount whether a backup is due
 * and calls the provided `onBackupDue` callback if so.
 *
 * Note: this runs only while the app is open — it is NOT a service-worker cron.
 */
export function useScheduledBackup(onBackupDue?: () => void) {
  const [settings, setSettings] = useState<ScheduledBackupSettings>(
    () => loadSettings(),
  );

  // Persist settings on change
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  // Check on mount whether a backup is overdue
  useEffect(() => {
    if (!settings.enabled || !onBackupDue) return;

    const interval = FREQUENCY_MS[settings.frequency];
    const lastRun = settings.lastRun ? new Date(settings.lastRun).getTime() : 0;
    const now = Date.now();

    if (now - lastRun >= interval) {
      onBackupDue();
      setSettings((prev) => ({ ...prev, lastRun: new Date().toISOString() }));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps — intentionally run once on mount

  /** Toggle scheduled backup on/off. */
  const toggleEnabled = useCallback(() => {
    setSettings((prev) => ({ ...prev, enabled: !prev.enabled }));
  }, []);

  /** Update backup frequency. */
  const setFrequency = useCallback((frequency: BackupFrequency) => {
    setSettings((prev) => ({ ...prev, frequency }));
  }, []);

  /** Mark a backup as just completed. */
  const markCompleted = useCallback(() => {
    setSettings((prev) => ({ ...prev, lastRun: new Date().toISOString() }));
  }, []);

  /** Compute the next scheduled backup date. */
  const getNextBackupDate = useCallback((): Date | null => {
    if (!settings.enabled) return null;
    const lastRun = settings.lastRun ? new Date(settings.lastRun).getTime() : Date.now();
    return new Date(lastRun + FREQUENCY_MS[settings.frequency]);
  }, [settings]);

  return {
    settings,
    toggleEnabled,
    setFrequency,
    markCompleted,
    getNextBackupDate,
  };
}
