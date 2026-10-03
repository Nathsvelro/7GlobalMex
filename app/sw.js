// Service worker: makes the app work in airplane mode after the first load.
//  - cache-first: app shell, onnxruntime-web, model, cards.json, every audio file listed in cards.json
//  - cards.json / labels.json / config.json: served from cache, refreshed in the background when online;
//    a refresh also downloads audio whose file or source changed (e.g. a new native recording) and a new model
//  - /api/*: network only (never cached, so "hub reachable" is never faked)
// VERSION = hash of every precached file, written by scripts/bump_sw_version.py (run.sh runs it before starting the
// hub; run it by hand before copying app/ to a static host). A new VERSION makes phones re-download everything.
const VERSION = 'cafetal-63025f1518';
const SHELL = [
  './', 'index.html', 'style.css', 'app.js', 'content.js', 'store.js', 'infer.js', 'sms.js',
  'manifest.webmanifest',
  'icons/icons.svg', 'icons/logo.svg', 'icons/tip.svg', 'icons/leaf_home.svg', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/res_sano.svg', 'icons/res_roya.svg', 'icons/res_minador.svg', 'icons/res_phoma.svg',
  'icons/res_cercospora.svg', 'icons/res_acaro_rojo.svg', 'icons/res_duda.svg',
  'vendor/ort.wasm.min.js', 'vendor/ort-wasm-simd-threaded.mjs', 'vendor/ort-wasm-simd-threaded.wasm',
];
const abs = (u) => new URL(u, self.location.href).href;
const CARDS = abs('../content/cards.json');
const LABELS = abs('model/labels.json');
const CONFIG = abs('config.json');
const INDEX = abs('index.html');
const fresh = (u) => new Request(u, { cache: 'reload' });

const modelUrl = (labels) => abs('model/' + ((labels && labels.file) || 'cafetal.onnx'));
function audioMap(cards) {
  const m = new Map(); // url -> audio_source (changes when a native recording replaces the file)
  for (const c of (cards && cards.cards) || []) {
    for (const [lang, p] of Object.entries(c.audio || {})) {
      if (p) m.set(abs('../content/' + p), (c.audio_source && c.audio_source[lang]) || '');
    }
  }
  return m;
}
async function cachedJson(cache, url) {
  const r = await cache.match(url);
  try {
    return r ? await r.json() : null;
  } catch {
    return null;
  }
}

async function precache() {
  const cache = await caches.open(VERSION);
  await cache.addAll(SHELL.map((u) => fresh(abs(u)))); // required: install fails if any is missing
  const [cardsRes, labelsRes, configRes] = await Promise.all([CARDS, LABELS, CONFIG].map((u) => fetch(fresh(u))));
  if (!cardsRes.ok || !labelsRes.ok) throw new Error('cards.json or labels.json missing');
  const cards = await cardsRes.clone().json();
  const labels = await labelsRes.clone().json();
  await cache.put(CARDS, cardsRes);
  await cache.put(LABELS, labelsRes);
  if (configRes.ok) await cache.put(CONFIG, configRes);
  await cache.add(fresh(modelUrl(labels)));
  // Audio: one missing file must not break offline diagnosis; the status check reports it instead.
  await Promise.all([...audioMap(cards).keys()].map((u) => cache.add(fresh(u)).catch(() => console.warn('no audio', u))));
}

self.addEventListener('install', (e) => {
  e.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('cafetal-') && k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

// After a newer cards.json / labels.json arrives: fetch only the files that changed.
async function topUp(url, oldJson, newJson) {
  const cache = await caches.open(VERSION);
  if (url === CARDS) {
    const before = audioMap(oldJson);
    for (const [u, src] of audioMap(newJson)) {
      if (before.get(u) !== src || !(await cache.match(u))) await cache.add(fresh(u)).catch(() => {});
    }
  } else if (url === LABELS) {
    const changed = !oldJson || oldJson.version !== newJson.version || oldJson.size_bytes !== newJson.size_bytes ||
      oldJson.file !== newJson.file;
    if (changed || !(await cache.match(modelUrl(newJson)))) await cache.add(fresh(modelUrl(newJson))).catch(() => {});
  }
}

async function staleWhileRevalidate(e, url) {
  const cache = await caches.open(VERSION);
  const cached = await cache.match(url);
  const update = (async () => {
    try {
      const res = await fetch(fresh(url));
      if (!res.ok) return null;
      const text = await res.clone().text();
      const old = cached ? await cached.clone().text() : null;
      if (text !== old) {
        // download changed audio / model first, then switch the JSON, so they never point at missing files
        if (url !== CONFIG) await topUp(url, old && JSON.parse(old), JSON.parse(text));
        await cache.put(url, res.clone());
      }
      return res;
    } catch {
      return null;
    }
  })();
  if (cached) {
    e.waitUntil(update);
    return cached;
  }
  return (await update) || new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
}

const offlineApi = () => new Response(JSON.stringify({ ok: false, offline: true }), {
  status: 503, headers: { 'Content-Type': 'application/json' },
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/api/')) {
    e.respondWith(fetch(req).catch(offlineApi));
    return;
  }
  if (req.method !== 'GET') return;
  const plain = url.origin + url.pathname;
  if (plain === CARDS || plain === LABELS || plain === CONFIG) {
    e.respondWith(staleWhileRevalidate(e, plain));
    return;
  }
  if (req.mode === 'navigate') {
    e.respondWith(caches.match(req, { ignoreSearch: true })
      .then((r) => r || caches.match(INDEX))
      .then((r) => r || fetch(req)));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then((r) => r || fetch(req)));
});

// The page asks "is everything needed offline in the cache?" -> {ready, missing}
self.addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'status' || !e.ports[0]) return;
  e.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    const cards = await cachedJson(cache, CARDS);
    const labels = await cachedJson(cache, LABELS);
    const need = [...SHELL.map(abs), CARDS, LABELS];
    if (labels) need.push(modelUrl(labels));
    if (cards) need.push(...audioMap(cards).keys());
    const missing = [];
    for (const u of need) if (!(await cache.match(u))) missing.push(u);
    e.ports[0].postMessage({ ready: !!cards && !!labels && missing.length === 0, missing, total: need.length, version: VERSION });
  })());
});
