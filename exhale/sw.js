/**
 * Exhale Service Worker
 * Provides offline support for the January 24-25, 2026 development session page
 */

const CACHE_NAME = 'exhale-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
    '/icon.svg',
    '/data/commits.json',
    '/data/metrics.json',
    '/data/arcs.json',
    '/data/files.json',
    // Google Fonts (IBM Plex)
    'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap'
];

// Install: cache assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching assets');
                return cache.addAll(ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {
                            console.log('[SW] Removing old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => self.clients.claim())
    );
});

// Fetch: serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') return;
    
    // Skip cross-origin requests except fonts
    const url = new URL(event.request.url);
    const isFonts = url.hostname === 'fonts.googleapis.com' || 
                   url.hostname === 'fonts.gstatic.com';
    
    if (url.origin !== location.origin && !isFonts) return;
    
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                return fetch(event.request)
                    .then((response) => {
                        // Don't cache non-successful responses
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            // Allow opaque responses for fonts
                            if (isFonts && response && response.type === 'opaque') {
                                const responseClone = response.clone();
                                caches.open(CACHE_NAME)
                                    .then((cache) => cache.put(event.request, responseClone));
                            }
                            return response;
                        }
                        
                        // Cache successful responses
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME)
                            .then((cache) => cache.put(event.request, responseClone));
                        
                        return response;
                    });
            })
    );
});

// Log version
console.log('[SW] Exhale Service Worker v1 loaded');
