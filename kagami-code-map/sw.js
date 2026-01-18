/**
 * Service Worker for Code Galaxy PWA
 * Provides offline caching and background sync
 */

const CACHE_VERSION = 'code-galaxy-v7.0.0';
const STATIC_CACHE = CACHE_VERSION + '-static';
const DATA_CACHE = CACHE_VERSION + '-data';

// Static assets to cache on install
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon.svg',
  './icon-192.png',
  './icon-512.png',
];

// Data files that should be cached but updated when online
const DATA_ASSETS = [
  './codebase-analysis.json',
];

// Install event - cache static assets
self.addEventListener('install', event => {
  console.log(`[SW] Installing ${CACHE_VERSION}...`);
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        // Also try to cache data assets (may fail if not available)
        return caches.open(DATA_CACHE)
          .then(cache => {
            return Promise.all(
              DATA_ASSETS.map(url => 
                cache.add(url).catch(err => console.log('[SW] Data not cached:', url))
              )
            );
          });
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames
            .filter(name => name.startsWith('code-galaxy-') && name !== STATIC_CACHE && name !== DATA_CACHE)
            .map(name => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache, update in background
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Only handle same-origin requests
  if (url.origin !== location.origin) {
    return;
  }
  
  // Handle data files with stale-while-revalidate
  if (url.pathname.includes('codebase-analysis.json')) {
    event.respondWith(staleWhileRevalidate(event.request, DATA_CACHE));
    return;
  }
  
  // Handle static assets with cache-first
  event.respondWith(cacheFirst(event.request, STATIC_CACHE));
});

// Cache-first strategy for static assets
async function cacheFirst(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network failed:', request.url);
    
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      return caches.match('./index.html');
    }
    
    throw error;
  }
}

// Stale-while-revalidate for data files
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);
  
  // Fetch in background and update cache
  const fetchPromise = fetch(request)
    .then(networkResponse => {
      if (networkResponse.ok) {
        cache.put(request, networkResponse.clone());
        
        // Notify clients of update
        self.clients.matchAll().then(clients => {
          clients.forEach(client => {
            client.postMessage({
              type: 'DATA_UPDATED',
              url: request.url,
            });
          });
        });
      }
      return networkResponse;
    })
    .catch(err => {
      console.log('[SW] Network fetch failed:', err);
      return cachedResponse;
    });
  
  // Return cached response immediately, or wait for network
  return cachedResponse || fetchPromise;
}

// Handle messages from clients
self.addEventListener('message', event => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
