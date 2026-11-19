// Offline support for the program explorer.
// The page is one self-contained file, so keeping a copy of it is enough.
// Network first, so a new deploy shows on the next visit; the saved copy
// answers when offline, or when conference wifi takes more than 4 seconds.
const CACHE = 'aip2026-v1';
const CORE = ['./', './manifest.webmanifest', './icon-192.png', './icon-512.png', './apple-touch-icon.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});

function fromCache(request){
  return caches.match(request, { ignoreSearch: true })
    .then(hit => hit || (request.mode === 'navigate' ? caches.match('./') : undefined));
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;
  const network = fetch(request).then(response => {
    if (response.ok && response.type === 'basic'){
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(request, copy));
    }
    return response;
  });
  event.respondWith(new Promise(resolve => {
    let settled = false;
    const finish = response => { if (!settled && response){ settled = true; resolve(response); } };
    network.then(finish, () => fromCache(request).then(hit => finish(hit || Response.error())));
    setTimeout(() => fromCache(request).then(finish), 4000);
  }));
});
