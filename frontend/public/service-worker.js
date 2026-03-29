const APP_PREFIX = new URL(self.registration.scope).pathname;
const CACHE_NAME = 'filamentfinder-shell-v11';
const CORE_URLS = [
  APP_PREFIX,
  `${APP_PREFIX}manifest.webmanifest?v=11`,
  `${APP_PREFIX}fila-logo.png`,
  `${APP_PREFIX}pwa-192.png`,
  `${APP_PREFIX}pwa-512.png`,
  `${APP_PREFIX}apple-touch-icon.png`,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_URLS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }

  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  // Never cache API calls or the runtime env config — always pass through to network.
  if (
    requestUrl.pathname.includes('/api/') ||
    requestUrl.pathname.endsWith('/env-config.js')
  ) {
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        return cache.match(APP_PREFIX);
      }),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && requestUrl.pathname.startsWith(APP_PREFIX)) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        }
        return networkResponse;
      }).catch(() => {
        // Network failed and nothing in cache — let the browser handle it normally.
        return new Response('Network error', { status: 503, statusText: 'Service Unavailable' });
      });
    }),
  );
});
