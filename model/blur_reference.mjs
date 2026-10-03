// Reference JavaScript for the blur check (PLAN.md section 4). Must match model/blur.py.
// In the app: draw the center-square crop of the photo onto a 128x128 canvas, then
//   const d = ctx.getImageData(0, 0, 128, 128).data;   // RGBA
//   if (laplacianVariance(d, 128, 128) < labels.blur_threshold) -> fail-safe DUDA
// Parity with Python is checked by: node model/blur_reference.mjs <file.rgba> (raw RGBA 128x128).
export function laplacianVariance(rgba, w, h) {
  const g = new Float64Array(w * h);
  for (let i = 0; i < w * h; i++) {
    g[i] = 0.299 * rgba[4 * i] + 0.587 * rgba[4 * i + 1] + 0.114 * rgba[4 * i + 2];
  }
  let sum = 0, sum2 = 0, n = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const v = g[i - w] + g[i + w] + g[i - 1] + g[i + 1] - 4 * g[i];
      sum += v; sum2 += v * v; n++;
    }
  }
  const mean = sum / n;
  return sum2 / n - mean * mean; // population variance
}

if (process.argv[1] && process.argv[1].endsWith('blur_reference.mjs') && process.argv[2]) {
  const fs = await import('node:fs');
  for (const f of process.argv.slice(2)) {
    const b = fs.readFileSync(f);
    console.log(laplacianVariance(b, 128, 128).toFixed(4), f);
  }
}
