// Whole-journey check (Definition of Done in docs/CLAUDE_CODE_PROMPT.md), against a RUNNING hub.
//   ./run.sh                      (in another terminal; serves the hub and the phone app on :8000)
//   node tests/e2e/journey.mjs    (from the repo root)
// Env: HUB=http://localhost:8000 (hub URL; must be localhost or HTTPS for the service worker)
//      DATA_RAW=/home/user/data_raw (PlantDoc + Imagenette test images; those checks are SKIPPED if missing)
//      NO_RESET=1 (do not reset the DEMO data first; by default the test calls POST /api/demo/reset)
//      KEEP_STATE=1 (leave the hub as the journey left it; by default the DEMO data is reset again at the end so
//      the live demo can still fire the alert with Noor's ROYA)
// Playwright: uses `playwright` from node_modules or the global npm root. If Playwright cannot find its own
//   Chromium, the test falls back to /opt/pw-browsers/chromium-1194/chrome-linux/chrome (or set CHROMIUM=<path>).
//   Do not run "playwright install" in the sandbox.
// Offline: PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1 (set below) makes Playwright see and route the service
//   worker's own fetches; without it context.setOffline() does NOT stop them in Chromium. During the airplane-mode
//   phase every request that would leave the browser is also aborted by a route, and counted.
// Steps: A) first load -> SW caches everything -> offline reload -> onboarding (es, consent, M0123) -> rust
//   test image -> audio tzh+es from the cache; B) PlantDoc / non-plant / blurred -> diag_duda; C) SMS code;
//   D) back online: Simular envío -> observation, 3rd ROYA nearby -> alert + pending broadcasts, worklist,
//   approve one broadcast in the Bandeja page, sync photo; E) simulator SMS: PRECIO + free text; F) every
//   outbound SMS = a cards.json template with slots filled; every visible app text comes from cards.json.
// Writes reports/screenshots/journey_*.png and reports/journey_results.json. Exit code 1 if a check fails.
process.env.PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS ??= '1';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
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
const RAW = process.env.DATA_RAW || '/home/user/data_raw';
const FIX = path.join(ROOT, 'tests/e2e/fixtures');
const SHOTS = path.join(ROOT, 'reports/screenshots');
const IMG = {
  roya: path.join(FIX, 'journey_roya.jpg'), // first rust image of the model's TEST split (make_journey_fixtures.py)
  plantdoc: path.join(RAW, 'plantdoc/plant_doc_classification/Apple Scab Leaf/Apple-Scab-image-02.jpg'), // test split
  imagenette: path.join(RAW, 'imagenette/imagenette2-160/train/n02979186/n02979186_8558.JPEG'), // test split, cassette player
  object: path.join(FIX, 'journey_object.jpg'), // synthetic non-plant photo
  blurred: path.join(FIX, 'journey_blurred.jpg'), // rust image, Gaussian blur r=6
};
const NOOR = { member: 'M0123', phone: '+529670000123', lat: 16.912, lon: -92.108 };
const CODE_RE = /^CAF1 M\d{4} (SANO|ROYA|MINA|PHOM|CERC|ACAR|OTRO|DUDA) \d{1,2} \d{8} (-?\d+\.\d{2},-?\d+\.\d{2}|-) #[0-9A-Z]{4}$/i;
const cards = JSON.parse(fs.readFileSync(path.join(ROOT, 'content/cards.json'), 'utf8'));
const byId = Object.fromEntries(cards.cards.map((c) => [c.id, c]));
const T = (id, lang = 'es') => byId[id][lang];
fs.mkdirSync(SHOTS, { recursive: true });

const out = { hub: HUB, started: new Date().toISOString(), checks: [], results: {} };
let failures = 0;
function check(cond, msg, extra) {
  console.log((cond ? 'PASS ' : 'FAIL ') + msg);
  out.checks.push({ ok: !!cond, msg, ...(extra ? { extra } : {}) });
  if (!cond) failures++;
  return !!cond;
}
const skip = (msg) => {
  console.log('SKIP ' + msg);
  out.checks.push({ ok: null, msg: 'SKIP ' + msg });
};
async function api(p, body) {
  const r = await fetch(HUB + p, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${p} -> HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}
// Viewport screenshots (a full-page shot paints the fixed bottom nav in the middle of the page).
async function shot(page, name, scrollTo = null) {
  if (scrollTo) await page.locator(scrollTo).scrollIntoViewIfNeeded();
  else await page.evaluate(() => window.scrollTo(0, 0));
  await page.locator('#toast').waitFor({ state: 'hidden', timeout: 4000 }).catch(() => {}); // the phone's "saved" toast
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(SHOTS, name) });
}
function launchOpts() {
  const opts = { args: ['--autoplay-policy=no-user-gesture-required'] };
  const fallback = process.env.CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  let own = null;
  try {
    own = pw.chromium.executablePath();
  } catch { /* no bundled browser */ }
  if ((!own || !fs.existsSync(own)) && fs.existsSync(fallback)) opts.executablePath = fallback;
  return opts;
}

// ---------- "every sentence comes from cards.json" ----------
const cardTexts = new Set();
for (const c of cards.cards) for (const l of Object.keys(cards.languages)) if (typeof c[l] === 'string') cardTexts.add(c[l].trim());
for (const name of Object.values(cards.languages)) cardTexts.add(name);
// Data, not sentences: numbers, dates, percentages, the SMS code, the member id (and its fixed "M" prefix next to
// the digits box), the technical version line in Settings.
const isData = (s) => /^[\d\s.,:;%·/#+()\-–—•]*$/.test(s) || CODE_RE.test(s) || /^M(\d{4})?$/.test(s) ||
  /^app-v\d+ · [\w.-]+ · \+?\d+ \((DEMO|[A-Z]+)\)$/.test(s);
const textAudit = { screens: [], notFromCards: [] };
async function auditText(page, where) {
  const strings = await page.evaluate(() => {
    const seen = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const s = n.textContent.replace(/\s+/g, ' ').trim();
      const el = n.parentElement;
      if (!s || !el || el.closest('script,style,[hidden],dialog:not([open])')) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') continue;
      seen.push(s);
    }
    return [...new Set(seen)];
  });
  const bad = strings.filter((s) => !isData(s) && !cardTexts.has(s));
  textAudit.screens.push({ where, strings: strings.length, bad });
  for (const b of bad) textAudit.notFromCards.push({ where, text: b });
  check(bad.length === 0, `visible text on "${where}" comes from cards.json (${strings.length} strings)` +
    (bad.length ? ': NOT FROM CARDS: ' + JSON.stringify(bad) : ''));
}

// ---------- "every outbound SMS is a filled card template" ----------
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
function matchTemplate(body, cardId, lang) {
  const tpls = cardId ? [[cardId, lang]] : cards.cards.flatMap((c) => Object.keys(cards.languages).map((l) => [c.id, l]));
  for (const [id, l] of tpls) {
    const t = byId[id] && byId[id][l];
    if (typeof t !== 'string') continue;
    const slots = [...t.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
    const re = new RegExp('^' + esc(t).replace(/\\\{\w+\\\}/g, '(.+?)') + '$', 's');
    const m = body.match(re);
    if (m) return { id, lang: l, slots: Object.fromEntries(slots.map((s, i) => [s, m[i + 1]])) };
  }
  return null;
}
// Slot values may only be numbers, dates, units, places and source names: short, no sentence punctuation.
const okSlot = (v) => v.length <= 40 && !/[.!?¿¡]\s/.test(v);

// ---------- phone helpers ----------
async function diagnose(page, file, input = '#file-again') {
  const before = await page.evaluate(() => window.__cafetal.obs && window.__cafetal.obs.obs_id);
  await page.setInputFiles(input, file);
  await page.waitForFunction((b) => {
    const o = window.__cafetal.obs;
    return o && o.obs_id !== b && !document.getElementById('r-body').hidden;
  }, before, { timeout: 120000 });
  return page.evaluate(() => {
    const o = window.__cafetal.obs;
    return { obs_id: o.obs_id, label: o.label, code: o.code, top: o.top, conf: o.conf, reason: o.reason, blur: o.blur,
      ms: o.ms, probs: o.probs, sms_code: o.sms_code, model_version: o.model_version,
      diag_text: document.querySelector('#r-diag .say-text').textContent };
  });
}
async function failSafe(page, key, label) {
  if (!fs.existsSync(IMG[key])) return skip(`${label}: ${IMG[key]} not found (set DATA_RAW)`);
  const r = await diagnose(page, IMG[key]);
  out.results[key] = r;
  console.log(`  ${key}: ${r.sms_code} top=${r.top} reason=${r.reason} blur=${r.blur}`);
  check(r.diag_text === T('diag_duda') && ['DUDA', 'OTRO'].includes(r.code),
    `${label} -> "${T('diag_duda')}" (${r.code}, top ${r.top} ${r.conf}%, reason ${r.reason})`);
  return r;
}

async function phone(browser) {
  const ctx = await browser.newContext({
    ...pw.devices['Pixel 5'], locale: 'es-MX', permissions: ['geolocation'],
    geolocation: { latitude: NOOR.lat, longitude: NOOR.lon },
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !m.text().startsWith('Failed to load resource') && errors.push(m.text()));

  // ---- A) first load online, then airplane mode ----
  const t0 = Date.now();
  await page.goto(HUB + '/app/');
  await page.waitForSelector('body[data-offline="ready"]', { timeout: 300000 });
  await page.waitForSelector('#pill-offline:not([hidden])');
  out.results.first_load_ready_ms = Date.now() - t0;
  check(true, `service worker cached the whole app (ui_offline_ready shown) after ${Date.now() - t0} ms (unthrottled, localhost)`);
  await page.screenshot({ path: path.join(SHOTS, 'journey_01_offline_ready.png') }); // with the ui_offline_ready toast

  const net = { attempts: [], responses: [] };
  await ctx.setOffline(true);
  await ctx.route('**/*', (r) => {
    net.attempts.push((r.request().serviceWorker() ? 'sw ' : 'page ') + r.request().url().replace(HUB, ''));
    return r.abort('internetdisconnected');
  });
  const onResp = (r) => {
    if (!r.fromServiceWorker()) net.responses.push(r.url().replace(HUB, '') + ' ' + r.status());
  };
  ctx.on('response', onResp);
  await page.reload();
  await page.waitForSelector('#s-lang:not([hidden])');
  check(await page.isVisible('#pill-demo'), 'airplane mode: app opens from the cache; DEMO badge visible');
  await shot(page, 'journey_02_language.png');
  await auditText(page, 'language');
  await page.click('.lang-btn[data-lang="es"]');
  await page.click('#lang-next');
  await page.waitForSelector('#s-consent:not([hidden])');
  await shot(page, 'journey_03_consent.png');
  await auditText(page, 'consent');
  await page.click('#consent-yes');
  await page.waitForSelector('#s-member:not([hidden])');
  await page.fill('#member-digits', NOOR.member.slice(1));
  await shot(page, 'journey_04_member.png');
  await auditText(page, 'member id');
  await page.click('#member-next');
  await page.waitForSelector('#s-home:not([hidden])');
  await page.waitForTimeout(600); // geolocation permission answer
  await shot(page, 'journey_05_home.png');
  await auditText(page, 'home');

  // rust test image -> expect roya
  const roya = await diagnose(page, IMG.roya, '#file-camera');
  out.results.roya = roya;
  console.log('  rust test image:', JSON.stringify({ code: roya.sms_code, top: roya.top, probs: roya.probs, ms: roya.ms }));
  check(roya.label === 'roya', `JMuBEN rust TEST image -> ${roya.label} ${roya.conf}% (expected roya)`);
  const audio = await page.evaluate(async () => {
    const res = {};
    for (const l of ['tzh', 'es']) {
      const a = document.getElementById('audio-' + l);
      const r = await fetch(a.src).catch(() => null);
      res[l] = { src: a.getAttribute('src'), ok: !!(r && r.ok), bytes: r ? (await r.arrayBuffer()).byteLength : 0 };
    }
    return res;
  });
  check(audio.tzh.ok && audio.es.ok && audio.tzh.bytes > 1000 && audio.es.bytes > 1000,
    `audio for tzh and es present and loadable offline: ${audio.tzh.src} (${audio.tzh.bytes} B), ${audio.es.src} (${audio.es.bytes} B)`);
  for (const l of ['tzh', 'es']) {
    await page.click('#r-play-' + l);
    await page.waitForTimeout(1300);
    const t = await page.evaluate((x) => document.getElementById('audio-' + x).currentTime, l);
    check(t > 0, `${l} advice audio plays offline (currentTime ${t.toFixed(2)} s)`);
  }
  await page.evaluate(() => document.querySelectorAll('audio').forEach((a) => a.pause()));
  await shot(page, 'journey_06_result_roya.png');
  await shot(page, 'journey_06b_result_roya_advice.png', '#r-advice2');
  await shot(page, 'journey_06c_result_roya_sms.png', '#r-code');
  await auditText(page, 'result (roya)');

  // C) SMS code
  check(CODE_RE.test(roya.sms_code) && roya.sms_code.length <= 160,
    `SMS code valid, ${roya.sms_code.length} chars: ${roya.sms_code}`);
  check(roya.sms_code.includes(' 16.91,-92.11 '), 'location rounded to 2 decimals (~1 km)');
  const href = await page.getAttribute('#r-send', 'href');
  check(href === 'sms:+520000000000?body=' + encodeURIComponent(roya.sms_code), `"Enviar por SMS" link: ${href}`);
  await page.evaluate(() => document.addEventListener('click', (e) => {
    if (e.target.closest('a[href^="sms:"]')) e.preventDefault(); // no SMS app in the test browser
  }, true));
  await page.click('#r-send');
  check(await page.isVisible('#r-confirm'), 'after the sms: link the app asks "did you send it?" (nothing is sent by itself)');
  await page.click('#r-sent-no'); // keep it pending; the SIMULATED send below stands in for the real SMS

  // B) fail-safe photos
  await failSafe(page, 'plantdoc', 'PlantDoc test image (apple scab leaf)');
  await shot(page, 'journey_07_plantdoc.png');
  await failSafe(page, 'imagenette', 'Imagenette test image (cassette player, not a plant)');
  await failSafe(page, 'object', 'synthetic non-plant photo (bucket)');
  await shot(page, 'journey_08_not_plant.png');
  const bl = await failSafe(page, 'blurred', 'heavily blurred rust photo');
  check(bl && bl.reason === 'blurry' && / DUDA 0 /.test(bl.sms_code), `blurred photo caught by the blur check (score ${bl && bl.blur})`);
  await shot(page, 'journey_09_blurred.png');
  await auditText(page, 'result (duda)');

  await page.click('#nav [data-go="history"]');
  await page.waitForSelector('#hist-list li');
  await shot(page, 'journey_10_history.png');
  await auditText(page, 'history');
  await page.click('#nav [data-go="settings"]');
  await page.waitForSelector('#s-settings:not([hidden])');
  await auditText(page, 'settings');
  await page.click('#set-langs .lang-btn[data-lang="tzh"]');
  await auditText(page, 'settings (tzh)');
  await page.click('#nav [data-go="history"]');
  await page.click(`#hist-list button[data-obs="${roya.obs_id}"]`);
  await page.waitForSelector('#r-body:not([hidden])');
  await page.evaluate(() => document.querySelectorAll('audio').forEach((a) => a.pause()));
  await shot(page, 'journey_11_result_tzh.png');
  await auditText(page, 'result (roya, tzh)');
  await page.click('#nav [data-go="settings"]');
  await page.click('#set-langs .lang-btn[data-lang="es"]');

  ctx.off('response', onResp);
  out.results.offline_network = net;
  check(net.responses.length === 0,
    `airplane mode: 0 responses from the network (${net.attempts.length} attempts blocked: ${[...new Set(net.attempts)].join(', ')})`);

  // ---- D) back online (co-op Wi-Fi): simulated SMS + photo sync ----
  await ctx.unroute('**/*');
  await ctx.setOffline(false);
  await page.click('#nav [data-go="history"]');
  await page.click(`#hist-list button[data-obs="${roya.obs_id}"]`);
  await page.waitForSelector('#r-hub:not([hidden])', { timeout: 10000 });
  const alertsBefore = (await api('/api/alerts')).alerts.length;
  await page.click('#r-sim');
  await page.waitForSelector('#r-sim-reply .bubble, #r-sim-reply .say', { timeout: 15000 });
  const reply = (await page.textContent('#r-sim-reply')).trim();
  check(!!matchTemplate(reply, 'sms_obs_recibida', 'es'), `"Simular envío" -> hub reply (card sms_obs_recibida): "${reply}"`);
  check(await page.isVisible('#r-sim-chip'), 'SIMULATED label shown on the phone');
  await page.evaluate(() => document.querySelectorAll('audio').forEach((a) => a.pause()));
  await shot(page, 'journey_12_simulated_send.png', '#r-sim-reply');

  const uid = `${NOOR.member}-${roya.obs_id}`;
  const obs = (await api(`/api/observations?member_id=${NOOR.member}`)).observations;
  const mine = obs.find((o) => o.uid === uid);
  check(mine && mine.code === roya.code && mine.source === 'sms', `hub stored the observation ${uid} (${mine && mine.code} ${mine && mine.conf}%) from the SMS`);
  const alerts = (await api('/api/alerts')).alerts;
  out.results.alerts = alerts;
  check(alerts.length === alertsBefore + 1, `outbreak alert created (${alerts.length} alert(s)): ` + JSON.stringify(alerts[0] || {}).slice(0, 300));
  const pending = (await api('/api/outbox?status=pending_approval')).messages;
  const bcast = pending.filter((m) => m.card_id === 'alert_roya');
  check(bcast.length > 0, `${bcast.length} alert_roya broadcasts queued as pending_approval (nothing sent yet)`);
  const farms = (await api('/api/worklist')).farms;
  const farm = farms.find((f) => f.member_id === NOOR.member);
  out.results.worklist_noor = farm;
  check(!!farm, `Noor's farm on the officer worklist: rank ${farm && farm.rank}, "${farm && farm.reason}"`);

  await page.click('#r-sync');
  await page.waitForSelector('#r-sync-msg .say', { timeout: 20000 });
  check((await page.textContent('#r-sync-msg')).includes(T('ui_synced')), 'sync photos -> ui_synced');
  const after = (await api(`/api/observations?member_id=${NOOR.member}`)).observations.find((o) => o.uid === uid);
  const ph = after && after.photo_url ? await fetch(HUB + after.photo_url) : null;
  check(ph && ph.ok && ph.headers.get('content-type') === 'image/jpeg', `photo attached to ${uid}: ${after && after.photo_url}`);
  await shot(page, 'journey_13_synced.png', '#r-sync-msg');
  check(errors.length === 0, 'no page errors on the phone' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await ctx.close();
  return { uid, bcast };
}

async function hubPages(browser, { bcast }) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'es-MX' });
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept());
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  // approve ONE broadcast in the Bandeja page (staff tap)
  await page.goto(HUB + '/hub/bandeja.html?filter=pending_approval');
  await page.waitForSelector(`button[onclick="decide(${bcast[0].id},'approve')"]`);
  await shot(page, 'journey_14_bandeja_pending.png');
  await page.click(`button[onclick="decide(${bcast[0].id},'approve')"]`);
  await page.waitForTimeout(800);
  const all = (await api('/api/outbox')).messages;
  const m = all.find((x) => x.id === bcast[0].id);
  check(m && m.status === 'sent_simulated', `staff approved one broadcast in the Bandeja page -> ${m && m.status}; ` +
    `${all.filter((x) => x.status === 'pending_approval').length} still pending`);
  await shot(page, 'journey_15_bandeja_approved.png');

  for (const [file, name] of [['', 'journey_16_hub_home.png'], ['mapa.html', 'journey_17_mapa.png'],
    ['tecnico.html', 'journey_18_tecnico.png'], ['contenido.html', 'journey_19_contenido.png'], ['registro.html', 'journey_20_registro.png']]) {
    await page.goto(HUB + '/hub/' + file);
    await page.waitForLoadState('networkidle');
    await shot(page, name);
  }

  // ---- E) simulated basic phone ----
  await page.goto(HUB + '/hub/simulador.html?phone=' + encodeURIComponent(NOOR.phone));
  await page.waitForFunction(() => document.getElementById('who').options.length > 1);
  const sms = {};
  for (const body of ['PRECIO', 'cuanto estan pagando el kilo de cafe', 'mis matas tienen polvo naranja', 'asdf qwerty']) {
    await page.fill('#body', body);
    const [resp] = await Promise.all([page.waitForResponse((r) => r.url().endsWith('/api/sms/inbound')), page.click('#send')]);
    sms[body] = await resp.json();
    await page.waitForTimeout(400);
    if (body === 'PRECIO') await shot(page, 'journey_21_simulador_precio.png');
  }
  await page.waitForTimeout(2200); // thread refresh
  await shot(page, 'journey_22_simulador_texto.png');
  out.results.sms = sms;
  const prices = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/prices.json'), 'utf8'));
  const p = sms.PRECIO.replies[0] || {};
  const cafe = prices.items.find((i) => i.id === 'cafe_pergamino');
  check(p.card_id === 'sms_precio' && p.body.includes(cafe.price.toFixed(2)) && p.body.includes(prices.sms_fuente) &&
    p.body.includes(prices.sms_fecha), `PRECIO -> reference price ${cafe.price.toFixed(2)}, source "${prices.sms_fuente}", date "${prices.sms_fecha}": "${p.body}"`);
  const intentOf = (r) => (r.actions.find((a) => a.type === 'intent') || {});
  const fw = (r) => r.actions.some((a) => a.type === 'forwarded_to_officer');
  let r = sms['cuanto estan pagando el kilo de cafe'];
  check(intentOf(r).intent === 'precio' && r.replies[0].card_id === 'sms_precio',
    `"cuanto estan pagando el kilo de cafe" -> ${intentOf(r).intent} (${intentOf(r).conf}) -> ${r.replies[0].card_id}`);
  r = sms['mis matas tienen polvo naranja'];
  check(intentOf(r).intent === 'reporte' && r.replies[0].card_id === 'sms_reporte_instrucciones',
    `"mis matas tienen polvo naranja" -> ${intentOf(r).intent} (${intentOf(r).conf}) -> ${r.replies[0].card_id}`);
  r = sms['asdf qwerty'];
  check(fw(r) && r.replies[0].card_id === 'sms_pasar_tecnico',
    `"asdf qwerty" -> ${intentOf(r).intent} (${intentOf(r).conf}) -> ${r.replies[0].card_id}, forwarded to officer: ${fw(r)}`);
  const om = (await api('/api/officer/messages')).messages;
  check(om.some((x) => x.body === 'asdf qwerty'), 'the unknown message is in the officer\'s inbox (/api/officer/messages)');
  await page.goto(HUB + '/hub/tecnico.html#mensajes');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(SHOTS, 'journey_23_tecnico_mensajes.png'), fullPage: true });
  check(errors.length === 0, 'no page errors on the hub pages' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await ctx.close();
}

// ---- F) every outbound SMS is a cards.json template with slots filled ----
async function templates() {
  const outbox = (await api('/api/outbox')).messages;
  const thread = (await api('/api/sms/thread?phone=' + encodeURIComponent(NOOR.phone))).messages.filter((x) => x.direction === 'out');
  const bad = [];
  const slotsSeen = {};
  for (const m of [...outbox, ...thread]) {
    const t = matchTemplate(m.body, m.card_id, m.lang);
    if (!t || !Object.values(t.slots).every(okSlot)) bad.push({ id: m.id, card_id: m.card_id, body: m.body });
    else for (const [k, v] of Object.entries(t.slots)) (slotsSeen[k] = slotsSeen[k] || new Set()).add(v);
  }
  out.results.template_slots = Object.fromEntries(Object.entries(slotsSeen).map(([k, v]) => [k, [...v].slice(0, 8)]));
  check(bad.length === 0, `all ${outbox.length} outbox + ${thread.length} thread messages are cards.json templates ` +
    `with only slot values filled` + (bad.length ? ': BAD ' + JSON.stringify(bad.slice(0, 5)) : ''));
  console.log('  slot values seen:', JSON.stringify(out.results.template_slots));
}

// ---------- main ----------
const health = await fetch(HUB + '/api/health').then((r) => r.json(), () => null);
if (!health || !health.ok) {
  console.error(`No hub at ${HUB}. Start it first: ./run.sh   (or set HUB=...)`);
  process.exit(2);
}
if (!fs.existsSync(IMG.roya)) {
  console.error('Missing fixtures: run  python tests/e2e/make_journey_fixtures.py  (needs pillow + numpy)');
  process.exit(2);
}
if (!process.env.NO_RESET) await api('/api/demo/reset', {});
const browser = await pw.chromium.launch(launchOpts());
try {
  const ph = await phone(browser);
  await hubPages(browser, ph);
  await templates();
} catch (e) {
  console.error(e);
  check(false, 'journey crashed: ' + e.message);
} finally {
  await browser.close();
  if (!process.env.KEEP_STATE) await api('/api/demo/reset', {}).then(() => console.log('  DEMO data reset (KEEP_STATE=1 keeps the journey state)'), (e) => console.error(e));
}
out.text_audit = textAudit;
out.finished = new Date().toISOString();
out.failures = failures;
fs.writeFileSync(path.join(ROOT, 'reports/journey_results.json'), JSON.stringify(out, null, 2) + '\n');
console.log(failures ? `\n${failures} check(s) FAILED` : '\nALL CHECKS PASSED');
process.exit(failures ? 1 : 0);
