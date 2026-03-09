import { useState, useCallback, useEffect, useRef } from 'react';
import type { PageOut } from '../api/types';
import { proxyImageUrl, isCorsReady } from '../utils/imageProxy';
import { getImageAsObjectUrl } from '../utils/offlineDb';

interface ReaderImageProps {
  page: PageOut;
  /** IDB key for this page if the chapter is downloaded offline */
  offlineKey?: string;
  /** Called once the image fires onLoad so the parent can track readiness */
  onLoad?: () => void;
}

/**
 * A single comic page image with:
 * - Offline-first: checks IndexedDB blob before network
 * - Skeleton shimmer while loading
 * - Styled error block + Retry button on failure
 */
export default function ReaderImage({ page, offlineKey, onLoad }: ReaderImageProps) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [retrySuffix, setRetrySuffix] = useState('');
  const [offlineSrc, setOfflineSrc] = useState<string | null>(null);
  const offlineSrcRef = useRef<string | null>(null);

  // Try loading from IndexedDB first
  useEffect(() => {
    if (!offlineKey) return;

    let revoked = false;
    getImageAsObjectUrl(offlineKey).then((url) => {
      if (revoked) {
        if (url) URL.revokeObjectURL(url);
        return;
      }
      if (url) {
        offlineSrcRef.current = url;
        setOfflineSrc(url);
      }
    });

    return () => {
      revoked = true;
      if (offlineSrcRef.current) {
        URL.revokeObjectURL(offlineSrcRef.current);
        offlineSrcRef.current = null;
      }
    };
  }, [offlineKey]);

  const handleLoad = useCallback(() => {
    setStatus('loaded');
    onLoad?.();
  }, [onLoad]);

  const handleError = useCallback(() => {
    setStatus('error');
  }, []);

  const handleRetry = useCallback(() => {
    setStatus('loading');
    setRetrySuffix(`?retry=${Date.now()}`);
  }, []);

  // Use offline blob URL if available, otherwise proxy the network URL
  const networkSrc = `${proxyImageUrl(page.image_url) ?? page.image_url}${retrySuffix}`;
  const resolvedSrc = offlineSrc ?? networkSrc;

  return (
    <div className="reader-image-wrapper">
      {/* Shimmer placeholder — shown while loading */}
      {status === 'loading' && (
        <div className="reader-image-skeleton skeleton" aria-hidden="true" />
      )}

      {/* Error state */}
      {status === 'error' && (
        <div className="reader-image-error" role="alert">
          <span className="reader-image-error-icon">⚠</span>
          <p className="reader-image-error-text">Page {page.page_number} failed to load</p>
          <button className="reader-image-retry-btn" onClick={handleRetry}>
            Retry
          </button>
        </div>
      )}

      {/* The actual image — hidden until loaded, kept in DOM for IntersectionObserver */}
      <img
        src={resolvedSrc}
        alt={`Page ${page.page_number}`}
        className="reader-image"
        loading="eager"
        crossOrigin={!offlineSrc && isCorsReady(resolvedSrc) ? 'anonymous' : undefined}
        onLoad={handleLoad}
        onError={handleError}
        onContextMenu={(e) => e.preventDefault()}
        style={{ display: status === 'error' ? 'none' : 'block' }}
      />
    </div>
  );
}
