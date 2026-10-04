"""Blur check shared by calibration (Python) and the phone app (JavaScript).

PLAN.md section 4 - the JS in app/ must do exactly the same:
  1. center-square crop of the photo
  2. resize to 128x128 (bilinear; the app uses canvas drawImage)
  3. grey = 0.299*R + 0.587*G + 0.114*B   (floats, 0-255, no rounding)
  4. 3x3 Laplacian [0,1,0; 1,-4,1; 0,1,0] on the 126x126 interior pixels
  5. population variance (mean of squared deviations from the mean, divide by N)
If the variance < labels.json "blur_threshold" -> fail-safe DUDA, the model output is not trusted.
"""
import numpy as np
from PIL import Image

BLUR_SIZE = 128


def center_square(im):
    w, h = im.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    return im.crop((left, top, left + s, top + s))


def laplacian_variance_array(rgb):
    """rgb: HxWx3 uint8/float array already 128x128."""
    a = np.asarray(rgb, dtype=np.float64)
    g = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1]
    return float(lap.var())


def laplacian_variance(im):
    """im: PIL image (any size). Returns the blur score used by the app."""
    sq = center_square(im.convert("RGB")).resize((BLUR_SIZE, BLUR_SIZE), Image.BILINEAR)
    return laplacian_variance_array(np.asarray(sq, np.uint8))


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(f"{laplacian_variance(Image.open(p)):.2f}  {p}")
