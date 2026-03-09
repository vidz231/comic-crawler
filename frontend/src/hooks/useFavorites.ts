import { useState, useEffect, useCallback } from 'react';

// ── Types ───────────────────────────────────────────────────────────────────

export interface FavoriteEntry {
  source: string;
  slug: string;
  title: string;
  cover_url: string | null;
  addedAt: number;
}

// ── Storage helpers ─────────────────────────────────────────────────────────

const STORAGE_KEY = 'comic-favorites';

function loadFavorites(): FavoriteEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as FavoriteEntry[];
  } catch {
    return [];
  }
}

function saveFavorites(data: FavoriteEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // localStorage may be full or unavailable — fail silently
  }
}

// ── Hook ────────────────────────────────────────────────────────────────────

/**
 * Manages a favorites list backed by localStorage.
 * Follows the same pattern as useReadingProgress: lazy init, useEffect sync,
 * useCallback for stable references.
 */
export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteEntry[]>(() => loadFavorites());

  // Sync state → localStorage whenever favorites change
  useEffect(() => {
    saveFavorites(favorites);
  }, [favorites]);

  /** Toggle a series in/out of favorites. Returns new favorited state. */
  const toggleFavorite = useCallback(
    (source: string, slug: string, title: string, cover_url: string | null): boolean => {
      let added = false;
      setFavorites((prev) => {
        const exists = prev.some((f) => f.source === source && f.slug === slug);
        if (exists) {
          // Remove
          return prev.filter((f) => !(f.source === source && f.slug === slug));
        }
        // Add — newest first
        added = true;
        return [{ source, slug, title, cover_url, addedAt: Date.now() }, ...prev];
      });
      return added;
    },
    [],
  );

  /** Check if a series is favorited. */
  const isFavorite = useCallback(
    (source: string, slug: string): boolean => {
      return favorites.some((f) => f.source === source && f.slug === slug);
    },
    [favorites],
  );

  return { favorites, toggleFavorite, isFavorite };
}
