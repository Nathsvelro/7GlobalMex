// Check that an ONNX model loads and runs in onnxruntime-web (WASM backend, 1 thread) under Node.
// Usage: node model/check_ortweb.mjs <model.onnx> <onnxruntime-web dist dir> [input.f32 SIZE] [runs]
// input.f32 = raw little-endian float32 NHWC [1,SIZE,SIZE,3]; without it a constant grey image is used.
// Prints one JSON line: {ok, backend, input, output, probs, ms_first, ms_median, runs}
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [modelPath, distDir, inputPath, sizeArg, runsArg] = process.argv.slice(2);
const size = Number(sizeArg || 224);
const runs = Number(runsArg || 20);
const entry = ['ort.node.min.mjs', 'ort.wasm.min.mjs', 'ort.min.mjs']
  .map((f) => path.join(distDir, f)).find((f) => fs.existsSync(f));
if (!entry) {
  console.log(JSON.stringify({ ok: false, error: `no ort.node.min.mjs / ort.wasm.min.mjs / ort.min.mjs in ${distDir}` +
    ' (app/vendor holds only the browser build: use node_modules/onnxruntime-web/dist)' }));
  process.exit(1);
}
const ort = await import(pathToFileURL(entry).href);
ort.env.wasm.numThreads = 1;
ort.env.wasm.wasmPaths = pathToFileURL(distDir + path.sep).href;

try {
  const session = await ort.InferenceSession.create(fs.readFileSync(modelPath), { executionProviders: ['wasm'] });
  const inName = session.inputNames[0];
  const outName = session.outputNames[0];
  let data;
  if (inputPath) {
    const buf = fs.readFileSync(inputPath);
    data = new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
  } else {
    data = new Float32Array(size * size * 3).fill(128);
  }
  const feeds = { [inName]: new ort.Tensor('float32', data, [1, size, size, 3]) };
  let t = performance.now();
  let out = await session.run(feeds);
  const msFirst = performance.now() - t;
  const times = [];
  for (let i = 0; i < runs; i++) {
    t = performance.now();
    out = await session.run(feeds);
    times.push(performance.now() - t);
  }
  times.sort((a, b) => a - b);
  console.log(JSON.stringify({
    ok: true, backend: 'wasm', entry: path.basename(entry), input: inName, output: outName,
    probs: Array.from(out[outName].data), ms_first: msFirst, ms_median: times[Math.floor(times.length / 2)], runs,
  }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: String(e && e.message ? e.message : e) }));
  process.exit(1);
}
