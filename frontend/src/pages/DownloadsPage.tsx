import { useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Download,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
  X,
  HardDrive,
  BookOpen,
} from 'lucide-react';
import { useDownloadManager } from '../contexts/DownloadContext';
import { useDocTitle } from '../hooks/useDocTitle';
import './DownloadsPage.css';

interface GroupedSeries {
  source: string;
  slug: string;
  title: string;
  coverUrl?: string;
  chapters: {
    number: number;
    pageCount: number;
    downloadedAt: string;
  }[];
}

export default function DownloadsPage() {
  useDocTitle('Downloads');
  const {
    downloads,
    activeDownloads,
    downloadQueue,
    cancelQueue,
    deleteChapter,
    clearAllDownloads,
  } = useDownloadManager();

  const [expandedSeries, setExpandedSeries] = useState<Set<string>>(new Set());
  const [confirmClear, setConfirmClear] = useState(false);

  // Group downloads by series
  const grouped = useMemo<GroupedSeries[]>(() => {
    const map = new Map<string, GroupedSeries>();
    for (const d of downloads) {
      const key = `${d.source}/${d.slug}`;
      if (!map.has(key)) {
        map.set(key, {
          source: d.source,
          slug: d.slug,
          title: d.title,
          chapters: [],
        });
      }
      map.get(key)!.chapters.push({
        number: d.number,
        pageCount: d.pageCount,
        downloadedAt: d.downloadedAt,
      });
    }
    // Sort chapters within each series
    for (const g of map.values()) {
      g.chapters.sort((a, b) => a.number - b.number);
    }
    return Array.from(map.values()).sort((a, b) => a.title.localeCompare(b.title));
  }, [downloads]);

  const toggleExpanded = useCallback((key: string) => {
    setExpandedSeries((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const handleClearAll = useCallback(async () => {
    await clearAllDownloads();
    setConfirmClear(false);
    setExpandedSeries(new Set());
  }, [clearAllDownloads]);

  const hasActiveDownloads = !!downloadQueue || activeDownloads.size > 0;
  const hasDownloads = downloads.length > 0;
  const isEmpty = !hasActiveDownloads && !hasDownloads;

  return (
    <main className="downloads-page fade-in" id="main-content">
      <div className="container">
        {/* Header */}
        <header className="downloads-header">
          <div className="downloads-header__left">
            <HardDrive size={22} className="downloads-header__icon" />
            <h1 className="downloads-header__title">Downloads</h1>
          </div>
          {hasDownloads && (
            <div className="downloads-header__right">
              {confirmClear ? (
                <div className="downloads-confirm-clear">
                  <span>Delete all?</span>
                  <button className="confirm-clear-yes" onClick={handleClearAll}>Yes</button>
                  <button className="confirm-clear-no" onClick={() => setConfirmClear(false)}>No</button>
                </div>
              ) : (
                <button
                  className="downloads-clear-btn"
                  onClick={() => setConfirmClear(true)}
                >
                  <Trash2 size={14} />
                  Clear All
                </button>
              )}
            </div>
          )}
        </header>

        {/* Active Downloads Section */}
        {hasActiveDownloads && (
          <section className="downloads-active-section" aria-label="Active downloads">
            <h2 className="downloads-section-title">
              <Loader2 size={16} className="dl-spin" />
              Active Downloads
            </h2>

            {/* Global queue progress */}
            {downloadQueue && (
              <div className="dl-queue-banner glass-card">
                <div className="dl-queue-banner__info">
                  <Download size={16} className="dl-queue-banner__icon" />
                  <div className="dl-queue-banner__text">
                    <span className="dl-queue-banner__title">{downloadQueue.comicTitle}</span>
                    <span className="dl-queue-banner__sub">
                      Downloading chapter {downloadQueue.completed + 1} of {downloadQueue.total}
                    </span>
                  </div>
                </div>
                <div className="dl-queue-banner__bar">
                  <div
                    className="dl-queue-banner__fill"
                    style={{ width: `${downloadQueue.pct}%` }}
                  />
                </div>
                <button
                  className="dl-queue-banner__cancel"
                  onClick={cancelQueue}
                  aria-label="Cancel download queue"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Per-chapter active downloads */}
            {activeDownloads.size > 0 && (
              <div className="dl-active-list">
                {Array.from(activeDownloads.entries()).map(([key, progress]) => {
                  const parts = key.split('/');
                  const chNum = parts[parts.length - 1];
                  return (
                    <div key={key} className="dl-active-card glass-card">
                      <div className="dl-active-card__info">
                        <Loader2 size={14} className="dl-spin" />
                        <span className="dl-active-card__chapter">Ch. {chNum}</span>
                      </div>
                      <div className="dl-active-card__progress">
                        <div className="dl-active-card__bar">
                          <div
                            className="dl-active-card__fill"
                            style={{ width: `${progress.pct}%` }}
                          />
                        </div>
                        <span className="dl-active-card__count">
                          {progress.loaded}/{progress.total} pages
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* Downloaded Comics Section */}
        {hasDownloads && (
          <section className="downloads-completed-section" aria-label="Downloaded comics">
            <h2 className="downloads-section-title">
              <Download size={16} />
              Downloaded
              <span className="downloads-section-badge">{downloads.length} chapters</span>
            </h2>

            <div className="dl-series-list">
              {grouped.map((series) => {
                const seriesKey = `${series.source}/${series.slug}`;
                const isExpanded = expandedSeries.has(seriesKey);
                const detailUrl = `/comic/${encodeURIComponent(series.source)}/${encodeURIComponent(series.slug)}`;

                return (
                  <div key={seriesKey} className="dl-series-card glass-card">
                    <button
                      className="dl-series-header"
                      onClick={() => toggleExpanded(seriesKey)}
                      aria-expanded={isExpanded}
                    >
                      <div className="dl-series-info">
                        <div className="dl-series-title-row">
                          <Link
                            to={detailUrl}
                            className="dl-series-title"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {series.title}
                          </Link>
                        </div>
                        <span className="dl-series-meta">
                          {series.chapters.length} chapter{series.chapters.length !== 1 ? 's' : ''} offline
                        </span>
                      </div>
                      {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>

                    {isExpanded && (
                      <ul className="dl-chapter-list">
                        {series.chapters.map((ch) => (
                          <li key={ch.number} className="dl-chapter-item">
                            <Link
                              to={`${detailUrl}/chapter/${ch.number}`}
                              className="dl-chapter-link"
                            >
                              <span className="dl-chapter-num">Chapter {ch.number}</span>
                              <span className="dl-chapter-meta">
                                {ch.pageCount} pages
                                <span className="dl-chapter-date">
                                  {new Date(ch.downloadedAt).toLocaleDateString()}
                                </span>
                              </span>
                            </Link>
                            <button
                              className="dl-chapter-delete"
                              onClick={() => deleteChapter(series.source, series.slug, ch.number)}
                              aria-label={`Delete chapter ${ch.number}`}
                            >
                              <Trash2 size={14} />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Empty State */}
        {isEmpty && (
          <div className="downloads-empty">
            <div className="downloads-empty__icon">
              <BookOpen size={48} />
            </div>
            <h2 className="downloads-empty__title">No downloads yet</h2>
            <p className="downloads-empty__text">
              Download chapters from any comic's detail page to read offline.
            </p>
            <Link to="/search" className="downloads-empty__cta">
              Browse Comics
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
