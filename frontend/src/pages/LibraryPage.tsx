import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Heart, Download, Trash2, ChevronDown } from 'lucide-react';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useFavorites } from '../hooks/useFavorites';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import { useDocTitle } from '../hooks/useDocTitle';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import './LibraryPage.css';

// ── Helpers ────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  const secs = Math.floor((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1_073_741_824) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
}

type Tab = 'reading' | 'favorites' | 'downloaded';

// ── Component ──────────────────────────────────────────────────────────────

export default function LibraryPage() {
  useDocTitle('My Library — ComicCrawler');

  const [activeTab, setActiveTab] = useState<Tab>('reading');
  const { recentlyRead } = useReadingProgress();
  const { favorites } = useFavorites();
  const { downloads, deleteChapter, clearAllDownloads } = useOfflineChapters();

  // Storage estimate
  const [storageEstimate, setStorageEstimate] = useState<{
    usage: number;
    quota: number;
  } | null>(null);

  useEffect(() => {
    if (navigator.storage?.estimate) {
      navigator.storage.estimate().then((est) => {
        setStorageEstimate({
          usage: est.usage ?? 0,
          quota: est.quota ?? 0,
        });
      });
    }
  }, [downloads.length]);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'reading', label: 'Reading', count: recentlyRead.length },
    { key: 'favorites', label: 'Favorites', count: favorites.length },
    { key: 'downloaded', label: 'Downloaded', count: downloads.length },
  ];

  return (
    <main className="library-page" id="main-content">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="library-header">
        <h1 className="library-header__title">My Library</h1>
      </header>

      {/* ── Tabs ───────────────────────────────────────────────── */}
      <div className="library-tabs" role="tablist" aria-label="Library sections">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`library-tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
            <span className="library-tab__count">({tab.count})</span>
          </button>
        ))}
      </div>

      {/* ── Tab content ────────────────────────────────────────── */}
      <div className="library-content" key={activeTab} role="tabpanel">
        {activeTab === 'reading' && (
          <ReadingTab entries={recentlyRead} />
        )}
        {activeTab === 'favorites' && (
          <FavoritesTab entries={favorites} />
        )}
        {activeTab === 'downloaded' && (
          <DownloadedTab
            downloads={downloads}
            onDelete={deleteChapter}
            onClearAll={clearAllDownloads}
          />
        )}
      </div>

      {/* ── Storage footer ─────────────────────────────────────── */}
      {storageEstimate && storageEstimate.quota > 0 && (
        <div className="library-storage">
          <span className="library-storage__label">Storage</span>
          <div className="library-storage__bar-wrap">
            <div className="library-storage__bar">
              <div
                className="library-storage__bar-fill"
                style={{
                  width: `${Math.min(100, (storageEstimate.usage / storageEstimate.quota) * 100)}%`,
                }}
              />
            </div>
            <span className="library-storage__usage">
              {formatBytes(storageEstimate.usage)} / {formatBytes(storageEstimate.quota)}
            </span>
          </div>
          <button
            className="library-storage__clear-btn"
            onClick={() => {
              if (confirm('Clear all cached data?')) {
                clearAllDownloads();
              }
            }}
          >
            Clear Cache
          </button>
        </div>
      )}
    </main>
  );
}

// ── Reading Tab ────────────────────────────────────────────────────────────

function ReadingTab({ entries }: { entries: ReturnType<typeof useReadingProgress>['recentlyRead'] }) {
  if (entries.length === 0) {
    return (
      <div className="library-empty">
        <BookOpen size={40} className="library-empty__icon" />
        <p className="library-empty__text">No reading history yet</p>
        <p className="library-empty__sub">
          Comics you read will appear here so you can quickly pick up where you left off.
        </p>
      </div>
    );
  }

  return (
    <div className="library-list">
      {entries.map((entry) => {
        const coverSrc = proxyImageUrl(entry.cover_url) ?? undefined;
        const href = `/comic/${encodeURIComponent(entry.source)}/${encodeURIComponent(entry.slug)}`;
        const progressPct = Math.min(100, (entry.lastChapter / Math.max(entry.lastChapter + 5, 20)) * 100);

        return (
          <Link key={`${entry.source}:${entry.slug}`} to={href} className="library-card">
            <div className="library-card__cover-wrap">
              {coverSrc ? (
                <img
                  src={coverSrc}
                  alt=""
                  className="library-card__cover"
                  loading="lazy"
                  crossOrigin={isCorsReady(coverSrc) ? 'anonymous' : undefined}
                />
              ) : (
                <div className="library-card__cover-placeholder" />
              )}
            </div>
            <div className="library-card__info">
              <span className="library-card__title">{entry.title}</span>
              <span className="library-card__source">{entry.source}</span>
              <span className="library-card__meta">
                Last read: Ch. {entry.lastChapter} • {timeAgo(entry.visitedAt)}
              </span>
            </div>
            <div className="library-card__progress">
              <div
                className="library-card__progress-fill"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </Link>
        );
      })}
    </div>
  );
}

// ── Favorites Tab ──────────────────────────────────────────────────────────

function FavoritesTab({ entries }: { entries: ReturnType<typeof useFavorites>['favorites'] }) {
  if (entries.length === 0) {
    return (
      <div className="library-empty">
        <Heart size={40} className="library-empty__icon" />
        <p className="library-empty__text">No favorites yet</p>
        <p className="library-empty__sub">
          Tap the heart icon on any comic to save it to your favorites.
        </p>
      </div>
    );
  }

  return (
    <div className="library-list">
      {entries.map((fav) => {
        const coverSrc = proxyImageUrl(fav.cover_url) ?? undefined;
        const href = `/comic/${encodeURIComponent(fav.source)}/${encodeURIComponent(fav.slug)}`;

        return (
          <Link key={`${fav.source}:${fav.slug}`} to={href} className="library-card">
            <div className="library-card__cover-wrap">
              {coverSrc ? (
                <img
                  src={coverSrc}
                  alt=""
                  className="library-card__cover"
                  loading="lazy"
                  crossOrigin={isCorsReady(coverSrc) ? 'anonymous' : undefined}
                />
              ) : (
                <div className="library-card__cover-placeholder" />
              )}
            </div>
            <div className="library-card__info">
              <span className="library-card__title">{fav.title}</span>
              <span className="library-card__source">{fav.source}</span>
              <span className="library-card__meta">
                Added {timeAgo(fav.addedAt)}
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

// ── Downloaded Tab ─────────────────────────────────────────────────────────

interface DownloadedGroup {
  source: string;
  slug: string;
  title: string;
  chapters: { number: number; pageCount: number; downloadedAt: string }[];
}

function groupDownloads(
  downloads: { source: string; slug: string; number: number; title: string; pageCount: number; downloadedAt: string }[]
): DownloadedGroup[] {
  const map = new Map<string, DownloadedGroup>();
  for (const d of downloads) {
    const key = `${d.source}/${d.slug}`;
    let group = map.get(key);
    if (!group) {
      group = { source: d.source, slug: d.slug, title: d.title, chapters: [] };
      map.set(key, group);
    }
    group.chapters.push({ number: d.number, pageCount: d.pageCount, downloadedAt: d.downloadedAt });
  }
  // Sort chapters within each group
  for (const g of map.values()) {
    g.chapters.sort((a, b) => a.number - b.number);
  }
  return Array.from(map.values());
}

function DownloadedTab({
  downloads,
  onDelete,
  onClearAll,
}: {
  downloads: { source: string; slug: string; number: number; title: string; pageCount: number; downloadedAt: string }[];
  onDelete: (source: string, slug: string, number: number) => void;
  onClearAll: () => void;
}) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  if (downloads.length === 0) {
    return (
      <div className="library-empty">
        <Download size={40} className="library-empty__icon" />
        <p className="library-empty__text">No downloaded chapters</p>
        <p className="library-empty__sub">
          Download chapters while reading to enjoy them offline.
        </p>
      </div>
    );
  }

  const groups = groupDownloads(downloads);

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const deleteGroup = (group: DownloadedGroup) => {
    if (confirm(`Delete all ${group.chapters.length} downloaded chapters of "${group.title}"?`)) {
      for (const ch of group.chapters) {
        onDelete(group.source, group.slug, ch.number);
      }
    }
  };

  return (
    <div className="library-list">
      {groups.map((group) => {
        const key = `${group.source}/${group.slug}`;
        const expanded = expandedGroups.has(key);
        const comicHref = `/comic/${encodeURIComponent(group.source)}/${encodeURIComponent(group.slug)}`;

        return (
          <div key={key} className="dl-group">
            {/* Group header */}
            <div className="dl-group__header">
              <button
                className="dl-group__toggle"
                onClick={() => toggleGroup(key)}
                aria-expanded={expanded}
              >
                <div className="dl-group__info">
                  <span className="dl-group__title">{group.title}</span>
                  <span className="dl-group__meta">
                    {group.source} · {group.chapters.length} chapter{group.chapters.length !== 1 ? 's' : ''}
                  </span>
                </div>
                <ChevronDown
                  size={14}
                  className={`dl-group__chevron${expanded ? ' dl-group__chevron--open' : ''}`}
                />
              </button>
              <button
                className="library-card__delete-btn"
                onClick={() => deleteGroup(group)}
                aria-label={`Delete all chapters of ${group.title}`}
                title="Delete all"
              >
                <Trash2 size={14} />
              </button>
            </div>

            {/* Expanded chapter list */}
            {expanded && (
              <div className="dl-group__chapters">
                {group.chapters.map((ch) => {
                  const href = `${comicHref}/chapter/${ch.number}`;
                  return (
                    <div key={ch.number} className="dl-chapter">
                      <Link to={href} className="dl-chapter__link">
                        <span className="dl-chapter__num">Ch. {ch.number}</span>
                        <span className="dl-chapter__pages">{ch.pageCount}p</span>
                      </Link>
                      <button
                        className="library-card__delete-btn"
                        onClick={() => onDelete(group.source, group.slug, ch.number)}
                        aria-label={`Delete chapter ${ch.number}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {downloads.length > 1 && (
        <button
          className="library-storage__clear-btn"
          style={{ alignSelf: 'center', marginTop: 8 }}
          onClick={() => {
            if (confirm('Delete all downloaded chapters?')) {
              onClearAll();
            }
          }}
        >
          <Trash2 size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
          Clear All Downloads
        </button>
      )}
    </div>
  );
}
