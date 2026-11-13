/* 반도체 새김 서비스 워커 — 오프라인에서도 열리게 한다.
   - 이 사이트의 파일(화면·데이터): 네트워크 우선(항상 최신), 느리거나 끊기면 저장해 둔 것을 보여 준다.
   - 글꼴·수식·마크다운 같은 외부 라이브러리: 저장해 둔 것 우선. 사이트가 바뀌면 VERSION 을 올리면 옛 저장분이 지워진다. */
const VERSION = 'semicbt-v1';
const SHELL = ['./', 'index.html', 'tw.css', 'manifest.webmanifest', 'data/questions.json', 'data/interviews.json', 'data/theories.json', 'data/theory_pages.json', 'data/careers.json'];
const EXTERNAL = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com', 'cdn.tailwindcss.com'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(new Request(u, { cache: 'reload' })).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

const put = (req, res) => { if (res && (res.ok || res.type === 'opaque')) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {}); } return res; };

function networkFirst(req) {
  return new Promise((resolve) => {
    let done = false;
    const fallback = () => caches.match(req, { ignoreSearch: true }).then((hit) => hit || (req.mode === 'navigate' ? caches.match('index.html') : null));
    const t = setTimeout(() => fallback().then((hit) => { if (hit && !done) { done = true; resolve(hit); } }), 4000);
    fetch(req).then((res) => { clearTimeout(t); if (!done) { done = true; resolve(put(req, res)); } else put(req, res); })
      .catch(() => { clearTimeout(t); if (!done) { done = true; fallback().then((hit) => resolve(hit || Response.error())); } });
  });
}
function cacheFirst(req) {
  return caches.match(req).then((hit) => hit || fetch(req).then((res) => put(req, res)));
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) { e.respondWith(networkFirst(req)); return; }
  if (EXTERNAL.includes(url.hostname)) e.respondWith(cacheFirst(req));
});
