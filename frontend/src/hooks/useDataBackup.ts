import { useCallback } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

/** Shape of the exported backup file */
export interface BackupData {
  version: 1;
  exportedAt: string;
  data: {
    'comic-progress'?: unknown;
    'comic-favorites'?: unknown;
    'reader-settings'?: unknown;
  };
}

/** Options controlling which data keys to export. */
export interface ExportOptions {
  readingHistory: boolean;
  bookmarks: boolean;
  settings: boolean;
}

/** Metadata returned after a successful export. */
export interface ExportResult {
  fileName: string;
  fileSize: number;
  itemCounts: {
    comics: number;
    chapters: number;
    bookmarks: number;
    historyEntries: number;
    settingsIncluded: boolean;
  };
}

/** A single conflict detected during import. */
export interface ConflictItem {
  key: string;       // e.g. "mangakakalot:solo-leveling"
  title: string;
  existingValue: unknown;
  importedValue: unknown;
}

/** Progress callback shape */
export type ImportProgressCallback = (
  step: number,
  totalSteps: number,
  label: string,
) => void;

/** Resolution strategy for a conflict */
export type ConflictResolution = 'keep' | 'replace' | 'both';

const ALL_KEYS = ['comic-progress', 'comic-favorites', 'reader-settings'] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Map export options → localStorage keys to include. */
function keysFromOptions(opts: ExportOptions): typeof ALL_KEYS[number][] {
  const keys: typeof ALL_KEYS[number][] = [];
  if (opts.readingHistory) keys.push('comic-progress');
  if (opts.bookmarks) keys.push('comic-favorites');
  if (opts.settings) keys.push('reader-settings');
  return keys;
}

/** Count items inside a parsed localStorage value. */
function countItems(key: string, value: unknown): {
  comics: number;
  chapters: number;
  bookmarks: number;
  historyEntries: number;
} {
  const result = { comics: 0, chapters: 0, bookmarks: 0, historyEntries: 0 };
  if (!value || typeof value !== 'object') return result;

  if (key === 'comic-progress') {
    const p = value as { lastChapter?: Record<string, number>; readChapters?: Record<string, string[]>; recentlyRead?: unknown[] };
    result.comics = Object.keys(p.lastChapter ?? {}).length;
    result.chapters = Object.values(p.readChapters ?? {}).reduce((sum, arr) => sum + arr.length, 0);
    result.historyEntries = (p.recentlyRead ?? []).length;
  } else if (key === 'comic-favorites') {
    result.bookmarks = Array.isArray(value) ? value.length : 0;
  }
  return result;
}

/** Detect conflicts between existing and incoming progress data. */
function detectConflicts(
  existingRaw: string | null,
  importedData: unknown,
): ConflictItem[] {
  if (!existingRaw || !importedData) return [];

  try {
    const existing = JSON.parse(existingRaw) as {
      lastChapter?: Record<string, number>;
      recentlyRead?: Array<{ source: string; slug: string; title: string; lastChapter: number }>;
    };
    const imported = importedData as typeof existing;

    if (!existing.lastChapter || !imported.lastChapter) return [];

    const conflicts: ConflictItem[] = [];
    for (const [key, importedChapter] of Object.entries(imported.lastChapter)) {
      const existingChapter = existing.lastChapter[key];
      if (existingChapter !== undefined && existingChapter !== importedChapter) {
        // Find title from recentlyRead
        const title =
          imported.recentlyRead?.find(
            (e) => `${e.source}:${e.slug}` === key,
          )?.title ??
          existing.recentlyRead?.find(
            (e) => `${e.source}:${e.slug}` === key,
          )?.title ??
          key;

        conflicts.push({
          key,
          title,
          existingValue: existingChapter,
          importedValue: importedChapter,
        });
      }
    }
    return conflicts;
  } catch {
    return [];
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Export/import all localStorage-backed user data as a JSON backup file.
 * Enhanced with selective export, progress tracking, and conflict detection.
 */
export function useDataBackup() {
  /**
   * Export selected data keys to a downloadable JSON file.
   * Returns metadata about the export.
   */
  const exportData = useCallback(
    (options?: ExportOptions): ExportResult => {
      const opts = options ?? { readingHistory: true, bookmarks: true, settings: true };
      const keys = keysFromOptions(opts);

      const data: BackupData['data'] = {};
      const totals = { comics: 0, chapters: 0, bookmarks: 0, historyEntries: 0 };

      for (const key of keys) {
        try {
          const raw = localStorage.getItem(key);
          if (raw) {
            const parsed = JSON.parse(raw);
            data[key] = parsed;
            const counts = countItems(key, parsed);
            totals.comics += counts.comics;
            totals.chapters += counts.chapters;
            totals.bookmarks += counts.bookmarks;
            totals.historyEntries += counts.historyEntries;
          }
        } catch {
          /* skip unparseable entries */
        }
      }

      const backup: BackupData = {
        version: 1,
        exportedAt: new Date().toISOString(),
        data,
      };

      const jsonStr = JSON.stringify(backup, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const fileName = `comic-crawler-backup-${new Date().toISOString().slice(0, 10)}.json`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      return {
        fileName,
        fileSize: blob.size,
        itemCounts: {
          ...totals,
          settingsIncluded: opts.settings,
        },
      };
    },
    [],
  );

  /**
   * Import data from a File with optional progress and conflict callbacks.
   */
  const importData = useCallback(
    (
      file: File,
      onProgress?: ImportProgressCallback,
    ): Promise<{
      success: boolean;
      message: string;
      conflicts: ConflictItem[];
    }> => {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = async (e) => {
          try {
            const text = e.target?.result as string;
            onProgress?.(1, 5, 'Validating backup file…');
            await sleep(300);

            const parsed = JSON.parse(text) as BackupData;

            // Validate structure
            if (!parsed.version || !parsed.data || typeof parsed.data !== 'object') {
              resolve({ success: false, message: 'Invalid backup file format.', conflicts: [] });
              return;
            }

            onProgress?.(2, 5, 'Scanning for conflicts…');
            await sleep(300);

            // Detect conflicts with reading progress
            const conflicts = detectConflicts(
              localStorage.getItem('comic-progress'),
              parsed.data['comic-progress'],
            );

            if (conflicts.length > 0) {
              // Return conflicts without applying — caller must resolve first
              resolve({
                success: true,
                message: `Found ${conflicts.length} conflict(s). Please resolve before applying.`,
                conflicts,
              });
              return;
            }

            // No conflicts — apply directly
            onProgress?.(3, 5, 'Importing comics…');
            await sleep(200);

            let restored = 0;
            for (const key of ALL_KEYS) {
              if (parsed.data[key] !== undefined) {
                onProgress?.(3 + restored, 5, `Importing ${key.replace('comic-', '')}…`);
                localStorage.setItem(key, JSON.stringify(parsed.data[key]));
                restored++;
                await sleep(150);
              }
            }

            onProgress?.(5, 5, 'Import complete!');

            resolve({
              success: true,
              message: `Restored ${restored} data key${restored !== 1 ? 's' : ''}. Reload to apply.`,
              conflicts: [],
            });
          } catch {
            resolve({ success: false, message: 'Failed to parse backup file.', conflicts: [] });
          }
        };
        reader.onerror = () =>
          resolve({ success: false, message: 'Failed to read file.', conflicts: [] });
        reader.readAsText(file);
      });
    },
    [],
  );

  /**
   * Apply an import with a specific conflict resolution strategy.
   */
  const applyImportWithResolution = useCallback(
    (
      file: File,
      resolution: ConflictResolution,
      onProgress?: ImportProgressCallback,
    ): Promise<{ success: boolean; message: string }> => {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = async (e) => {
          try {
            const text = e.target?.result as string;
            const parsed = JSON.parse(text) as BackupData;

            onProgress?.(1, 5, 'Applying import…');
            await sleep(200);

            let restored = 0;
            for (const key of ALL_KEYS) {
              if (parsed.data[key] === undefined) continue;

              if (key === 'comic-progress' && resolution !== 'replace') {
                // Merge progress data
                const existingRaw = localStorage.getItem(key);
                if (existingRaw && resolution === 'keep') {
                  // Keep existing — only add comics not already tracked
                  const existing = JSON.parse(existingRaw) as Record<string, unknown>;
                  const imported = parsed.data[key] as Record<string, unknown>;
                  const merged = mergeProgressKeepExisting(existing, imported);
                  localStorage.setItem(key, JSON.stringify(merged));
                } else if (existingRaw && resolution === 'both') {
                  // Merge both — take the higher chapter number
                  const existing = JSON.parse(existingRaw) as Record<string, unknown>;
                  const imported = parsed.data[key] as Record<string, unknown>;
                  const merged = mergeProgressKeepBoth(existing, imported);
                  localStorage.setItem(key, JSON.stringify(merged));
                } else {
                  localStorage.setItem(key, JSON.stringify(parsed.data[key]));
                }
              } else {
                localStorage.setItem(key, JSON.stringify(parsed.data[key]));
              }

              restored++;
              onProgress?.(2 + restored, 5, `Imported ${key.replace('comic-', '')}…`);
              await sleep(150);
            }

            onProgress?.(5, 5, 'Import complete!');
            resolve({
              success: true,
              message: `Restored ${restored} data key${restored !== 1 ? 's' : ''}. Reload to apply.`,
            });
          } catch {
            resolve({ success: false, message: 'Failed to apply import.' });
          }
        };
        reader.onerror = () =>
          resolve({ success: false, message: 'Failed to read file.' });
        reader.readAsText(file);
      });
    },
    [],
  );

  /**
   * Import from a remote URL (fetch + parse).
   */
  const importFromUrl = useCallback(
    async (
      url: string,
      onProgress?: ImportProgressCallback,
    ): Promise<{ success: boolean; message: string; conflicts: ConflictItem[] }> => {
      try {
        onProgress?.(1, 5, 'Fetching remote backup…');
        const resp = await fetch(url);
        if (!resp.ok) {
          return { success: false, message: `HTTP ${resp.status}: ${resp.statusText}`, conflicts: [] };
        }
        const blob = await resp.blob();
        const file = new File([blob], 'remote-backup.json', { type: 'application/json' });
        return importData(file, onProgress);
      } catch (err) {
        return {
          success: false,
          message: `Failed to fetch: ${err instanceof Error ? err.message : 'Unknown error'}`,
          conflicts: [],
        };
      }
    },
    [importData],
  );

  return { exportData, importData, applyImportWithResolution, importFromUrl };
}

// ── Merge helpers ─────────────────────────────────────────────────────────────

function mergeProgressKeepExisting(
  existing: Record<string, unknown>,
  imported: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...imported };
  // For lastChapter: keep existing values where they exist
  const existLC = (existing as { lastChapter?: Record<string, number> }).lastChapter ?? {};
  const importLC = (imported as { lastChapter?: Record<string, number> }).lastChapter ?? {};
  (result as { lastChapter: Record<string, number> }).lastChapter = { ...importLC, ...existLC };

  // For readChapters: merge arrays, dedup
  const existRC = (existing as { readChapters?: Record<string, string[]> }).readChapters ?? {};
  const importRC = (imported as { readChapters?: Record<string, string[]> }).readChapters ?? {};
  const mergedRC: Record<string, string[]> = { ...importRC };
  for (const [key, arr] of Object.entries(existRC)) {
    mergedRC[key] = [...new Set([...(mergedRC[key] ?? []), ...arr])];
  }
  (result as { readChapters: Record<string, string[]> }).readChapters = mergedRC;

  // For recentlyRead: keep existing entries, dedup by source:slug
  const existRR = (existing as { recentlyRead?: unknown[] }).recentlyRead ?? [];
  const importRR = (imported as { recentlyRead?: unknown[] }).recentlyRead ?? [];
  const seen = new Set<string>();
  const mergedRR: unknown[] = [];
  for (const entry of [...existRR, ...importRR]) {
    const e = entry as { source: string; slug: string };
    const k = `${e.source}:${e.slug}`;
    if (!seen.has(k)) { seen.add(k); mergedRR.push(entry); }
  }
  (result as { recentlyRead: unknown[] }).recentlyRead = mergedRR.slice(0, 10);

  return result;
}

function mergeProgressKeepBoth(
  existing: Record<string, unknown>,
  imported: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...imported };
  // For lastChapter: take the higher chapter number
  const existLC = (existing as { lastChapter?: Record<string, number> }).lastChapter ?? {};
  const importLC = (imported as { lastChapter?: Record<string, number> }).lastChapter ?? {};
  const mergedLC: Record<string, number> = { ...importLC };
  for (const [key, val] of Object.entries(existLC)) {
    mergedLC[key] = Math.max(mergedLC[key] ?? 0, val);
  }
  (result as { lastChapter: Record<string, number> }).lastChapter = mergedLC;

  // For readChapters: union of all read chapters
  const existRC = (existing as { readChapters?: Record<string, string[]> }).readChapters ?? {};
  const importRC = (imported as { readChapters?: Record<string, string[]> }).readChapters ?? {};
  const mergedRC: Record<string, string[]> = { ...importRC };
  for (const [key, arr] of Object.entries(existRC)) {
    mergedRC[key] = [...new Set([...(mergedRC[key] ?? []), ...arr])];
  }
  (result as { readChapters: Record<string, string[]> }).readChapters = mergedRC;

  // For recentlyRead: merge, keep newest per key
  const existRR = (existing as { recentlyRead?: Array<{ source: string; slug: string; visitedAt: number }> }).recentlyRead ?? [];
  const importRR = (imported as { recentlyRead?: Array<{ source: string; slug: string; visitedAt: number }> }).recentlyRead ?? [];
  const map = new Map<string, typeof existRR[number]>();
  for (const entry of [...importRR, ...existRR]) {
    const k = `${entry.source}:${entry.slug}`;
    const existing = map.get(k);
    if (!existing || entry.visitedAt > existing.visitedAt) map.set(k, entry);
  }
  (result as { recentlyRead: unknown[] }).recentlyRead = [...map.values()]
    .sort((a, b) => b.visitedAt - a.visitedAt)
    .slice(0, 10);

  return result;
}

/** Small delay for progress UI feedback. */
function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
