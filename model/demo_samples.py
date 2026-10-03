"""Demo images for the app: held-out lab crops (in the repo) and held-out iNaturalist field photos.

  python3 model/demo_samples.py --field     # plain python3, standard library only (no venv):
                                            # downloads the 2 CC BY-NC field rust photos into model/demo_samples/field/
                                            # (gitignored: not redistributed), checks size + sha256 of every field photo,
                                            # prints the attribution to show with them
  python3 model/demo_samples.py --readme    # rewrite model/demo_samples/README.md from samples.json
  python model/demo_samples.py --data /home/user/data_proc/cafetal   # (venv) re-pick the lab crops

Everything is listed in model/demo_samples/samples.json (file, expected app answer, source, licence, attribution;
field photos also sha256 + size). `node model/check_demo_samples.mjs` checks every sample in the real app logic.

Lab crops: per coffee class, 2 test photos from different near-duplicate groups that the shipped model answers
correctly with top-1 >= max(0.9, threshold), plus a blurred copy (fail-safe DUDA). Kenyan JMuBEN crops (CC BY 4.0),
not Chiapas photos. No 'otro' samples: PlantDoc and Imagenette images are web-scraped and their copyright varies -
for "not coffee" photograph any object or another plant.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "model", "demo_samples")
MANIFEST = os.path.join(OUT, "samples.json")


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def save_manifest(m):
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------- field photos (standard library only)
def fetch_field(force=False):
    ok = True
    for s in load_manifest()["samples"]:
        if s["kind"] != "field photo":
            continue
        dst = os.path.join(OUT, s["file"])
        if not s["in_repo"] and (force or not os.path.exists(dst) or sha256(dst) != s["sha256"]):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                with urllib.request.urlopen(s["download_url"], timeout=60) as resp:
                    data = resp.read()
            except OSError as e:
                print(f"FAIL {s['file']}: download failed ({e}). Needs internet once; then it works offline.")
                ok = False
                continue
            with open(dst + ".part", "wb") as fh:
                fh.write(data)
            os.replace(dst + ".part", dst)
        if not os.path.exists(dst):
            print(f"FAIL {s['file']}: missing")
            ok = False
            continue
        size, digest = os.path.getsize(dst), sha256(dst)
        good = size == s["size_bytes"] and digest == s["sha256"]
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {os.path.relpath(dst, REPO)}  ({size} bytes, sha256 {digest[:12]}"
              f"{'' if good else ', expected ' + s['sha256'][:12]})  app should say: {s['expected_app']}")
        print(f"     {s['attribution']} - {s['photo_url']}")
    if ok:
        print("Field photos ready. Show the attribution line with each photo. The CC BY-NC photos are for "
              "non-commercial use and must not be committed (model/demo_samples/field/ is gitignored).")
    return ok


# ---------------------------------------------------------------- README (standard library only)
def write_readme():
    m = load_manifest()
    lab = [s for s in m["samples"] if s["kind"] != "field photo"]
    field = [s for s in m["samples"] if s["kind"] == "field photo"]
    L = ["# Demo sample images", "",
         "Upload them in the app to show each result. Everything here is **held out**: never used to train the "
         "shipped model (`app/model/labels.json`). Generated from `samples.json` by `model/demo_samples.py --readme`; "
         "every answer below is checked in the real app logic (Chromium, `app/infer.js`: blur check, threshold, "
         "`otro` -> DUDA) by `node model/check_demo_samples.mjs` (result: `reports/model_demo_samples_check.json`).", "",
         "## Lab crops (in the repo)", "",
         "Kenyan JMuBEN close-up crops (about 128x128 px) from the model's held-out TEST split, like the training "
         "data - **not** Chiapas field photos. For 'not coffee' (expected: DUDA) photograph any object or another "
         "plant.", "",
         "| file | true label | what the app should say | source (dataset path) | licence |", "|---|---|---|---|---|"]
    for s in lab:
        L.append(f"| {s['file']} | {s['true']} | {s['expected_app']} | {s['source']} | {s['license']} |")
    L += ["", "Attribution: JMuBEN/JMuBEN2, Jepkoech et al. 2021, *Data in Brief* 36:107142 (CC BY 4.0). "
          "`blurred_roya.jpg` is a Gaussian-blurred copy (radius 4) of `roya_1.jpg`.", "",
          "## Field photos (iNaturalist, held-out field test)", "",
          "Real photos from the held-out field test (`reports/field_inat_attribution.csv`, split `field_test`: "
          "the observers were never used for training). Labels are the iNaturalist community identification, not an "
          "agronomist's diagnosis. Only CC BY photos may be kept in this repository; the CC BY-NC ones are "
          "downloaded on the demo machine with:", "",
          "```bash", "python3 model/demo_samples.py --field   # plain python3, no venv; needs internet once", "```", "",
          "| file | in repo? | true label | what the app should say | licence | attribution | link | why this photo |",
          "|---|---|---|---|---|---|---|---|"]
    for s in field:
        L.append(f"| {s['file']} | {'yes' if s['in_repo'] else 'no - downloaded by `--field` (gitignored)'} | "
                 f"{s['true']} | {s['expected_app']} | {s['license']} | {s['attribution']} | {s['photo_url']} | "
                 f"{s['why_chosen']} |")
    L += ["", "Location (rounded to 0.1 degree), date and quality grade of each field photo are in `samples.json`. "
          "The two rust photos were picked because the app answers them correctly: they show what it can do on a "
          "clear field photo, they are not a measure of accuracy (that is `reports/field_eval.md`).", ""]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("wrote", os.path.relpath(os.path.join(OUT, "README.md"), REPO))


# ---------------------------------------------------------------- lab crops (needs the training venv)
def pick_lab(data):
    import numpy as np
    import onnxruntime as ort
    from PIL import Image, ImageFilter
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from blur import laplacian_variance

    labels = json.load(open(os.path.join(REPO, "app", "model", "labels.json")))
    classes = labels["classes"]
    min_p = max(0.9, labels["threshold"])
    sess = ort.InferenceSession(os.path.join(REPO, "app", "model", "cafetal.onnx"), providers=["CPUExecutionProvider"])
    te = np.load(os.path.join(data, "test.npz"))
    probs = np.concatenate([sess.run(None, {labels["input"]["name"]: te["x"][i:i + 64].astype(np.float32)})[0]
                            for i in range(0, len(te["y"]), 64)])
    lic, att = "CC BY 4.0", "JMuBEN/JMuBEN2, Jepkoech et al. 2021, Data in Brief 36:107142"
    rows = []
    for k, c in enumerate(classes):
        if c == "otro":
            continue
        used = set()
        for i in np.argsort(-probs[:, k]):
            if len(used) >= 2:
                break
            if te["y"][i] != k or te["view"][i] != "full" or te["group"][i] in used or probs[i, k] < min_p:
                continue
            im = Image.open(str(te["path"][i])).convert("RGB")
            if laplacian_variance(im) < labels["blur_threshold"] * 3:
                continue  # keep clearly sharp examples
            used.add(te["group"][i])
            name = f"{c}_{len(used)}.jpg"
            im.save(os.path.join(OUT, name), quality=92)
            src = "JMuBEN " + os.path.relpath(str(te["path"][i]), "/home/user/data_raw/arabica")
            rows.append({"file": name, "kind": "lab crop", "true": c, "expected_app": c, "in_repo": True,
                         "source": src, "split": "test", "license": lic, "attribution": att})
            if c == "roya" and len(used) == 1:  # blurred copy -> blur check / fail-safe
                im.filter(ImageFilter.GaussianBlur(4)).save(os.path.join(OUT, "blurred_roya.jpg"), quality=92)
                rows.append({"file": "blurred_roya.jpg", "kind": "lab crop, blurred",
                             "true": "roya (Gaussian blur radius 4 of roya_1.jpg)", "expected_app": "DUDA",
                             "expected_reason": "blurry", "in_repo": True, "source": src, "split": "test",
                             "license": lic, "attribution": att})
    m = load_manifest()
    m["samples"] = rows + [s for s in m["samples"] if s["kind"] == "field photo"]
    save_manifest(m)
    print(json.dumps(rows, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--field", action="store_true", help="download + verify the field photos (standard library only)")
    ap.add_argument("--force", action="store_true", help="with --field: download again even if the file is fine")
    ap.add_argument("--readme", action="store_true", help="rewrite README.md from samples.json")
    ap.add_argument("--data", help="prepared data folder: re-pick the lab crops with the shipped model (venv)")
    args = ap.parse_args()
    if not (args.field or args.readme or args.data):
        ap.error("choose --field, --readme or --data DIR")
    if args.data:
        pick_lab(args.data)
        write_readme()
    if args.readme:
        write_readme()
    if args.field and not fetch_field(args.force):
        sys.exit(1)


if __name__ == "__main__":
    main()
