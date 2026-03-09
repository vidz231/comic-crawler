import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, useCallback } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react';

import { fetchChapter } from '../api/endpoints';
import type { ChapterReadResponse } from '../api/types';
import { getChapterData, saveChapterData, chapterDataKey } from '../utils/offlineDb';
import { useComicDetail, makeChapterLink } from '../hooks/useComicDetail';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useDocTitle } from '../hooks/useDocTitle';
import { usePageTracker } from '../hooks/usePageTracker';
import { useScrollRestore } from '../hooks/useScrollRestore';
import { useScrollToTop } from '../hooks/useScrollToTop';
import { useReaderContext } from '../layouts/ReaderLayout';
import { usePinchZoom } from '../hooks/usePinchZoom';
import ReaderImage from '../components/ReaderImage';
import { useOfflineChapters } from '../hooks/useOfflineChapters';
import ChapterSkeleton from '../components/ChapterSkeleton';
import ErrorMessage from '../components/ErrorMessage';
import { hapticLight } from '../utils/haptics';
import './ChapterReaderPage.css';

export default function ChapterReaderPage() {
  const {
    source = '',
    slug = '',
    number = '1',
  } = useParams<{ source: string; slug: string; number: string }>();

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Back navigation: go to browser history if available, else fall back to detail page.
  // This keeps native device back and in-app back button consistent.
  const detailUrl = `/comic/${encodeURIComponent(source)}/${encodeURIComponent(slug)}`;
  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(detailUrl);
    }
  }, [navigate, detailUrl]);
  const chapterNum = parseFloat(number);
  const { markRead, isChapterRead } = useReadingProgress();
  const { isChapterDownloaded } = useOfflineChapters();
  const isDownloaded = isChapterDownloaded(source, slug, chapterNum);

  const { settings } = useReaderContext();

  // Pinch-to-zoom + double-tap zoom for strip mode
  const { containerRef: pinchRef, resetZoom } = usePinchZoom<HTMLDivElement>();

  // Reset zoom on chapter change
  useEffect(() => {
    resetZoom();
  }, [chapterNum, resetZoom]);

  // ── Auto-hide top bar (scroll direction + idle + mouse proximity) ───────────
  const [barVisible, setBarVisible] = useState(true);
  const barRef = useRef<HTMLElement>(null);
  const lastScrollY = useRef(0);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const scheduleHide = useCallback(() => {
    clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => setBarVisible(false), 3000);
  }, []);

  const revealBar = useCallback(() => {
    setBarVisible(true);
    scheduleHide();
  }, [scheduleHide]);

  useEffect(() => {
    const handleScroll = () => {
      const y = window.scrollY;
      const delta = y - lastScrollY.current;
      lastScrollY.current = y;
      if (delta > 8) {
        clearTimeout(hideTimerRef.current);
        setBarVisible(false);
      } else if (delta < -8) {
        revealBar();
      }
    };
    const handleMouseMove = (e: MouseEvent) => {
      if (e.clientY < 80) revealBar();
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    // Auto-hide 3 seconds after mount
    scheduleHide();

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('mousemove', handleMouseMove);
      clearTimeout(hideTimerRef.current);
    };
  }, [revealBar, scheduleHide]);

  // ── Sync aria-hidden + inert on reader bar ─────────────────────────────────
  useEffect(() => {
    const el = barRef.current;
    if (!el) return;
    el.setAttribute('aria-hidden', String(!barVisible));
    if (!barVisible) {
      el.setAttribute('inert', '');
    } else {
      el.removeAttribute('inert');
    }
  }, [barVisible]);



  // ── Data fetching (with IDB offline fallback) ────────────────────────────
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['chapter', source, slug, chapterNum],
    queryFn: async (): Promise<ChapterReadResponse> => {
      try {
        const result = await fetchChapter(source, slug, chapterNum);
        // Cache for offline reading
        const cdKey = chapterDataKey(source, slug, chapterNum);
        saveChapterData(cdKey, result).catch(() => {/* best-effort */});
        return result;
      } catch (err) {
        // Offline fallback: try IDB
        const cdKey = chapterDataKey(source, slug, chapterNum);
        const cached = await getChapterData<ChapterReadResponse>(cdKey);
        if (cached) return cached;
        throw err;
      }
    },
    enabled: !!source && !!slug && !isNaN(chapterNum),
    staleTime: 5 * 60_000,
  });

  const { data: detail } = useComicDetail(source, slug);

  // ── Dynamic page title ─────────────────────────────────────────────────────
  useDocTitle(data ? `Ch.${data.chapter_number} · ${data.series_title}` : 'Loading…');

  // ── Mark read ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!data || !source || !slug || isNaN(chapterNum)) return;
    markRead(source, slug, chapterNum, {
      title: data.series_title,
      cover_url: detail?.series.cover_url ?? null,
    });
  }, [data, source, slug, chapterNum, detail, markRead]);

  // ── Chapter navigation helpers ─────────────────────────────────────────────
  const sortedChapters = detail
    ? [...detail.chapters].sort((a, b) => Number(a.number) - Number(b.number))
    : [];
  const currentIdx = sortedChapters.findIndex((c) => Number(c.number) === Number(chapterNum));
  const prevChapter = currentIdx > 0 ? sortedChapters[currentIdx - 1] : null;
  const nextChapter =
    currentIdx < sortedChapters.length - 1 ? sortedChapters[currentIdx + 1] : null;

  const mkLink = (num: number) => makeChapterLink(source, slug, num);

  // ── Prefetch next chapter ──────────────────────────────────────────────────
  const prefetchedImagesRef = useRef(false);

  useEffect(() => {
    if (!data || !nextChapter) return;
    // Prefetch chapter API data immediately
    queryClient.prefetchQuery({
      queryKey: ['chapter', source, slug, nextChapter.number],
      queryFn: () => fetchChapter(source, slug, nextChapter.number),
      staleTime: 5 * 60_000,
    });
    prefetchedImagesRef.current = false; // reset on chapter change
  }, [data, source, slug, nextChapter, queryClient]);

  // Pre-load first 3 images of next chapter when user hits 50% scroll
  useEffect(() => {
    if (!nextChapter) return;
    const handleScroll = () => {
      if (prefetchedImagesRef.current) return;
      const scrollPct =
        window.scrollY / (document.documentElement.scrollHeight - window.innerHeight);
      if (scrollPct >= 0.5) {
        prefetchedImagesRef.current = true;
        // Load next chapter data and pre-warm first 3 page images
        queryClient
          .fetchQuery({
            queryKey: ['chapter', source, slug, nextChapter.number],
            queryFn: () => fetchChapter(source, slug, nextChapter.number),
            staleTime: 5 * 60_000,
          })
          .then((nextData) => {
            nextData.pages.slice(0, 3).forEach((p) => {
              const img = new Image();
              img.src = p.image_url;
            });
          })
          .catch(() => {/* best-effort */});
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [source, slug, nextChapter, queryClient]);

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.key === 'ArrowRight' && nextChapter) navigate(mkLink(nextChapter.number), { replace: true });
      else if (e.key === 'ArrowLeft' && prevChapter) navigate(mkLink(prevChapter.number), { replace: true });
      else if (e.key === 'Escape') navigate(detailUrl);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate, nextChapter, prevChapter, detailUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Scroll to top on chapter change (mobile-safe with retries) ──────────
  useScrollToTop(chapterNum);

  // ── Page counter + scroll restore ─────────────────────────────────────────
  const [imagesReady, setImagesReady] = useState(false);
  const loadedCountRef = useRef(0);
  const totalPages = data?.pages.length ?? 0;
  const scrollPage = usePageTracker(totalPages, imagesReady);
  const [pagedPage, setPagedPage] = useState(1);
  const currentPage = settings.readingMode === 'paged' ? pagedPage : scrollPage;
  const wasAlreadyRead = isChapterRead(source, slug, chapterNum);
  useScrollRestore(source, slug, chapterNum, wasAlreadyRead, imagesReady);

  const handleImageLoad = useCallback(() => {
    loadedCountRef.current += 1;
    if (!imagesReady && loadedCountRef.current >= 1) setImagesReady(true);
  }, [imagesReady]);

  useEffect(() => {
    loadedCountRef.current = 0;
    setImagesReady(false);
    setPagedPage(1);
  }, [chapterNum]);

  // ── Auto-advance to next chapter ──────────────────────────────────────────
  const [autoAdvanceToast, setAutoAdvanceToast] = useState(false);
  const autoAdvanceTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Strip mode: auto-advance when near the end of the chapter
  // Uses hybrid check: page tracker shows last/second-to-last page + near scroll bottom
  useEffect(() => {
    if (settings.readingMode !== 'strip' || !settings.autoAdvance || !nextChapter || !imagesReady) return;
    if (totalPages === 0) return;

    const checkAutoAdvance = () => {
      const el = document.documentElement;
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      const nearBottom = distFromBottom < 200;
      // Page tracker can be 1 short due to IntersectionObserver rootMargin
      const onLastPages = scrollPage >= totalPages - 1;

      if (nearBottom && onLastPages) {
        if (!autoAdvanceTimerRef.current) {
          setAutoAdvanceToast(true);
          autoAdvanceTimerRef.current = setTimeout(() => {
            navigate(mkLink(nextChapter.number), { replace: true });
          }, 1500);
        }
      } else {
        if (autoAdvanceTimerRef.current) {
          clearTimeout(autoAdvanceTimerRef.current);
          autoAdvanceTimerRef.current = undefined;
          setAutoAdvanceToast(false);
        }
      }
    };

    // Check immediately (for when scrollPage changes)
    checkAutoAdvance();

    // Also listen to scroll for the distance check
    window.addEventListener('scroll', checkAutoAdvance, { passive: true });
    return () => {
      window.removeEventListener('scroll', checkAutoAdvance);
      if (autoAdvanceTimerRef.current) {
        clearTimeout(autoAdvanceTimerRef.current);
        autoAdvanceTimerRef.current = undefined;
      }
    };
  }, [scrollPage, totalPages, settings.readingMode, settings.autoAdvance, nextChapter, imagesReady, navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  // Paged mode: advance when pressing next on last page
  const handlePagedNext = useCallback(() => {
    if (currentPage >= totalPages && settings.autoAdvance && nextChapter) {
      navigate(mkLink(nextChapter.number), { replace: true });
    } else {
      const next = Math.min(totalPages, currentPage + 1);
      window.scrollTo({ top: 0 });
      setPagedPage(next);
    }
  }, [currentPage, totalPages, settings.autoAdvance, nextChapter, navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clean up toast on chapter change
  useEffect(() => {
    setAutoAdvanceToast(false);
  }, [chapterNum]);

  if (isLoading) return <ChapterSkeleton />;
  if (isError || !data)
    return (
      <div className="container" style={{ paddingTop: 40 }}>
        <ErrorMessage message={(error as Error)?.message ?? 'Failed to load chapter.'} />
      </div>
    );

  return (
    <main className="reader-page" id="main-content">
      {/* Auto-hiding top bar — aria-hidden + inert managed via ref+useEffect */}
      <nav
        ref={barRef}
        className={`reader-bar glass${barVisible ? '' : ' hidden'}`}
        aria-label="Chapter navigation"
      >
        <button
          className="reader-back"
          onClick={() => { hapticLight(); handleBack(); }}
          aria-label="Back to comic"
        >
          <ArrowLeft size={16} />
          <span className="reader-series">{data.series_title}</span>
        </button>

        <select
          className="reader-chapter-select"
          value={chapterNum}
          onChange={(e) => navigate(mkLink(Number(e.target.value)), { replace: true })}
          aria-label="Jump to chapter"
        >
          {sortedChapters.map((c) => (
            <option key={c.number} value={c.number}>
              Chapter {c.number}
            </option>
          ))}
        </select>

        {totalPages > 0 && (
          <span className="reader-page-counter" aria-live="polite">
            {currentPage} / {totalPages}
          </span>
        )}

        <div className="reader-nav">
          {prevChapter ? (
            <button
              className="reader-nav-btn"
              onClick={() => { hapticLight(); navigate(mkLink(prevChapter.number), { replace: true }); }}
              aria-label="Previous chapter"
            >
              <ChevronLeft size={16} />Prev
            </button>
          ) : (
            <button className="reader-nav-btn" disabled aria-label="No previous chapter">
              <ChevronLeft size={16} />Prev
            </button>
          )}
          {nextChapter ? (
            <button
              className="reader-nav-btn"
              onClick={() => { hapticLight(); navigate(mkLink(nextChapter.number), { replace: true }); }}
              aria-label="Next chapter"
            >
              Next<ChevronRight size={16} />
            </button>
          ) : (
            <button className="reader-nav-btn" disabled aria-label="No next chapter">
              Next<ChevronRight size={16} />
            </button>
          )}
        </div>
      </nav>

      {/* Full-bleed image strip / paged view */}
      {settings.readingMode === 'strip' ? (
        <div
          ref={pinchRef}
          className={`reader-strip${settings.fitWidth ? ' reader-strip--fit' : ''}`}
          style={
            {
              '--reader-img-width': `${settings.imageWidth}px`,
              '--reader-brightness': `${settings.brightness}%`,
              '--reader-gap': `${settings.pageGap}px`,
            } as React.CSSProperties
          }
        >
          {data.pages.map((page, i) => (
            <ReaderImage
              key={page.page_number}
              page={page}
              offlineKey={isDownloaded ? `${source}/${slug}/${chapterNum}/${i}` : undefined}
              onLoad={handleImageLoad}
            />
          ))}
        </div>
      ) : (
        <div
          className={`reader-paged${settings.fitWidth ? ' reader-paged--fit' : ''}`}
          style={
            {
              '--reader-img-width': `${settings.imageWidth}px`,
              '--reader-brightness': `${settings.brightness}%`,
            } as React.CSSProperties
          }
        >
          <ReaderImage
            key={data.pages[currentPage - 1]?.page_number ?? 0}
            page={data.pages[currentPage - 1] ?? data.pages[0]}
            offlineKey={isDownloaded ? `${source}/${slug}/${chapterNum}/${currentPage - 1}` : undefined}
            onLoad={handleImageLoad}
          />
          <div className="reader-paged-nav">
            <button
              className="reader-paged-btn"
              onClick={() => {
                const prev = Math.max(1, currentPage - 1);
                const el = document.querySelector('.reader-paged');
                el?.scrollTo({ top: 0 });
                // Force page tracker update by scrolling to the image
                window.scrollTo({ top: 0 });
                // Navigate to prev page by programmatic scroll
                setPagedPage(prev);
              }}
              disabled={currentPage <= 1}
              aria-label="Previous page"
            >
              <ChevronLeft size={16} />
              Prev
            </button>
            <span className="reader-paged-counter">
              {currentPage} / {totalPages}
            </span>
            <button
              className="reader-paged-btn"
              onClick={handlePagedNext}
              disabled={currentPage >= totalPages && (!settings.autoAdvance || !nextChapter)}
              aria-label={currentPage >= totalPages && settings.autoAdvance && nextChapter ? 'Next chapter' : 'Next page'}
            >
              {currentPage >= totalPages && settings.autoAdvance && nextChapter ? 'Next Ch.' : 'Next'}
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Auto-advance toast */}
      {autoAdvanceToast && nextChapter && (
        <div className="reader-auto-advance-toast">
          Advancing to Chapter {nextChapter.number}…
        </div>
      )}
    </main>
  );
}
