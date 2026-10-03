// End-to-end check of the phone app (Playwright + Chromium, phone viewport).
//   node tests/e2e/app_offline.mjs            (from the repo root; needs python3 and playwright)
// Phase A (offline): first load -> service worker caches everything -> server stopped + browser offline ->
//   reload -> onboarding -> photo -> on-device result + audio from cache -> SMS code -> blurred photo = DUDA ->
//   history -> settings/PIN/lock -> delete everything.
// Phase B (hub buttons): service worker blocked, /api/* mocked -> "Simular envío" and "Sincronizar fotos".
// Phase C (real hub, skipped if .venv/bin/uvicorn is missing): a throw-away hub (temporary DB) serves the app;
//   register a member, diagnose, simulated send -> observation on the hub, sync -> photo on the hub.
// Screenshots go to reports/screenshots/app_*.png. Asserts the flow, not model accuracy.
import { spawn, execSync } from 'node:child_process';
import os from 'node:os';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import net from 'node:net';
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
const FIX = path.join(ROOT, 'tests/e2e/fixtures');
const SHOTS = path.join(ROOT, 'reports/screenshots');
// A free port of our own, so that killing the server really means "no network" (another dev server, e.g. the
// hub, may already be running on a common port). Note: Playwright's setOffline() does NOT stop service-worker
// fetches in Chromium, so stopping the server is what makes this test truly offline.
const freePort = () => new Promise((resolve) => {
  const s = net.createServer().listen(0, '127.0.0.1', () => {
    const p = s.address().port;
    s.close(() => resolve(p));
  });
});
const PORT = Number(process.env.PORT) || await freePort();
const BASE = `http://127.0.0.1:${PORT}/app/`;
const CODE_RE = /^CAF1 M\d{4} (SANO|ROYA|MINA|PHOM|CERC|ACAR|OTRO|DUDA) \d{1,2} \d{8} (-?\d{1,2}\.\d{2},-?\d{1,3}\.\d{2}|-) #[0-9A-Z]{4}$/;
const cards = JSON.parse(fs.readFileSync(path.join(ROOT, 'content/cards.json'), 'utf8'));
const T = (id, lang = 'es') => cards.cards.find((c) => c.id === id)[lang];
fs.mkdirSync(SHOTS, { recursive: true });

let failures = 0;
function check(cond, msg) {
  console.log((cond ? 'PASS ' : 'FAIL ') + msg);
  if (!cond) failures++;
}

async function startServer() {
  const p = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 100));
    if (await fetch(BASE + 'config.json').then((r) => r.ok, () => false)) return p;
  }
  throw new Error('static server did not start on port ' + PORT);
}
async function serverDown() {
  return fetch(BASE + 'config.json').then(() => false, () => true);
}

async function launchOpts() {
  const opts = { args: ['--autoplay-policy=no-user-gesture-required'] };
  const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  try {
    pw.chromium.executablePath();
  } catch {
    if (fs.existsSync(exe)) opts.executablePath = exe;
  }
  return opts;
}

const phone = {
  viewport: { width: 360, height: 740 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
  locale: 'es-MX', permissions: ['geolocation'], geolocation: { latitude: 16.9123, longitude: -92.1087 },
};

async function shot(page, name, full = false) {
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(SHOTS, name), fullPage: full });
}

async function noMissingCards(page, where) {
  const txt = await page.evaluate(() => document.body.innerText);
  const m = txt.match(/\[(ui|diag|advice|name|limits|sms|alert)_[a-z_]+\]/);
  check(!m, `no missing card ids on screen (${where})${m ? ': ' + m[0] : ''}`);
}

async function phaseOffline(browser) {
  let server = await startServer();
  const ctx = await browser.newContext(phone);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  // "Failed to load resource" = the expected 503 from /api/health while the hub is unreachable
  page.on('console', (m) => m.type() === 'error' && !m.text().startsWith('Failed to load resource') && errors.push(m.text()));

  // 1. first load (online): the service worker downloads app + model + cards + audio
  const t0 = Date.now();
  await page.goto(BASE);
  await page.waitForSelector('body[data-offline="ready"]', { timeout: 120000 });
  console.log(`  offline cache ready after ${Date.now() - t0} ms`);
  await page.waitForSelector('#pill-offline:not([hidden])');
  check(true, 'service worker cached everything (ui_offline_ready shown)');

  // 2. airplane mode: stop the server AND set the browser offline, then reload
  server.kill();
  await ctx.setOffline(true);
  for (let i = 0; i < 20 && !(await serverDown()); i++) await new Promise((r) => setTimeout(r, 100));
  check(await serverDown(), 'server stopped: from here on nothing can come from the network');
  await page.reload();
  await page.waitForSelector('#s-lang:not([hidden])');
  check(await page.isVisible('#pill-demo'), 'DEMO badge visible (config gateway_label = DEMO)');
  await page.click('.lang-btn[data-lang="tzh"]');
  check((await page.textContent('#lang-next')).includes(T('ui_continue', 'tzh')), 'Tseltal selected -> labels switch to Tseltal');
  await page.click('.lang-btn[data-lang="es"]');
  await shot(page, 'app_01_language.png');
  await page.click('#lang-next');

  // consent: decline returns to start and stores nothing
  await page.waitForSelector('#s-consent:not([hidden])');
  check((await page.textContent('#s-consent')).includes(T('ui_consent_text').slice(0, 40)), 'consent text shown');
  check(await page.isVisible('#s-consent .speak'), 'consent has a play button');
  await shot(page, 'app_02_consent.png');
  await page.click('#consent-no');
  await page.waitForSelector('#s-lang:not([hidden])');
  check(await page.evaluate(() => localStorage.length === 0), 'decline -> back to start, nothing stored');
  await page.click('.lang-btn[data-lang="es"]');
  await page.click('#lang-next');
  await page.click('#consent-yes');

  // member ID validation
  await page.waitForSelector('#s-member:not([hidden])');
  await page.fill('#member-digits', '12');
  await page.click('#member-next');
  check(await page.isVisible('#member-err'), 'invalid member ID rejected (ui_member_id_invalid)');
  await page.fill('#member-digits', '0123');
  await shot(page, 'app_03_member.png');
  await page.click('#member-next');
  await page.waitForSelector('#s-home:not([hidden])');
  const settings = await page.evaluate(() => JSON.parse(localStorage.getItem('cafetal.settings')));
  check(settings && settings.member_id === 'M0123' && settings.pin_hash === null, 'settings saved: member M0123, no PIN');
  await page.waitForTimeout(500); // geolocation permission answer
  await shot(page, 'app_04_home.png');
  await noMissingCards(page, 'home');

  // 3-6. photo -> on-device diagnosis (offline)
  const t1 = Date.now();
  await page.setInputFiles('#file-gallery', path.join(FIX, 'leaf_photo.jpg'));
  await page.waitForSelector('#r-body:not([hidden])', { timeout: 120000 });
  console.log(`  first diagnosis (runtime + model load + inference) ${Date.now() - t1} ms`);
  const r1 = await page.evaluate(() => {
    const o = window.__cafetal.obs;
    return { code: o.sms_code, label: o.label, conf: o.conf, probs: o.probs, ms: o.ms, model: o.model_version, reason: o.reason };
  });
  console.log('  result 1:', JSON.stringify(r1));
  check(CODE_RE.test(r1.code) && r1.code.length <= 160, `SMS code matches PLAN §5: ${r1.code}`);
  check(r1.code.includes(' 16.91,-92.11 '), 'location rounded to 2 decimals in the code');
  check(r1.probs !== null && r1.model !== 'none', 'model ran offline (probabilities present)');
  check((await page.textContent('#r-code')) === r1.code, 'SMS code shown on screen');
  const name = (await page.textContent('#r-name')).trim();
  check(name.length > 0 && !name.startsWith('['), `result name shown: ${name}`);
  check(await page.isVisible('#r-diag .badge.unverified'), 'UNVERIFIED badge next to diagnosis text');
  check(await page.isVisible('#r-badge-tzh'), 'UNVERIFIED badge on Tseltal audio button');
  const audio = await page.evaluate(async () => {
    const out = {};
    for (const l of ['tzh', 'es']) {
      const a = document.getElementById('audio-' + l);
      const r = await fetch(a.src);
      const b = await r.arrayBuffer();
      out[l] = { src: a.getAttribute('src'), ok: r.ok, bytes: b.byteLength };
    }
    return out;
  });
  console.log('  audio:', JSON.stringify(audio));
  check(audio.tzh.src && audio.es.src && audio.tzh.ok && audio.es.ok && audio.es.bytes > 1000,
    'both audio elements have src and their files load offline (from the cache)');
  await page.click('#r-play-es');
  await page.waitForTimeout(1500);
  const playing = await page.evaluate(() => {
    const a = document.getElementById('audio-es');
    return { t: a.currentTime, paused: a.paused, err: a.error && a.error.code };
  });
  check(playing.t > 0 && !playing.err, `Spanish audio plays offline (currentTime ${playing.t.toFixed(2)} s)`);
  await page.click('#r-play-tzh');
  await page.waitForTimeout(1200);
  const playingTzh = await page.evaluate(() => document.getElementById('audio-tzh').currentTime);
  check(playingTzh > 0, `Tseltal audio plays offline (currentTime ${playingTzh.toFixed(2)} s)`);
  await page.evaluate(() => document.querySelectorAll('audio').forEach((a) => a.pause()));
  await shot(page, 'app_05_result.png', true);
  await noMissingCards(page, 'result');

  // send by SMS: sms: link + manual confirmation (never sent automatically)
  const href = await page.getAttribute('#r-send', 'href');
  check(href === 'sms:+520000000000?body=' + encodeURIComponent(r1.code), 'sms: link has gateway number and encoded code');
  check((await page.textContent('#r-sms-status')) === T('ui_pending_sms'), 'status is pending before the user confirms');
  await page.evaluate(() => document.addEventListener('click', (e) => {
    if (e.target.closest('a[href^="sms:"]')) e.preventDefault(); // the test cannot open an SMS app
  }, true));
  await page.click('#r-send');
  check(await page.isVisible('#r-confirm'), 'after tapping send, the app asks the user to confirm');
  await page.click('#r-sent-yes');
  await page.waitForFunction((t) => document.getElementById('r-sms-status').textContent === t, T('ui_sent'));
  check(true, 'marked sent only after the user confirmed');
  check(!(await page.isVisible('#r-hub')), 'hub buttons hidden while the hub is unreachable');

  // blurred photo -> fail-safe DUDA
  await page.click('#nav [data-go="home"]');
  await page.setInputFiles('#file-camera', path.join(FIX, 'leaf_blurred.jpg'));
  await page.waitForSelector('#r-body:not([hidden])', { timeout: 60000 });
  const r2 = await page.evaluate(() => window.__cafetal.obs);
  console.log('  result 2:', JSON.stringify({ code: r2.sms_code, reason: r2.reason, blur: r2.blur }));
  check(/ DUDA 0 /.test(r2.sms_code) && CODE_RE.test(r2.sms_code), `blurred photo -> DUDA, conf 0: ${r2.sms_code}`);
  check((await page.textContent('#r-diag .say-text')) === T('diag_duda'), `shows "${T('diag_duda')}"`);
  check((await page.textContent('#r-reason .say-text')) === T('ui_reason_blurry'), 'reason: blurry photo');
  check((await page.textContent('#r-advice .say-text')) === T('advice_call_officer'), 'advice: call the officer');
  await shot(page, 'app_06_duda.png', true);

  // history
  await page.click('#nav [data-go="history"]');
  await page.waitForSelector('#hist-list li');
  const rows = await page.$$eval('#hist-list li', (l) => l.length);
  check(rows === 2, `history lists 2 observations (got ${rows})`);
  await shot(page, 'app_07_history.png');
  await page.click(`#hist-list button[data-obs="${r2.obs_id}"]`);
  await page.waitForSelector('#r-body:not([hidden])');
  check((await page.textContent('#r-code')) === r2.sms_code, 'tapping a history row reopens its result');

  // settings: language, PIN, lock
  await page.click('#nav [data-go="settings"]');
  await page.click('#set-langs .lang-btn[data-lang="tzh"]');
  check((await page.textContent('#nav [data-go="history"]')).includes(T('ui_history', 'tzh')), 'language toggle -> Tseltal UI');
  await shot(page, 'app_08_settings_tzh.png', true);
  await page.click('#set-langs .lang-btn[data-lang="es"]');
  await page.fill('#set-pin', '1234');
  await page.click('#set-pin-save');
  const s2 = await page.evaluate(() => JSON.parse(localStorage.getItem('cafetal.settings')));
  check(/^[0-9a-f]{64}$/.test(s2.pin_hash) && !JSON.stringify(s2).includes('1234'), 'only a SHA-256 hash of the PIN is stored');
  await page.reload();
  await page.waitForSelector('#s-lock:not([hidden])');
  check(await page.isHidden('#nav'), 'lock screen on open, navigation hidden');
  await page.fill('#pin-enter', '9999');
  await page.click('#pin-ok');
  check(await page.isVisible('#pin-err'), 'wrong PIN -> ui_pin_wrong');
  await shot(page, 'app_09_lock.png');
  await page.fill('#pin-enter', '1234');
  await page.click('#pin-ok');
  await page.waitForSelector('#s-home:not([hidden])');
  check(true, 'right PIN unlocks');

  // delete everything
  await page.click('#nav [data-go="settings"]');
  await page.click('#set-delete');
  await page.waitForSelector('#dlg-delete[open]');
  await shot(page, 'app_10_delete.png');
  await page.click('#del-yes');
  await page.waitForSelector('#s-lang:not([hidden])');
  const left = await page.evaluate(async () => {
    const dbs = indexedDB.databases ? await indexedDB.databases() : [];
    return { ls: localStorage.length, dbs: dbs.map((d) => d.name), caches: await caches.keys() };
  });
  check(left.ls === 0 && !left.dbs.includes('cafetal'), 'delete everything wiped settings and observations');
  check(left.caches.some((k) => k.startsWith('cafetal-')), 'offline app cache kept after delete');
  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await ctx.close();
}

async function phaseHub(browser) {
  // No service worker here so page.route can stand in for the hub (the real hub is tested by tests/).
  const server = await startServer();
  const ctx = await browser.newContext({ ...phone, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const seen = { inbound: null, sync: null };
  await page.route('**/api/health', (r) => r.fulfill({ json: { ok: true } }));
  await page.route('**/api/sms/inbound', (r) => {
    seen.inbound = r.request().postDataJSON();
    r.fulfill({ json: { replies: [{ body: T('sms_obs_recibida'), card_id: 'sms_obs_recibida' }], actions: [] } });
  });
  await page.route('**/api/observations/sync', (r) => {
    seen.sync = r.request().postDataJSON();
    r.fulfill({ json: { results: seen.sync.records.map(() => ({ ok: true })) } });
  });
  await page.goto(BASE);
  await page.click('.lang-btn[data-lang="es"]');
  await page.click('#lang-next');
  await page.click('#consent-yes');
  await page.fill('#member-digits', '0456');
  await page.click('#member-next');
  await page.setInputFiles('#file-gallery', path.join(FIX, 'leaf_roya.jpg'));
  await page.waitForSelector('#r-body:not([hidden])', { timeout: 120000 });
  await page.waitForSelector('#r-hub:not([hidden])', { timeout: 5000 });
  check(true, 'hub reachable -> "Simular envío" and "Sincronizar fotos" shown');
  await page.click('#r-sim');
  await page.waitForSelector('#r-sim-reply .bubble');
  const code = await page.textContent('#r-code');
  check(seen.inbound && seen.inbound.member_id === 'M0456' && seen.inbound.body === code, 'simulated send posts {member_id, body}');
  check((await page.textContent('#r-sim-reply .bubble')) === T('sms_obs_recibida'), 'hub reply shown as-is');
  check(await page.isVisible('#r-sim-chip'), 'SIMULATED label shown');
  await page.click('#r-sync');
  await page.waitForSelector('#r-sync-msg .say');
  const o = seen.sync && seen.sync.records[0];
  check(o && o.photo && o.photo.startsWith('data:image/jpeg;base64,') && o.obs_id && o.member_id === 'M0456',
    'sync posts the record with a JPEG data URL');
  check((await page.textContent('#r-sync-msg')).includes(T('ui_synced')), 'ui_synced shown');
  check(await page.isVisible('#r-synced'), 'record marked synced');
  await shot(page, 'app_11_hub_simulated.png', true);
  await ctx.close();
  server.kill();
}

async function phaseRealHub(browser) {
  const uvicorn = path.join(ROOT, '.venv/bin/uvicorn');
  if (!fs.existsSync(uvicorn) || !fs.existsSync(path.join(ROOT, 'hub/main.py'))) {
    console.log('SKIP real-hub phase (no .venv/bin/uvicorn or hub/main.py)');
    return;
  }
  const port = await freePort();
  const hubUrl = `http://127.0.0.1:${port}`;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cafetal-e2e-'));
  const env = { ...process.env, CAFETAL_DB: path.join(tmp, 'hub.db'), CAFETAL_UPLOADS: path.join(tmp, 'uploads') };
  const hub = spawn(uvicorn, ['hub.main:app', '--host', '127.0.0.1', '--port', String(port)], { cwd: ROOT, env, stdio: 'ignore' });
  try {
    let up = false;
    for (let i = 0; i < 100 && !up; i++) {
      await new Promise((r) => setTimeout(r, 150));
      up = await fetch(hubUrl + '/api/health').then((r) => r.ok, () => false);
    }
    if (!up) throw new Error('hub did not start');
    const reg = await fetch(hubUrl + '/api/members', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Prueba E2E', phone: '+529990001122', community: 'Prueba', lat: 16.9, lon: -92.1,
        consent: true, consent_by: 'e2e test' }),
    }).then((r) => r.json());
    const mid = reg.member_id;
    check(/^M\d{4}$/.test(mid || ''), `real hub: member registered ${mid}`);
    const ctx = await browser.newContext(phone);
    const page = await ctx.newPage();
    await page.goto(hubUrl + '/app/');
    await page.waitForSelector('body[data-offline="ready"]', { timeout: 120000 });
    check(true, 'real hub: app served at /app/ and cached by the service worker');
    await page.click('.lang-btn[data-lang="es"]');
    await page.click('#lang-next');
    await page.click('#consent-yes');
    await page.fill('#member-digits', mid.slice(1));
    await page.click('#member-next');
    await page.setInputFiles('#file-gallery', path.join(FIX, 'leaf_roya.jpg'));
    await page.waitForSelector('#r-body:not([hidden])', { timeout: 120000 });
    await page.waitForSelector('#r-hub:not([hidden])', { timeout: 5000 });
    const { obsId, probs } = await page.evaluate(() => ({ obsId: window.__cafetal.obs.obs_id, probs: window.__cafetal.obs.probs }));
    check(probs !== null, 'real hub: model ran in the page served by the hub (WASM + .mjs MIME types OK)');
    await page.click('#r-sim');
    await page.waitForSelector('#r-sim-reply .bubble, #r-sim-reply .say', { timeout: 10000 });
    const reply = (await page.textContent('#r-sim-reply')).trim();
    check(reply.startsWith('Cafetal') && !(await page.isVisible('#r-sim-reply .say')), `real hub: reply shown: "${reply}"`);
    let obs = (await fetch(`${hubUrl}/api/observations?member_id=${mid}`).then((r) => r.json())).observations;
    check(obs.some((o) => o.obs_id === obsId), `real hub: observation #${obsId} stored from the simulated SMS`);
    await page.click('#r-sync');
    await page.waitForSelector('#r-sync-msg .say', { timeout: 10000 });
    check((await page.textContent('#r-sync-msg')).includes(T('ui_synced')), 'real hub: sync answered ui_synced');
    obs = (await fetch(`${hubUrl}/api/observations?member_id=${mid}`).then((r) => r.json())).observations;
    const o = obs.find((x) => x.obs_id === obsId);
    check(o && o.photo_url, `real hub: photo stored for #${obsId} (${o && o.photo_url})`);
    await shot(page, 'app_12_real_hub.png', true);
    await ctx.close();
  } finally {
    hub.kill();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

const browser = await pw.chromium.launch(await launchOpts());
try {
  await phaseOffline(browser);
  await phaseHub(browser);
  await phaseRealHub(browser);
} catch (e) {
  console.error(e);
  failures++;
} finally {
  await browser.close();
}
console.log(failures ? `\n${failures} check(s) FAILED` : '\nALL CHECKS PASSED');
process.exit(failures ? 1 : 0);
