/**
 * Source ordering — asura first (default), mangadex & mangakakalot last.
 * Used by both Home and Search pages.
 */

const SOURCE_ORDER: Record<string, number> = {
  asura:        0,
  truyenvn:     1,
  truyenqq:     2,
  mangadex:     3,
  mangakakalot: 4,
};

/** Sort sources by preferred order. Unknown sources go between known ones. */
export function sortSources<T extends { name: string }>(sources: T[]): T[] {
  return [...sources].sort(
    (a, b) => (SOURCE_ORDER[a.name] ?? 2.5) - (SOURCE_ORDER[b.name] ?? 2.5)
  );
}

/** The default source name (first in the preferred order). */
export const DEFAULT_SOURCE = 'asura';
