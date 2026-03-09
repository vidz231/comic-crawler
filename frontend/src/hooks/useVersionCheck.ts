import { useEffect, useRef } from 'react';

/**
 * Polls /version.json every `intervalMs` and hard-reloads the page
 * when the deployed build hash differs from the running one.
 *
 * This bypasses all service-worker caching issues on iOS by performing
 * a cache-busting fetch of a tiny JSON file and comparing the server's
 * hash against the build-time constant injected by Vite.
 */
export function useVersionCheck(intervalMs = 60_000) {
  const currentHash = useRef<string>(__BUILD_HASH__);

  useEffect(() => {
    async function check() {
      try {
        const res = await fetch(`/version.json?_=${Date.now()}`, {
          cache: 'no-store',
        });
        if (!res.ok) return;
        const { hash } = await res.json();
        if (hash && hash !== currentHash.current) {
          // New version deployed → nuke SW caches and hard reload
          if ('caches' in window) {
            const keys = await caches.keys();
            await Promise.all(keys.map((k) => caches.delete(k)));
          }
          // Unregister all service workers so the fresh one registers on reload
          if ('serviceWorker' in navigator) {
            const registrations = await navigator.serviceWorker.getRegistrations();
            await Promise.all(registrations.map((r) => r.unregister()));
          }
          window.location.reload();
        }
      } catch {
        // offline / server down — skip silently
      }
    }

    // Check immediately on mount (covers the case where user just opened PWA)
    check();
    const timer = setInterval(check, intervalMs);

    // Also check when the app returns to foreground
    const onVisibility = () => {
      if (document.visibilityState === 'visible') check();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [intervalMs]);
}
