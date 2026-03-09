import { useRef, useEffect, useCallback } from 'react';

interface ZoomState {
  scale: number;
  translateX: number;
  translateY: number;
}

const MIN_SCALE = 1;
const MAX_SCALE = 4;
const DOUBLE_TAP_DELAY = 300;

/**
 * Provides pinch-to-zoom and double-tap-to-zoom on a container element.
 *
 * Usage:
 *   const { containerRef } = usePinchZoom();
 *   return <div ref={containerRef}>...</div>
 */
export function usePinchZoom<T extends HTMLElement = HTMLDivElement>() {
  const containerRef = useRef<T>(null);
  const stateRef = useRef<ZoomState>({ scale: 1, translateX: 0, translateY: 0 });

  // Pinch tracking
  const initialDistRef = useRef(0);
  const initialScaleRef = useRef(1);

  // Double-tap tracking
  const lastTapRef = useRef(0);

  const applyTransform = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const { scale, translateX, translateY } = stateRef.current;
    if (scale <= 1) {
      el.style.transform = '';
      el.style.transformOrigin = '';
      stateRef.current = { scale: 1, translateX: 0, translateY: 0 };
    } else {
      el.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
      el.style.transformOrigin = '0 0';
    }
  }, []);

  const resetZoom = useCallback(() => {
    stateRef.current = { scale: 1, translateX: 0, translateY: 0 };
    applyTransform();
  }, [applyTransform]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // ── Pinch-to-zoom ──────────────────────────────────────────────────────
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        initialDistRef.current = Math.hypot(dx, dy);
        initialScaleRef.current = stateRef.current.scale;
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const newScale = Math.min(
          MAX_SCALE,
          Math.max(MIN_SCALE, initialScaleRef.current * (dist / initialDistRef.current))
        );
        stateRef.current.scale = newScale;
        applyTransform();
      } else if (e.touches.length === 1 && stateRef.current.scale > 1) {
        // Pan when zoomed
        e.preventDefault();
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (e.touches.length === 0 && stateRef.current.scale <= 1.05) {
        resetZoom();
      }

      // ── Double-tap zoom ──────────────────────────────────────────────────
      if (e.changedTouches.length === 1) {
        const now = Date.now();
        if (now - lastTapRef.current < DOUBLE_TAP_DELAY) {
          // Toggle between 1x and 2.5x
          if (stateRef.current.scale > 1) {
            resetZoom();
          } else {
            const touch = e.changedTouches[0];
            const rect = el.getBoundingClientRect();
            const x = touch.clientX - rect.left;
            const y = touch.clientY - rect.top;
            stateRef.current = {
              scale: 2.5,
              translateX: -(x * 1.5),
              translateY: -(y * 1.5),
            };
            applyTransform();
          }
          lastTapRef.current = 0; // reset to prevent triple-tap
        } else {
          lastTapRef.current = now;
        }
      }
    };

    el.addEventListener('touchstart', handleTouchStart, { passive: false });
    el.addEventListener('touchmove', handleTouchMove, { passive: false });
    el.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      el.removeEventListener('touchstart', handleTouchStart);
      el.removeEventListener('touchmove', handleTouchMove);
      el.removeEventListener('touchend', handleTouchEnd);
    };
  }, [applyTransform, resetZoom]);

  return { containerRef, resetZoom };
}
