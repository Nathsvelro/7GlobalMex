// On-device diagnosis: blur check + image model (onnxruntime-web, WASM, 1 thread). PLAN.md §3-§4.
import { CODES } from './sms.js';

const DEFAULTS = {
  version: 'unknown',
  classes: ['sano', 'roya', 'minador', 'phoma', 'cercospora', 'otro'],
  input: { name: null, size: 224 },
  output: { name: null, type: 'probabilities' },
  threshold: 1.0, // never used to answer: see getLabels()
  blur_threshold: 0,
  file: 'cafetal.onnx',
};
const BLUR_SIZE = 128;

let labelsPromise = null;
let sessionPromise = null;

// Fail closed: if labels.json (threshold, blur threshold) did not load, `loaded` is false and diagnose() answers
// the fail-safe 'duda' (code UNSR); the failed fetch is not cached, so the next photo tries again.
export function getLabels() {
  if (!labelsPromise) {
    labelsPromise = fetch('model/labels.json')
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({}))
      .then((l) => {
        if (!l || typeof l !== 'object') l = {};
        const loaded = typeof l.threshold === 'number' && typeof l.blur_threshold === 'number';
        if (!loaded) labelsPromise = null;
        return { ...DEFAULTS, ...l, loaded, input: { ...DEFAULTS.input, ...l.input }, output: { ...DEFAULTS.output, ...l.output } };
      });
  }
  return labelsPromise;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (window.ort) return resolve();
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error('cannot load ' + src));
    document.head.append(s);
  });
}

// Lazy: the runtime (11 MB WASM) and the model load on the first photo, then stay in memory.
export function getSession() {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const L = await getLabels();
      await loadScript('vendor/ort.wasm.min.js');
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
      ort.env.wasm.wasmPaths = new URL('vendor/', location.href).href;
      const res = await fetch('model/' + L.file);
      if (!res.ok) throw new Error('model ' + res.status);
      const bytes = new Uint8Array(await res.arrayBuffer());
      return ort.InferenceSession.create(bytes, { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
    })();
    sessionPromise.catch(() => (sessionPromise = null)); // allow a retry next time
  }
  return sessionPromise;
}

// Center-square crop of the photo, scaled to size x size.
export function squareCanvas(img, size) {
  const w = img.naturalWidth || img.width;
  const h = img.naturalHeight || img.height;
  const s = Math.min(w, h);
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, Math.floor((w - s) / 2), Math.floor((h - s) / 2), s, s, 0, 0, size, size);
  return c;
}

// Same algorithm as model/blur.py: grey -> 3x3 Laplacian on interior pixels -> population variance.
export function laplacianVariance(rgba, w, h) {
  const g = new Float64Array(w * h);
  for (let i = 0; i < w * h; i++) g[i] = 0.299 * rgba[4 * i] + 0.587 * rgba[4 * i + 1] + 0.114 * rgba[4 * i + 2];
  let sum = 0;
  let sum2 = 0;
  let n = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const v = g[i - w] + g[i + w] + g[i - 1] + g[i + 1] - 4 * g[i];
      sum += v;
      sum2 += v * v;
      n++;
    }
  }
  const mean = sum / n;
  return sum2 / n - mean * mean;
}

export function blurScore(img) {
  const c = squareCanvas(img, BLUR_SIZE);
  return laplacianVariance(c.getContext('2d').getImageData(0, 0, BLUR_SIZE, BLUR_SIZE).data, BLUR_SIZE, BLUR_SIZE);
}

const pct = (p) => Math.max(0, Math.min(99, Math.floor(p * 100)));

// Returns {label, code, conf, probs, top, reason, blur, model_version, ms}.
// label is a model class or 'duda'. reason: null | 'blurry' | 'not_coffee' | 'low_conf' | 'model_error'.
export async function diagnose(img) {
  const L = await getLabels();
  const t0 = performance.now();
  const blur = blurScore(img);
  const base = { blur: Math.round(blur * 100) / 100, model_version: L.version, probs: null, top: null };
  if (!L.loaded) {
    return { ...base, label: 'duda', code: CODES.duda, conf: 0, reason: 'model_error', model_version: 'none',
      ms: Math.round(performance.now() - t0) };
  }
  if (blur < L.blur_threshold) {
    return { ...base, label: 'duda', code: CODES.duda, conf: 0, reason: 'blurry', ms: Math.round(performance.now() - t0) };
  }
  let p;
  try {
    const session = await getSession();
    const size = L.input.size;
    const d = squareCanvas(img, size).getContext('2d').getImageData(0, 0, size, size).data;
    const x = new Float32Array(size * size * 3);
    for (let i = 0, j = 0; i < size * size; i++, j += 4) {
      x[3 * i] = d[j];
      x[3 * i + 1] = d[j + 1];
      x[3 * i + 2] = d[j + 2];
    }
    const inName = session.inputNames.includes(L.input.name) ? L.input.name : session.inputNames[0];
    const outName = session.outputNames.includes(L.output.name) ? L.output.name : session.outputNames[0];
    const out = await session.run({ [inName]: new ort.Tensor('float32', x, [1, size, size, 3]) });
    p = Array.from(out[outName].data);
    if (L.output.type !== 'probabilities') {
      const m = Math.max(...p);
      const e = p.map((v) => Math.exp(v - m));
      const s = e.reduce((a, b) => a + b, 0);
      p = e.map((v) => v / s);
    }
  } catch (e) {
    console.error('model failed', e);
    return { ...base, label: 'duda', code: CODES.duda, conf: 0, reason: 'model_error', model_version: 'none',
      ms: Math.round(performance.now() - t0) };
  }
  const k = p.indexOf(Math.max(...p));
  const top = L.classes[k];
  const probs = Object.fromEntries(L.classes.map((c, i) => [c, Math.round(p[i] * 1000) / 1000]));
  const r = { ...base, probs, top, conf: pct(p[k]), ms: Math.round(performance.now() - t0) };
  if (top === 'otro') return { ...r, label: 'otro', code: CODES.otro, reason: 'not_coffee' };
  if (p[k] < L.threshold || !CODES[top]) return { ...r, label: 'duda', code: CODES.duda, reason: 'low_conf' };
  return { ...r, label: top, code: CODES[top], reason: null };
}
