import { useEffect } from 'react';

/**
 * Sets the document <title> while the component is mounted.
 * Restores the previous title on unmount (handles nested routes).
 */
export function useDocTitle(title: string) {
  useEffect(() => {
    const prev = document.title;
    document.title = `${title} — ComicCrawler`;
    return () => {
      document.title = prev;
    };
  }, [title]);
}
