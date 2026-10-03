# Cafetal phone app (PWA)

Static files, no build step. Vanilla JS modules:

| file | what |
|---|---|
| `index.html`, `style.css` | screens (language, consent, member ID/PIN, lock, home, result, history, settings) |
| `app.js` | screen flow, saving, SMS link, hub buttons |
| `content.js` | every visible/audible word comes from `../content/cards.json` (missing card -> `[card_id]`) |
| `infer.js` | blur check (PLAN §4, same maths as `model/blur.py`) + onnxruntime-web, lazy-loaded |
| `sms.js` | observation SMS code v1 (PLAN §5) |
| `store.js` | settings (localStorage), observations + photos (IndexedDB), PIN hash (SHA-256) |
| `sw.js` | offline cache. **Bump `VERSION` in `sw.js` whenever an app file changes**, or phones keep the old copy |
| `config.json` | SMS gateway number used in the `sms:` link (`DEMO` label shows a DEMO badge) |
| `vendor/` | onnxruntime-web 1.19.2 (MIT), see `vendor/README.md` |
| `model/` | `cafetal.onnx` + `labels.json` (owned by `model/`) |

## Run
- With the hub: `./run.sh`, then open `http://localhost:8000/app/`.
- Without the hub: `python3 -m http.server 8000` from the repo root, open `http://localhost:8000/app/`
  (`app/` and `content/` must be siblings; the hub buttons stay hidden).

## Test
`node tests/e2e/app_offline.mjs` (Playwright + Chromium; makes its own server; screenshots in `reports/screenshots/app_*.png`).
Fixtures: `python tests/e2e/make_fixtures.py` (Pillow).

## Offline needs a secure origin (Android)
Service worker, Cache API and geolocation work only on `https://` or `http://localhost`.
On `http://<hub-ip>:8000/app/` the app still diagnoses while the hub is reachable, but it will **not** work in
airplane mode and the SMS location is `-`. Options for the demo phone:
1. USB: `adb reverse tcp:8000 tcp:8000`, then open `http://localhost:8000/app/` in Chrome on the phone (recommended).
2. Put `app/` + `content/` on any HTTPS static host (the hub buttons stay hidden there).
3. Demo only: `chrome://flags/#unsafely-treat-insecure-origin-as-secure` = `http://<hub-ip>:8000` on the phone.

First load downloads about 15.6 MB (onnxruntime WASM 11.0 MB raw / 2.9 MB gzip, model ~2 MB, 142 MP3s 2.4 MB),
then nothing more is needed offline.
