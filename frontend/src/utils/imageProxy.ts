import { buildApiUrl, isApiUrl } from '../config/api';

/**
 * Rewrite an external image URL to go through the backend image proxy.
 * Only proxies TruyenQQ CDN domains to bypass hotlink protection.
 *
 * Returns `null` for null/undefined inputs, passes through everything else as-is.
 */

// Domains that need proxying to bypass hotlink / referrer protection
const PROXY_DOMAINS = [
  // TruyenQQ CDNs
  'truyenqqno.com', 'truyenvua.com', 'tintruyen.net', 'hinhhinh.com', 'hinhtruyen.com',
  // MangaKakalot / Manganato CDN
  '2xstorage.com',
  // WordPress-hosted manga images behind Cloudflare
  'khotruyen.ac',
];

export function proxyImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith('data:') || url.includes('/api/v1/image-proxy')) return url;
  // Only proxy allowlisted CDN domains
  if (!PROXY_DOMAINS.some(d => url!.includes(d))) return url;
  return buildApiUrl(`/api/v1/image-proxy?url=${encodeURIComponent(url)}`);
}

/**
 * Whether the resolved image URL can safely use `crossOrigin="anonymous"`.
 * True for same-origin paths (like our image proxy) and data: URIs.
 * False for external CDN images that don't return CORS headers.
 */
export function isCorsReady(resolvedUrl: string | null | undefined): boolean {
  if (!resolvedUrl) return false;
  if (resolvedUrl.startsWith('data:')) return true;
  // Our own proxy / relative paths are same-origin → always CORS-safe
  if (resolvedUrl.startsWith('/')) return true;
  if (isApiUrl(resolvedUrl)) return true;
  try {
    return new URL(resolvedUrl).origin === window.location.origin;
  } catch {
    return false;
  }
}
