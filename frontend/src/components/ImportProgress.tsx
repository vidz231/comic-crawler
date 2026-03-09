import { AlertTriangle } from 'lucide-react';
import type { ConflictItem } from '../hooks/useDataBackup';
import './ImportProgress.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

const STEP_LABELS = [
  'Validating backup file',
  'Scanning for conflicts',
  'Importing comics',
  'Importing bookmarks',
  'Importing preferences',
];

// ── Component ─────────────────────────────────────────────────────────────────

interface ImportProgressProps {
  step: number;
  totalSteps: number;
  label: string;
  fileName: string;
  fileSize: number;
  conflicts: ConflictItem[];
  onResolve: (resolution: 'keep' | 'replace' | 'both') => void;
  onCancel: () => void;
}

export default function ImportProgress({
  step,
  totalSteps,
  label,
  fileName,
  fileSize,
  conflicts,
  onResolve,
  onCancel,
}: ImportProgressProps) {
  const pct = Math.round((step / totalSteps) * 100);
  const circumference = 2 * Math.PI * 42; // r=42
  const offset = circumference - (pct / 100) * circumference;
  const hasConflicts = conflicts.length > 0;

  return (
    <div className="ip-overlay" role="dialog" aria-label="Import progress">
      <div className="ip-card">
        {/* Circular progress ring */}
        <div className="ip-ring-wrap">
          <div className="ip-ring">
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle className="ip-ring-bg" cx="50" cy="50" r="42" />
              <circle
                className="ip-ring-fill"
                cx="50" cy="50" r="42"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
              />
            </svg>
            <span className="ip-ring-pct">{pct}%</span>
          </div>
        </div>

        <h2 className="ip-title">
          {hasConflicts ? 'Conflicts Found' : 'Importing Data…'}
        </h2>
        <p className="ip-label">{label}</p>

        {/* Step list */}
        {!hasConflicts && (
          <div className="ip-steps">
            {STEP_LABELS.map((lbl, i) => {
              const stepNum = i + 1;
              const done = stepNum < step;
              const active = stepNum === step;
              const cls = done ? 'ip-step--done' : active ? 'ip-step--active' : 'ip-step--pending';
              return (
                <div key={i} className={`ip-step ${cls}`}>
                  <span className="ip-step-icon">
                    {done ? '✓' : active ? <span className="ip-spinner">⟳</span> : '○'}
                  </span>
                  {lbl}
                </div>
              );
            })}
          </div>
        )}

        {/* File info */}
        <div className="ip-file-info">
          <span className="ip-file-name">{fileName}</span>
          <span className="ip-file-size">{formatBytes(fileSize)}</span>
        </div>

        {/* Conflict resolution */}
        {hasConflicts && (
          <div className="ip-conflict-card">
            <h3 className="ip-conflict-title">
              <AlertTriangle size={14} />
              {conflicts.length} conflict{conflicts.length !== 1 ? 's' : ''} found
            </h3>
            {conflicts.slice(0, 3).map((c) => (
              <div key={c.key} className="ip-conflict-item">
                <span className="ip-conflict-name">{c.title}</span>
                <span className="ip-conflict-detail">
                  Existing: Ch.{String(c.existingValue)} → Imported: Ch.{String(c.importedValue)}
                </span>
              </div>
            ))}
            {conflicts.length > 3 && (
              <p className="ip-conflict-detail" style={{ paddingTop: 4 }}>
                +{conflicts.length - 3} more conflicts
              </p>
            )}
            <div className="ip-conflict-actions">
              <button className="ip-conflict-btn" onClick={() => onResolve('keep')}>
                Keep Existing
              </button>
              <button className="ip-conflict-btn ip-conflict-btn--primary" onClick={() => onResolve('both')}>
                Keep Both
              </button>
              <button className="ip-conflict-btn" onClick={() => onResolve('replace')}>
                Use Imported
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="ip-footer">
          <span className="ip-warning">
            ⚠️ Do not close the app
          </span>
          <button className="ip-cancel" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
