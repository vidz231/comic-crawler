import { useState, useEffect, useRef } from 'react';

/**
 * Tracks which comic page is currently in view using IntersectionObserver.
 * Watches all elements matching the given selector inside a container ref.
 *
 * @param totalPages - Total number of pages in the chapter
 * @param imagesReady - Set to true once images have been rendered
 * @returns currentPage (1-indexed), updates as the user scrolls
 */
export function usePageTracker(totalPages: number, imagesReady: boolean): number {
  const [currentPage, setCurrentPage] = useState(1);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (!imagesReady || totalPages === 0) return;

    // Small delay to let the DOM settle after images mount
    const timer = setTimeout(() => {
      const images = Array.from(
        document.querySelectorAll<HTMLImageElement>('.reader-image'),
      );
      if (images.length === 0) return;

      // Track which pages are currently intersecting; pick the topmost one
      const visiblePages = new Set<number>();

      observerRef.current = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            const idx = images.indexOf(entry.target as HTMLImageElement);
            if (idx === -1) return;
            if (entry.isIntersecting) {
              visiblePages.add(idx + 1);
            } else {
              visiblePages.delete(idx + 1);
            }
          });
          if (visiblePages.size > 0) {
            setCurrentPage(Math.min(...visiblePages));
          }
        },
        {
          // Trigger once the image top enters the top 60% of the viewport
          rootMargin: '0px 0px -40% 0px',
          threshold: 0,
        },
      );

      images.forEach((img) => observerRef.current!.observe(img));
    }, 100);

    return () => {
      clearTimeout(timer);
      observerRef.current?.disconnect();
      observerRef.current = null;
    };
  }, [totalPages, imagesReady]);

  return currentPage;
}
