import { defineConfig } from 'vite'
import { writeFileSync } from 'fs'
import { resolve } from 'path'
import { randomBytes } from 'crypto'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Generate a unique build hash for each build
const BUILD_HASH = randomBytes(8).toString('hex')

/**
 * Tiny Vite plugin that writes a version.json into the output directory
 * after every production build. The frontend polls this file to detect
 * when a new version has been deployed.
 */
function versionJsonPlugin() {
  return {
    name: 'version-json',
    closeBundle() {
      const versionData = JSON.stringify({ hash: BUILD_HASH, builtAt: new Date().toISOString() })
      writeFileSync(resolve(__dirname, 'dist', 'version.json'), versionData)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __BUILD_HASH__: JSON.stringify(BUILD_HASH),
  },
  build: {
    target: ['es2020', 'safari15', 'chrome87', 'firefox78', 'edge88'],
  },
  plugins: [
    react(),
    versionJsonPlugin(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['pwa-icon.svg', 'offline.html'],

      // ── Web App Manifest ──────────────────────────────────────────────────────
      manifest: {
        name: 'Comic Reader',
        short_name: 'Comics',
        description: 'Read your favourite manga & webtoons — even offline.',
        theme_color: '#080810',
        background_color: '#080810',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/?source=pwa',
        categories: ['comics', 'entertainment'],
        icons: [
          {
            src: 'pwa-icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: 'icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },

      // ── Workbox service-worker config ─────────────────────────────────────────
      workbox: {
        // Pre-cache the app shell (but NOT version.json — must always hit server)
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        globIgnores: ['**/version.json'],

        // Force the new SW to activate immediately — prevents blank screen
        // after deploys where old SW serves stale precached assets
        skipWaiting: true,
        clientsClaim: true,
        // Remove old precache buckets so stale JS/CSS don't linger
        cleanupOutdatedCaches: true,

        runtimeCaching: [
          {
            // Google Fonts stylesheets — SWR keeps font-face rules fresh
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'google-fonts-css',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            // Google Fonts files — CacheFirst (immutable)
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-woff2',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // External comic images (pages + covers from CDN origins)
            // CacheFirst: images never change once published
            urlPattern: /^https:\/\/.*\.(jpg|jpeg|png|webp|gif|avif)(\?.*)?$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'comic-images',
              expiration: {
                maxEntries: 500,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            // Chapter API responses — cache-first (rarely change)
            urlPattern: /\/api\/v1\/.*\/chapter\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'chapter-api',
              expiration: {
                maxEntries: 60,
                maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // All other API calls — network-first with 5 s fallback to cache
            urlPattern: /\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24, // 1 day
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],

        // Show offline.html when navigation fails and page isn't cached
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],

  server: {
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
