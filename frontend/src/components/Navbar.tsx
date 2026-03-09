import { Link, useLocation } from 'react-router-dom';
import { useLayoutEffect } from 'react';
import { BookOpen, Home, Search, Library, Download, Settings } from 'lucide-react';
import { useDownloadManager } from '../contexts/DownloadContext';
import './Navbar.css';

// Exact paths that map to the bottom-bar tabs
const TAB_ROUTES = ['/', '/search', '/library', '/downloads', '/settings'];

export default function Navbar() {
  const { pathname } = useLocation();
  const isTabRoute = TAB_ROUTES.includes(pathname);
  const { downloadQueue, activeDownloads } = useDownloadManager();
  const hasActiveDownloads = !!downloadQueue || activeDownloads.size > 0;

  // Toggle body class so CSS can conditionally add bottom padding for the tab bar
  useLayoutEffect(() => {
    if (isTabRoute) {
      document.body.classList.add('has-tabbar');
    } else {
      document.body.classList.remove('has-tabbar');
    }
    return () => document.body.classList.remove('has-tabbar');
  }, [isTabRoute]);

  // Only show the navbar on the main tab routes
  if (!isTabRoute) return null;

  return (
    <nav className="navbar glass" aria-label="Main navigation">
      <div className="navbar-inner container">
        <Link to="/" className="navbar-brand">
          <BookOpen size={22} aria-hidden="true" />
          <span>ComicCrawler</span>
        </Link>

        <div className="navbar-links">
          <Link
            to="/"
            aria-current={pathname === '/' ? 'page' : undefined}
            className={`navbar-link ${pathname === '/' ? 'active' : ''}`}
          >
            <Home size={18} aria-hidden="true" />
            <span className="navbar-link-label">Home</span>
          </Link>
          <Link
            to="/search"
            aria-current={pathname.startsWith('/search') ? 'page' : undefined}
            className={`navbar-link ${pathname.startsWith('/search') ? 'active' : ''}`}
          >
            <Search size={18} aria-hidden="true" />
            <span className="navbar-link-label">Search</span>
          </Link>
          <Link
            to="/library"
            aria-current={pathname.startsWith('/library') ? 'page' : undefined}
            className={`navbar-link ${pathname.startsWith('/library') ? 'active' : ''}`}
          >
            <Library size={18} aria-hidden="true" />
            <span className="navbar-link-label">Library</span>
          </Link>
          <Link
            to="/downloads"
            aria-current={pathname === '/downloads' ? 'page' : undefined}
            className={`navbar-link ${pathname === '/downloads' ? 'active' : ''}${hasActiveDownloads ? ' has-badge' : ''}`}
          >
            <Download size={18} aria-hidden="true" />
            <span className="navbar-link-label">Downloads</span>
            {hasActiveDownloads && <span className="navbar-badge" aria-label="Downloads in progress" />}
          </Link>
          <Link
            to="/settings"
            aria-current={pathname === '/settings' ? 'page' : undefined}
            className={`navbar-link ${pathname === '/settings' ? 'active' : ''}`}
          >
            <Settings size={18} aria-hidden="true" />
            <span className="navbar-link-label">Settings</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
