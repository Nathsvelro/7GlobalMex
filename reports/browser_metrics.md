# Browser metrics (EMULATED: desktop Chromium, not a phone)

Last run 2026-10-03T19:12:05.637Z by `node tests/e2e/browser_metrics.mjs` against the hub at http://localhost:8000.
Chromium 141.0.7390.37 headless, Pixel 5 profile, host: Intel(R) Xeon(R) Processor @ 2.10GHz x4 CPUs, no GPU.

**Nothing here was measured on a real phone or a real mobile network.** CPU throttling (CDP
`Emulation.setCPUThrottlingRate`) slows this Xeon's page thread by the given factor as a rough stand-in for a
low-end Android phone; it does not model a phone's memory, thermal limits or WASM performance exactly.

## Model inference in the app page (onnxruntime-web 1.19.2, WASM, 1 thread)

| CPU throttle | first photo, cold (runtime + model load + run) | diagnose() 128 px crop, median of 10 | diagnose() 12 MP photo, median of 10 | session.run() only, median of 10 |
|---|---|---|---|---|
| x1 (none) | 653.1 ms | 19.1 ms | 15.5 ms | 12.9 ms |
| x4 | 2648.8 ms | 66.3 ms | 68.5 ms | 59.4 ms |
| x6 | 4061.6 ms | 101.8 ms | 80.5 ms | 68.7 ms |

`diagnose()` is the app's own function (app/infer.js): blur check + centre crop + resize + model. The 12 MP
case starts from an already-decoded 4000x3000 canvas, so JPEG decoding of a real camera photo is NOT included.

## First-load download time (CDP Network.emulateNetworkConditions)

| Hub setup | Network (down / up / latency) | Model file alone | Whole offline bundle (everything the SW precaches) |
|---|---|---|---|
| as built (no compression) | 3G (750 / 250 kbps / 100 ms) | 21.2 s (1.97 MB) | 169.2 s = 2.8 min (171 files, 15.70 MB on the wire, 15.65 MB decoded, no compression) |
| as built (no compression) | slow 3G (400 / 400 kbps / 400 ms) | 39.9 s (1.97 MB) | 318.3 s = 5.3 min (171 files, 15.70 MB on the wire, 15.65 MB decoded, no compression) |
| gzip for text/JS/WASM (hub after integration fix) | 3G (750 / 250 kbps / 100 ms) | 21.2 s (1.97 MB) | 81.1 s = 1.4 min (171 files, 7.43 MB on the wire, 15.65 MB decoded, 26 gzip responses) |
| gzip for text/JS/WASM (hub after integration fix) | slow 3G (400 / 400 kbps / 400 ms) | 39.9 s (1.97 MB) | 153.1 s = 2.6 min (171 files, 7.43 MB on the wire, 15.65 MB decoded, 26 gzip responses) |

The bundle is fetched by the page in the same four groups as `precache()` in app/sw.js (app shell incl. the
onnxruntime WASM, then cards/labels/config, then the model, then all audio). The real service worker install
could not be throttled: Chromium applies CDP throttling to page requests, not to service-worker fetches. The
page's own first requests (13 files: index.html, JS, CSS, icons, cards.json) come on top: 134 KB uncompressed,
33 KB with gzip (measured once with CDP, unthrottled). Once cached, nothing is downloaded again until a file
changes.
