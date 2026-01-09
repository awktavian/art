/**
 * Service Worker for "What About the Weather?"
 *
 * Cache-first strategy for static assets,
 * Network-first for API calls
 *
 * h(x) >= 0
 */

const CACHE_NAME = 'weather-celestial-v1';
const STATIC_CACHE = 'weather-static-v1';
const DYNAMIC_CACHE = 'weather-dynamic-v1';

// Static assets to cache immediately
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/styles.css',
    '/main.js',
    '/i18n.js',
    '/favicon.svg',
    '/manifest.webmanifest'
];

// External resources (fonts, CDNs)
const EXTERNAL_ASSETS = [
    'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap'
];

// =========================================================================
// INSTALL - Cache static assets
// =========================================================================

self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');

    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[SW] Static assets cached');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[SW] Install failed:', error);
            })
    );
});

// =========================================================================
// ACTIVATE - Clean up old caches
// =========================================================================

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            // Delete old cache versions
                            return name.startsWith('weather-') &&
                                   name !== STATIC_CACHE &&
                                   name !== DYNAMIC_CACHE;
                        })
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Claiming clients');
                return self.clients.claim();
            })
    );
});

// =========================================================================
// FETCH - Serve from cache with network fallback
// =========================================================================

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // Weather API calls - network first, cache fallback
    if (url.hostname === 'api.open-meteo.com' ||
        url.hostname === 'ipapi.co') {
        event.respondWith(networkFirst(request));
        return;
    }

    // CDN resources (Three.js, fonts) - cache first
    if (url.hostname.includes('cdn') ||
        url.hostname.includes('fonts') ||
        url.hostname.includes('gstatic')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Static assets - cache first
    if (STATIC_ASSETS.some(asset => url.pathname.endsWith(asset.replace('/', '')))) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Everything else - stale while revalidate
    event.respondWith(staleWhileRevalidate(request));
});

// =========================================================================
// CACHING STRATEGIES
// =========================================================================

/**
 * Cache first, network fallback
 * Best for: static assets that don't change often
 */
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        console.error('[SW] Cache-first fetch failed:', error);
        return new Response('Offline', { status: 503 });
    }
}

/**
 * Network first, cache fallback
 * Best for: API calls where freshness matters
 */
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        console.log('[SW] Network failed, trying cache...');
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        return new Response(JSON.stringify({
            error: 'Offline',
            cached: false
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * Stale while revalidate
 * Best for: content that can be slightly stale
 */
async function staleWhileRevalidate(request) {
    const cache = await caches.open(DYNAMIC_CACHE);
    const cached = await cache.match(request);

    const fetchPromise = fetch(request)
        .then((response) => {
            if (response.ok) {
                cache.put(request, response.clone());
            }
            return response;
        })
        .catch(() => cached);

    return cached || fetchPromise;
}

// =========================================================================
// BACKGROUND SYNC (for offline weather updates)
// =========================================================================

self.addEventListener('sync', (event) => {
    if (event.tag === 'weather-sync') {
        console.log('[SW] Background sync: weather-sync');
        event.waitUntil(syncWeatherData());
    }
});

async function syncWeatherData() {
    // Attempt to refresh weather data when back online
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_COMPLETE',
            timestamp: Date.now()
        });
    });
}

// =========================================================================
// PUSH NOTIFICATIONS (ready for future use)
// =========================================================================

self.addEventListener('push', (event) => {
    if (!event.data) return;

    const data = event.data.json();
    const options = {
        body: data.body || 'Weather update available',
        icon: '/favicon.svg',
        badge: '/favicon.svg',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'Weather', options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});

console.log('[SW] Service worker loaded');
