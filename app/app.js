// Cafetal phone app: onboarding, photo -> on-device diagnosis -> advice + audio -> save -> send by SMS.
// Farmer-facing words come only from ../content/cards.json (see content.js).
import * as C from './content.js';
import * as S from './store.js';
import * as M from './infer.js';
import { buildCode, smsLink, today } from './sms.js';

const APP_VERSION = 'app-v1';
const $ = (id) => document.getElementById(id);
const st = {
  settings: null, // {lang, member_id, consent_at, pin_hash, geo}
  config: { gateway_number: '', gateway_label: 'DEMO' },
  onboarding: null,
  obs: null, // observation on the result screen
  seq: [], // cards played on the result screen
  screen: null,
  offlineReady: false,
};
window.__cafetal = st; // for debugging and tests

// Result-screen play buttons: Tseltal and Spanish always; English only while the UI language is English.
const PLAY_LANGS = ['tzh', 'es', 'en'];
const isDuda = (label) => label === 'duda' || label === 'otro';
const ICON = (label) => 'icons/res_' + (isDuda(label) ? 'duda' : label) + '.svg';
const DIAG = (label) => (isDuda(label) ? 'diag_duda' : 'diag_' + label);
const NAME = (label) => (isDuda(label) ? 'name_duda' : 'name_' + label);
const REASON = { blurry: 'ui_reason_blurry', not_coffee: 'ui_reason_not_coffee', low_conf: 'ui_reason_low_conf',
  model_error: 'ui_reason_low_conf', bad_image: 'ui_reason_low_conf' };
function adviceCards(label) {
  if (isDuda(label)) return ['advice_call_officer'];
  if (label === 'roya') return ['advice_roya', 'advice_call_officer'];
  return ['advice_' + label];
}

// ---------- screens ----------
function go(name) {
  C.stopAll();
  $('toast').hidden = true;
  document.querySelectorAll('.screen').forEach((s) => (s.hidden = s.id !== 's-' + name));
  st.screen = name;
  const inApp = !!st.settings && name !== 'lock';
  $('nav').hidden = !inApp;
  document.querySelectorAll('#nav [data-go]').forEach((b) => b.classList.toggle('active', b.dataset.go === name));
  $('btn-lock').hidden = !(inApp && st.settings.pin_hash);
  refresh();
  window.scrollTo(0, 0);
  // voice first: onboarding screens read themselves aloud (if the browser allows playback)
  if (name === 'consent') C.say(['ui_consent_title', 'ui_consent_text']);
  if (name === 'member') C.say('ui_member_id_prompt');
  if (name === 'home') showHome();
  if (name === 'history') showHistory();
  if (name === 'settings') showSettings();
}

// Re-fill every text in the current language and update the status pills.
function refresh() {
  C.render($('top'));
  C.render($('nav'));
  C.render($('strip'));
  const screen = $('s-' + st.screen);
  const unverified = (screen && C.render(screen)) || C.render($('nav'));
  $('pill-unverified').hidden = !unverified;
  $('pill-demo').hidden = st.config.gateway_label !== 'DEMO';
  $('pill-offline').hidden = !st.offlineReady;
  $('r-play-en').hidden = C.getLang() !== 'en';
  $('btn-lock').setAttribute('aria-label', C.text('ui_lock'));
}

let toastTimer = null;
function toast(cardId) {
  const t = $('toast');
  t.textContent = C.text(cardId);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2800);
}

function langButtons(box, current, onPick) {
  box.textContent = '';
  const langs = Object.entries(C.languages()).sort((a, b) => (b[0] === 'tzh') - (a[0] === 'tzh')); // local language first
  for (const [code, name] of langs) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'lang-btn' + (code === current ? ' selected' : '');
    b.dataset.lang = code;
    b.innerHTML = '<svg class="i"><use href="icons/icons.svg#speaker"/></svg>';
    const s = document.createElement('span');
    s.textContent = name; // language names come from cards.json "languages"
    b.append(s);
    b.addEventListener('click', () => {
      box.querySelectorAll('.lang-btn').forEach((x) => x.classList.toggle('selected', x === b));
      onPick(code);
      C.say('ui_choose_language', code);
    });
    box.append(b);
  }
}

// ---------- first use: language -> consent -> member ID (+ optional PIN) ----------
function startOnboarding() {
  st.onboarding = { lang: null, consent_at: null };
  C.setLang('es');
  langButtons($('lang-list'), null, (code) => {
    st.onboarding.lang = code;
    C.setLang(code);
    $('lang-next').disabled = false;
    refresh();
  });
  $('lang-next').disabled = true;
  go('lang');
}

function consentYes() {
  st.onboarding.consent_at = new Date().toISOString();
  go('member');
}

function consentNo() {
  st.onboarding = null; // nothing is stored
  startOnboarding();
}

function memberNext() {
  const digits = $('member-digits').value.trim();
  const pin = $('pin-new').value.trim();
  $('member-err').hidden = /^\d{4}$/.test(digits);
  $('pin-new').classList.toggle('bad', !!pin && !/^\d{4}$/.test(pin));
  if (!$('member-err').hidden) return C.say('ui_member_id_invalid');
  if (pin && !/^\d{4}$/.test(pin)) return C.say('ui_pin_optional');
  const member_id = 'M' + digits;
  st.settings = { lang: C.getLang(), member_id, consent_at: st.onboarding.consent_at,
    pin_hash: pin ? S.pinHash(member_id, pin) : null, geo: null };
  S.saveSettings(st.settings);
  st.onboarding = null;
  $('member-digits').value = $('pin-new').value = '';
  askGeoOnce();
  go('home');
}

// Location is optional: asked once; if refused (or the origin is not secure) the SMS carries "-".
function askGeoOnce() {
  if (!navigator.geolocation || st.settings.geo) return;
  navigator.geolocation.getCurrentPosition(
    () => saveGeo('allowed'),
    (e) => saveGeo(e.code === 1 ? 'denied' : 'allowed'),
    { timeout: 20000, maximumAge: 600000 },
  );
}
function saveGeo(v) {
  if (!st.settings) return;
  st.settings.geo = v;
  S.saveSettings(st.settings);
}
function getLocation() {
  if (!navigator.geolocation || !st.settings || st.settings.geo !== 'allowed') return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: Math.round(p.coords.latitude * 100) / 100, lon: Math.round(p.coords.longitude * 100) / 100 }),
      (e) => {
        if (e.code === 1) saveGeo('denied');
        resolve(null);
      },
      { timeout: 6000, maximumAge: 1800000 },
    );
  });
}

function unlock() {
  const pin = $('pin-enter').value.trim();
  $('pin-enter').value = '';
  if (S.pinHash(st.settings.member_id, pin) === st.settings.pin_hash) {
    $('pin-err').hidden = true;
    go('home');
  } else {
    $('pin-err').hidden = false;
    C.say('ui_pin_wrong');
  }
}

// ---------- home ----------
async function showHome() {
  const pending = (await S.listObs(st.settings.member_id)).filter((o) => o.sms_status !== 'sent').length;
  $('home-pending').hidden = !pending;
  $('home-pending-n').textContent = pending;
}

// ---------- photo -> diagnosis ----------
function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('image decode failed'));
    img.src = url;
  });
}

function downscale(img, max = 640) {
  const k = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement('canvas');
  c.width = Math.round(img.naturalWidth * k);
  c.height = Math.round(img.naturalHeight * k);
  const ctx = c.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, c.width, c.height);
  return new Promise((resolve) => c.toBlob(resolve, 'image/jpeg', 0.8));
}

async function onPhoto(ev) {
  const file = ev.target.files && ev.target.files[0];
  ev.target.value = '';
  if (!file) return;
  go('result');
  $('r-busy').hidden = false;
  $('r-body').hidden = true;
  $('r-icon').hidden = true;
  const url = URL.createObjectURL(file);
  $('r-photo').src = url;
  const where = getLocation(); // runs while the model works
  let img = null;
  let r;
  try {
    img = await loadImage(url);
    r = await M.diagnose(img);
  } catch (e) {
    console.error(e);
    const L = await M.getLabels();
    r = { label: 'duda', code: 'DUDA', conf: 0, probs: null, top: null, reason: 'bad_image', model_version: L.version };
  }
  const loc = await where;
  const o = {
    obs_id: await S.newObsId(),
    member_id: st.settings.member_id,
    code: r.code,
    label: r.label,
    top: r.top,
    conf: r.conf,
    probs: r.probs,
    reason: r.reason,
    blur: r.blur ?? null,
    ms: r.ms ?? null,
    date: today(),
    created_at: new Date().toISOString(),
    lat: loc ? loc.lat : null,
    lon: loc ? loc.lon : null,
    photo: img ? await downscale(img) : null,
    sms_status: 'pending',
    synced: false,
    model_version: r.model_version,
  };
  o.sms_code = buildCode(o);
  await S.putObs(o);
  if (st.screen !== 'result') return; // user left while analysing; the record is saved
  showResult(o, true);
  toast('ui_saved');
}

// ---------- result ----------
let photoUrl = null;
function showResult(o, fresh) {
  st.obs = o;
  if (st.screen !== 'result') go('result');
  if (!fresh) {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    photoUrl = o.photo ? URL.createObjectURL(o.photo) : '';
    $('r-photo').src = photoUrl;
  }
  $('r-busy').hidden = true;
  $('r-body').hidden = false;
  $('r-icon').hidden = false;
  $('r-icon').src = ICON(o.label);
  $('r-result').dataset.result = isDuda(o.label) ? 'duda' : o.label;
  $('r-name').dataset.card = NAME(o.label);
  $('r-diag').dataset.card = DIAG(o.label);
  const reason = REASON[o.reason];
  $('r-reason').hidden = !reason;
  if (reason) $('r-reason').dataset.card = reason;
  $('r-conf').textContent = o.conf + '%';
  $('r-bar').style.width = o.conf + '%';
  const adv = adviceCards(o.label);
  $('r-advice').dataset.card = adv[0];
  $('r-advice2').hidden = adv.length < 2;
  if (adv[1]) $('r-advice2').dataset.card = adv[1];
  st.seq = [DIAG(o.label), ...(reason ? [reason] : []), ...adv, 'limits_yield'];
  for (const l of PLAY_LANGS) {
    const a = $('audio-' + l);
    a.onended = null;
    a.src = C.audioUrl(st.seq[0], l) || '';
    $('r-badge-' + l).hidden = st.seq.every((id) => C.audioVerified(id, l));
  }
  $('r-sim-reply').textContent = '';
  $('r-sync-msg').textContent = '';
  renderSms();
  refresh();
  checkHub().then((ok) => ($('r-hub').hidden = !ok));
  if (fresh) playResult(C.getLang()); // auto-play once, if the browser allows it
}

function playResult(l) {
  C.stopAll();
  C.playCards($('audio-' + l), st.seq, l).catch((e) => console.info('autoplay blocked:', e.message));
}

function renderSms() {
  const o = st.obs;
  $('r-code').textContent = o.sms_code;
  $('r-send').href = smsLink(st.config.gateway_number, o.sms_code);
  $('r-confirm').hidden = true;
  const s = $('r-sms-status');
  s.dataset.card = o.sms_status === 'sent' ? 'ui_sent' : 'ui_pending_sms';
  s.className = 'chip ' + (o.sms_status === 'sent' ? 'ok' : 'warn');
  $('r-sim-chip').hidden = o.sms_via !== 'simulated';
  $('r-synced').hidden = !o.synced;
  $('r-demo').hidden = st.config.gateway_label !== 'DEMO';
  C.render($('r-sms'));
}

async function markSent(via) {
  st.obs = await S.updateObs(st.obs.obs_id, { sms_status: 'sent', sms_via: via, sent_at: new Date().toISOString() });
  renderSms();
}

// ---------- hub (co-op Wi-Fi): only when reachable, only on tap ----------
async function checkHub() {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 1500);
  try {
    const r = await fetch('../api/health', { cache: 'no-store', signal: ctl.signal });
    return r.ok && (await r.json()).ok === true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function sayInto(box, cardId) {
  box.textContent = '';
  const d = document.createElement('div');
  d.className = 'say';
  d.dataset.card = cardId;
  box.append(d);
  C.renderEl(d);
}

async function simulateSend() {
  const box = $('r-sim-reply');
  box.textContent = '';
  try {
    const res = await fetch('../api/sms/inbound', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: st.obs.member_id, body: st.obs.sms_code }),
    });
    if (res.status === 404) return sayInto(box, 'ui_member_not_registered'); // member id unknown at this hub
    if (!res.ok) throw new Error('hub ' + res.status);
    const j = await res.json();
    for (const r of j.replies || []) {
      const b = document.createElement('div');
      b.className = 'bubble';
      b.textContent = typeof r === 'string' ? r : r.body || r.text || ''; // already a filled card from the hub
      box.append(b);
    }
    // Sent only if the hub stored the report (not e.g. "no entendimos el codigo").
    if ((j.actions || []).some((a) => a.type === 'observation_stored' || a.type === 'observation_duplicate')) {
      await markSent('simulated');
    }
  } catch (e) {
    console.warn(e);
    sayInto(box, 'ui_hub_offline');
  }
}

const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
  const fr = new FileReader();
  fr.onload = () => resolve(fr.result);
  fr.onerror = () => reject(fr.error);
  fr.readAsDataURL(blob);
});

async function syncPhotos(msgBox) {
  msgBox.textContent = '';
  let failed = null; // card to show if the hub refused a record
  try {
    const todo = (await S.listObs(st.settings.member_id)).filter((o) => !o.synced);
    for (let i = 0; i < todo.length; i += 5) {
      const batch = todo.slice(i, i + 5);
      const records = await Promise.all(batch.map(async (o) => ({
        ...o, photo: o.photo ? await blobToDataUrl(o.photo) : null, // JPEG data URL
      })));
      const res = await fetch('../api/observations/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records }),
      });
      if (!res.ok) throw new Error('hub ' + res.status);
      // The hub answers 200 with one result per record: mark only the records it stored, so the rest can retry.
      const results = (await res.json()).results || [];
      for (const [k, o] of batch.entries()) {
        const r = results[k] || {};
        if (r.ok === true) await S.updateObs(o.obs_id, { synced: true });
        else if (r.status === 404) failed = 'ui_member_not_registered';
        else failed = failed || 'ui_hub_offline';
      }
    }
    sayInto(msgBox, failed || 'ui_synced');
    if (st.obs) st.obs = (await S.getObs(st.obs.obs_id)) || st.obs;
    if (st.screen === 'result') renderSms();
    if (st.screen === 'history') showHistory();
  } catch (e) {
    console.warn(e);
    sayInto(msgBox, 'ui_hub_offline');
  }
}

// ---------- history ----------
function chip(cardId, cls, icon) {
  const s = document.createElement('span');
  s.className = 'chip ' + cls;
  if (icon) s.innerHTML = `<svg class="i"><use href="icons/icons.svg#${icon}"/></svg>`;
  const t = document.createElement('span');
  t.dataset.card = cardId;
  s.append(t);
  return s;
}

async function showHistory() {
  const list = await S.listObs(st.settings.member_id);
  const ul = $('hist-list');
  ul.textContent = '';
  $('hist-empty').hidden = list.length > 0;
  for (const o of list) {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'hist-row';
    b.dataset.obs = o.obs_id;
    const img = document.createElement('img');
    img.src = ICON(o.label);
    img.alt = '';
    const mid = document.createElement('div');
    mid.className = 'hist-mid';
    const name = document.createElement('b');
    name.dataset.card = NAME(o.label);
    const meta = document.createElement('small');
    meta.textContent = `${o.date.slice(6, 8)}/${o.date.slice(4, 6)}/${o.date.slice(0, 4)} · ${o.conf}%`;
    mid.append(name, meta);
    const chips = document.createElement('div');
    chips.className = 'hist-chips';
    chips.append(o.sms_status === 'sent' ? chip('ui_sent', 'ok', 'check') : chip('ui_pending_sms', 'warn', 'sms'));
    if (o.synced) chips.append(chip('ui_synced', 'ok', 'sync'));
    b.append(img, mid, chips);
    b.addEventListener('click', () => showResult(o, false));
    li.append(b);
    ul.append(li);
  }
  refresh();
  const unsynced = list.some((o) => !o.synced);
  $('hist-hub').hidden = true;
  if (unsynced) checkHub().then((ok) => ($('hist-hub').hidden = !ok));
}

// ---------- settings ----------
async function showSettings() {
  langButtons($('set-langs'), C.getLang(), (code) => {
    st.settings.lang = code;
    S.saveSettings(st.settings);
    C.setLang(code);
    refresh();
  });
  $('set-member').textContent = st.settings.member_id;
  $('set-lock').hidden = !st.settings.pin_hash;
  const L = await M.getLabels();
  $('set-tech').textContent = `${APP_VERSION} · ${L.version} · ${st.config.gateway_number} (${st.config.gateway_label})`;
}

function savePin() {
  const pin = $('set-pin').value.trim();
  $('set-pin').classList.toggle('bad', !!pin && !/^\d{4}$/.test(pin));
  if (pin && !/^\d{4}$/.test(pin)) return C.say('ui_pin_optional');
  st.settings.pin_hash = pin ? S.pinHash(st.settings.member_id, pin) : null;
  S.saveSettings(st.settings);
  $('set-pin').value = '';
  $('set-lock').hidden = !st.settings.pin_hash;
  $('btn-lock').hidden = !st.settings.pin_hash;
  toast('ui_saved');
}

async function deleteAll() {
  $('dlg-delete').close();
  await S.wipeAll();
  st.settings = null;
  st.obs = null;
  startOnboarding();
}

// ---------- offline cache (service worker) ----------
function askSW(worker, msg) {
  return new Promise((resolve) => {
    const ch = new MessageChannel();
    ch.port1.onmessage = (e) => resolve(e.data);
    worker.postMessage(msg, [ch.port2]);
    setTimeout(() => resolve(null), 15000);
  });
}

async function registerSW() {
  if (!('serviceWorker' in navigator)) {
    console.warn('No service worker: offline mode needs HTTPS or localhost.');
    return;
  }
  try {
    await navigator.serviceWorker.register('sw.js');
    const reg = await navigator.serviceWorker.ready;
    const status = await askSW(reg.active, { type: 'status' });
    st.offlineReady = !!(status && status.ready);
    document.body.dataset.offline = st.offlineReady ? 'ready' : 'incomplete';
    if (!st.offlineReady) console.warn('offline cache incomplete', status);
    refresh();
    if (st.offlineReady && !sessionStorage.getItem('cafetal.readyShown')) {
      sessionStorage.setItem('cafetal.readyShown', '1');
      toast('ui_offline_ready');
    }
  } catch (e) {
    console.warn('service worker failed', e);
  }
}

// ---------- wiring ----------
function bind() {
  $('lang-next').addEventListener('click', () => go('consent'));
  $('consent-yes').addEventListener('click', consentYes);
  $('consent-no').addEventListener('click', consentNo);
  $('member-next').addEventListener('click', memberNext);
  $('pin-ok').addEventListener('click', unlock);
  $('pin-enter').addEventListener('keydown', (e) => e.key === 'Enter' && unlock());
  $('file-camera').addEventListener('change', onPhoto);
  $('file-gallery').addEventListener('change', onPhoto);
  $('file-again').addEventListener('change', onPhoto);
  document.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => go(b.dataset.go)));
  $('btn-lock').addEventListener('click', () => go('lock'));
  $('set-lock').addEventListener('click', () => go('lock'));
  $('home-pending').addEventListener('click', () => go('history'));
  $('r-play-tzh').addEventListener('click', () => playResult('tzh'));
  $('r-play-es').addEventListener('click', () => playResult('es'));
  $('r-play-en').addEventListener('click', () => playResult('en'));
  $('r-send').addEventListener('click', () => ($('r-confirm').hidden = false)); // the sms: link opens the SMS app
  $('r-sent-yes').addEventListener('click', () => markSent('sms').then(() => toast('ui_sent')));
  $('r-sent-no').addEventListener('click', () => ($('r-confirm').hidden = true));
  $('r-sim').addEventListener('click', simulateSend);
  $('r-sync').addEventListener('click', () => syncPhotos($('r-sync-msg')));
  $('hist-sync').addEventListener('click', () => syncPhotos($('hist-sync-msg')));
  $('set-pin-save').addEventListener('click', savePin);
  $('set-delete').addEventListener('click', () => {
    C.render($('dlg-delete'));
    $('dlg-delete').showModal();
    C.say('ui_delete_confirm');
  });
  $('del-no').addEventListener('click', () => $('dlg-delete').close());
  $('del-yes').addEventListener('click', deleteAll);
}

async function boot() {
  registerSW();
  try {
    st.config = { ...st.config, ...(await (await fetch('config.json')).json()) };
  } catch (e) {
    console.warn('config.json', e);
  }
  try {
    await C.loadCards();
  } catch (e) {
    console.error('cards.json could not be loaded', e); // texts will show as [card_id]
  }
  bind();
  st.settings = S.getSettings();
  if (!st.settings) return startOnboarding();
  C.setLang(st.settings.lang || 'es');
  go(st.settings.pin_hash ? 'lock' : 'home');
}

boot();
