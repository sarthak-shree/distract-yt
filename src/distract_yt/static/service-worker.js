/* No-op service worker.
   Some browser extensions probe for /service-worker.js; this benign file
   keeps the console clean without registering any caching behavior. */
self.addEventListener("install", function (event) {
  self.skipWaiting();
});
self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", function (event) {
  /* pass through — we don't cache anything offline */
});