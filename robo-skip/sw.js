/**
 * Robo-Skip Service Worker
 * ========================
 * Network-first for everything (always get latest code).
 * Falls back to cache when offline.
 */

const CACHE_NAME = 'roboskip-v11';
const SHELL_ASSETS = [
    './',
    './index.html',
    './styles.css',
    './main.js',
    './engine.js',
    './data.js',
    './manifest.json',
];

// Install — cache app shell
self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(SHELL_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate — clean old caches
self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// Fetch — network-first everywhere, cache as offline fallback
self.addEventListener('fetch', (e) => {
    e.respondWith(
        fetch(e.request)
            .then(res => {
                // Cache a clone for offline use
                const clone = res.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
                return res;
            })
            .catch(() => caches.match(e.request))
    );
});
