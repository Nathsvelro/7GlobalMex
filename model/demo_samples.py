"""Copy a few held-out TEST images into model/demo_samples/ for the demo (upload them in the app).

  python model/demo_samples.py --data /home/user/data_proc/cafetal

Per coffee class: 2 test photos from different near-duplicate groups that the shipped model answers
correctly with top-1 >= 0.9, plus a blurred copy, which must give the fail-safe DUDA. These are
Kenyan JMuBEN crops (CC BY 4.0), not Chiapas photos. No 'otro' samples are copied: PlantDoc and
Imagenette images are web-scraped and their copyright varies - for "not coffee" just photograph
any object or another plant.
"""
import argparse
import json
import os
import sys

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import laplacian_variance  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "model", "demo_samples"))
    args = ap.parse_args()
    labels = json.load(open(os.path.join(REPO, "app", "model", "labels.json")))
    classes = labels["classes"]
    sess = ort.InferenceSession(os.path.join(REPO, "app", "model", "cafetal.onnx"), providers=["CPUExecutionProvider"])
    te = np.load(os.path.join(args.data, "test.npz"))
    probs = np.concatenate([sess.run(None, {labels["input"]["name"]: te["x"][i:i + 64].astype(np.float32)})[0]
                            for i in range(0, len(te["y"]), 64)])
    os.makedirs(args.out, exist_ok=True)
    rows = []
    for k, c in enumerate(classes):
        if c == "otro":
            continue
        n_want = 2
        used = set()
        order = np.argsort(-probs[:, k])
        for i in order:
            if len(used) >= n_want:
                break
            if te["y"][i] != k or te["view"][i] != "full" or te["group"][i] in used or probs[i, k] < 0.9:
                continue
            im = Image.open(str(te["path"][i])).convert("RGB")
            if laplacian_variance(im) < labels["blur_threshold"] * 3:
                continue  # keep clearly sharp examples
            used.add(te["group"][i])
            name = f"{c}_{len(used)}.jpg"
            im.save(os.path.join(args.out, name), quality=92)
            rows.append({"file": name, "true": c, "expected_app": c,
                         "source": os.path.relpath(str(te["path"][i]), "/home/user/data_raw"),
                         "top1": round(float(probs[i].max()), 3)})
            if c == "roya" and len(used) == 1:  # blurred copy -> blur check / fail-safe
                im.filter(ImageFilter.GaussianBlur(4)).save(os.path.join(args.out, "blurred_roya.jpg"), quality=92)
                rows.append({"file": "blurred_roya.jpg", "true": "roya (blurred r=4)", "expected_app": "DUDA",
                             "source": rows[-1]["source"], "top1": None})
    with open(os.path.join(args.out, "README.md"), "w") as fh:
        fh.write("# Demo sample images\n\nHeld-out TEST images (never trained on), written by "
                 "`model/demo_samples.py`. Upload them in the app to show each result. They are Kenyan "
                 "close-up crops (128x128) like the training data - **not** Chiapas field photos. For 'not "
                 "coffee' (expected: DUDA) photograph any object or another plant.\n\n"
                 "| file | true label | what the app should say | source (dataset path) |\n|---|---|---|---|\n")
        for r in rows:
            fh.write(f"| {r['file']} | {r['true']} | {r['expected_app']} | {r['source']} |\n")
        fh.write("\nAttribution: coffee images from JMuBEN/JMuBEN2, Jepkoech et al. 2021, *Data in Brief* 36:107142 "
                 "(CC BY 4.0). `blurred_roya.jpg` is a "
                 "Gaussian-blurred copy (radius 4) of `roya_1.jpg`.\n")
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
