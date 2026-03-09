import { useState, useEffect } from 'react';
import { Trash2, HardDrive, Download, X } from 'lucide-react';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import './CacheManager.css';

export default function CacheManager({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { downloads, clearAllDownloads, deleteChapter } = useOfflineChapters();
  const [storageEstimate, setStorageEstimate] = useState<{
    usage: number;
    quota: number;
  } | null>(null);

  useEffect(() => {
    if (open && navigator.storage?.estimate) {
      navigator.storage.estimate().then((est) => {
        setStorageEstimate({
          usage: est.usage ?? 0,
          quota: est.quota ?? 0,
        });
      });
    }
  }, [open, downloads.length]);

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1_048_576).toFixed(1)} MB`;
  };

  return (
    <>
      {open && (
        <div className="cache-backdrop" onClick={onClose} aria-hidden="true" />
      )}
      <aside className={`cache-panel glass${open ? ' open' : ''}`} aria-label="Cache management">
        <div className="cache-header">
          <span className="cache-title">
            <HardDrive size={16} /> Storage
          </span>
          <button className="cache-close" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {storageEstimate && (
          <div className="cache-meter">
            <div className="cache-meter__bar">
              <div
                className="cache-meter__fill"
                style={{
                  width: `${Math.min(100, (storageEstimate.usage / storageEstimate.quota) * 100)}%`,
                }}
              />
            </div>
            <span className="cache-meter__label">
              {formatBytes(storageEstimate.usage)} / {formatBytes(storageEstimate.quota)}
            </span>
          </div>
        )}

        <div className="cache-section">
          <h4 className="cache-subtitle">
            <Download size={14} /> Downloaded Chapters ({downloads.length})
          </h4>

          {downloads.length === 0 ? (
            <p className="cache-empty">No chapters downloaded yet.</p>
          ) : (
            <ul className="cache-list">
              {downloads.map((d) => (
                <li key={`${d.source}/${d.slug}/${d.number}`} className="cache-item">
                  <div className="cache-item__info">
                    <span className="cache-item__title">{d.title}</span>
                    <span className="cache-item__meta">
                      Ch.{d.number} · {d.pageCount} pages · {d.source}
                    </span>
                  </div>
                  <button
                    className="cache-item__delete"
                    onClick={() => deleteChapter(d.source, d.slug, d.number)}
                    aria-label={`Delete chapter ${d.number}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {downloads.length > 0 && (
          <button
            className="cache-clear-btn"
            onClick={() => {
              if (confirm('Delete all downloaded chapters?')) {
                clearAllDownloads();
              }
            }}
          >
            <Trash2 size={14} /> Clear All Downloads
          </button>
        )}
      </aside>
    </>
  );
}
