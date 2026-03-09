import { useLocation } from 'react-router-dom';
import { useLayoutEffect } from 'react';

/**
 * Scrolls to the top of the page on every route change.
 * Must be rendered inside <BrowserRouter>.
 */
export default function ScrollToTop() {
  const { pathname } = useLocation();

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname]);

  return null;
}
