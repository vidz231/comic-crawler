import { useEffect, useRef } from 'react';

/**
 * Reliably scrolls to the top of the page whenever any of the `deps` change.
 *
 * A single `window.scrollTo(0)` call can be silently swallowed on mobile when
 * momentum scrolling is active, the dynamic viewport is resizing, or images
 * are still loading and causing layout shifts. This hook retries with
 * increasing delays until `scrollY` is actually 0.
 *
 * Place this **before** `useScrollRestore` so it fires first; the restore hook
 * can then override with a saved position for previously-read chapters.
 */
export function useScrollToTop(...deps: unknown[]): void {
  const prevDeps = useRef<unknown[]>(deps);

  useEffect(() => {
    // Skip the very first mount — only fire on *changes*
    const changed = deps.some((d, i) => d !== prevDeps.current[i]);
    prevDeps.current = deps;
    if (!changed) return;

    const scrollToZero = () => {
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0; // legacy WebKit
    };

    // Fire immediately
    scrollToZero();

    // Retry schedule (ms) — covers layout-shift, momentum, and image-load delays
    const retries = [50, 150, 400];
    const timers: ReturnType<typeof setTimeout>[] = [];

    retries.forEach((ms) => {
      timers.push(
        setTimeout(() => {
          if (window.scrollY > 0) scrollToZero();
        }, ms),
      );
    });

    return () => timers.forEach(clearTimeout);
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
}
