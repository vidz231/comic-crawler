import { useNavigate, useLocation } from 'react-router-dom';
import { Download, Loader2 } from 'lucide-react';
import { useDownloadManager } from '../contexts/DownloadContext';
import './DownloadIndicator.css';

/**
 * Persistent floating pill shown on all pages (except the reader and the downloads page)
 * when downloads are actively in progress.
 */
export default function DownloadIndicator() {
  const { downloadQueue, activeDownloads } = useDownloadManager();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  // Don't show on reader or downloads page
  const isReader = pathname.includes('/chapter/');
  const isDownloadsPage = pathname === '/downloads';
  const hasActivity = downloadQueue || activeDownloads.size > 0;

  if (isReader || isDownloadsPage || !hasActivity) return null;

  const label = downloadQueue
    ? `Downloading ${downloadQueue.completed + 1}/${downloadQueue.total}…`
    : `Downloading…`;

  const pct = downloadQueue
    ? downloadQueue.pct
    : (() => {
        // Average progress across active downloads
        let total = 0, loaded = 0;
        activeDownloads.forEach((p) => { total += p.total; loaded += p.loaded; });
        return total > 0 ? Math.round((loaded / total) * 100) : 0;
      })();

  return (
    <button
      className="download-indicator glass"
      onClick={() => navigate('/downloads')}
      aria-label="View active downloads"
    >
      <span className="download-indicator__icon">
        {downloadQueue ? (
          <Loader2 size={16} className="download-indicator__spin" />
        ) : (
          <Download size={16} />
        )}
      </span>
      <span className="download-indicator__label">{label}</span>
      <span className="download-indicator__bar">
        <span
          className="download-indicator__fill"
          style={{ width: `${pct}%` }}
        />
      </span>
    </button>
  );
}
