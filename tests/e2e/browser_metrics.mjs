// Browser measurements for METRICS.md, against a RUNNING hub (./run.sh). EMULATED in desktop Chromium, not a phone.
//   node tests/e2e/browser_metrics.mjs [inference|network|all|report]  (default all; network takes ~10 min;
//   report = only rewrite the .md from the .json)
// Env: HUB=http://localhost:8000, CHROMIUM=<path> (fallback /opt/pw-browsers/chromium-1194/chrome-linux/chrome),
//      LABEL=<name of this server setup, e.g. "gzip on">: network results are stored per LABEL, so runs against
//      differently configured hubs end up side by side in the report
// 1) Inference in the app page (Pixel 5 profile): app's own diagnose() (blur check + resize + model) and the bare
//    onnxruntime session.run(), median of 10, at CDP Emulation.setCPUThrottlingRate 1, 4 and 6; plus the cold
//    first photo (runtime + WASM compile + model load + first run).
// 2) Download time under CDP Network.emulateNetworkConditions for (i) the model file alone and (ii) every file the
//    service worker precaches (list read from app/sw.js + cards.json + labels.json), fetched by the PAGE in the
//    same groups as sw.js. Why not the real SW install: Chromium's CDP throttling does not apply to service-worker
//    fetches (checked: an install with 8 Mbps set on the page and on the SW target still finished in ~1.2 s).
// Writes reports/browser_metrics.json and reports/browser_metrics.md.
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
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
const HUB = (process.env.HUB || 'http://localhost:8000').replace(/\/$/, '');
const WHAT = process.argv[2] || 'all';
const OUT_JSON = path.join(ROOT, 'reports/browser_metrics.json');
const RATES = [1, 4, 6];
const N = 10;
// kbps / ms. "3G" and "slow 3G" as defined for this project (not the DevTools presets).
const PROFILES = [
  { name: '3G', down_kbps: 750, up_kbps: 250, latency_ms: 100 },
  { name: 'slow 3G', down_kbps: 400, up_kbps: 400, latency_ms: 400 },
];

function launchOpts() {
  const opts = {};
  const fallback = process.env.CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  let own = null;
  try {
    own = pw.chromium.executablePath();
  } catch { /* no bundled browser */ }
  if ((!own || !fs.existsSync(own)) && fs.existsSync(fallback)) opts.executablePath = fallback;
  return opts;
}
const median = (a) => {
  const s = [...a].sort((x, y) => x - y);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};
const r1 = (x) => Math.round(x * 10) / 10;

// ---------- 1) inference ----------
async function inference(browser) {
  const crop = 'data:image/jpeg;base64,' + fs.readFileSync(path.join(ROOT, 'tests/e2e/fixtures/journey_roya.jpg')).toString('base64');
  const rows = [];
  for (const rate of RATES) {
    const ctx = await browser.newContext({ ...pw.devices['Pixel 5'] });
    const page = await ctx.newPage();
    await page.goto(HUB + '/app/');
    await page.waitForSelector('body[data-offline="ready"]', { timeout: 120000 });
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    const r = await page.evaluate(async ({ crop, n }) => {
      const M = await import('./infer.js'); // the same module instance the app uses
      const img = await new Promise((res, rej) => {
        const i = new Image();
        i.onload = () => res(i);
        i.onerror = rej;
        i.src = crop;
      });
      // a decoded 12 MP photo (4000x3000) with the leaf in the middle: the app crops + resizes it itself
      const big = document.createElement('canvas');
      big.width = 4000;
      big.height = 3000;
      big.getContext('2d').drawImage(img, 500, 0, 3000, 3000);
      let t = performance.now();
      const first = await M.diagnose(img);
      const cold = performance.now() - t;
      const time = async (fn) => {
        const out = [];
        for (let i = 0; i < n; i++) {
          t = performance.now();
          await fn();
          out.push(performance.now() - t);
        }
        return out;
      };
      const small = await time(() => M.diagnose(img));
      const photo12 = await time(() => M.diagnose(big));
      const s = await M.getSession();
      const L = await M.getLabels();
      const x = new Float32Array(L.input.size * L.input.size * 3).map(() => Math.random() * 255);
      const feeds = { [s.inputNames[0]]: new ort.Tensor('float32', x, [1, L.input.size, L.input.size, 3]) };
      const run = await time(() => s.run(feeds));
      return { first: { label: first.label, conf: first.conf }, cold, small, photo12, run, ua: navigator.userAgent };
    }, { crop, n: N });
    rows.push({
      cpu_throttle: rate, cold_first_photo_ms: r1(r.cold), first_result: r.first,
      diagnose_128px_median_ms: r1(median(r.small)), diagnose_12mp_median_ms: r1(median(r.photo12)),
      session_run_median_ms: r1(median(r.run)),
      raw_ms: { diagnose_128px: r.small.map(r1), diagnose_12mp: r.photo12.map(r1), session_run: r.run.map(r1) },
    });
    console.log(`CPU x${rate}: cold ${r1(r.cold)} ms, diagnose(128px) ${r1(median(r.small))} ms, ` +
      `diagnose(12MP) ${r1(median(r.photo12))} ms, session.run ${r1(median(r.run))} ms (median of ${N})`);
    await ctx.close();
  }
  return rows;
}

// ---------- 2) downloads ----------
function precacheGroups() {
  const sw = fs.readFileSync(path.join(ROOT, 'app/sw.js'), 'utf8');
  const shell = JSON.parse(sw.match(/const SHELL = (\[[\s\S]*?\]);/)[1].replace(/'/g, '"').replace(/,\s*\]/, ']'));
  const labels = JSON.parse(fs.readFileSync(path.join(ROOT, 'app/model/labels.json'), 'utf8'));
  const cards = JSON.parse(fs.readFileSync(path.join(ROOT, 'content/cards.json'), 'utf8'));
  const audio = new Set();
  for (const c of cards.cards) for (const p of Object.values(c.audio || {})) if (p) audio.add('/content/' + p);
  return [ // same order and grouping as precache() in app/sw.js
    shell.map((u) => new URL(u, HUB + '/app/').pathname),
    ['/content/cards.json', '/app/model/labels.json', '/app/config.json'],
    ['/app/model/' + labels.file],
    [...audio],
  ];
}

async function download(browser, prof) {
  const ctx = await browser.newContext({ serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await page.goto(HUB + '/api/health');
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  const wire = { bytes: 0, gzip: 0 };
  const enc = new Map();
  cdp.on('Network.responseReceived', (e) => enc.set(e.requestId, (e.response.headers['content-encoding'] || e.response.headers['Content-Encoding'] || '')));
  cdp.on('Network.loadingFinished', (e) => {
    wire.bytes += e.encodedDataLength;
    if (enc.get(e.requestId) === 'gzip') wire.gzip++;
  });
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false, latency: prof.latency_ms, downloadThroughput: (prof.down_kbps * 1000) / 8, uploadThroughput: (prof.up_kbps * 1000) / 8,
  });
  const fetchGroups = (groups) => page.evaluate(async (groups) => {
    const t0 = performance.now();
    let bytes = 0;
    let files = 0;
    for (const g of groups) {
      const sizes = await Promise.all(g.map((u) => fetch(u, { cache: 'no-store' }).then((r) => {
        if (!r.ok) throw new Error(u + ' ' + r.status);
        return r.arrayBuffer();
      }).then((b) => b.byteLength)));
      bytes += sizes.reduce((a, b) => a + b, 0);
      files += g.length;
    }
    return { ms: performance.now() - t0, body_bytes: bytes, files };
  }, groups);
  const groups = precacheGroups();
  wire.bytes = 0;
  const model = await fetchGroups([groups[2]]);
  const modelWire = wire.bytes;
  wire.bytes = 0;
  wire.gzip = 0;
  const bundle = await fetchGroups(groups);
  const res = {
    profile: prof,
    model: { seconds: r1(model.ms / 1000), body_bytes: model.body_bytes, wire_bytes: modelWire },
    bundle: { seconds: r1(bundle.ms / 1000), files: bundle.files, body_bytes: bundle.body_bytes, wire_bytes: wire.bytes, gzip_responses: wire.gzip },
  };
  console.log(`${prof.name}: model ${res.model.seconds} s (${(modelWire / 1e6).toFixed(2)} MB on the wire); ` +
    `offline bundle ${res.bundle.seconds} s (${bundle.files} files, ${(wire.bytes / 1e6).toFixed(2)} MB on the wire, ` +
    `${(bundle.body_bytes / 1e6).toFixed(2)} MB decoded, ${wire.gzip} gzip responses)`);
  await ctx.close();
  return res;
}

// ---------- report ----------
function writeMd(m) {
  const L = [];
  L.push('# Browser metrics (EMULATED: desktop Chromium, not a phone)', '');
  L.push(`Last run ${m.measured_at} by \`node tests/e2e/browser_metrics.mjs\` against the hub at ${m.hub}.`);
  L.push(`Chromium ${m.env.chromium} headless, Pixel 5 profile, host: ${m.env.cpu} x${m.env.cpus} CPUs, no GPU.`, '');
  L.push('**Nothing here was measured on a real phone or a real mobile network.** CPU throttling (CDP',
    '`Emulation.setCPUThrottlingRate`) slows this Xeon\'s page thread by the given factor as a rough stand-in for a',
    'low-end Android phone; it does not model a phone\'s memory, thermal limits or WASM performance exactly.', '');
  if (m.inference) {
    L.push('## Model inference in the app page (onnxruntime-web 1.19.2, WASM, 1 thread)', '');
    L.push('| CPU throttle | first photo, cold (runtime + model load + run) | diagnose() 128 px crop, median of 10 | diagnose() 12 MP photo, median of 10 | session.run() only, median of 10 |');
    L.push('|---|---|---|---|---|');
    for (const r of m.inference) {
      L.push(`| x${r.cpu_throttle}${r.cpu_throttle === 1 ? ' (none)' : ''} | ${r.cold_first_photo_ms} ms | ${r.diagnose_128px_median_ms} ms | ${r.diagnose_12mp_median_ms} ms | ${r.session_run_median_ms} ms |`);
    }
    L.push('', '`diagnose()` is the app\'s own function (app/infer.js): blur check + centre crop + resize + model. The 12 MP',
      'case starts from an already-decoded 4000x3000 canvas, so JPEG decoding of a real camera photo is NOT included.', '');
  }
  if (m.network && Object.keys(m.network).length) {
    L.push('## First-load download time (CDP Network.emulateNetworkConditions)', '');
    L.push('| Hub setup | Network (down / up / latency) | Model file alone | Whole offline bundle (everything the SW precaches) |');
    L.push('|---|---|---|---|');
    for (const [label, runs] of Object.entries(m.network)) {
      for (const r of runs) {
        const p = r.profile;
        const gz = r.bundle.gzip_responses ? `, ${r.bundle.gzip_responses} gzip responses` : ', no compression';
        L.push(`| ${label} | ${p.name} (${p.down_kbps} / ${p.up_kbps} kbps / ${p.latency_ms} ms) | ${r.model.seconds} s (${(r.model.wire_bytes / 1e6).toFixed(2)} MB) | ` +
          `${r.bundle.seconds} s = ${(r.bundle.seconds / 60).toFixed(1)} min (${r.bundle.files} files, ${(r.bundle.wire_bytes / 1e6).toFixed(2)} MB on the wire, ${(r.bundle.body_bytes / 1e6).toFixed(2)} MB decoded${gz}) |`);
      }
    }
    L.push('', 'The bundle is fetched by the page in the same four groups as `precache()` in app/sw.js (app shell incl. the',
      'onnxruntime WASM, then cards/labels/config, then the model, then all audio). The real service worker install',
      'could not be throttled: Chromium applies CDP throttling to page requests, not to service-worker fetches. The',
      'page\'s own first requests (13 files: index.html, JS, CSS, icons, cards.json) come on top: 134 KB uncompressed,',
      '33 KB with gzip (measured once with CDP, unthrottled). Once cached, nothing is downloaded again until a file',
      'changes.', '');
  }
  fs.writeFileSync(path.join(ROOT, 'reports/browser_metrics.md'), L.join('\n'));
}

const health = await fetch(HUB + '/api/health').then((r) => r.json(), () => null);
if (!health || !health.ok) {
  console.error(`No hub at ${HUB}. Start it first: ./run.sh`);
  process.exit(2);
}
const prev = fs.existsSync(OUT_JSON) ? JSON.parse(fs.readFileSync(OUT_JSON, 'utf8')) : {};
const browser = await pw.chromium.launch(launchOpts());
const LABEL = process.env.LABEL || 'default';
const m = {
  ...prev, label: undefined, emulated: true, hub: HUB,
  measured_at: WHAT === 'report' && prev.measured_at ? prev.measured_at : new Date().toISOString(),
  env: { chromium: browser.version(), cpus: os.cpus().length, cpu: os.cpus()[0].model, headless: true, device: 'Pixel 5 (Playwright)' },
};
try {
  if (WHAT === 'all' || WHAT === 'inference') m.inference = await inference(browser);
  if (WHAT === 'all' || WHAT === 'network') {
    m.network = Array.isArray(prev.network) || !prev.network ? {} : prev.network;
    m.network[LABEL] = [];
    for (const p of PROFILES) m.network[LABEL].push(await download(browser, p));
  }
} finally {
  await browser.close();
}
fs.writeFileSync(OUT_JSON, JSON.stringify(m, null, 2) + '\n');
writeMd(m);
console.log('wrote reports/browser_metrics.json and reports/browser_metrics.md');
