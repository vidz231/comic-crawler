import { Link } from 'react-router-dom';
import { Star, BookOpen, Heart } from 'lucide-react';
import type { SearchLiteItem } from '../api/types';
import { useFavorites } from '../hooks/useFavorites';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import './ComicCard.css';

interface Props {
  source: string;
  item: SearchLiteItem;
}

export default function ComicCard({ source, item }: Props) {
  const href = `/comic/${encodeURIComponent(source)}/${encodeURIComponent(item.slug)}`;
  const coverSrc = proxyImageUrl(item.cover_url) ?? undefined;
  const { toggleFavorite, isFavorite } = useFavorites();
  const favorited = isFavorite(source, item.slug);

  const handleFavorite = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleFavorite(source, item.slug, item.title, item.cover_url);
  };

  return (
    <Link to={href} className="comic-card" aria-label={`Open ${item.title}`}>
      <div className="comic-card__cover-wrap">
        {item.cover_url ? (
          <img
            src={coverSrc}
            alt={`Cover for ${item.title}`}
            className="comic-card__cover"
            loading="lazy"
            crossOrigin={isCorsReady(coverSrc) ? 'anonymous' : undefined}
          />
        ) : (
          <div className="comic-card__cover-placeholder">
            <BookOpen size={36} />
          </div>
        )}
        <button
          className={`comic-card__fav${favorited ? ' comic-card__fav--active' : ''}`}
          onClick={handleFavorite}
          aria-label={favorited ? 'Remove from favorites' : 'Add to favorites'}
        >
          <Heart size={16} fill={favorited ? 'currentColor' : 'none'} />
        </button>
        {item.status && (
          <span className={`comic-card__badge badge--${item.status.toLowerCase()}`}>
            {item.status}
          </span>
        )}
        {item.latest_chapter != null && (
          <span className="comic-card__latest">Ch.{item.latest_chapter}</span>
        )}
      </div>

      <div className="comic-card__body">
        <h3 className="comic-card__title">{item.title}</h3>
        <span className="comic-card__source">{source}</span>
        {item.rating != null && (
          <div className="comic-card__rating">
            <Star size={12} aria-hidden="true" />
            <span>{item.rating.toFixed(1)}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
