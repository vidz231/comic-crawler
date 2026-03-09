import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// ── Service Worker update handling (framework-independent) ────────────────
// This runs BEFORE React mounts, so even if the app bundle crashes the SW
// update mechanism still works. This is the primary update driver; the React
// PwaUpdatePrompt component is a secondary helper.
if ('serviceWorker' in navigator) {
  // 1. Auto-reload when a new SW takes control (skipWaiting + clientsClaim)
  //    This fires when the browser finishes activating a new SW version.
  let refreshing = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;       // prevent infinite reload loops
    refreshing = true;
    window.location.reload();
  });

  // 2. Periodically check for SW updates + on tab focus
  //    Mobile users often keep a PWA open in the background for hours/days.
  //    We force an update check every 60s AND when the tab gets focus.
  navigator.serviceWorker.ready.then((registration) => {
    // Check for updates every 60 seconds
    setInterval(async () => {
      try {
        await registration.update();
      } catch {
        // Network error or server down — skip
      }
    }, 60 * 1000);

    // Also check when the user returns to the app (tab/app switch)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        registration.update().catch(() => {});
      }
    });
  });
}

// ── Mount React ───────────────────────────────────────────────────────────
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
