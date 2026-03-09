import { useState, useEffect, useCallback } from 'react';

// ── Types ───────────────────────────────────────────────────────────────────

export interface RecentEntry {
  source: string;
  slug: string;
  title: string;
  cover_url: string | null;
  lastChapter: number;
  visitedAt: number;
}

interface StoredProgress {
  lastChapter: Record<string, number>;      // `${source}:${slug}` → chapter num
  readChapters: Record<string, string[]>;   // `${source}:${slug}` → ["1", "2", "75.5"]
  recentlyRead: RecentEntry[];              // max 10, newest first
}

// ── Storage helpers ─────────────────────────────────────────────────────────

const STORAGE_KEY = 'comic-progress';
const MAX_RECENT = 10;

function makeKey(source: string, slug: string): string {
  return `${source}:${slug}`;
}

function loadProgress(): StoredProgress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { lastChapter: {}, readChapters: {}, recentlyRead: [] };
    const parsed = JSON.parse(raw) as StoredProgress;
    // Migrate: old format stored readChapters as number[] — coerce all to string[]
    const migratedReadChapters: Record<string, string[]> = {};
    for (const [key, arr] of Object.entries(parsed.readChapters ?? {})) {
      migratedReadChapters[key] = (arr as (string | number)[]).map(String);
    }
    return { ...parsed, readChapters: migratedReadChapters };
  } catch {
    return { lastChapter: {}, readChapters: {}, recentlyRead: [] };
  }
}


function saveProgress(data: StoredProgress): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // localStorage may be full or unavailable — fail silently
  }
}

// ── Hook ────────────────────────────────────────────────────────────────────

/**
 * Manages reading progress backed by localStorage.
 * Follows react-dev skill: lazy useState initializer, explicit generics,
 * single useEffect for persistence, useCallback for stable references.
 */
export function useReadingProgress() {
  // Lazy init: parse localStorage once on mount, not on every render
  const [progress, setProgress] = useState<StoredProgress>(() => loadProgress());

  // Sync state → localStorage whenever progress changes
  useEffect(() => {
    saveProgress(progress);
  }, [progress]);

  /** Mark a chapter as read and update last-read pointer for the series. */
  const markRead = useCallback(
    (
      source: string,
      slug: string,
      chapterNum: number,
      meta: { title: string; cover_url: string | null },
    ) => {
      setProgress((prev) => {
        const key = makeKey(source, slug);

        // Update last chapter
        const lastChapter = { ...prev.lastChapter, [key]: chapterNum };

        // Append chapter to read set (deduplicated, stored as strings for safe equality)
        const chapterKey = String(chapterNum);
        const prevRead = prev.readChapters[key] ?? [];
        const readChapters = {
          ...prev.readChapters,
          [key]: prevRead.includes(chapterKey) ? prevRead : [...prevRead, chapterKey],
        };

        // Upsert recent entry — remove stale entry for same series, prepend fresh
        const filtered = prev.recentlyRead.filter(
          (e) => !(e.source === source && e.slug === slug),
        );
        const newEntry: RecentEntry = {
          source,
          slug,
          title: meta.title,
          cover_url: meta.cover_url,
          lastChapter: chapterNum,
          visitedAt: Date.now(),
        };
        const recentlyRead = [newEntry, ...filtered].slice(0, MAX_RECENT);

        return { lastChapter, readChapters, recentlyRead };
      });
    },
    [],
  );

  /** Returns the last chapter number read for a series, or null. */
  const getLastChapter = useCallback(
    (source: string, slug: string): number | null => {
      return progress.lastChapter[makeKey(source, slug)] ?? null;
    },
    [progress.lastChapter],
  );

  /** Returns true if the given chapter has been visited. */
  const isChapterRead = useCallback(
    (source: string, slug: string, chapterNum: number): boolean => {
      return (progress.readChapters[makeKey(source, slug)] ?? []).includes(String(chapterNum));
    },
    [progress.readChapters],
  );

  /** Clear all reading history (recently read + read chapters) but keep bookmarks. */
  const clearHistory = useCallback(() => {
    setProgress((prev) => ({
      ...prev,
      readChapters: {},
      recentlyRead: [],
    }));
  }, []);

  return {
    recentlyRead: progress.recentlyRead,
    markRead,
    getLastChapter,
    isChapterRead,
    clearHistory,
  };
}
