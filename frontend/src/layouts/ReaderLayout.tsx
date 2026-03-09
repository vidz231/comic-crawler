import { Outlet, useOutletContext } from 'react-router-dom';
import { useEffect, useLayoutEffect, useRef, useState, useCallback } from 'react';
import { ArrowUp } from 'lucide-react';
import { useReaderSettings } from '../hooks/useReaderSettings';
import ReaderSettingsPanel from '../components/ReaderSettingsPanel';
import './ReaderLayout.css';

// ── Outlet context type — shared from layout down to ChapterReaderPage ────────
interface ReaderLayoutContext {
  settings: ReturnType<typeof useReaderSettings>['settings'];
  setSettings: ReturnType<typeof useReaderSettings>['setSettings'];
  scrollProgress: number;
}

export function useReaderContext() {
  return useOutletContext<ReaderLayoutContext>();
}

/**
 * Outer layout for the chapter reader.
 * Owns all `position: fixed` chrome (FABs, settings panel, progress bar)
 * so they are NOT children of any transformed/animated/filtered ancestor.
 *
 * ChapterReaderPage renders as an Outlet inside the plain <div> wrapper.
 */
export default function ReaderLayout() {
  const { settings, setSettings, resetSettings, defaults } = useReaderSettings();

  // ── Body class — hides global navbar, applied before paint to avoid flash ─────
  useLayoutEffect(() => {
    document.body.classList.add('reader-mode');
    return () => document.body.classList.remove('reader-mode');
  }, []);

  // ── Scroll progress (for progress bar + FAB threshold) ───────────────────
  const [scrollProgress, setScrollProgress] = useState(0);
  const rafRef = useRef<ReturnType<typeof requestAnimationFrame> | undefined>(undefined);

  useEffect(() => {
    const handleScroll = () => {
      if (rafRef.current !== undefined) return;
      rafRef.current = requestAnimationFrame(() => {
        const el = document.documentElement;
        const scrollable = el.scrollHeight - el.clientHeight;
        const pct = scrollable > 0 ? el.scrollTop / scrollable : 0;
        setScrollProgress(Math.min(1, Math.max(0, pct)));
        rafRef.current = undefined;
      });
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const scrollToTop = useCallback(() => window.scrollTo({ top: 0, behavior: 'smooth' }), []);

  const context: ReaderLayoutContext = { settings, setSettings, scrollProgress };

  return (
    <>
      {/* The reader page content — plain wrapper with NO transform/filter/animation */}
      <div className="reader-layout-content">
        <Outlet context={context} />
      </div>

      {/*
        All `position: fixed` UI lives here, OUTSIDE any animated/transformed ancestor.
        This is the key architectural fix: these elements are direct children of
        the document flow root, so `position: fixed` is relative to the true viewport.
      */}

      {/* Thin scroll progress bar — always on top */}
      <div
        className="reader-progress-bar"
        style={{ transform: `scaleX(${scrollProgress})` }}
        role="progressbar"
        aria-valuenow={Math.round(scrollProgress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Reading progress"
      />

      {/* Settings panel (gear FAB + slide-out drawer) */}
      <ReaderSettingsPanel
        settings={settings}
        defaults={defaults}
        onUpdate={setSettings}
        onReset={resetSettings}
      />

      {/* Scroll-to-top FAB */}
      <button
        className={`reader-fab reader-fab--top${scrollProgress > 0.3 ? ' visible' : ''}`}
        onClick={scrollToTop}
        aria-label="Scroll to top"
        title="Back to top"
      >
        <ArrowUp size={18} />
      </button>
    </>
  );
}
