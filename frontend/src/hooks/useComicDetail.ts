import { useQuery } from '@tanstack/react-query';
import { fetchComicDetail } from '../api/endpoints';

/**
 * Shared hook for fetching comic detail data.
 *
 * Used by both `ComicDetailPage` and `ChapterReaderPage`
 * to avoid duplicated `useQuery` configuration.
 */
export function useComicDetail(source: string, slug: string) {
  return useQuery({
    queryKey: ['comic', source, slug],
    queryFn: () => fetchComicDetail(source, slug),
    enabled: !!source && !!slug,
    staleTime: 5 * 60_000,
  });
}

/**
 * Build a chapter link path from source, slug, and chapter number.
 *
 * Used across `ComicDetailPage` and `ChapterReaderPage`
 * to generate consistent navigation URLs.
 */
export function makeChapterLink(
  source: string,
  slug: string,
  chapterNum: number,
): string {
  return `/comic/${encodeURIComponent(source)}/${encodeURIComponent(slug)}/chapter/${chapterNum}`;
}
