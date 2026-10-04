// Farmer-facing text and audio. Every sentence comes from ../content/cards.json (PLAN.md §10).
// A missing card is shown as "[card_id]" and logged; this file never makes up a sentence.

const CARDS_URL = '../content/cards.json';
let data = { languages: {}, cards: [] };
let byId = {};
export const DEFAULT_LANG = 'en'; // English is the main language; cards.json "languages" lists the others
let lang = DEFAULT_LANG;

export async function loadCards() {
  const res = await fetch(CARDS_URL);
  if (!res.ok) throw new Error('cards.json ' + res.status);
  data = await res.json();
  byId = Object.fromEntries(data.cards.map((c) => [c.id, c]));
}

export const languages = () => data.languages || {};
export const getLang = () => lang;
// A language that cards.json does not (or no longer) list falls back to the default.
export function setLang(l) {
  lang = l in languages() ? l : DEFAULT_LANG;
  document.documentElement.lang = lang;
}

export function text(id, l = lang, slots = {}) {
  const c = byId[id];
  if (!c || typeof c[l] !== 'string') {
    console.warn('missing card', id, l);
    return '[' + id + ']';
  }
  return c[l].replace(/\{(\w+)\}/g, (m, k) => (k in slots ? String(slots[k]) : m));
}

// Audio path relative to the app folder, or null when the card has no audio in that language.
export function audioUrl(id, l = lang) {
  const p = byId[id] && byId[id].audio && byId[id].audio[l];
  return p ? '../content/' + p : null;
}

export function textVerified(id, l = lang) {
  const c = byId[id];
  return !!(c && c.status && c.status[l] === 'verified');
}

// Audio counts as verified only if the card is verified AND the audio is not the provisional synthetic voice.
export function audioVerified(id, l = lang) {
  const c = byId[id];
  const src = (c && c.audio_source && c.audio_source[l]) || '';
  return textVerified(id, l) && !src.startsWith('synthetic-provisional');
}

export function badge() {
  const b = document.createElement('span');
  b.className = 'badge unverified';
  b.textContent = text('ui_unverified');
  return b;
}

// Plays one or more cards in a row on the given <audio> element.
export function playCards(audio, ids, l = lang) {
  const urls = ids.map((id) => audioUrl(id, l)).filter(Boolean);
  if (!urls.length) return Promise.resolve();
  let i = 0;
  audio.onended = () => {
    i += 1;
    if (i < urls.length) {
      audio.src = urls[i];
      audio.play().catch(() => {});
    }
  };
  audio.src = urls[0];
  return audio.play();
}

const player = new Audio();
export function say(ids, l = lang) {
  stopAll();
  return playCards(player, [].concat(ids), l).catch((e) => console.warn('audio', e.message));
}
export function stopAll() {
  for (const a of [player, ...document.querySelectorAll('audio')]) {
    a.onended = null;
    a.pause();
  }
}

// Fill one element from its data-card attribute (data-lang overrides the current language).
//  - plain element: textContent only
//  - element with class "say": text + speaker button + UNVERIFIED badge(s)
// Returns true when something shown is unverified.
export function renderEl(el) {
  const id = el.dataset.card;
  if (!id) return false;
  const l = el.dataset.lang || lang;
  const t = text(id, l);
  if (!el.classList.contains('say')) {
    el.textContent = t;
    return !textVerified(id, l);
  }
  el.textContent = '';
  const p = document.createElement('p');
  p.className = 'say-text';
  p.textContent = t;
  el.append(p);
  const url = audioUrl(id, l);
  if (url) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'speak';
    b.setAttribute('aria-label', t);
    b.innerHTML = '<svg class="i"><use href="icons/icons.svg#speaker"/></svg>';
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      say(id, l);
    });
    el.append(b);
  }
  const unverified = !textVerified(id, l) || (url && !audioVerified(id, l));
  if (unverified) el.append(badge());
  return unverified;
}

export function render(root = document) {
  let unverified = false;
  root.querySelectorAll('[data-card]').forEach((el) => {
    if (renderEl(el)) unverified = true;
  });
  return unverified;
}
