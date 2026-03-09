import { lazy, Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import PwaUpdatePrompt from './components/PwaUpdatePrompt';
import InstallPrompt from './components/InstallPrompt';
import OfflineBanner from './components/OfflineBanner';
import ScrollToTop from './components/ScrollToTop';
import ErrorBoundary from './components/ErrorBoundary';
import ReaderLayout from './layouts/ReaderLayout';
import DownloadIndicator from './components/DownloadIndicator';
import { DownloadProvider } from './contexts/DownloadContext';
import { useVersionCheck } from './hooks/useVersionCheck';
import { useAppearance } from './hooks/useAppearance';

// Lazy-loaded pages for code-splitting
const HomePage = lazy(() => import('./pages/HomePage'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const ComicDetailPage = lazy(() => import('./pages/ComicDetailPage'));
const ChapterReaderPage = lazy(() => import('./pages/ChapterReaderPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LibraryPage = lazy(() => import('./pages/LibraryPage'));
const ImportExportPage = lazy(() => import('./pages/ImportExportPage'));
const DownloadsPage = lazy(() => import('./pages/DownloadsPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/** Minimal full-page skeleton shown while a lazy route chunk loads. */
function PageFallback() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <div className="skeleton" style={{ width: 48, height: 48, borderRadius: '50%' }} />
    </div>
  );
}

export default function App() {
  // Poll /version.json — hard-reload + nuke SW caches when a new build is deployed
  useVersionCheck(60_000);
  // Apply global appearance (theme + text size) on initial mount
  useAppearance();

  return (
    <QueryClientProvider client={queryClient}>
      <DownloadProvider>
        <BrowserRouter>
          <ScrollToTop />
          <a href="#main-content" className="skip-link">Skip to main content</a>
          <Navbar />
          <PwaUpdatePrompt />
          <InstallPrompt />
          <OfflineBanner />
          <DownloadIndicator />
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<ErrorBoundary label="Home"><HomePage /></ErrorBoundary>} />
              <Route path="/search" element={<ErrorBoundary label="Search"><SearchPage /></ErrorBoundary>} />
              <Route path="/settings" element={<ErrorBoundary label="Settings"><SettingsPage /></ErrorBoundary>} />
              <Route path="/settings/import-export" element={<ErrorBoundary label="Import/Export"><ImportExportPage /></ErrorBoundary>} />
              <Route path="/library" element={<ErrorBoundary label="Library"><LibraryPage /></ErrorBoundary>} />
              <Route path="/downloads" element={<ErrorBoundary label="Downloads"><DownloadsPage /></ErrorBoundary>} />
              <Route path="/comic/:source/:slug" element={<ErrorBoundary label="Comic Detail"><ComicDetailPage /></ErrorBoundary>} />

              {/* Chapter reader — nested inside ReaderLayout so all fixed chrome
                  (FABs, settings panel, progress bar) lives outside any animated
                  ancestor, keeping position:fixed relative to the true viewport */}
              <Route element={<ReaderLayout />}>
                <Route
                  path="/comic/:source/:slug/chapter/:number"
                  element={<ErrorBoundary label="Chapter Reader"><ChapterReaderPage /></ErrorBoundary>}
                />
              </Route>

              {/* 404 fallback */}
              <Route
                path="*"
                element={
                  <div style={{ textAlign: 'center', padding: '80px 24px', color: 'var(--color-text-muted)' }}>
                    <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '2rem', color: '#fff', marginBottom: 12 }}>
                      404
                    </h2>
                    Page not found.
                  </div>
                }
              />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </DownloadProvider>
    </QueryClientProvider>
  );
}
