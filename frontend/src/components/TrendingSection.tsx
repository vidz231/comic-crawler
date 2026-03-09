import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Flame, BookOpen, Star } from 'lucide-react';
import { fetchTrending } from '../api/endpoints';
import ErrorMessage from './ErrorMessage';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import './TrendingSection.css';

// ── Period map — derived from spider.trending_periods on the backend ────────
const SOURCE_PERIODS: Record<string, string[]> = {
  mangadex:     ['today', 'weekly', 'monthly', 'all'],
  mangakakalot: ['today', 'weekly', 'monthly', 'all'],
  asura:        ['today', 'weekly', 'monthly', 'all'],
  truyenvn:     ['trending', 'views', 'rating', 'new'],
  truyenqq:     ['daily', 'weekly', 'monthly'],
};

function getDefaultPeriod(source: string): string {
  return SOURCE_PERIODS[source]?.[0] ?? 'today';
}

interface Props {
  source: string;
}

export default function TrendingSection({ source }: Props) {
  const [period, setPeriod] = useState(() => getDefaultPeriod(source));

  // Reset period whenever source changes
  useEffect(() => {
    setPeriod(getDefaultPeriod(source));
  }, [source]);

  const periods = SOURCE_PERIODS[source] ?? [];

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['trending', source, period],
    queryFn: () => fetchTrending(source, period),
    enabled: !!source && periods.length > 0,
    staleTime: 5 * 60_000, // 5 min
  });

  // Don't render if the source has no known trending periods
  if (!source || periods.length === 0) return null;

  return (
    <section className="trending-section" aria-label="Trending comics">
      {/* Heading row */}
      <div className="trending-header">
        <h2 className="trending-heading">
          <Flame size={15} aria-hidden="true" />
          Trending on <span className="trending-heading__source">{source.charAt(0).toUpperCase() + source.slice(1)}</span>
        </h2>
        <div className="trending-pills" role="tablist" aria-label="Trending period">
          {periods.map((p) => (
            <button
              key={p}
              role="tab"
              aria-selected={period === p}
              className={`trending-pill${period === p ? ' active' : ''}`}
              onClick={() => setPeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="trending-loading" aria-busy="true" aria-label="Loading trending comics">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={`ts-${i}`} className="trending-wide-card-sk">
              <div className="trending-wide-card-sk__cover skeleton" />
              <div className="trending-wide-card-sk__info">
                <div className="trending-wide-card-sk__title skeleton" />
                <div className="trending-wide-card-sk__rating skeleton" />
                <div className="trending-wide-card-sk__genres">
                  <div className="trending-wide-card-sk__genre skeleton" />
                  <div className="trending-wide-card-sk__genre skeleton" />
                </div>
                <div className="trending-wide-card-sk__chapter skeleton" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && (
        <ErrorMessage message={(error as Error)?.message ?? 'Failed to load trending comics.'} />
      )}

      {/* Results — Wide horizontal cards matching mockup */}
      {!isLoading && !isError && data && (
        <div className="trending-list" role="list">
          {!data.items?.length ? (
            <p className="trending-empty">No trending data available.</p>
          ) : (
            data.items.map((item) => {
              const href = `/comic/${encodeURIComponent(source)}/${encodeURIComponent(item.slug)}`;
              return (
                <Link
                  key={item.slug}
                  to={href}
                  className="trending-wide-card"
                  role="listitem"
                  aria-label={`${item.title}${item.rank != null ? `, rank ${item.rank}` : ''}`}
                >
                  {/* Cover image — left side */}
                  <div className="trending-wide-card__cover">
                    {item.cover_url ? (
                      (() => {
                        const src = proxyImageUrl(item.cover_url) ?? undefined;
                        return (
                          <img
                            src={src}
                            alt={`Cover for ${item.title}`}
                            className="trending-wide-card__img"
                            loading="lazy"
                            crossOrigin={isCorsReady(src) ? 'anonymous' : undefined}
                          />
                        );
                      })()
                    ) : (
                      <div className="trending-wide-card__placeholder">
                        <BookOpen size={24} />
                      </div>
                    )}
                  </div>

                  {/* Info — right side */}
                  <div className="trending-wide-card__info">
                    <h3 className="trending-wide-card__title">{item.title}</h3>
                    {item.rating != null && (
                      <div className="trending-wide-card__rating">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <Star
                            key={star}
                            size={12}
                            fill={star <= Math.round(item.rating!) ? '#fbbf24' : 'none'}
                            stroke="#fbbf24"
                            aria-hidden="true"
                          />
                        ))}
                        <span className="trending-wide-card__rating-text">{item.rating.toFixed(1)}</span>
                      </div>
                    )}
                    {/* Genre pills */}
                    {item.genres && item.genres.length > 0 && (
                      <div className="trending-wide-card__genres">
                        {item.genres.slice(0, 3).map((g) => (
                          <span className="trending-wide-card__genre" key={g}>{g}</span>
                        ))}
                      </div>
                    )}
                    {item.latest_chapter != null && (
                      <span className="trending-wide-card__chapter">Ch. {item.latest_chapter}</span>
                    )}
                  </div>
                </Link>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}
