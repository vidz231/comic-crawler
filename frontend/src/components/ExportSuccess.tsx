import { Share2, Cloud, Copy, Check } from 'lucide-react';
import { useState, useCallback } from 'react';
import type { ExportResult } from '../hooks/useDataBackup';
import './ExportSuccess.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface ExportSuccessProps {
  result: ExportResult;
  onDone: () => void;
}

export default function ExportSuccess({ result, onDone }: ExportSuccessProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyPath = useCallback(() => {
    navigator.clipboard.writeText(`Downloads/${result.fileName}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => { /* ignore */ });
  }, [result.fileName]);

  const handleShare = useCallback(async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Comic Crawler Backup',
          text: `My Comic Crawler backup — ${result.fileName}`,
        });
      } catch {
        /* user cancelled */
      }
    }
  }, [result.fileName]);

  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
  const timeStr = now.toLocaleTimeString('en-US', {
    hour: 'numeric', minute: '2-digit',
  });

  return (
    <div className="es-overlay" role="dialog" aria-label="Export success">
      <div className="es-card">
        {/* Checkmark */}
        <div className="es-check-wrap">
          <div className="es-check">
            <span className="es-check-icon">✓</span>
          </div>
        </div>

        <h2 className="es-title">Export Successful!</h2>
        <p className="es-subtitle">Your data has been saved</p>

        {/* Summary */}
        <div className="es-summary">
          <div className="es-summary-row">
            <span className="es-summary-label">Date</span>
            <span className="es-summary-value">{dateStr} at {timeStr}</span>
          </div>
          <div className="es-summary-row">
            <span className="es-summary-label">Format</span>
            <span className="es-summary-value">JSON</span>
          </div>
          <div className="es-summary-row">
            <span className="es-summary-label">Size</span>
            <span className="es-summary-value">{formatBytes(result.fileSize)}</span>
          </div>

          <div className="es-divider" />

          <div className="es-breakdown">
            <div className="es-breakdown-row">
              <span className="es-breakdown-icon">📚</span>
              Comics: {result.itemCounts.comics}
            </div>
            <div className="es-breakdown-row">
              <span className="es-breakdown-icon">📖</span>
              Chapters tracked: {result.itemCounts.chapters}
            </div>
            <div className="es-breakdown-row">
              <span className="es-breakdown-icon">🔖</span>
              Bookmarks: {result.itemCounts.bookmarks}
            </div>
            <div className="es-breakdown-row">
              <span className="es-breakdown-icon">📊</span>
              History entries: {result.itemCounts.historyEntries}
            </div>
            {result.itemCounts.settingsIncluded && (
              <div className="es-breakdown-row">
                <span className="es-breakdown-icon">⚙️</span>
                App settings: Included
              </div>
            )}
          </div>
        </div>

        {/* File location */}
        <div className="es-file-card">
          <p className="es-file-label">File saved to</p>
          <p className="es-file-path">Downloads/{result.fileName}</p>
          <div className="es-file-actions">
            <button className="es-file-btn" onClick={handleCopyPath}>
              {copied ? <><Check size={10} /> Copied</> : <><Copy size={10} /> Copy path</>}
            </button>
          </div>
        </div>

        {/* Share buttons */}
        <div className="es-share-btns">
          {'share' in navigator && (
            <button className="es-share-primary" onClick={handleShare}>
              <Share2 size={18} />
              Share Backup
            </button>
          )}
          <button className="es-share-secondary" onClick={() => { /* placeholder */ }}>
            <Cloud size={16} />
            Save to Cloud
          </button>
        </div>

        {/* Done */}
        <button className="es-done" onClick={onDone}>
          Done
        </button>
      </div>
    </div>
  );
}
