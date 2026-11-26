// Service Worker do Aponta e Fala — garante abertura e uso da prancha mesmo sem internet.
const CACHE_NAME = "aponta-e-fala-v1";
const PRECACHE = [
  "/",
  "/manifest.webmanifest",
  "/static/offline-core.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/barriga.svg",
  "/static/icons/cabeca.svg",
  "/api/config",
  "/api/ngram",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(PRECACHE.map((url) => cache.add(url)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

async function networkFirst(request, timeoutMs) {
  const cache = await caches.open(CACHE_NAME);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(request, { signal: ctrl.signal });
    clearTimeout(timer);
    if (resp && resp.ok) {
      cache.put(request, resp.clone());
    }
    return resp;
  } catch {
    clearTimeout(timer);
    const cached = await cache.match(request);
    if (cached) return cached;
    throw new Error("offline");
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  const resp = await fetch(request);
  if (resp && resp.ok) cache.put(request, resp.clone());
  return resp;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === "/api/health" || url.pathname.startsWith("/admin") || url.pathname.startsWith("/api/admin")) {
    return;
  }

  if (url.pathname === "/" || url.pathname === "/api/config" || url.pathname === "/api/ngram") {
    event.respondWith(networkFirst(req, 2500));
    return;
  }

  if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/uploads/") || url.pathname === "/manifest.webmanifest") {
    event.respondWith(cacheFirst(req));
  }
});
