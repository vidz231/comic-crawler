import { Link } from 'react-router-dom';
import type { RecentEntry } from '../hooks/useReadingProgress';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import './ContinueReading.css';

interface Props {
  entries: RecentEntry[];
}

function timeAgo(ts: number): string {
  const secs = Math.floor((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function ContinueReading({ entries }: Props) {
  if (entries.length === 0) return null;

  return (
    <section className="continue-reading" aria-label="Continue reading">
      <h2 className="continue-reading__heading">
        Continue Reading
      </h2>

      <div className="continue-reading__scroll">
        {entries.map((entry) => {
          const href = `/comic/${encodeURIComponent(entry.source)}/${encodeURIComponent(entry.slug)}/chapter/${entry.lastChapter}`;
          const coverSrc = proxyImageUrl(entry.cover_url) ?? undefined;

          return (
            <Link
              key={`${entry.source}:${entry.slug}`}
              to={href}
              className="continue-card"
            >
              <div className="continue-card__cover-wrap">
                {coverSrc ? (
                  <img
                    src={coverSrc}
                    alt=""
                    className="continue-card__cover"
                    loading="lazy"
                    crossOrigin={isCorsReady(coverSrc) ? 'anonymous' : undefined}
                  />
                ) : (
                  <div className="continue-card__cover-placeholder" />
                )}
              </div>
              <div className="continue-card__info">
                <span className="continue-card__title">{entry.title}</span>
                <span className="continue-card__meta">
                  Ch.{entry.lastChapter} · {timeAgo(entry.visitedAt)}
                </span>
                <div className="continue-card__progress">
                  <div
                    className="continue-card__progress-fill"
                    style={{ width: `${Math.min(100, (entry.lastChapter / Math.max(entry.lastChapter + 5, 20)) * 100)}%` }}
                  />
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
