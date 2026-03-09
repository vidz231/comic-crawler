import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sun,
  Download,
  Trash2,
  HardDrive,
  Smartphone,
  Github,
  Type,
  ChevronRight,
} from 'lucide-react';
import { useReaderSettings } from '../hooks/useReaderSettings';
import { useAppearance } from '../hooks/useAppearance';
import type { Theme } from '../hooks/useAppearance';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import { useInstallPrompt } from '../hooks/useInstallPrompt';
import { useDocTitle } from '../hooks/useDocTitle';
import './SettingsPage.css';

// ── Storage estimate helpers ──────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1_073_741_824) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  useDocTitle('Settings');
  const navigate = useNavigate();

  // ── Reader settings (shared with ReaderSettingsPanel via useSyncExternalStore) ─
  const { settings, setSettings } = useReaderSettings();

  // ── Appearance (shared globally — applies data-theme + font-size to <html>) ─
  const { theme, textSize, setTheme, setTextSize } = useAppearance();

  // ── Data & Storage ────────────────────────────────────────────────────────
  const { clearHistory } = useReadingProgress();
  const { canInstall, isInstalled, installApp } = useInstallPrompt();
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const { clearAllDownloads } = useOfflineChapters();

  const [storageEst, setStorageEst] = useState<{ usage: number; quota: number } | null>(null);
  useEffect(() => {
    if (navigator.storage?.estimate) {
      navigator.storage.estimate().then((est) =>
        setStorageEst({ usage: est.usage ?? 0, quota: est.quota ?? 0 })
      );
    }
  }, []);

  const handleClearCache = useCallback(() => {
    if (confirm('Delete all downloaded chapters?')) {
      clearAllDownloads();
      setToast({ ok: true, msg: 'Cache cleared!' });
      // Re-estimate
      navigator.storage?.estimate?.().then((est) =>
        setStorageEst({ usage: est.usage ?? 0, quota: est.quota ?? 0 })
      );
    }
  }, [clearAllDownloads]);

  const handleClearHistory = useCallback(() => {
    if (confirm('Clear all reading history? Bookmarks will be kept.')) {
      clearHistory();
      setToast({ ok: true, msg: 'Reading history cleared!' });
    }
  }, [clearHistory]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <main className="settings-page" id="main-content">
      {/* Header */}
      <div className="settings-header">
        <h1 className="settings-title">Settings</h1>
      </div>

      {/* ── Reader Preferences ─────────────────────────────────────────────── */}
      <section className="settings-section" aria-labelledby="settings-reader-heading">
        <h2 className="settings-section-title" id="settings-reader-heading">
          Reader Preferences
        </h2>

        {/* Reading Mode */}
        <div className="setting-row">
          <span className="setting-label">Reading Mode</span>
          <div className="segmented-control">
            <button
              className={`segmented-btn${settings.readingMode === 'strip' ? ' active' : ''}`}
              onClick={() => setSettings({ readingMode: 'strip' })}
              aria-pressed={settings.readingMode === 'strip'}
            >
              Webtoon
            </button>
            <button
              className={`segmented-btn${settings.readingMode === 'paged' ? ' active' : ''}`}
              onClick={() => setSettings({ readingMode: 'paged' })}
              aria-pressed={settings.readingMode === 'paged'}
            >
              Paged
            </button>
          </div>
        </div>

        {/* Auto-advance */}
        <div className="setting-row setting-row--inline">
          <span className="setting-label">Auto-advance chapters</span>
          <button
            className={`toggle-switch${settings.autoAdvance ? ' on' : ''}`}
            role="switch"
            aria-checked={settings.autoAdvance}
            onClick={() => setSettings({ autoAdvance: !settings.autoAdvance })}
          >
            <span className="toggle-thumb" />
          </button>
        </div>

        {/* Image Quality */}
        <div className="setting-row">
          <span className="setting-label">Image Quality</span>
          <div className="segmented-control">
            {(['low', 'medium', 'high'] as const).map((q) => (
              <button
                key={q}
                className={`segmented-btn${settings.imageQuality === q ? ' active' : ''}`}
                onClick={() => setSettings({ imageQuality: q })}
                aria-pressed={settings.imageQuality === q}
              >
                {q.charAt(0).toUpperCase() + q.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Brightness */}
        <div className="setting-row">
          <span className="setting-label">Brightness</span>
          <div className="setting-slider-row">
            <Sun size={16} className="setting-slider-icon" />
            <input
              type="range"
              min={50}
              max={130}
              step={5}
              value={settings.brightness}
              onChange={(e) => setSettings({ brightness: Number(e.target.value) })}
              className="setting-slider"
              aria-label="Brightness"
            />
            <span className="setting-slider-value">{settings.brightness}%</span>
          </div>
        </div>
      </section>

      {/* ── Appearance ─────────────────────────────────────────────────────── */}
      <section className="settings-section" aria-labelledby="settings-appearance-heading">
        <h2 className="settings-section-title" id="settings-appearance-heading">
          Appearance
        </h2>

        {/* Theme */}
        <div className="setting-row">
          <span className="setting-label">Theme</span>
          <div className="segmented-control">
            {([
              { key: 'light' as Theme, label: 'Light' },
              { key: 'dark' as Theme, label: 'Dark' },
              { key: 'oled' as Theme, label: 'OLED Black' },
            ]).map(({ key, label }) => (
              <button
                key={key}
                className={`segmented-btn${theme === key ? ' active' : ''}`}
                onClick={() => setTheme(key)}
                aria-pressed={theme === key}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Text Size */}
        <div className="setting-row">
          <span className="setting-label">Text Size</span>
          <div className="setting-slider-row">
            <Type size={14} className="setting-slider-icon" />
            <input
              type="range"
              min={80}
              max={140}
              step={5}
              value={textSize}
              onChange={(e) => setTextSize(Number(e.target.value))}
              className="setting-slider"
              aria-label="Text size"
            />
            <span className="setting-slider-value">{textSize}%</span>
          </div>
        </div>
      </section>

      {/* ── Data & Storage ─────────────────────────────────────────────────── */}
      <section className="settings-section" aria-labelledby="settings-data-heading">
        <h2 className="settings-section-title" id="settings-data-heading">
          Data & Storage
        </h2>

        {/* Import & Export navigation card */}
        <button
          className="settings-nav-card"
          onClick={() => navigate('/settings/import-export')}
        >
          <div className="settings-nav-card-left">
            <Download size={16} />
            <div>
              <span className="settings-nav-card-title">Import & Export</span>
              <span className="settings-nav-card-desc">Backup, restore, and manage your data</span>
            </div>
          </div>
          <ChevronRight size={16} className="settings-nav-card-arrow" />
        </button>

        {/* Cache */}
        <div className="settings-cache-row">
          <div className="settings-cache-info">
            <span className="settings-cache-label">
              <HardDrive size={14} style={{ verticalAlign: '-2px', marginRight: 6 }} />
              Cache size
            </span>
            <span className="settings-cache-value">
              {storageEst ? `${formatBytes(storageEst.usage)} used` : 'Calculating…'}
            </span>
          </div>
          <button className="settings-clear-btn" onClick={handleClearCache}>
            Clear
          </button>
        </div>

        {/* Clear History */}
        <button className="settings-danger-btn" onClick={handleClearHistory}>
          <Trash2 size={16} />
          Clear reading history
        </button>

        {/* Toast */}
        {toast && (
          <div className={`settings-toast ${toast.ok ? 'settings-toast--ok' : 'settings-toast--err'}`}>
            {toast.msg}
          </div>
        )}
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="settings-footer">
        <span className="settings-version">Comic Crawler v1.0.0</span>

        {!isInstalled && (
          <button
            className="settings-install-btn"
            onClick={installApp}
            disabled={!canInstall}
          >
            <Smartphone size={18} />
            Install as App
          </button>
        )}

        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="settings-github-link"
        >
          <Github size={16} />
          View on GitHub
        </a>
      </footer>
    </main>
  );
}
