import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Upload,
  FileUp,
  Link2,
  Layers,
  Clock,
  Trash2,
  AlertTriangle,
  Calendar,
  HardDrive,
  FileJson,
  Archive,
  Clipboard,
} from 'lucide-react';
import { useDataBackup } from '../hooks/useDataBackup';
import type { ExportOptions, ExportResult, ConflictItem, ImportProgressCallback } from '../hooks/useDataBackup';
import { useBackupHistory } from '../hooks/useBackupHistory';
import { useScheduledBackup } from '../hooks/useScheduledBackup';
import type { BackupFrequency } from '../hooks/useScheduledBackup';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import { useDocTitle } from '../hooks/useDocTitle';
import ImportProgress from '../components/ImportProgress';
import ExportSuccess from '../components/ExportSuccess';
import './ImportExportPage.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ImportExportPage() {
  useDocTitle('Import & Export');
  const navigate = useNavigate();

  // Hooks
  const { exportData, importData, applyImportWithResolution } = useDataBackup();
  const { entries: backupHistory, addEntry, removeEntry } = useBackupHistory();
  const { clearHistory } = useReadingProgress();
  const { clearAllDownloads } = useOfflineChapters();

  // Scheduled backup
  const handleAutoBackup = useCallback(() => {
    const result = exportData();
    addEntry({
      date: new Date().toISOString(),
      fileSize: result.fileSize,
      itemCount: result.itemCounts.comics + result.itemCounts.bookmarks,
      type: 'export',
      fileName: result.fileName,
    });
  }, [exportData, addEntry]);

  const {
    settings: scheduleSettings,
    toggleEnabled: toggleSchedule,
    setFrequency,
    getNextBackupDate,
  } = useScheduledBackup(handleAutoBackup);

  // UI state
  const fileRef = useRef<HTMLInputElement>(null);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState('');

  // Export options
  const [exportOpts, setExportOpts] = useState<ExportOptions>({
    readingHistory: true,
    bookmarks: true,
    settings: true,
  });

  // Import progress modal
  const [importProgress, setImportProgress] = useState<{
    step: number;
    total: number;
    label: string;
    file: File;
    conflicts: ConflictItem[];
  } | null>(null);

  // Export success modal
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Export ──────────────────────────────────────────────────────────────────

  const handleExport = useCallback(() => {
    const result = exportData(exportOpts);
    addEntry({
      date: new Date().toISOString(),
      fileSize: result.fileSize,
      itemCount: result.itemCounts.comics + result.itemCounts.bookmarks,
      type: 'export',
      fileName: result.fileName,
    });
    setExportResult(result);
  }, [exportData, exportOpts, addEntry]);

  // ── Import from file ───────────────────────────────────────────────────────

  const startImport = useCallback(
    async (file: File) => {
      const onProgress: ImportProgressCallback = (step, total, label) => {
        setImportProgress((prev) => prev ? { ...prev, step, total, label } : {
          step, total, label, file, conflicts: [],
        });
      };

      setImportProgress({ step: 0, total: 5, label: 'Starting…', file, conflicts: [] });

      const result = await importData(file, onProgress);

      if (result.conflicts.length > 0) {
        setImportProgress((prev) => prev ? { ...prev, conflicts: result.conflicts, label: 'Conflicts found' } : null);
        return;
      }

      if (result.success) {
        addEntry({
          date: new Date().toISOString(),
          fileSize: file.size,
          itemCount: 0,
          type: 'import',
          fileName: file.name,
        });
        setToast({ ok: true, msg: result.message });
      } else {
        setToast({ ok: false, msg: result.message });
      }
      setImportProgress(null);
    },
    [importData, addEntry],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) startImport(file);
      if (fileRef.current) fileRef.current.value = '';
    },
    [startImport],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) startImport(file);
    },
    [startImport],
  );

  // ── Import from URL ────────────────────────────────────────────────────────

  const handleUrlImport = useCallback(async () => {
    if (!urlInput.trim()) return;
    setToast({ ok: true, msg: 'Fetching remote backup…' });
    try {
      const resp = await fetch(urlInput.trim());
      const blob = await resp.blob();
      const file = new File([blob], 'remote-backup.json', { type: 'application/json' });
      startImport(file);
    } catch {
      setToast({ ok: false, msg: 'Failed to fetch remote backup.' });
    }
  }, [urlInput, startImport]);

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      setUrlInput(text);
    } catch {
      setToast({ ok: false, msg: 'Clipboard access denied.' });
    }
  }, []);

  // ── Conflict resolution ────────────────────────────────────────────────────

  const handleResolveConflicts = useCallback(
    async (resolution: 'keep' | 'replace' | 'both') => {
      if (!importProgress) return;
      const onProgress: ImportProgressCallback = (step, total, label) => {
        setImportProgress((prev) => prev ? { ...prev, step, total, label, conflicts: [] } : null);
      };
      const result = await applyImportWithResolution(importProgress.file, resolution, onProgress);
      if (result.success) {
        addEntry({
          date: new Date().toISOString(),
          fileSize: importProgress.file.size,
          itemCount: 0,
          type: 'import',
          fileName: importProgress.file.name,
        });
        setToast({ ok: true, msg: result.message });
      } else {
        setToast({ ok: false, msg: result.message });
      }
      setImportProgress(null);
    },
    [importProgress, applyImportWithResolution, addEntry],
  );

  // ── Danger zone ────────────────────────────────────────────────────────────

  const handleClearHistory = useCallback(() => {
    if (confirm('Clear all reading history? Bookmarks will be kept.')) {
      clearHistory();
      setToast({ ok: true, msg: 'Reading history cleared!' });
    }
  }, [clearHistory]);

  const handleClearCache = useCallback(() => {
    if (confirm('Delete all downloaded chapters?')) {
      clearAllDownloads();
      setToast({ ok: true, msg: 'Cache cleared!' });
    }
  }, [clearAllDownloads]);

  const handleResetAll = useCallback(() => {
    if (confirm('⚠️ This will erase ALL your data including favorites, progress, and settings. This cannot be undone. Are you sure?')) {
      localStorage.clear();
      setToast({ ok: true, msg: 'All data reset. Reloading…' });
      setTimeout(() => window.location.reload(), 1500);
    }
  }, []);

  // ── Render ──────────────────────────────────────────────────────────────────

  const nextBackup = getNextBackupDate();

  return (
    <main className="ie-page" id="main-content">
      {/* Header */}
      <div className="ie-header">
        <button className="ie-back" onClick={() => navigate('/settings')} aria-label="Go back to Settings">
          <ArrowLeft size={18} />
        </button>
        <h1 className="ie-title">Import & Export</h1>
      </div>

      {/* ── Import Section ────────────────────────────────────────────── */}
      <section className="ie-section" aria-labelledby="ie-import-heading">
        <div className="ie-section-header">
          <Download size={16} className="ie-section-icon" />
          <h2 className="ie-section-title" id="ie-import-heading">Import Data</h2>
        </div>

        <div className="ie-grid">
          {/* Import from File */}
          <div className="ie-card">
            <h3 className="ie-card-title">
              <FileUp size={16} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Import from File
            </h3>
            <p className="ie-card-desc">
              Import library data from a JSON backup file.
            </p>
            <div className="ie-card-formats">
              <span className="ie-format-badge">JSON</span>
              <span className="ie-format-badge">ZIP</span>
            </div>
            <div
              className={`ie-file-drop${dragOver ? ' dragover' : ''}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              role="button"
              tabIndex={0}
              aria-label="Select backup file"
            >
              <Upload size={28} className="ie-file-drop-icon" />
              <span className="ie-file-drop-text">
                Tap to browse or drag file here
              </span>
              <span className="ie-file-drop-hint">
                Supports .json backup files
              </span>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json"
              onChange={handleFileSelect}
              className="sr-only"
              aria-label="Choose backup file"
            />
          </div>

          {/* Import from URL */}
          <div className="ie-card">
            <h3 className="ie-card-title">
              <Link2 size={16} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Import from URL
            </h3>
            <p className="ie-card-desc">
              Import from a remote backup URL.
            </p>
            <div className="ie-url-row">
              <input
                className="ie-url-input"
                type="url"
                placeholder="https://example.com/backup.json"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                aria-label="Backup URL"
              />
              <button className="ie-url-paste" onClick={handlePaste} aria-label="Paste from clipboard">
                <Clipboard size={14} />
                Paste
              </button>
            </div>
            {urlInput.trim() && (
              <button
                className="ie-btn ie-btn--primary"
                style={{ width: '100%', marginTop: 10 }}
                onClick={handleUrlImport}
              >
                <Download size={16} />
                Import
              </button>
            )}
          </div>

          {/* Import from Other Apps */}
          <div className="ie-card ie-full-width">
            <h3 className="ie-card-title">
              <Layers size={16} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Import from Other Apps
            </h3>
            <p className="ie-card-desc">
              Import from MAL, AniList, or Tachiyomi/Mihon backup.
            </p>
            <div className="ie-source-list">
              <button className="ie-source-btn" onClick={() => setToast({ ok: false, msg: 'MAL import coming soon!' })}>
                <span className="ie-source-dot ie-source-dot--mal" />
                MyAnimeList
              </button>
              <button className="ie-source-btn" onClick={() => setToast({ ok: false, msg: 'AniList import coming soon!' })}>
                <span className="ie-source-dot ie-source-dot--anilist" />
                AniList
              </button>
              <button className="ie-source-btn" onClick={() => setToast({ ok: false, msg: 'Tachiyomi import coming soon!' })}>
                <span className="ie-source-dot ie-source-dot--tachiyomi" />
                Tachiyomi
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Export Section ─────────────────────────────────────────────── */}
      <section className="ie-section" aria-labelledby="ie-export-heading">
        <div className="ie-section-header">
          <Upload size={16} className="ie-section-icon" />
          <h2 className="ie-section-title" id="ie-export-heading">Export Data</h2>
        </div>

        <div className="ie-grid">
          {/* Export Library */}
          <div className="ie-card">
            <h3 className="ie-card-title">Export Library</h3>
            <p className="ie-card-desc">
              Export your full library including reading progress, bookmarks, and preferences.
            </p>

            <div className="ie-toggle-list">
              <div className="ie-toggle-row">
                <span className="ie-toggle-label">
                  <span className="ie-toggle-icon">📖</span>
                  Reading History
                </span>
                <button
                  className={`ie-toggle${exportOpts.readingHistory ? ' on' : ''}`}
                  role="switch"
                  aria-checked={exportOpts.readingHistory}
                  onClick={() => setExportOpts((p) => ({ ...p, readingHistory: !p.readingHistory }))}
                >
                  <span className="ie-toggle-thumb" />
                </button>
              </div>
              <div className="ie-toggle-row">
                <span className="ie-toggle-label">
                  <span className="ie-toggle-icon">🔖</span>
                  Bookmarks
                </span>
                <button
                  className={`ie-toggle${exportOpts.bookmarks ? ' on' : ''}`}
                  role="switch"
                  aria-checked={exportOpts.bookmarks}
                  onClick={() => setExportOpts((p) => ({ ...p, bookmarks: !p.bookmarks }))}
                >
                  <span className="ie-toggle-thumb" />
                </button>
              </div>
              <div className="ie-toggle-row">
                <span className="ie-toggle-label">
                  <span className="ie-toggle-icon">⚙️</span>
                  App Settings
                </span>
                <button
                  className={`ie-toggle${exportOpts.settings ? ' on' : ''}`}
                  role="switch"
                  aria-checked={exportOpts.settings}
                  onClick={() => setExportOpts((p) => ({ ...p, settings: !p.settings }))}
                >
                  <span className="ie-toggle-thumb" />
                </button>
              </div>
            </div>

            <div className="ie-export-btns">
              <button className="ie-btn ie-btn--primary" onClick={handleExport}>
                <FileJson size={16} />
                Export JSON
              </button>
              <button className="ie-btn ie-btn--secondary" onClick={handleExport}>
                <Archive size={16} />
                Export ZIP
              </button>
            </div>
          </div>

          {/* Scheduled Backup */}
          <div className="ie-card">
            <h3 className="ie-card-title">
              <Clock size={16} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Scheduled Backup
            </h3>
            <p className="ie-card-desc">
              Auto-backup your data periodically while the app is open.
            </p>

            <div className="ie-schedule-row">
              <span className="ie-schedule-label">Enable</span>
              <button
                className={`ie-toggle${scheduleSettings.enabled ? ' on' : ''}`}
                role="switch"
                aria-checked={scheduleSettings.enabled}
                onClick={toggleSchedule}
              >
                <span className="ie-toggle-thumb" />
              </button>
            </div>

            {scheduleSettings.enabled && (
              <>
                <div className="ie-schedule-row">
                  <span className="ie-schedule-label">Frequency</span>
                  <select
                    className="ie-freq-select"
                    value={scheduleSettings.frequency}
                    onChange={(e) => setFrequency(e.target.value as BackupFrequency)}
                    aria-label="Backup frequency"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                {nextBackup && (
                  <div className="ie-next-backup">
                    <Calendar size={12} />
                    Next backup: {formatDate(nextBackup.toISOString())}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </section>

      {/* ── Data Management Section ───────────────────────────────────── */}
      <section className="ie-section" aria-labelledby="ie-data-heading">
        <div className="ie-section-header">
          <HardDrive size={16} className="ie-section-icon" />
          <h2 className="ie-section-title" id="ie-data-heading">Data Management</h2>
        </div>

        <div className="ie-grid">
          {/* Backup History */}
          <div className="ie-card">
            <h3 className="ie-card-title">Backup History</h3>
            <div className="ie-history-list">
              {backupHistory.length === 0 ? (
                <p className="ie-history-empty">No backups yet</p>
              ) : (
                backupHistory.slice(0, 3).map((entry) => (
                  <div key={entry.id} className="ie-history-item">
                    <div className="ie-history-info">
                      <span className="ie-history-date">{formatDate(entry.date)}</span>
                      <span className="ie-history-meta">
                        {entry.type === 'export' ? '↑ Export' : '↓ Import'} · {formatBytes(entry.fileSize)}
                      </span>
                    </div>
                    <div className="ie-history-actions">
                      <button
                        className="ie-history-btn"
                        onClick={() => removeEntry(entry.id)}
                        aria-label={`Remove ${entry.fileName}`}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Clear Data — Danger Zone */}
          <div className="ie-danger-card">
            <h3 className="ie-danger-title">
              <AlertTriangle size={16} />
              Danger Zone
            </h3>
            <div className="ie-danger-list">
              <button className="ie-danger-btn" onClick={handleClearHistory}>
                <Trash2 size={16} />
                Clear reading history
              </button>
              <button className="ie-danger-btn" onClick={handleClearCache}>
                <HardDrive size={16} />
                Clear cache
              </button>
              <button className="ie-danger-btn" onClick={handleResetAll}>
                <AlertTriangle size={16} />
                Reset all data
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Modals ─────────────────────────────────────────────────────── */}
      {importProgress && (
        <ImportProgress
          step={importProgress.step}
          totalSteps={importProgress.total}
          label={importProgress.label}
          fileName={importProgress.file.name}
          fileSize={importProgress.file.size}
          conflicts={importProgress.conflicts}
          onResolve={handleResolveConflicts}
          onCancel={() => setImportProgress(null)}
        />
      )}

      {exportResult && (
        <ExportSuccess
          result={exportResult}
          onDone={() => setExportResult(null)}
        />
      )}

      {/* ── Toast ──────────────────────────────────────────────────────── */}
      {toast && (
        <div className={`ie-toast ${toast.ok ? 'ie-toast--ok' : 'ie-toast--err'}`}>
          {toast.msg}
        </div>
      )}
    </main>
  );
}
