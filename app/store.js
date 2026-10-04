// Local storage on the phone: settings in localStorage, observations (with photo) in IndexedDB.
// Nothing here leaves the phone unless the user taps a send/sync button.

const SETTINGS_KEY = 'cafetal.settings';
const DB_NAME = 'cafetal';
const STORE = 'obs';

export function getSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY));
  } catch {
    return null;
  }
}
export function saveSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const st = req.result.createObjectStore(STORE, { keyPath: 'obs_id' });
      st.createIndex('member_id', 'member_id');
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(mode, fn) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const result = fn(t.objectStore(STORE));
    t.oncomplete = () => {
      db.close();
      resolve(result && 'result' in result ? result.result : undefined);
    };
    t.onerror = () => reject(t.error);
  });
}

export const putObs = (o) => tx('readwrite', (s) => s.put(o));
export const getObs = (id) => tx('readonly', (s) => s.get(id));
export async function listObs(memberId) {
  const all = await tx('readonly', (s) => s.index('member_id').getAll(memberId));
  return (all || []).sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}
export async function updateObs(id, patch) {
  const o = await getObs(id);
  if (!o) return null;
  Object.assign(o, patch);
  await putObs(o);
  return o;
}

// 4-char base36 id, unique among the records on this phone (PLAN.md §5).
export async function newObsId() {
  for (;;) {
    const id = Math.floor(Math.random() * 36 ** 4).toString(36).toUpperCase().padStart(4, '0');
    if (!(await getObs(id))) return id;
  }
}

// "Borrar todo": observations, photos and settings. The app's offline cache is kept.
export async function wipeAll() {
  localStorage.removeItem(SETTINGS_KEY);
  await new Promise((resolve) => {
    const req = indexedDB.deleteDatabase(DB_NAME);
    req.onsuccess = req.onerror = req.onblocked = () => resolve();
  });
}

// PIN: only a SHA-256 hash is stored. Pure-JS SHA-256 because crypto.subtle is missing on plain-http
// origins (e.g. the hub on the co-op LAN). A 4-digit PIN only stops casual use on a shared phone.
export const pinHash = (memberId, pin) => sha256('cafetal:' + memberId + ':' + pin);

function sha256(str) {
  const K = [];
  const H = [];
  let n = 2;
  let found = 0;
  const frac = (x) => ((x - Math.floor(x)) * 0x100000000) | 0;
  while (found < 64) {
    let prime = true;
    for (let f = 2; f * f <= n; f++) if (n % f === 0) prime = false;
    if (prime) {
      if (found < 8) H[found] = frac(n ** 0.5);
      K[found++] = frac(n ** (1 / 3));
    }
    n++;
  }
  const bytes = Array.from(new TextEncoder().encode(str));
  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  for (let i = 7; i >= 0; i--) bytes.push(i > 3 ? 0 : (bitLen >>> (8 * i)) & 0xff);
  const rotr = (x, r) => (x >>> r) | (x << (32 - r));
  for (let o = 0; o < bytes.length; o += 64) {
    const w = [];
    for (let i = 0; i < 16; i++) {
      w[i] = (bytes[o + 4 * i] << 24) | (bytes[o + 4 * i + 1] << 16) | (bytes[o + 4 * i + 2] << 8) | bytes[o + 4 * i + 3];
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      [h, g, f, e, d, c, b, a] = [g, f, e, (d + t1) | 0, c, b, a, (t1 + t2) | 0];
    }
    [a, b, c, d, e, f, g, h].forEach((v, i) => (H[i] = (H[i] + v) | 0));
  }
  return H.map((v) => (v >>> 0).toString(16).padStart(8, '0')).join('');
}
