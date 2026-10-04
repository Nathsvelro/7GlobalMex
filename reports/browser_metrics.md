# Browser metrics (EMULATED: desktop Chromium, not a phone)

Last run 2026-10-04T01:43:56.391Z by `node tests/e2e/browser_metrics.mjs` against the hub at http://localhost:8100.
Chromium 141.0.7390.37 headless, Pixel 5 profile, host: Intel(R) Xeon(R) Processor @ 2.10GHz x4 CPUs, no GPU.
Bundle measured: model cafetal-img-v2 (1972422 bytes, threshold 0.9), service-worker cache cafetal-841334ea01.

**Nothing here was measured on a real phone or a real mobile network.** CPU throttling (CDP
`Emulation.setCPUThrottlingRate`) slows this Xeon's page thread by the given factor as a rough stand-in for a
low-end Android phone; it does not model a phone's memory, thermal limits or WASM performance exactly.

## Model inference in the app page (onnxruntime-web 1.19.2, WASM, 1 thread)

| CPU throttle | first photo, cold (runtime + model load + run) | diagnose() 128 px crop, median of 10 | diagnose() 12 MP photo, median of 10 | session.run() only, median of 10 |
|---|---|---|---|---|
| x1 (none) | 645.6 ms | 18.4 ms | 22.2 ms | 10 ms |
| x4 | 3687.1 ms | 61.9 ms | 64 ms | 54.3 ms |
| x6 | 3648.2 ms | 98 ms | 105.4 ms | 83.5 ms |

`diagnose()` is the app's own function (app/infer.js): blur check + centre crop + resize + model. The 12 MP
case starts from an already-decoded 4000x3000 canvas, so JPEG decoding of a real camera photo is NOT included.

## First-load download time (CDP Network.emulateNetworkConditions)

| Hub setup | Network (down / up / latency) | Model file alone | Whole offline bundle (everything the SW precaches) |
|---|---|---|---|
| as built (gzip for text/JS/WASM) | 3G (750 / 250 kbps / 100 ms) | 21.2 s (1.97 MB) | 87.6 s = 1.5 min (251 files, 7.98 MB on the wire, 16.21 MB decoded, 26 gzip responses) |
| as built (gzip for text/JS/WASM) | slow 3G (400 / 400 kbps / 400 ms) | 39.9 s (1.97 MB) | 165.7 s = 2.8 min (251 files, 7.98 MB on the wire, 16.21 MB decoded, 26 gzip responses) |

The bundle is fetched by the page in the same four groups as `precache()` in app/sw.js (app shell incl. the
onnxruntime WASM, then cards/labels/config, then the model, then all audio). The real service worker install
could not be throttled: Chromium applies CDP throttling to page requests, not to service-worker fetches.
The page's own first requests (13 files: index.html, JS, CSS, icons, cards.json ...; /api/ calls not
counted) come on top: 173 KB decoded, 39 KB on the wire (13 gzip responses; measured with CDP, unthrottled, service worker blocked, as built (gzip for text/JS/WASM)).
Once cached, nothing is downloaded again until a file changes.
