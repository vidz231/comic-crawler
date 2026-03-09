import { useRef, useCallback, useEffect } from 'react';

/**
 * Hook that fires a callback after the user presses and holds for `delay` ms.
 * Cancels automatically on pointer-up, leave, cancel, or any scroll movement
 * (so scrolling through images never accidentally triggers the overlay).
 */
export function useLongPress(callback: () => void, delay = 500) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const activeRef = useRef(false);

  const clear = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = undefined;
    activeRef.current = false;
  }, []);

  // Cancel on any scroll while the press is active
  useEffect(() => {
    const onScroll = () => {
      if (activeRef.current) clear();
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [clear]);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      // Only primary button (touch or left-click)
      if (e.button !== 0) return;
      activeRef.current = true;
      timerRef.current = setTimeout(() => {
        activeRef.current = false;
        callback();
      }, delay);
    },
    [callback, delay],
  );

  const onPointerUp = useCallback(() => clear(), [clear]);
  const onPointerLeave = useCallback(() => clear(), [clear]);
  const onPointerCancel = useCallback(() => clear(), [clear]);

  // Cleanup on unmount
  useEffect(() => () => clear(), [clear]);

  return { onPointerDown, onPointerUp, onPointerLeave, onPointerCancel };
}
