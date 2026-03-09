import { useState } from 'react';
import { useInstallPrompt } from '../hooks/useInstallPrompt';
import './InstallPrompt.css';

const DISMISSED_KEY = 'pwa-install-dismissed';

/**
 * Bottom-sheet banner encouraging the user to install the PWA.
 * Shown once per session unless the user dismisses it.
 */
export default function InstallPrompt() {
  const { canInstall, isInstalled, installApp } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISSED_KEY) === '1'; }
    catch { return false; }
  });

  const handleDismiss = () => {
    setDismissed(true);
    try { sessionStorage.setItem(DISMISSED_KEY, '1'); } catch { /* noop */ }
  };

  if (isInstalled || !canInstall || dismissed) return null;

  return (
    <div className="install-prompt glass" role="alert">
      <span className="install-prompt__icon" aria-hidden="true">📖</span>
      <div className="install-prompt__body">
        <p className="install-prompt__title">Install Comic Reader</p>
        <p className="install-prompt__desc">Quick access &amp; offline reading</p>
      </div>
      <div className="install-prompt__actions">
        <button className="install-prompt__btn install-prompt__btn--primary" onClick={installApp}>
          Install
        </button>
        <button className="install-prompt__btn install-prompt__btn--dismiss" onClick={handleDismiss}>
          Not now
        </button>
      </div>
    </div>
  );
}
