import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, BookOpen } from 'lucide-react';
import { fetchSources } from '../api/endpoints';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useFavorites } from '../hooks/useFavorites';
import { useDocTitle } from '../hooks/useDocTitle';
import TrendingSection from '../components/TrendingSection';
import ContinueReading from '../components/ContinueReading';
import RecentlyUpdated from '../components/RecentlyUpdated';
import PullToRefreshContainer from '../components/PullToRefreshContainer';
import { sortSources } from '../utils/sourceOrder';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import './HomePage.css';

export default function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchInput, setSearchInput] = useState('');

  useDocTitle('Comic Crawler');
  const { recentlyRead } = useReadingProgress();
  const { favorites } = useFavorites();

  // Fetch sources list
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: fetchSources,
    staleTime: Infinity,
  });

  // Sort sources using preferred order (asura first, mangadex/mangakakalot last)
  const sortedSources = sourcesData?.sources ? sortSources(sourcesData.sources) : [];

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchInput.trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
  };

  const handleRefresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['recentlyUpdated'] });
    await queryClient.invalidateQueries({ queryKey: ['trending'] });
  }, [queryClient]);

  return (
    <PullToRefreshContainer onRefresh={handleRefresh} as="main" className="home-page" id="main-content">
      {/* ── Compact header bar ─────────────────────────────────── */}
      <header className="home-header">
        <div className="home-header__left">
          <BookOpen size={28} className="home-header__logo" aria-hidden="true" />
          <div className="home-header__text">
            <span className="home-header__title">Comic Crawler</span>
            <span className="home-header__sub">Discover Comics</span>
          </div>
        </div>
        <form className="home-header__search-form" onSubmit={handleSearchSubmit}>
          <Search size={16} className="home-header__search-icon" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search comics…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="home-header__search-input"
            autoComplete="off"
          />
        </form>
      </header>

      <div className="container">
        {/* Continue Reading */}
        <ContinueReading entries={recentlyRead} />

        {/* Favorites — circular avatars */}
        {favorites.length > 0 && (
          <section className="favorites-section" aria-label="Favorites">
            <div className="favorites-header">
              <h2 className="section-heading">
                Favorites
              </h2>
              <button
                className="favorites-see-all"
                onClick={() => navigate('/search')}
              >
                See All
              </button>
            </div>
            <div className="favorites-scroll">
              {favorites.map((fav) => (
                <button
                  key={`${fav.source}:${fav.slug}`}
                  className="fav-circle"
                  onClick={() => navigate(`/comic/${encodeURIComponent(fav.source)}/${encodeURIComponent(fav.slug)}`)}
                >
                  <div className="fav-circle__img-wrap">
                    {fav.cover_url ? (
                      (() => {
                        const src = proxyImageUrl(fav.cover_url) ?? undefined;
                        return (
                          <img
                            src={src}
                            alt={fav.title}
                            className="fav-circle__img"
                            loading="lazy"
                            crossOrigin={isCorsReady(src) ? 'anonymous' : undefined}
                          />
                        );
                      })()
                    ) : (
                      <div className="fav-circle__placeholder" />
                    )}
                  </div>
                  <span className="fav-circle__name">{fav.title}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Recently Updated — cross-source */}
        <RecentlyUpdated />

        {/* ── Trending per source ─────────────────────────────── */}
        {sortedSources.map((src) => (
          <TrendingSection key={src.name} source={src.name} />
        ))}
      </div>
    </PullToRefreshContainer>
  );
}
