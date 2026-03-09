import { useEffect } from 'react';

const PREFIX = 'reader-pos';

function makeKey(source: string, slug: string, chapterNum: number): string {
  return `${PREFIX}:${source}:${slug}:${chapterNum}`;
}

/**
 * Saves the user's scroll position (scrollY) when they leave a chapter,
 * and restores it when they return — but only if the chapter was already read.
 *
 * Uses sessionStorage so the position resets when the browser tab is closed.
 *
 * @param source - Comic source identifier
 * @param slug - Comic slug
 * @param chapterNum - Chapter number
 * @param wasAlreadyRead - Only restore if true (prevents jump on first visit)
 * @param imagesReady - Wait until images have rendered before restoring
 */
export function useScrollRestore(
  source: string,
  slug: string,
  chapterNum: number,
  wasAlreadyRead: boolean,
  imagesReady: boolean,
): void {
  const key = makeKey(source, slug, chapterNum);

  // Restore scroll once images are loaded
  useEffect(() => {
    if (!imagesReady || !wasAlreadyRead) return;
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) return;
      const savedY = Number(raw);
      if (!isNaN(savedY) && savedY > 0) {
        // Small timeout to let layout stabilise after image renders
        const timer = setTimeout(() => {
          window.scrollTo({ top: savedY, behavior: 'instant' });
        }, 120);
        return () => clearTimeout(timer);
      }
    } catch {
      /* sessionStorage unavailable */
    }
  }, [imagesReady, wasAlreadyRead, key]);

  // Save scroll position on unmount
  useEffect(() => {
    return () => {
      try {
        sessionStorage.setItem(key, String(Math.round(window.scrollY)));
      } catch {
        /* sessionStorage unavailable */
      }
    };
  }, [key]);
}
