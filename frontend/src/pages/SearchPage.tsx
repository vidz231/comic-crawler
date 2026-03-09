import { useEffect, useCallback, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, ChevronRight, ChevronLeft, Tag, X, ArrowUpDown, Filter } from 'lucide-react';
import { fetchSources, fetchBrowse, fetchCategories, fetchMultiSearch } from '../api/endpoints';
import { useDocTitle } from '../hooks/useDocTitle';
import ComicCard from '../components/ComicCard';
import ComicCardSkeleton from '../components/ComicCardSkeleton';
import ErrorMessage from '../components/ErrorMessage';
import PullToRefreshContainer from '../components/PullToRefreshContainer';
import { sortSources, DEFAULT_SOURCE } from '../utils/sourceOrder';
import './SearchPage.css';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [inputValue, setInputValue] = useState(() => searchParams.get('q') ?? '');
  const isMountRef = useRef(true);

  const query = searchParams.get('q') ?? '';
  const page  = Number(searchParams.get('page') ?? '1');
  const genre = searchParams.get('genre') ?? '';
  const sortBy = searchParams.get('sort') ?? '';
  const statusFilter = searchParams.get('status') ?? '';
  const source = searchParams.get('source') ?? DEFAULT_SOURCE;

  useDocTitle('Search & Browse');

  // Debounce — write query into URL (resets page to 1)
  useEffect(() => {
    if (isMountRef.current) {
      isMountRef.current = false;
      return;
    }
    const timer = setTimeout(() => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (inputValue) {
            next.set('q', inputValue);
          } else {
            next.delete('q');
          }
          next.set('page', '1');
          return next;
        },
        { replace: true }
      );
    }, 400);
    return () => clearTimeout(timer);
  }, [inputValue]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch sources list
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: fetchSources,
    staleTime: Infinity,
  });

  // Auto-select default source if current doesn't exist in loaded sources
  useEffect(() => {
    if (sourcesData?.sources?.length && !sourcesData.sources.some(s => s.name === source) && source !== '__all__') {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('source', DEFAULT_SOURCE);
        return next;
      }, { replace: true });
    }
  }, [sourcesData, source, setSearchParams]);

  // Sort sources for display
  const sortedSources = sourcesData?.sources ? sortSources(sourcesData.sources) : [];

  // Fetch categories for the active source
  const { data: categoriesData } = useQuery({
    queryKey: ['categories', source],
    queryFn: () => fetchCategories(source),
    enabled: !!source,
    staleTime: 5 * 60_000,
  });

  const categories = categoriesData?.[0]?.categories ?? [];
  const supportsMultiGenre = categoriesData?.[0]?.supports_multi_genre ?? false;

  const activeGenres = new Set(
    genre ? genre.split(',').filter(Boolean) : []
  );

  const isAllSources = source === '__all__';

  // Fetch browse results — single source
  const {
    data: browseData,
    isLoading: browseLoading,
    isError: browseError,
    error: browseErr,
  } = useQuery({
    queryKey: ['browse', source, query, page, genre],
    queryFn: () => fetchBrowse(source, query || undefined, page, genre || undefined),
    enabled: !!source && !isAllSources,
    staleTime: 60_000,
  });

  // Fetch multi-source search results
  const {
    data: multiData,
    isLoading: multiLoading,
    isError: multiError,
    error: multiErr,
  } = useQuery({
    queryKey: ['multiSearch', query, page],
    queryFn: () => fetchMultiSearch(query || undefined, undefined, undefined, page),
    enabled: isAllSources && !!query,
    staleTime: 60_000,
  });

  const isLoading = isAllSources ? multiLoading : browseLoading;
  const isError = isAllSources ? multiError : browseError;
  const error = isAllSources ? multiErr : browseErr;

  const handleGenreSelect = useCallback(
    (slug: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          const current = new Set(
            (prev.get('genre') ?? '').split(',').filter(Boolean)
          );

          if (supportsMultiGenre) {
            if (current.has(slug)) {
              current.delete(slug);
            } else {
              current.add(slug);
            }
          } else {
            if (current.has(slug)) {
              current.clear();
            } else {
              current.clear();
              current.add(slug);
            }
          }

          if (current.size > 0) {
            next.set('genre', [...current].join(','));
          } else {
            next.delete('genre');
          }
          next.set('page', '1');
          return next;
        },
        { replace: true }
      );
    },
    [supportsMultiGenre, setSearchParams]
  );

  const clearGenre = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('genre');
        next.set('page', '1');
        return next;
      },
      { replace: true }
    );
  }, [setSearchParams]);

  const handlePrevPage = useCallback(
    () =>
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('page', String(Math.max(1, page - 1)));
        return next;
      }),
    [page, setSearchParams]
  );
  const handleNextPage = useCallback(
    () =>
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('page', String(page + 1));
        return next;
      }),
    [page, setSearchParams]
  );

  const comics = browseData?.results ?? [];

  const filteredComics = comics
    .filter((c) => !statusFilter || (c.status?.toLowerCase() ?? '') === statusFilter)
    .sort((a, b) => {
      if (sortBy === 'rating') return (b.rating ?? 0) - (a.rating ?? 0);
      if (sortBy === 'title') return (a.title ?? '').localeCompare(b.title ?? '');
      if (sortBy === 'latest') return (b.latest_chapter ?? 0) - (a.latest_chapter ?? 0);
      return 0;
    });

  const setSortParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    }, { replace: true });
  };

  const handleRefresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['browse'] });
    await queryClient.invalidateQueries({ queryKey: ['multiSearch'] });
  }, [queryClient]);

  return (
    <PullToRefreshContainer onRefresh={handleRefresh} as="main" className="search-page" id="main-content">
      <div className="container">
        {/* Page title */}
        <h1 className="search-page__title">Search & Browse</h1>

        {/* Search bar */}
        <label htmlFor="comic-search" className="sr-only">Search comics</label>
        <div className="search-bar">
          <Search size={16} aria-hidden="true" className="search-bar__icon" />
          <input
            id="comic-search"
            type="search"
            placeholder="Search by title…"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            className="search-bar__input"
            autoComplete="off"
          />
        </div>

        {/* Source selector */}
        <div className="source-selector">
          <button
            className={`source-btn ${isAllSources ? 'active' : ''}`}
            onClick={() => { setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set('source', '__all__'); next.set('page', '1'); next.delete('genre'); return next; }, { replace: true }); }}
            aria-pressed={isAllSources}
          >
            All Sources
          </button>
          {sortedSources.map((s) => (
            <button
              key={s.name}
              className={`source-btn ${source === s.name ? 'active' : ''}`}
              onClick={() => { setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set('source', s.name); next.set('page', '1'); next.delete('genre'); return next; }, { replace: true }); }}
              aria-pressed={source === s.name}
            >
              {s.name}
            </button>
          ))}
        </div>

        {/* Genre chips */}
        {!isAllSources && categories.length > 0 && (
          <section className="genre-section" aria-label="Filter by genre">
            <div className="genre-bar">
              <Tag size={14} className="genre-bar__icon" aria-hidden="true" />
              <div className="genre-chips">
                {genre && (
                  <button
                    className="genre-chip genre-chip--clear"
                    onClick={clearGenre}
                    aria-label="Clear genre filter"
                  >
                    <X size={12} />
                    Clear
                  </button>
                )}
                {categories.map((cat) => (
                  <button
                    key={cat.slug}
                    className={`genre-chip ${activeGenres.has(cat.slug) ? 'genre-chip--active' : ''}`}
                    onClick={() => handleGenreSelect(cat.slug)}
                    aria-pressed={activeGenres.has(cat.slug)}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Active genre indicator */}
        {!isAllSources && activeGenres.size > 0 && (
          <div className="genre-active-bar fade-in">
            <span className="genre-active-label">
              <Tag size={13} aria-hidden="true" />
              Browsing:{' '}
              <strong>
                {[...activeGenres]
                  .map((g) => categories.find((c) => c.slug === g)?.name ?? g)
                  .join(', ')}
              </strong>
            </span>
            <button className="genre-active-clear" onClick={clearGenre}>
              <X size={14} />
              Clear filter{activeGenres.size > 1 ? 's' : ''}
            </button>
          </div>
        )}

        {/* Sort & Status filters */}
        {!isAllSources && (
          <div className="filter-bar">
            <label className="filter-select">
              <ArrowUpDown size={13} aria-hidden="true" />
              <select
                value={sortBy}
                onChange={(e) => setSortParam('sort', e.target.value)}
                aria-label="Sort by"
              >
                <option value="">Default order</option>
                <option value="latest">Latest chapter</option>
                <option value="rating">Highest rated</option>
                <option value="title">Title A–Z</option>
              </select>
            </label>
            <label className="filter-select">
              <Filter size={13} aria-hidden="true" />
              <select
                value={statusFilter}
                onChange={(e) => setSortParam('status', e.target.value)}
                aria-label="Filter by status"
              >
                <option value="">All statuses</option>
                <option value="ongoing">Ongoing</option>
                <option value="completed">Completed</option>
              </select>
            </label>
          </div>
        )}

        {/* Results */}
        {isLoading && (
          <div className="comic-grid">
            {Array.from({ length: 18 }, (_, i) => (
              <ComicCardSkeleton key={`skeleton-${i}`} />
            ))}
          </div>
        )}
        {isError && (
          <ErrorMessage
            message={(error as Error)?.message ?? 'Failed to load comics.'}
          />
        )}

        {!isLoading && !isError && !isAllSources && (
          <>
            {filteredComics.length === 0 ? (
              <p className="search-empty">No comics found. Try a different query or source.</p>
            ) : (
              <div className="comic-grid fade-in">
                {filteredComics.map((item) => (
                  <ComicCard key={item.slug} source={source} item={item} />
                ))}
              </div>
            )}

            {/* Pagination */}
            <div className="pagination">
              <button
                className="pagination-btn"
                onClick={handlePrevPage}
                disabled={page <= 1}
                aria-label="Previous page"
              >
                <ChevronLeft size={16} />
                Prev
              </button>
              <span className="pagination-page">Page {page}</span>
              <button
                className="pagination-btn"
                onClick={handleNextPage}
                disabled={!browseData?.has_next_page}
                aria-label="Next page"
              >
                Next
                <ChevronRight size={16} />
              </button>
            </div>
          </>
        )}

        {/* Multi-source results */}
        {!isLoading && !isError && isAllSources && (
          <>
            {!query ? (
              <p className="search-empty">Type a search query to search across all sources.</p>
            ) : multiData && multiData.total_count === 0 ? (
              <p className="search-empty">No results found across any source.</p>
            ) : multiData ? (
              <div className="multi-source-results fade-in">
                {multiData.results.map((srcResult) => (
                  <section key={srcResult.source} className="multi-source-group">
                    <h3 className="multi-source-label">
                      {srcResult.source}
                      <span className="multi-source-count">{srcResult.series_count} results</span>
                    </h3>
                    {srcResult.results.length === 0 ? (
                      <p className="multi-source-empty">No results from this source.</p>
                    ) : (
                      <div className="comic-grid">
                        {srcResult.results.map((item) => (
                          <ComicCard key={`${srcResult.source}-${item.slug}`} source={srcResult.source} item={item} />
                        ))}
                      </div>
                    )}
                  </section>
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>
    </PullToRefreshContainer>
  );
}
