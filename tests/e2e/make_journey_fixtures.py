"""Builds the images used by tests/e2e/journey.mjs (needs pillow + numpy; e.g. /home/user/venv-train/bin/python).

  journey_roya.jpg     the FIRST leaf-rust image of the model's held-out TEST split (manifest order, not
                       hand-picked): JMuBEN Leaf_rust/1(105).jpg, CC BY 4.0, Jepkoech et al. 2021. Unchanged.
  journey_blurred.jpg  the same image, Gaussian blur radius 6, upscaled to 960x960 like a phone photo -> DUDA
  journey_object.jpg   a synthetic non-plant photo (a blue bucket on a concrete floor), drawn here -> DUDA/OTRO

PlantDoc and Imagenette test images are NOT copied into the repo (web-collected / ImageNet terms): journey.mjs
reads them from $DATA_RAW (default /home/user/data_raw) and skips those two checks when they are missing.
Run: python tests/e2e/make_journey_fixtures.py [path to the raw JMuBEN rust image]

  python tests/e2e/make_journey_fixtures.py --pick-plantdoc   (needs onnxruntime + the prepared data)
prints the PlantDoc image journey.mjs uses, by a fixed rule: the FIRST plantdoc test image in manifest order
(<data>/manifest.csv, split=test, selected=1) that the shipped model (app/model/, decided like the app: blur check,
top-1 >= threshold, otro -> DUDA) rejects. The first one, Apple Scab Leaf/Apple-Scab-image-02.jpg, is a known v2
false alarm (roya 0.98 at t = 0.90; one of the 8 of 446 otro test images v2 accepts, reports/model_eval.md (a))."""
import os
import sys

if "--pick-plantdoc" in sys.argv:
    import csv
    import json

    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(REPO, 'model'))
    from blur import center_square, laplacian_variance
    data = os.environ.get('DATA', '/home/user/data_proc/cafetal')
    labels = json.load(open(os.path.join(REPO, 'app/model/labels.json')))
    sess = ort.InferenceSession(os.path.join(REPO, 'app/model', labels['file']), providers=['CPUExecutionProvider'])
    size, classes = labels['input']['size'], labels['classes']
    for r in csv.DictReader(open(os.path.join(data, 'manifest.csv'))):
        if r['source'] != 'plantdoc' or r['split'] != 'test' or r['selected'] != '1':
            continue
        im = Image.open(r['path']).convert('RGB')
        x = np.asarray(center_square(im).resize((size, size), Image.BILINEAR), np.float32)[None]
        p = sess.run(None, {labels['input']['name']: x})[0][0]
        k = int(p.argmax())
        duda = laplacian_variance(im) < labels['blur_threshold'] or classes[k] == 'otro' or p[k] < labels['threshold']
        print(f"{'DUDA' if duda else classes[k]:10s} top {classes[k]} {p[k]:.3f}  {r['path']}")
        if duda:
            break
    sys.exit(0)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'fixtures')
RAW = os.environ.get('DATA_RAW', '/home/user/data_raw')
SRC = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(RAW, 'arabica/arabica_coffee_leaf_disease_classification/Leaf_rust/1(105).jpg')
os.makedirs(OUT, exist_ok=True)

leaf = Image.open(SRC).convert('RGB')
leaf.save(os.path.join(OUT, 'journey_roya.jpg'), quality=95)
leaf.filter(ImageFilter.GaussianBlur(6)).resize((960, 960), Image.BICUBIC) \
    .save(os.path.join(OUT, 'journey_blurred.jpg'), quality=90)

rng = np.random.default_rng(7)
w, h = 960, 720
floor = np.linspace(150, 110, h)[:, None, None] * np.ones((h, w, 3)) + rng.normal(0, 9, (h, w, 3))
img = Image.fromarray(np.clip(floor, 0, 255).astype('uint8'))
d = ImageDraw.Draw(img)
d.polygon([(330, 230), (630, 230), (590, 600), (370, 600)], fill=(30, 80, 190))   # bucket body
d.ellipse((330, 200, 630, 260), fill=(20, 60, 160), outline=(15, 40, 110), width=6)  # rim
d.ellipse((370, 580, 590, 620), fill=(25, 70, 175))
d.arc((350, 90, 610, 330), 200, 340, fill=(60, 60, 60), width=8)                      # handle
d.rectangle((0, 640, w, h), fill=(95, 90, 85))                                        # step
img = img.filter(ImageFilter.GaussianBlur(0.6))
img.save(os.path.join(OUT, 'journey_object.jpg'), quality=88)
print('wrote', [f for f in sorted(os.listdir(OUT)) if f.startswith('journey_')])
