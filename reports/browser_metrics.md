# Browser metrics (EMULATED: desktop Chromium, not a phone)

Last run 2026-10-03T22:16:54.613Z by `node tests/e2e/browser_metrics.mjs` against the hub at http://localhost:8000.
Chromium 141.0.7390.37 headless, Pixel 5 profile, host: Intel(R) Xeon(R) Processor @ 2.10GHz x4 CPUs, no GPU.
Bundle measured: model cafetal-img-v2 (1972422 bytes, threshold 0.9), service-worker cache cafetal-7b8eb4c086.

**Nothing here was measured on a real phone or a real mobile network.** CPU throttling (CDP
`Emulation.setCPUThrottlingRate`) slows this Xeon's page thread by the given factor as a rough stand-in for a
low-end Android phone; it does not model a phone's memory, thermal limits or WASM performance exactly.

## Model inference in the app page (onnxruntime-web 1.19.2, WASM, 1 thread)

| CPU throttle | first photo, cold (runtime + model load + run) | diagnose() 128 px crop, median of 10 | diagnose() 12 MP photo, median of 10 | session.run() only, median of 10 |
|---|---|---|---|---|
| x1 (none) | 657.3 ms | 19.2 ms | 16.8 ms | 14.1 ms |
| x4 | 2497.4 ms | 51.7 ms | 53 ms | 57.5 ms |
| x6 | 3739.9 ms | 106.2 ms | 83.4 ms | 71.1 ms |

`diagnose()` is the app's own function (app/infer.js): blur check + centre crop + resize + model. The 12 MP
case starts from an already-decoded 4000x3000 canvas, so JPEG decoding of a real camera photo is NOT included.

## First-load download time (CDP Network.emulateNetworkConditions)

| Hub setup | Network (down / up / latency) | Model file alone | Whole offline bundle (everything the SW precaches) |
|---|---|---|---|
| as built (gzip for text/JS/WASM) | 3G (750 / 250 kbps / 100 ms) | 21.2 s (1.97 MB) | 94 s = 1.6 min (251 files, 8.59 MB on the wire, 16.81 MB decoded, 26 gzip responses) |
| as built (gzip for text/JS/WASM) | slow 3G (400 / 400 kbps / 400 ms) | 39.9 s (1.97 MB) | 177.5 s = 3.0 min (251 files, 8.59 MB on the wire, 16.81 MB decoded, 26 gzip responses) |

The bundle is fetched by the page in the same four groups as `precache()` in app/sw.js (app shell incl. the
onnxruntime WASM, then cards/labels/config, then the model, then all audio). The real service worker install
could not be throttled: Chromium applies CDP throttling to page requests, not to service-worker fetches.
The page's own first requests (13 files: index.html, JS, CSS, icons, cards.json ...; /api/ calls not
counted) come on top: 157 KB decoded, 37 KB on the wire (13 gzip responses; measured with CDP, unthrottled, service worker blocked, as built (gzip for text/JS/WASM)).
Once cached, nothing is downloaded again until a file changes.
