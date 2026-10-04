// Check every demo image (model/demo_samples/samples.json) in the REAL app logic: Chromium loads the phone app from
// a throw-away static server and calls diagnose() from app/infer.js (blur check + centre crop + resize + model +
// threshold + "otro" -> fail-safe), exactly as when a farmer picks the photo.
//   node model/check_demo_samples.mjs [--out FILE]   (from the repo root; needs python3 + playwright, like tests/e2e)
// A sample passes when the app's answer label (diagnose().label) is samples.json's expected_app, the SMS code the app
// returns is the code the app's own table (CODES in app/sms.js, read at run time) gives for that label, samples.json's
// expected_code agrees with that table, the reason matches (if given) and the model version is the shipped one.
// Field photos that are not downloaded yet (python3 model/demo_samples.py --field) are reported as SKIP.
// Writes reports/model_demo_samples_check.json (or --out FILE); exit code 1 if any present sample fails.
import { spawn, execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import crypto from 'node:crypto';
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
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIR = path.join(ROOT, 'model/demo_samples');
const manifest = JSON.parse(fs.readFileSync(path.join(DIR, 'samples.json'), 'utf8'));
const labels = JSON.parse(fs.readFileSync(path.join(ROOT, 'app/model/labels.json'), 'utf8'));
const modelSha = crypto.createHash('sha1').update(fs.readFileSync(path.join(ROOT, 'app/model', labels.file))).digest('hex').slice(0, 12);
const outIdx = process.argv.indexOf('--out');
const OUT = outIdx > 0 ? path.resolve(process.argv[outIdx + 1]) : path.join(ROOT, 'reports/model_demo_samples_check.json');

const port = await new Promise((resolve) => {
  const s = net.createServer().listen(0, '127.0.0.1', () => {
    const p = s.address().port;
    s.close(() => resolve(p));
  });
});
const BASE = `http://127.0.0.1:${port}/app/`;
const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
let failures = 0;
let codes = null;
const results = [];
try {
  for (let i = 0; i < 50 && !(await fetch(BASE + 'config.json').then((r) => r.ok, () => false)); i++) {
    await new Promise((r) => setTimeout(r, 100));
  }
  const opts = {};
  const exe = process.env.CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  try {
    if (!fs.existsSync(pw.chromium.executablePath())) opts.executablePath = exe;
  } catch {
    if (fs.existsSync(exe)) opts.executablePath = exe;
  }
  const browser = await pw.chromium.launch(opts);
  const ctx = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 360, height: 740 } });
  const page = await ctx.newPage();
  await page.goto(BASE);
  codes = await page.evaluate(async () => ({ ...(await import('./sms.js')).CODES }));
  console.log('SMS code table from app/sms.js:', JSON.stringify(codes));
  for (const s of manifest.samples) {
    const file = path.join(DIR, s.file);
    if (!fs.existsSync(file)) {
      console.log(`SKIP ${s.file}: not downloaded (python3 model/demo_samples.py --field)`);
      results.push({ file: s.file, kind: s.kind, expected_app: s.expected_app, expected_code: s.expected_code || null,
        skipped: true });
      continue;
    }
    const url = 'data:image/jpeg;base64,' + fs.readFileSync(file).toString('base64');
    const r = await page.evaluate(async (src) => {
      const M = await import('./infer.js');
      const img = await new Promise((res, rej) => {
        const i = new Image();
        i.onload = () => res(i);
        i.onerror = rej;
        i.src = src;
      });
      const o = await M.diagnose(img);
      return { label: o.label, code: o.code, conf: o.conf, top: o.top, reason: o.reason, blur: o.blur, probs: o.probs,
        model_version: o.model_version, size: [img.naturalWidth, img.naturalHeight] };
    }, url);
    const tableCode = codes[s.expected_app];  // the code the app's own table gives for the expected answer
    const labelOk = r.label === s.expected_app;
    const codeOk = !!tableCode && r.code === tableCode;
    const manifestOk = !s.expected_code || s.expected_code === tableCode;
    const ok = labelOk && codeOk && manifestOk
      && (!s.expected_reason || r.reason === s.expected_reason) && r.model_version === labels.version;
    if (!ok) failures++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${s.file} (${s.kind}): app says ${r.label} / code ${r.code} (top ${r.top} ${r.conf}%, ` +
      `reason ${r.reason}, blur ${r.blur}); expected ${s.expected_app} / code ${tableCode} (app/sms.js)` +
      `${s.expected_reason ? ' / ' + s.expected_reason : ''}` +
      (manifestOk ? '' : `; samples.json expects code ${s.expected_code} but app/sms.js says ${tableCode}`));
    results.push({ file: s.file, kind: s.kind, license: s.license, expected_app: s.expected_app,
      expected_code: s.expected_code || null, app_table_code: tableCode || null, expected_reason: s.expected_reason || null,
      pass: ok, label_ok: labelOk, code_ok: codeOk, manifest_code_ok: manifestOk, ...r });
  }
  await browser.close();
} finally {
  server.kill();
}
const out = {
  generated_by: 'node model/check_demo_samples.mjs', measured_at: new Date().toISOString(),
  how: 'Chromium (Playwright), app/infer.js diagnose() on each file, service worker blocked, static server; SMS codes ' +
    'compared with the CODES table of app/sms.js, read in the page at run time',
  model: { version: labels.version, file: 'app/model/' + labels.file, sha1_12: modelSha, threshold: labels.threshold,
    blur_threshold: labels.blur_threshold },
  sms_codes_from_app: codes,
  passed: results.filter((r) => r.pass).length, failed: failures, skipped: results.filter((r) => r.skipped).length,
  results,
};
fs.writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n');
console.log(`${out.passed} passed, ${out.failed} failed, ${out.skipped} skipped -> ${path.relative(ROOT, OUT)}`);
process.exit(failures ? 1 : 0);
