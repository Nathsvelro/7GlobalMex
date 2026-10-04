// Service worker update check (Playwright + Chromium): a newer labels.json / cards.json is only switched in the
// cache once every file it references (model / changed audio) was downloaded; if one fails, the old JSON stays.
//   node tests/e2e/sw_update.mjs            (from the repo root; needs playwright)
// Uses its own small static server so responses can be changed between steps (page.route does not see
// service-worker fetches). One audio file is missing from the start (tolerated at install, like a real 404).
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
let pw;
try {
  pw = require('playwright');
} catch {
  pw = require(path.join(execSync('npm root -g').toString().trim(), 'playwright'));
}
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.wasm': 'application/wasm', '.mp3': 'audio/mpeg',
};
const LABELS_P = '/app/model/labels.json';
const CARDS_P = '/content/cards.json';
const labels0 = fs.readFileSync(path.join(ROOT, 'app/model/labels.json'), 'utf8');
const cards0 = fs.readFileSync(path.join(ROOT, 'content/cards.json'), 'utf8');
const L = JSON.parse(labels0);
const C = JSON.parse(cards0);
const MODEL_P = '/app/model/' + L.file;
// Gikuyu: its audio is the provisional synthetic voice, so it is the first a native speaker would re-record.
const LANG = 'kik';
const audioCards = C.cards.filter((c) => c.audio && c.audio[LANG]);
const MISSING_P = '/content/' + audioCards[0].audio[LANG]; // never served: missing since install
const CHANGED = audioCards[1]; // gets a "new native recording" in the update
const CHANGED_P = '/content/' + CHANGED.audio[LANG];

const overrides = new Map(); // path -> {status, body, type}
const hits = new Map();
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  hits.set(p, (hits.get(p) || 0) + 1);
  const o = overrides.get(p);
  if (o) {
    res.writeHead(o.status, { 'Content-Type': o.type || 'application/json', 'Cache-Control': 'no-store' });
    res.end(o.body);
    return;
  }
  const f = path.join(ROOT, path.normalize(p), p.endsWith('/') ? 'index.html' : '');
  fs.readFile(f, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(data);
  });
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const ORIGIN = `http://127.0.0.1:${server.address().port}`;
const BASE = ORIGIN + '/app/';

let failures = 0;
function check(cond, msg) {
  console.log((cond ? 'PASS ' : 'FAIL ') + msg);
  if (!cond) failures++;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fail500 = { status: 500, body: 'boom', type: 'text/plain' };

async function launchOpts() {
  const opts = {};
  const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  try {
    pw.chromium.executablePath();
  } catch {
    if (fs.existsSync(exe)) opts.executablePath = exe;
  }
  return opts;
}

const browser = await pw.chromium.launch(await launchOpts());
try {
  const page = await (await browser.newContext()).newPage();
  const cached = (p) => page.evaluate(async (u) => {
    const r = await caches.match(u);
    return r ? r.text() : null;
  }, ORIGIN + p);
  // ask the service worker for the JSON (it answers from cache and revalidates in the background)
  const revalidate = (p) => page.evaluate((u) => fetch(u).then((r) => r.status), ORIGIN + p);
  // the background update must not switch the JSON: wait until the failing file was requested, then watch a while
  async function staysOld(p, old, failingP) {
    const n = hits.get(failingP) || 0;
    await revalidate(p);
    for (let i = 0; i < 100 && (hits.get(failingP) || 0) === n; i++) await sleep(100);
    check((hits.get(failingP) || 0) > n, `  (the service worker tried to download ${failingP})`);
    for (let i = 0; i < 20; i++) {
      if ((await cached(p)) !== old) return false;
      await sleep(100);
    }
    return true;
  }
  async function switchesTo(p, text) {
    await revalidate(p);
    for (let i = 0; i < 100; i++) {
      if ((await cached(p)) === text) return true;
      await sleep(100);
    }
    return false;
  }

  // 1. first load: everything cached except the one audio file the server never had
  overrides.set(MISSING_P, { status: 404, body: '' });
  await page.goto(BASE);
  await page.waitForSelector('body[data-offline]', { timeout: 120000 });
  if (!(await page.evaluate(() => !!navigator.serviceWorker.controller))) await page.reload();
  check(await page.evaluate(() => !!navigator.serviceWorker.controller), 'page is controlled by the service worker');
  check((await cached(LABELS_P)) === labels0 && (await cached(CARDS_P)) === cards0, 'labels.json and cards.json cached');
  const model0 = await cached(MODEL_P);
  check(!!model0 && (await cached(MISSING_P)) === null, 'model cached; the never-served audio file is not');

  // 2. new labels.json pointing at a new model file whose download fails -> old labels.json stays
  const NEW_P = '/app/model/cafetal-v3.onnx';
  const labels3 = JSON.stringify({ ...L, version: 'cafetal-img-v3', file: 'cafetal-v3.onnx', threshold: 0.5 });
  overrides.set(LABELS_P, { status: 200, body: labels3 });
  overrides.set(NEW_P, fail500);
  check(await staysOld(LABELS_P, labels0, NEW_P), 'labels.json with a new model file that fails to download: old labels.json kept');
  check((await cached(NEW_P)) === null && (await cached(MODEL_P)) === model0, 'old model still cached, failed one not');

  // 3. new labels.json for a retrained model at the same URL whose download fails -> old labels.json stays
  const labelsSame = JSON.stringify({ ...L, version: 'cafetal-img-v3', size_bytes: L.size_bytes + 1, threshold: 0.5 });
  overrides.set(LABELS_P, { status: 200, body: labelsSame });
  overrides.set(MODEL_P, fail500);
  check(await staysOld(LABELS_P, labels0, MODEL_P), 'labels.json for a same-URL model that fails to download: old labels.json kept');
  check((await cached(MODEL_P)) === model0, 'old model still cached');
  overrides.delete(MODEL_P);

  // 4. once the new model downloads, the new labels.json is switched in (control: the update path still works)
  overrides.set(LABELS_P, { status: 200, body: labels3 });
  overrides.set(NEW_P, { status: 200, body: fs.readFileSync(path.join(ROOT, 'app' + MODEL_P.slice(4))), type: 'application/octet-stream' });
  check(await switchesTo(LABELS_P, labels3), 'model download works -> new labels.json switched in');
  check(!!(await cached(NEW_P)), 'new model cached');

  // 5. new cards.json with a changed audio file whose download fails -> old cards.json stays
  const upd = JSON.parse(cards0);
  const card = upd.cards.find((c) => c.id === CHANGED.id);
  card.audio_source = { ...card.audio_source, [LANG]: 'native:test-recording' };
  const cards5 = JSON.stringify(upd);
  overrides.set(CARDS_P, { status: 200, body: cards5 });
  overrides.set(CHANGED_P, fail500);
  check(await staysOld(CARDS_P, cards0, CHANGED_P), 'cards.json with a changed audio file that fails to download: old cards.json kept');

  // 6. the changed audio downloads; the audio file missing since install still 404s -> must not block the update
  overrides.delete(CHANGED_P);
  check(await switchesTo(CARDS_P, cards5), 'changed audio downloads -> new cards.json switched in (old missing file does not block)');
} catch (e) {
  console.error(e);
  failures++;
} finally {
  await browser.close();
  server.close();
}
console.log(failures ? `\n${failures} check(s) FAILED` : '\nALL CHECKS PASSED');
process.exit(failures ? 1 : 0);
