import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import {
  saveImage, imageKey, deleteChapterImages, clearAllImages,
  saveChapterData, chapterDataKey, deleteChapterData, clearAllChapterData,
} from '../utils/offlineDb';
import { proxyImageUrl } from '../utils/imageProxy';
import type { ChapterReadResponse } from '../api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DownloadProgress {
  total: number;
  loaded: number;
  /** 0-100 */
  pct: number;
}

export interface DownloadedMeta {
  source: string;
  slug: string;
  number: number;
  title: string;
  pageCount: number;
  downloadedAt: string;
}

export interface DownloadQueueState {
  /** Comic title for the queue */
  comicTitle: string;
  /** Total chapters in the queue */
  total: number;
  /** Chapters completed so far */
  completed: number;
  /** Chapter number currently downloading, or null */
  current: number | null;
  /** Overall queue progress 0-100 */
  pct: number;
}

export interface ChapterDownloadDescriptor {
  number: number;
  fetchPages: () => Promise<string[]>;
  chapterData?: ChapterReadResponse;
}

// ── Context value shape ───────────────────────────────────────────────────────

interface DownloadContextValue {
  downloads: DownloadedMeta[];
  activeDownloads: Map<string, DownloadProgress>;
  downloadQueue: DownloadQueueState | null;
  isChapterDownloaded: (source: string, slug: string, number: number) => boolean;
  downloadChapter: (
    source: string, slug: string, number: number, title: string,
    imageUrls: string[], chapterResponse?: ChapterReadResponse
  ) => void;
  downloadMultipleChapters: (
    source: string, slug: string, title: string,
    chapters: ChapterDownloadDescriptor[]
  ) => void;
  cancelQueue: () => void;
  deleteChapter: (source: string, slug: string, number: number) => Promise<void>;
  clearAllDownloads: () => Promise<void>;
}

const DownloadContext = createContext<DownloadContextValue | null>(null);

// ── Helpers ───────────────────────────────────────────────────────────────────

const META_KEY = 'offline-chapters-meta';

function readMeta(): DownloadedMeta[] {
  try {
    return JSON.parse(localStorage.getItem(META_KEY) || '[]');
  } catch {
    return [];
  }
}

function writeMeta(meta: DownloadedMeta[]) {
  localStorage.setItem(META_KEY, JSON.stringify(meta));
}

function chapterCacheKey(source: string, slug: string, number: number) {
  return `${source}/${slug}/${number}`;
}

async function downloadImageBatch(
  imageUrls: string[],
  source: string,
  slug: string,
  chapterNum: number,
  progress: DownloadProgress,
  onProgress: (p: DownloadProgress) => void,
  cancelledRef?: React.RefObject<boolean>
): Promise<void> {
  for (let i = 0; i < imageUrls.length; i++) {
    if (cancelledRef?.current) break;

    const key = imageKey(source, slug, chapterNum, i);
    try {
      const fetchUrl = proxyImageUrl(imageUrls[i]) ?? imageUrls[i];
      const resp = await fetch(fetchUrl, { mode: 'cors' });
      if (resp.ok) {
        const blob = await resp.blob();
        await saveImage(key, blob);
      }
    } catch {
      /* skip individual failures */
    }

    progress.loaded += 1;
    progress.pct = Math.round((progress.loaded / progress.total) * 100);
    onProgress({ ...progress });
  }
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function DownloadProvider({ children }: { children: ReactNode }) {
  const [downloads, setDownloads] = useState<DownloadedMeta[]>(readMeta);
  const [activeDownloads, setActiveDownloads] = useState<Map<string, DownloadProgress>>(new Map());
  const [downloadQueue, setDownloadQueue] = useState<DownloadQueueState | null>(null);
  const cancelledRef = useRef(false);

  // Sync metadata across tabs
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === META_KEY) setDownloads(readMeta());
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const isChapterDownloaded = useCallback(
    (source: string, slug: string, number: number) =>
      downloads.some(
        (d) => d.source === source && d.slug === slug && d.number === number
      ),
    [downloads]
  );

  const downloadChapter = useCallback(
    async (
      source: string,
      slug: string,
      number: number,
      title: string,
      imageUrls: string[],
      chapterResponse?: ChapterReadResponse
    ) => {
      const key = chapterCacheKey(source, slug, number);

      if (
        downloads.some((d) => d.source === source && d.slug === slug && d.number === number) ||
        activeDownloads.has(key)
      ) {
        return;
      }

      const progress: DownloadProgress = { total: imageUrls.length, loaded: 0, pct: 0 };
      setActiveDownloads((prev) => new Map(prev).set(key, { ...progress }));

      try {
        await downloadImageBatch(
          imageUrls, source, slug, number, progress,
          (p) => setActiveDownloads((prev) => new Map(prev).set(key, p))
        );

        if (chapterResponse) {
          const cdKey = chapterDataKey(source, slug, number);
          await saveChapterData(cdKey, chapterResponse);
        }

        const meta: DownloadedMeta = {
          source, slug, number, title,
          pageCount: imageUrls.length,
          downloadedAt: new Date().toISOString(),
        };
        const updated = [...readMeta(), meta];
        writeMeta(updated);
        setDownloads(updated);
      } finally {
        setActiveDownloads((prev) => {
          const next = new Map(prev);
          next.delete(key);
          return next;
        });
      }
    },
    [downloads, activeDownloads]
  );

  const downloadMultipleChapters = useCallback(
    async (
      source: string,
      slug: string,
      title: string,
      chapters: ChapterDownloadDescriptor[]
    ) => {
      const currentMeta = readMeta();
      const toDownload = chapters.filter(
        (ch) => !currentMeta.some(
          (d) => d.source === source && d.slug === slug && d.number === ch.number
        )
      );

      if (toDownload.length === 0) return;

      cancelledRef.current = false;
      const queueState: DownloadQueueState = {
        comicTitle: title,
        total: toDownload.length,
        completed: 0,
        current: null,
        pct: 0,
      };
      setDownloadQueue({ ...queueState });

      for (const ch of toDownload) {
        if (cancelledRef.current) break;

        queueState.current = ch.number;
        setDownloadQueue({ ...queueState });

        try {
          const urls = await ch.fetchPages();
          if (cancelledRef.current) break;

          const key = chapterCacheKey(source, slug, ch.number);
          const progress: DownloadProgress = { total: urls.length, loaded: 0, pct: 0 };
          setActiveDownloads((prev) => new Map(prev).set(key, { ...progress }));

          try {
            await downloadImageBatch(
              urls, source, slug, ch.number, progress,
              (p) => setActiveDownloads((prev) => new Map(prev).set(key, p)),
              cancelledRef
            );

            if (!cancelledRef.current) {
              const meta: DownloadedMeta = {
                source, slug, number: ch.number, title,
                pageCount: urls.length,
                downloadedAt: new Date().toISOString(),
              };
              const updated = [...readMeta(), meta];
              writeMeta(updated);
              setDownloads(updated);
            }
          } finally {
            setActiveDownloads((prev) => {
              const next = new Map(prev);
              next.delete(key);
              return next;
            });
          }
        } catch {
          /* skip chapter if fetchPages fails */
        }

        queueState.completed += 1;
        queueState.pct = Math.round((queueState.completed / queueState.total) * 100);
        setDownloadQueue({ ...queueState });
      }

      setDownloadQueue(null);
    },
    []
  );

  const cancelQueue = useCallback(() => {
    cancelledRef.current = true;
    setDownloadQueue(null);
  }, []);

  const deleteChapter = useCallback(
    async (source: string, slug: string, number: number) => {
      const prefix = chapterCacheKey(source, slug, number);
      await deleteChapterImages(`${prefix}/`);
      await deleteChapterData(chapterDataKey(source, slug, number));

      const updated = readMeta().filter(
        (d) => !(d.source === source && d.slug === slug && d.number === number)
      );
      writeMeta(updated);
      setDownloads(updated);
    },
    []
  );

  const clearAllDownloads = useCallback(async () => {
    await clearAllImages();
    await clearAllChapterData();
    writeMeta([]);
    setDownloads([]);
  }, []);

  return (
    <DownloadContext.Provider
      value={{
        downloads,
        activeDownloads,
        downloadQueue,
        isChapterDownloaded,
        downloadChapter,
        downloadMultipleChapters,
        cancelQueue,
        deleteChapter,
        clearAllDownloads,
      }}
    >
      {children}
    </DownloadContext.Provider>
  );
}

/** Consume the global download context. Throws if used outside DownloadProvider. */
export function useDownloadManager() {
  const ctx = useContext(DownloadContext);
  if (!ctx) throw new Error('useDownloadManager must be used within DownloadProvider');
  return ctx;
}
