import { useState, useId } from 'react';
import { Settings, X, BookOpen, Columns2 } from 'lucide-react';
import type { ReaderSettings } from '../hooks/useReaderSettings';

interface ReaderSettingsPanelProps {
  settings: ReaderSettings;
  defaults: ReaderSettings;
  onUpdate: (update: Partial<ReaderSettings>) => void;
  onReset: () => void;
}

/**
 * Floating gear FAB + slide-out settings drawer for reader display preferences.
 * Controls image width, brightness, fit-width, page gap, and reading mode.
 */
export default function ReaderSettingsPanel({
  settings,
  defaults,
  onUpdate,
  onReset,
}: ReaderSettingsPanelProps) {
  const [open, setOpen] = useState(false);
  const widthId = useId();
  const brightnessId = useId();
  const gapId = useId();

  const hasChanges =
    settings.imageWidth !== defaults.imageWidth ||
    settings.brightness !== defaults.brightness ||
    settings.fitWidth !== defaults.fitWidth ||
    settings.pageGap !== defaults.pageGap ||
    settings.readingMode !== defaults.readingMode ||
    settings.autoAdvance !== defaults.autoAdvance;

  return (
    <>
      {/* Settings FAB */}
      <button
        className="reader-fab reader-fab--settings"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open reading settings"
        aria-expanded={open}
        title="Reader settings"
      >
        <Settings size={18} />
      </button>

      {/* Drawer backdrop */}
      {open && (
        <div
          className="reader-settings-backdrop"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Settings drawer */}
      <aside className={`reader-settings-panel glass${open ? ' open' : ''}`} aria-label="Reader settings">
        <div className="reader-settings-header">
          <span className="reader-settings-title">Display Settings</span>
          <button
            className="reader-settings-close"
            onClick={() => setOpen(false)}
            aria-label="Close settings"
          >
            <X size={16} />
          </button>
        </div>

        <div className="reader-settings-body">
          {/* Reading Mode */}
          <div className="reader-setting-row">
            <span className="reader-setting-label">Reading Mode</span>
            <div className="reader-setting-toggle-group">
              <button
                className={`reader-setting-toggle${settings.readingMode === 'strip' ? ' active' : ''}`}
                onClick={() => onUpdate({ readingMode: 'strip' })}
                aria-pressed={settings.readingMode === 'strip'}
              >
                <BookOpen size={14} />
                Strip
              </button>
              <button
                className={`reader-setting-toggle${settings.readingMode === 'paged' ? ' active' : ''}`}
                onClick={() => onUpdate({ readingMode: 'paged' })}
                aria-pressed={settings.readingMode === 'paged'}
              >
                <Columns2 size={14} />
                Paged
              </button>
            </div>
          </div>

          {/* Fit to Width */}
          <div className="reader-setting-row reader-setting-row--inline">
            <span className="reader-setting-label">Fit to Width</span>
            <button
              className={`reader-setting-switch${settings.fitWidth ? ' on' : ''}`}
              onClick={() => onUpdate({ fitWidth: !settings.fitWidth })}
              role="switch"
              aria-checked={settings.fitWidth}
            >
              <span className="reader-setting-switch-thumb" />
            </button>
          </div>

          {/* Auto Advance */}
          <div className="reader-setting-row reader-setting-row--inline">
            <span className="reader-setting-label">Auto Advance</span>
            <button
              className={`reader-setting-switch${settings.autoAdvance ? ' on' : ''}`}
              onClick={() => onUpdate({ autoAdvance: !settings.autoAdvance })}
              role="switch"
              aria-checked={settings.autoAdvance}
            >
              <span className="reader-setting-switch-thumb" />
            </button>
          </div>

          {/* Image Width — only shown when fitWidth is off */}
          {!settings.fitWidth && (
            <div className="reader-setting-row">
              <label htmlFor={widthId} className="reader-setting-label">
                Image Width
                <span className="reader-setting-value">{settings.imageWidth}px</span>
              </label>
              <input
                id={widthId}
                type="range"
                min={600}
                max={1400}
                step={50}
                value={settings.imageWidth}
                onChange={(e) => onUpdate({ imageWidth: Number(e.target.value) })}
                className="reader-setting-slider"
              />
              <div className="reader-setting-hints">
                <span>600</span><span>1400</span>
              </div>
            </div>
          )}

          {/* Brightness */}
          <div className="reader-setting-row">
            <label htmlFor={brightnessId} className="reader-setting-label">
              Brightness
              <span className="reader-setting-value">{settings.brightness}%</span>
            </label>
            <input
              id={brightnessId}
              type="range"
              min={50}
              max={130}
              step={5}
              value={settings.brightness}
              onChange={(e) => onUpdate({ brightness: Number(e.target.value) })}
              className="reader-setting-slider"
            />
            <div className="reader-setting-hints">
              <span>50%</span><span>130%</span>
            </div>
          </div>

          {/* Page Gap */}
          <div className="reader-setting-row">
            <label htmlFor={gapId} className="reader-setting-label">
              Page Gap
              <span className="reader-setting-value">{settings.pageGap}px</span>
            </label>
            <input
              id={gapId}
              type="range"
              min={0}
              max={32}
              step={2}
              value={settings.pageGap}
              onChange={(e) => onUpdate({ pageGap: Number(e.target.value) })}
              className="reader-setting-slider"
            />
            <div className="reader-setting-hints">
              <span>0</span><span>32px</span>
            </div>
          </div>

          {/* Reset */}
          {hasChanges && (
            <button className="reader-settings-reset" onClick={onReset}>
              Reset to defaults
            </button>
          )}
        </div>
      </aside>
    </>
  );
}

