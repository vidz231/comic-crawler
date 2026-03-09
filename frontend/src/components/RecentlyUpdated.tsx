import { useQuery } from '@tanstack/react-query';
import { Clock } from 'lucide-react';
import { fetchMultiSearch } from '../api/endpoints';
import ComicCard from './ComicCard';
import './RecentlyUpdated.css';

/**
 * Recently Updated — aggregates the default browse order from all sources.
 * The default ordering in most sources is "recently updated", so we simply
 * fetch page 1 across all sources and merge the results.
 */
export default function RecentlyUpdated() {
  const { data, isLoading } = useQuery({
    queryKey: ['recentlyUpdated'],
    queryFn: () => fetchMultiSearch(undefined, undefined, undefined, 1),
    staleTime: 2 * 60_000,
  });

  if (isLoading || !data) return null;

  // Flatten + de-dupe across sources, take first 12
  const seen = new Set<string>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: { source: string; item: any }[] = [];
  const results = Array.isArray(data.results) ? data.results : [];
  for (const result of results) {
    const inner = Array.isArray(result?.results) ? result.results : [];
    for (const r of inner) {
      if (r?.slug && !seen.has(r.slug) && items.length < 12) {
        seen.add(r.slug);
        items.push({ source: result.source, item: r });
      }
    }
  }

  if (items.length === 0) return null;

  return (
    <section className="recently-updated" aria-label="Recently updated">
      <h2 className="section-heading">
        <Clock size={16} aria-hidden="true" />
        Recently Updated
      </h2>
      <div className="recently-updated__scroll">
        {items.map(({ source, item }) => (
          <ComicCard key={`${source}-${item.slug}`} source={source} item={item} />
        ))}
      </div>
    </section>
  );
}
