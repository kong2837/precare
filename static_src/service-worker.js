const CACHE_NAME = 'precare-cache-v1';
const urlsToCache = [
'/',
'/static_src/IC_LOGO.png', 
  '/manifest.json',
  // 필요한 정적 리소스들 추가
];

self.addEventListener('install', (event) => {
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
    );
  });
  
  self.addEventListener('fetch', (event) => {
    event.respondWith(
      caches.match(event.request).then((response) => response || fetch(event.request))
    );
  });
  
  self.addEventListener('activate', (event) => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
      caches.keys().then((cacheNames) =>
        Promise.all(
          cacheNames.map((cacheName) => {
            if (!cacheWhitelist.includes(cacheName)) {
              return caches.delete(cacheName);
            }
          })
        )
      )
    );
  });