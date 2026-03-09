import { Component, type ReactNode, type ErrorInfo } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';

/** Error boundary so a SW crash doesn't blank the whole app (e.g. Safari). */
class PwaBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(_e: Error, _info: ErrorInfo) { /* swallow */ }
  render() { return this.state.hasError ? null : this.props.children; }
}

/**
 * Registers the service worker via vite-plugin-pwa's virtual module.
 *
 * The heavy lifting (controllerchange reload, periodic update polling,
 * visibilitychange checks) lives in main.tsx and runs *before* React.
 * This component just ensures the virtual module is imported so the
 * vite-plugin-pwa autoUpdate wiring is active.
 */
function PwaUpdatePromptInner() {
  useRegisterSW({
    onRegisteredSW(swUrl: string, r: ServiceWorkerRegistration | undefined) {
      if (!r) return;
      // Extra polling with cache-busting fetch (belt-and-suspenders with main.tsx)
      setInterval(async () => {
        if (r.installing || !navigator) return;
        if ('connection' in navigator && !navigator.onLine) return;
        try {
          const resp = await fetch(swUrl, {
            cache: 'no-store',
            headers: { 'cache': 'no-store', 'cache-control': 'no-cache' },
          });
          if (resp?.status === 200) await r.update();
        } catch {
          // offline / server down — skip
        }
      }, 60 * 1000);
    },
  });

  return null;
}

export default function PwaUpdatePrompt() {
  return (
    <PwaBoundary>
      <PwaUpdatePromptInner />
    </PwaBoundary>
  );
}
