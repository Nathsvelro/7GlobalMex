# Vendored onnxruntime-web 1.19.2

Copied unchanged from the npm package `onnxruntime-web@1.19.2` (`dist/`), MIT License,
Copyright (c) Microsoft Corporation, https://github.com/microsoft/onnxruntime.

| file | what |
|---|---|
| `ort.wasm.min.js` | JS API, WASM backend only (sets the global `ort`) |
| `ort-wasm-simd-threaded.mjs` | Emscripten loader, imported by the JS API at run time |
| `ort-wasm-simd-threaded.wasm` | WASM runtime (11.0 MB raw, 2.9 MB gzip) |

The app sets `ort.env.wasm.numThreads = 1` and `ort.env.wasm.wasmPaths` to this folder, so no
SharedArrayBuffer / cross-origin isolation is needed. No CDN is used at run time.
