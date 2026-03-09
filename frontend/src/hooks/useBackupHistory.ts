import { useState, useEffect, useCallback } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BackupEntry {
  id: string;
  date: string;          // ISO string
  fileSize: number;      // bytes
  itemCount: number;     // total items in backup
  type: 'export' | 'import';
  fileName: string;
}

// ── Storage helpers ─────────────────────────────────────────────────────────

const STORAGE_KEY = 'backup-history';
const MAX_ENTRIES = 10;

function loadHistory(): BackupEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as BackupEntry[];
  } catch {
    return [];
  }
}

function saveHistory(entries: BackupEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    /* localStorage may be full — fail silently */
  }
}

/** Generate a short unique ID for backup entries. */
function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Manages a history of backup operations (exports & imports) in localStorage.
 * Keeps the last MAX_ENTRIES entries, newest first.
 */
export function useBackupHistory() {
  const [entries, setEntries] = useState<BackupEntry[]>(() => loadHistory());

  // Sync state → localStorage
  useEffect(() => {
    saveHistory(entries);
  }, [entries]);

  /** Record a new backup operation. */
  const addEntry = useCallback(
    (entry: Omit<BackupEntry, 'id'>) => {
      setEntries((prev) => {
        const next = [{ ...entry, id: uid() }, ...prev].slice(0, MAX_ENTRIES);
        return next;
      });
    },
    [],
  );

  /** Remove a single entry by ID. */
  const removeEntry = useCallback((id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }, []);

  /** Clear all backup history. */
  const clearHistory = useCallback(() => {
    setEntries([]);
  }, []);

  return { entries, addEntry, removeEntry, clearHistory };
}
