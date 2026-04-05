/**
 * AquaVision Service Worker
 * Strategy: Cache-First for static assets (CSS, JS, fonts, images).
 * Network-First for all Flask routes (never serve stale HTML).
 *
 * Safe design:
 *  - Flask routes always hit the network (no stale page risk)
 *  - Only caches /static/* resources
 *  - Cache name is versioned so updates clear old caches
 */

const CACHE_VERSION = 'av-v3';
const STATIC_CACHE  = `${CACHE_VERSION}-static`;

/* Resources to pre-cache on install */
const PRECACHE_URLS = [
    '/static/css/abyssal.css',
    '/static/js/abyssal.js',
    'https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css'
];

/* Install: pre-cache static assets */
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(STATIC_CACHE).then(cache => {
            /* Use individual adds so one failure doesn't block the rest */
            return Promise.allSettled(
                PRECACHE_URLS.map(url => cache.add(url).catch(() => {}))
            );
        })
    );
});

/* Activate: clean up old cache versions */
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k.startsWith('av-') && k !== STATIC_CACHE)
                    .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

/* Fetch: Cache-First ONLY for /static/ paths; Network-First for everything else */
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    /* Only handle GET requests */
    if (event.request.method !== 'GET') return;

    /* Flask routes → always network, never serve cached HTML */
    if (url.origin === location.origin && !url.pathname.startsWith('/static/')) {
        return; /* Let it fall through to normal network fetch */
    }

    /* Static assets → Cache-First */
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                /* Only cache successful, non-opaque responses */
                if (response && response.status === 200 && response.type !== 'opaque') {
                    const clone = response.clone();
                    caches.open(STATIC_CACHE).then(c => c.put(event.request, clone));
                }
                return response;
            }).catch(() => cached); /* Fallback to cache if network fails */
        })
    );
});
