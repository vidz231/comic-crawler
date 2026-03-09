import { useState, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  BookOpen,
  User,
  Tag,
  Hash,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  CheckCircle,
  Heart,
  Download,
  Loader2,
  Play,
  X,
  CheckSquare,
  Square,
} from 'lucide-react';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useFavorites } from '../hooks/useFavorites';
import { useComicDetail, makeChapterLink } from '../hooks/useComicDetail';
import { useDocTitle } from '../hooks/useDocTitle';
import { proxyImageUrl } from '../utils/imageProxy';
import { fetchRecommendations, fetchChapter } from '../api/endpoints';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import ComicCard from '../components/ComicCard';
import DetailSkeleton from '../components/DetailSkeleton';
import ErrorMessage from '../components/ErrorMessage';
import PullToRefreshContainer from '../components/PullToRefreshContainer';
import './ComicDetailPage.css';

export default function ComicDetailPage() {
  const { source = '', slug = '' } = useParams<{ source: string; slug: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [synopsisOpen, setSynopsisOpen] = useState(false);
  const [chapterSortAsc, setChapterSortAsc] = useState(false);

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedChapters, setSelectedChapters] = useState<Set<number>>(new Set());

  const { getLastChapter, isChapterRead } = useReadingProgress();
  const { toggleFavorite, isFavorite } = useFavorites();
  const {
    isChapterDownloaded,
    downloadChapter,
    activeDownloads,
    downloadQueue,
    downloadMultipleChapters,
    cancelQueue,
  } = useOfflineChapters();
  const favorited = isFavorite(source, slug);

  const { data, isLoading, isError, error } = useComicDetail(source, slug);

  // Dynamic page title — uses series title once loaded, placeholder while loading
  useDocTitle(data ? data.series.title : 'Loading…');

  const handleRefresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['comicDetail', source, slug] });
    await queryClient.invalidateQueries({ queryKey: ['recommendations', source, slug] });
  }, [queryClient, source, slug]);

  // ── Selection mode helpers ──────────────────────────────────────────────────

  const chapters = useMemo(() => data?.chapters ?? [], [data?.chapters]);

  const enterSelectionMode = useCallback(() => {
    // Pre-select all non-downloaded chapters
    const notDownloaded = chapters
      .filter((ch) => !isChapterDownloaded(source, slug, ch.number))
      .map((ch) => ch.number);
    setSelectedChapters(new Set(notDownloaded));
    setSelectionMode(true);
  }, [chapters, isChapterDownloaded, source, slug]);

  const exitSelectionMode = useCallback(() => {
    setSelectionMode(false);
    setSelectedChapters(new Set());
  }, []);

  const toggleChapterSelection = useCallback((chapterNum: number) => {
    setSelectedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterNum)) {
        next.delete(chapterNum);
      } else {
        next.add(chapterNum);
      }
      return next;
    });
  }, []);

  const selectableChapters = useMemo(
    () => chapters.filter((ch) => !isChapterDownloaded(source, slug, ch.number)),
    [chapters, isChapterDownloaded, source, slug]
  );

  const allSelected = selectableChapters.length > 0 &&
    selectableChapters.every((ch) => selectedChapters.has(ch.number));

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedChapters(new Set());
    } else {
      setSelectedChapters(new Set(selectableChapters.map((ch) => ch.number)));
    }
  }, [allSelected, selectableChapters]);

  const handleDownloadSelected = useCallback(async () => {
    if (!data || selectedChapters.size === 0) return;

    const descriptors = Array.from(selectedChapters)
      .sort((a, b) => a - b)
      .map((num) => ({
        number: num,
        fetchPages: async () => {
          const chData = await fetchChapter(source, slug, num);
          return chData.pages.map((p) => p.image_url);
        },
      }));

    setSelectionMode(false);
    setSelectedChapters(new Set());

    await downloadMultipleChapters(source, slug, data.series.title, descriptors);
  }, [data, selectedChapters, source, slug, downloadMultipleChapters]);

  // ── Render guards ───────────────────────────────────────────────────────────

  if (isLoading) return <DetailSkeleton />;
  if (isError || !data)
    return (
      <div className="container" style={{ paddingTop: 40 }}>
        <ErrorMessage message={(error as Error)?.message ?? 'Failed to load comic.'} />
      </div>
    );

  const { series } = data;
  const sortedChapters = [...chapters].sort((a, b) =>
    chapterSortAsc
      ? Number(a.number) - Number(b.number)
      : Number(b.number) - Number(a.number)
  );

  const lastChapter = getLastChapter(source, slug);
  const continueLink = lastChapter != null
    ? `/comic/${encodeURIComponent(source)}/${encodeURIComponent(slug)}/chapter/${lastChapter}`
    : null;

  // First & latest chapter numbers for quick-jump buttons
  const chapterNumbers = chapters.map((c) => Number(c.number)).sort((a, b) => a - b);
  const firstChapterNum = chapterNumbers[0];
  const latestChapterNum = chapterNumbers[chapterNumbers.length - 1];
  const mkLink = (num: number) => makeChapterLink(source, slug, num);

  // Safe back: if there is history within the SPA go back, otherwise go home
  const canGoBack = (window.history.state?.idx ?? 0) > 0;

  return (
    <>
    <PullToRefreshContainer onRefresh={handleRefresh} as="main" className="detail-page fade-in" id="main-content">
      {/* Blurred Cover Banner */}
      {series.cover_url && (
        <div className="detail-cover-banner">
          <img
            src={proxyImageUrl(series.cover_url) ?? undefined}
            alt=""
            className="detail-cover-banner__bg"
            aria-hidden="true"
          />
          <div className="detail-cover-banner__gradient" />
        </div>
      )}

      <div className="container">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="detail-breadcrumb">
          <ol className="breadcrumb-list">
            <li><Link to="/">Browse</Link></li>
            <li aria-current="page">{data.series.title}</li>
          </ol>
        </nav>

        {/* Back button */}
        <button
          className="detail-back"
          onClick={() => canGoBack ? navigate(-1) : navigate('/')}
          aria-label="Go back"
        >
          <ArrowLeft size={16} />
          Back
        </button>

        {/* Header */}
        <div className="detail-header">
          <div className="detail-cover-wrap">
            {series.cover_url ? (
              <img src={proxyImageUrl(series.cover_url) ?? undefined} alt={`Cover for ${series.title}`} className="detail-cover" />
            ) : (
              <div className="detail-cover-placeholder">
                <BookOpen size={48} />
              </div>
            )}
          </div>

          <div className="detail-meta">
            <div className="detail-meta-top">
              <div className="detail-source-badge">{data.source}</div>
              <button
                className={`detail-fav-btn${favorited ? ' detail-fav-btn--active' : ''}`}
                onClick={() => toggleFavorite(source, slug, series.title, series.cover_url)}
                aria-label={favorited ? 'Remove from favorites' : 'Add to favorites'}
              >
                <Heart size={16} fill={favorited ? 'currentColor' : 'none'} />
                {favorited ? 'Favorited' : 'Favorite'}
              </button>
            </div>
            <h1 className="detail-title">{series.title}</h1>

            <div className="detail-meta-rows">
              {series.author && (
                <div className="detail-meta-row">
                  <User size={14} aria-hidden="true" />
                  <span>{series.author}</span>
                </div>
              )}
              {series.status && (
                <div className="detail-meta-row">
                  <Hash size={14} aria-hidden="true" />
                  <span className={`status-chip status--${series.status.toLowerCase()}`}>
                    {series.status}
                  </span>
                </div>
              )}
              {series.genres.length > 0 && (
                <div className="detail-meta-row detail-genres">
                  <Tag size={14} aria-hidden="true" />
                  <div className="genre-list">
                    {series.genres.map((g) => (
                      <span className="genre-tag" key={g}>{g}</span>
                    ))}
                  </div>
                </div>
              )}
              {series.follower_count != null && (
                <div className="detail-meta-row">
                  <span className="detail-followers">
                    {series.follower_count.toLocaleString()} followers
                  </span>
                </div>
              )}
            </div>

            {/* Synopsis */}
            {series.synopsis && (
              <div className="detail-synopsis">
                <button
                  className="synopsis-toggle"
                  onClick={() => setSynopsisOpen((o) => !o)}
                  aria-expanded={synopsisOpen}
                >
                  Synopsis
                  {synopsisOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
                {synopsisOpen && (
                  <p className="synopsis-text">{series.synopsis}</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick-read buttons */}
        {chapters.length > 0 && (
          <div className="detail-quick-read">
            <Link
              to={mkLink(firstChapterNum)}
              className="quick-read-btn quick-read-first"
            >
              <BookOpen size={15} />
              Read First Chapter
            </Link>
            <Link
              to={mkLink(latestChapterNum)}
              className="quick-read-btn quick-read-latest"
            >
              <BookOpen size={15} />
              Read Latest Chapter
            </Link>
          </div>
        )}

        {/* Chapter list */}
        <section className="chapter-section" aria-label="Chapter list">
          <div className="chapter-header">
            <div className="chapter-header-left">
              <h2 className="chapter-heading">
                Chapters <span className="chapter-count">({chapters.length})</span>
              </h2>
              {/* Continue Reading button */}
              {continueLink && !selectionMode && (
                <Link to={continueLink} className="continue-btn" aria-label={`Continue reading chapter ${lastChapter}`}>
                  Continue Ch.{lastChapter}
                  <ChevronRight size={14} />
                </Link>
              )}
            </div>
            <div className="chapter-header-actions">
              {!selectionMode && (
                <button
                  className="chapter-select-btn"
                  onClick={enterSelectionMode}
                  aria-label="Select chapters to download"
                >
                  <Download size={14} />
                  Download
                </button>
              )}
              <button
                className="sort-btn"
                onClick={() => setChapterSortAsc((v) => !v)}
                aria-label={`Sort ${chapterSortAsc ? 'descending' : 'ascending'}`}
              >
                {chapterSortAsc ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {chapterSortAsc ? 'Oldest first' : 'Newest first'}
              </button>
            </div>
          </div>

          {/* Download Queue Progress Banner */}
          {downloadQueue && (
            <div className="download-queue-banner">
              <div className="download-queue-banner__info">
                <Loader2 size={14} className="chapter-dl-spin" />
                <span>Downloading {downloadQueue.completed + 1}/{downloadQueue.total} chapters…</span>
              </div>
              <div className="download-queue-banner__bar">
                <div
                  className="download-queue-banner__fill"
                  style={{ width: `${downloadQueue.pct}%` }}
                />
              </div>
              <button
                className="download-queue-banner__cancel"
                onClick={cancelQueue}
                aria-label="Cancel download queue"
              >
                <X size={12} />
              </button>
            </div>
          )}

          <ul className="chapter-list">
            {sortedChapters.map((ch) => {
              const read = isChapterRead(source, slug, ch.number);
              const downloaded = isChapterDownloaded(source, slug, ch.number);
              const dlKey = `${source}/${slug}/${ch.number}`;
              const progress = activeDownloads.get(dlKey);
              const isSelected = selectedChapters.has(ch.number);

              return (
                <li key={String(ch.number)} className={`chapter-item${read ? ' read' : ''}${selectionMode ? ' selecting' : ''}`}>
                  {/* Checkbox for selection mode */}
                  {selectionMode && (
                    <button
                      className={`chapter-checkbox${isSelected ? ' chapter-checkbox--checked' : ''}`}
                      onClick={() => toggleChapterSelection(ch.number)}
                      aria-label={`${isSelected ? 'Deselect' : 'Select'} chapter ${ch.number}`}
                      disabled={downloaded}
                    >
                      {downloaded ? (
                        <CheckCircle size={18} />
                      ) : isSelected ? (
                        <CheckSquare size={18} />
                      ) : (
                        <Square size={18} />
                      )}
                    </button>
                  )}
                  <Link
                    to={`/comic/${encodeURIComponent(source)}/${encodeURIComponent(slug)}/chapter/${ch.number}`}
                    className="chapter-link"
                  >
                    <span className="chapter-num">
                      {read ? (
                        <CheckCircle
                          size={12}
                          className="chapter-read-icon"
                          aria-label="Read"
                        />
                      ) : (
                        <span className="chapter-unread-dot" aria-label="Unread" />
                      )}
                      Chapter {ch.number}
                    </span>
                    {ch.title && <span className="chapter-title-text">{ch.title}</span>}
                    <div className="chapter-meta-right">
                      {ch.date_published && (
                        <span className="chapter-date">
                          {new Date(ch.date_published).toLocaleDateString()}
                        </span>
                      )}
                      {ch.page_count != null && (
                        <span className="chapter-pages">{ch.page_count}p</span>
                      )}
                    </div>
                  </Link>
                  {/* Download button (only when not in selection mode) */}
                  {!selectionMode && (() => {
                    if (progress) {
                      return (
                        <span className="chapter-dl-progress" title={`${progress.pct}%`}>
                          <Loader2 size={14} className="chapter-dl-spin" />
                        </span>
                      );
                    }
                    if (downloaded) {
                      return (
                        <span className="chapter-dl-done" title="Saved offline">
                          <Download size={14} />
                        </span>
                      );
                    }
                    return (
                      <button
                        className="chapter-dl-btn"
                        title="Download for offline"
                        aria-label={`Download chapter ${ch.number}`}
                        onClick={async (e) => {
                          e.preventDefault();
                          try {
                            const chData = await fetchChapter(source, slug, ch.number);
                            const urls = chData.pages.map((p) => p.image_url);
                            downloadChapter(source, slug, ch.number, data.series.title, urls);
                          } catch { /* best-effort */ }
                        }}
                      >
                        <Download size={14} />
                      </button>
                    );
                  })()}
                </li>
              );
            })}
          </ul>
        </section>

        {/* Recommendations — "You might also like" */}
        {source && slug && (
          <RecommendationsSection source={source} slug={slug} />
        )}
      </div>
    </PullToRefreshContainer>

    {/* Portal floating elements to document.body to avoid transform containment from PullToRefresh */}
    {selectionMode && createPortal(
      <div className="chapter-selection-bar">
        <button
          className="selection-bar__select-all"
          onClick={toggleSelectAll}
        >
          {allSelected ? <CheckSquare size={16} /> : <Square size={16} />}
          {allSelected ? 'Deselect All' : 'Select All'}
        </button>
        <span className="selection-bar__count">
          {selectedChapters.size} selected
        </span>
        <div className="selection-bar__actions">
          <button
            className="selection-bar__cancel"
            onClick={exitSelectionMode}
          >
            Cancel
          </button>
          <button
            className="selection-bar__download"
            onClick={handleDownloadSelected}
            disabled={selectedChapters.size === 0}
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>,
      document.body
    )}

    {continueLink && !selectionMode && createPortal(
      <Link to={continueLink} className="detail-floating-cta">
        <Play size={16} />
        Continue — Ch.{lastChapter}
      </Link>,
      document.body
    )}
  </>);
}

function RecommendationsSection({ source, slug }: { source: string; slug: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', source, slug],
    queryFn: () => fetchRecommendations(source, slug),
    staleTime: 5 * 60_000,
  });

  if (isLoading || !data || data.recommendations.length === 0) return null;

  return (
    <section className="detail-recommendations">
      <h3 className="detail-recommendations__title">You might also like</h3>
      <div className="detail-recommendations__scroll">
        {data.recommendations.map((item) => (
          <ComicCard key={item.slug} source={source} item={item} />
        ))}
      </div>
    </section>
  );
}
