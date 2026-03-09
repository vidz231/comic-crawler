/**
 * Backward-compatible re-export of the global download manager.
 *
 * Previously this hook held all download state locally.
 * Now it delegates to the singleton DownloadContext so that
 * every consumer (ComicDetailPage, ChapterReaderPage, LibraryPage, etc.)
 * shares the same live download state.
 */
export {
  useDownloadManager as useOfflineChapters,
  type DownloadProgress,
  type DownloadedMeta,
  type DownloadQueueState,
  type ChapterDownloadDescriptor,
} from '../contexts/DownloadContext';
