"""Test-time multi-crop for the phone app (app/infer.js must do exactly the same).

Views: the full centre square (what the app always used) + a grid of tiles cut from the same square.
  scheme "2x2": 4 tiles of 60 % of the side, at offsets 0 and 40 %.
  scheme "3x3": 9 tiles of 45 % of the side, at offsets 0, 27.5 % and 55 %.

Decision (conservative; "votes" = tiles whose top-1 is that disease with probability >= threshold):
  1. blur check on the full view fails            -> DUDA (unchanged)
  2. full view top-1 is a disease and >= threshold -> that disease (unchanged)
  3. one disease has >= k votes and no other disease has as many -> that disease
  4. full view top-1 is "sano" and >= threshold   -> sano (a tile alone never says "sano")
  5. otherwise                                    -> DUDA
So multicrop can only ADD disease answers to the single-view app: a "sano" answer is never created by a
tile, and a full-view "sano" is overridden only when >= k tiles agree on one disease.
"""
import numpy as np
from PIL import Image

SCHEMES = {"2x2": (0.60, (0.0, 0.40)), "3x3": (0.45, (0.0, 0.275, 0.55))}
NON_DISEASE = ("sano", "otro")


def tiles(scheme):
    side, offs = SCHEMES[scheme]
    return [(x, y, side) for y in offs for x in offs]


def views(square, size, scheme):
    """square: PIL RGB image (already the centre square). Returns uint8 [1 + n_tiles, size, size, 3]."""
    s = square.size[0]
    out = [np.asarray(square.resize((size, size), Image.BILINEAR), np.uint8)]
    for x, y, side in tiles(scheme):
        box = (int(round(x * s)), int(round(y * s)), int(round((x + side) * s)), int(round((y + side) * s)))
        out.append(np.asarray(square.crop(box).resize((size, size), Image.BILINEAR), np.uint8))
    return np.stack(out)


def decide_single(p_full, blur, classes, thr, blur_thr):
    """The v1 app rule. Returns (answer, reason)."""
    if blur < blur_thr:
        return "DUDA", "blurry"
    k = int(np.argmax(p_full))
    if classes[k] == "otro":
        return "DUDA", "not_coffee"
    if p_full[k] < thr:
        return "DUDA", "low_conf"
    return classes[k], None


def decide_multicrop(p_full, p_tiles, blur, classes, thr, blur_thr, k_votes=2):
    if blur < blur_thr:
        return "DUDA", "blurry"
    kf = int(np.argmax(p_full))
    full, pf = classes[kf], float(p_full[kf])
    if full not in NON_DISEASE and pf >= thr:
        return full, None
    votes = {}
    for p in p_tiles:
        kt = int(np.argmax(p))
        if classes[kt] not in NON_DISEASE and p[kt] >= thr:
            votes[classes[kt]] = votes.get(classes[kt], 0) + 1
    if votes:
        best = max(votes.values())
        winners = [d for d, n in votes.items() if n == best]
        if best >= k_votes and len(winners) == 1:
            return winners[0], "multicrop"
    if full == "sano" and pf >= thr:
        return "sano", None
    if full == "otro":
        return "DUDA", "not_coffee"
    return "DUDA", "low_conf"
