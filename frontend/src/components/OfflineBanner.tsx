import { useOnlineStatus } from '../hooks/useOnlineStatus';
import './OfflineBanner.css';

/**
 * Fixed banner that appears when the device goes offline and
 * auto-hides once connectivity is restored.
 */
export default function OfflineBanner() {
  const isOnline = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div className="offline-banner" role="alert" aria-live="assertive">
      <span className="offline-banner__icon" aria-hidden="true">📡</span>
      <span className="offline-banner__text">
        You're offline — cached content is still available.
      </span>
    </div>
  );
}
