"""Draws the PWA manifest icons (icon-192.png, icon-512.png, icon-maskable-512.png) with Pillow.
Run: python app/icons/make_png_icons.py   (needs pillow; no external assets)."""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def png(size, maskable=False):
    W = size * 4  # supersample, then downscale
    if maskable:  # full-bleed background, art inside the safe zone
        im = Image.new('RGBA', (W, W), (78, 52, 46, 255))
        d = ImageDraw.Draw(im)
    else:
        im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.22), fill=(78, 52, 46, 255))
    pad = 0.18 if maskable else 0.1

    def P(x, y):
        return (W * (pad + (1 - 2 * pad) * x / 64), W * (pad + (1 - 2 * pad) * y / 64))

    def half(t):
        return 17 * math.sin(math.pi * t) ** 0.8 * (1.05 - 0.35 * t)

    ts = [i / 60 for i in range(61)]
    pts = [P(32 + half(t), 8 + 48 * t) for t in ts] + [P(32 - half(t), 8 + 48 * t) for t in reversed(ts)]
    d.polygon(pts, fill=(102, 187, 106, 255), outline=(200, 230, 201, 255))
    d.line([P(32, 12), P(32, 52)], fill=(27, 94, 32, 255), width=int(W * 0.03))
    for yy in (22, 32, 42):
        d.line([P(32, yy + 4), P(22, yy)], fill=(27, 94, 32, 255), width=int(W * 0.018))
        d.line([P(32, yy + 4), P(42, yy)], fill=(27, 94, 32, 255), width=int(W * 0.018))
    cx, cy = P(46, 48)
    r = W * (1 - 2 * pad) * 7 / 64
    d.ellipse([cx - r, cy - r * 1.25, cx + r, cy + r * 1.25], fill=(198, 40, 40, 255),
              outline=(255, 255, 255, 255), width=int(W * 0.012))
    return im.resize((size, size), Image.LANCZOS)


if __name__ == '__main__':
    png(192).save(os.path.join(HERE, 'icon-192.png'))
    png(512).save(os.path.join(HERE, 'icon-512.png'))
    png(512, True).save(os.path.join(HERE, 'icon-maskable-512.png'))
    print('wrote icon-192.png icon-512.png icon-maskable-512.png')
