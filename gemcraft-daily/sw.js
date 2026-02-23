const CACHE = 'gemcraft-daily-v1';
const ASSETS = [
  './', './index.html', './css/game.css', './manifest.json',
  './js/main.js', './js/config.js', './js/rng.js', './js/gems.js',
  './js/engine.js', './js/puzzle.js', './js/render.js', './js/audio.js',
  './js/storage.js', './js/ui.js', './js/llm.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
