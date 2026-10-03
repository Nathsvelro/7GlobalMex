# Image model (`model/`)

Small on-device coffee leaf classifier for the phone app: MobileNetV3-Small (ImageNet weights),
fine-tuned, exported to ONNX, run in the browser by onnxruntime-web (WASM). Shipped file:
`app/model/cafetal.onnx`, **1.97 MB, fp16 weights** (arithmetic in float32; predictions identical
to fp32 on validation and test). The contract with the app is `app/model/labels.json` (PLAN.md
section 4). Results: `reports/model_eval.md`.

**Why not INT8?** Static INT8 post-training quantization (onnxruntime QDQ, per-channel) collapses
this model to a constant answer (validation accuracy 15 %; tried per-tensor, percentile
calibration, float bias, Conv-only - same result; signal-to-noise turns negative in the middle
blocks). INT8 *weights only* works but loses 3.2 points of validation macro-F1. fp16 weights are
lossless and halve the download. Quantization-aware training would be the next step.

| file | what |
|---|---|
| `prepare_data.py` | scan datasets, map labels, group near-duplicates, split 70/15/15 by group, cache arrays |
| `train.py` | two-stage fine-tuning (frozen backbone, then top blocks), resumable, checkpoint per epoch |
| `export_onnx.py` | Keras -> ONNX -> compressed candidates (INT8 static, INT8 weights, fp16 weights), onnxruntime-web check, threshold + blur calibration, writes `app/model/` |
| `evaluate.py` | test split, robustness, field photos, size/latency -> `reports/model_eval.{json,md}`, `reports/confusion_matrix.png` |
| `blur.py` | the blur check (the app's JavaScript must do exactly the same) |
| `check_ortweb.mjs` | runs an ONNX model in onnxruntime-web (Node, WASM, 1 thread) |
| `blur_reference.mjs` | the same blur check in JavaScript, for the app (parity with `blur.py` checked) |
| `demo_samples.py` | copies a few held-out test images into `demo_samples/` to upload during the demo |
| `inat_field.py` | iNaturalist field photos: label mapping, Mexico rule, split by observer, download, attribution CSV, contact sheets, field training views |
| `multicrop.py` | test-time multi-crop (full view + tiles) and its conservative decision rule (not shipped, see below) |
| `field_eval.py` | field evaluation of one or more models, single view vs multicrop, ship rule -> `reports/field_eval.{json,md}` |

## Reproduce (CPU only, ~30 minutes on 4 cores)

```bash
python3.11 -m venv /home/user/venv-train && source /home/user/venv-train/bin/activate
pip install -r requirements-train.txt

# 1. data (public, no login)
mkdir -p /home/user/data_raw && cd /home/user/data_raw
curl -LO https://agdata-data.s3.us-west-1.amazonaws.com/datasets/arabica_coffee_leaf_disease_classification.zip
curl -LO https://agdata-data.s3.us-west-1.amazonaws.com/datasets/plant_doc_classification.zip
curl -LO https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-160.tgz
curl -L -o coffea_arabica_mini.zip https://agdata-data.s3.us-west-1.amazonaws.com/datasets/iNatAg-mini/coffea_arabica.zip
mkdir -p arabica plantdoc imagenette inatag/mini
unzip -q arabica_coffee_leaf_disease_classification.zip -d arabica
unzip -q plant_doc_classification.zip -d plantdoc
tar xzf imagenette2-160.tgz -C imagenette
unzip -q coffea_arabica_mini.zip -d inatag/mini
cd /home/user/7GlobalMex

# 2. prepare (~5 min): hashing, group split, cached 224x224 arrays in /home/user/data_proc/cafetal
python model/prepare_data.py \
  --jmuben /home/user/data_raw/arabica/arabica_coffee_leaf_disease_classification \
  --plantdoc /home/user/data_raw/plantdoc/plant_doc_classification \
  --negatives /home/user/data_raw/imagenette/imagenette2-160 \
  --inat /home/user/data_raw/inatag/mini/coffea_arabica \
  --out /home/user/data_proc/cafetal

# 3. train (~15 min: 4 frozen epochs x 46 s + 8 fine-tuning epochs x 75 s). Resumable: rerun the same command after an interruption.
#    Add --max-minutes 9 to stop cleanly before a 10-minute shell limit, then rerun.
python model/train.py --data /home/user/data_proc/cafetal --out model/checkpoints

# 4. export + quantize + calibrate (~3 min) -> app/model/cafetal.onnx, app/model/labels.json
#    --ortweb = a folder with the onnxruntime-web 1.19.2 Node build (ort.node.min.mjs + ort-wasm-*.wasm).
#    app/vendor/ will NOT do: it holds only the browser build (ort.wasm.min.js).
npm i --prefix /tmp/ortweb onnxruntime-web@1.19.2
python model/export_onnx.py --data /home/user/data_proc/cafetal --ortweb /tmp/ortweb/node_modules/onnxruntime-web/dist

# 5. evaluate (~4 min) -> reports/model_eval.md, reports/model_eval.json, reports/confusion_matrix.png
python model/evaluate.py --data /home/user/data_proc/cafetal

# 6. optional: demo images (held-out test crops) -> model/demo_samples/
python model/demo_samples.py --data /home/user/data_proc/cafetal
```

### Field evaluation on iNaturalist photos (~5 minutes; v2 experiment ~20 minutes more)

Needs the iNaturalist metadata tables `obs_coffee.tsv` + `photos_coffee.tsv` (iNaturalist open data, filtered to
the six taxa listed in `inat_field.py`) in `/home/user/data_raw/inat/`. Images come from the public
`inaturalist-open-data` S3 bucket and stay outside the repository (many are CC BY-NC or ND).

```bash
# 7. manifest + split by observer + download (~770 photos, ~100 MB) -> reports/field_inat_attribution.csv
python model/inat_field.py --inat /home/user/data_raw/inat [--sheets /tmp/sheets]   # contact sheets for screening
#    (screening by eye is in reports/field_inat_screening.csv)
# 8. field table for the shipped model (section (g) of reports/model_eval.md)
python model/evaluate.py --data /home/user/data_proc/cafetal --inat-field /home/user/data_raw/inat
# 9. v2 experiment: field training views, train, export WITHOUT touching app/model/, compare
python model/inat_field.py --inat /home/user/data_raw/inat --no-download \
  --train-npz /home/user/data_proc/cafetal/field_train.npz
python model/train.py --data /home/user/data_proc/cafetal --out model/checkpoints/v2 \
  --extra /home/user/data_proc/cafetal/field_train.npz --extra-repeat 2 --log model/checkpoints/v2/training_log.csv
python model/export_onnx.py --data /home/user/data_proc/cafetal --ckpt model/checkpoints/v2/best.keras \
  --workdir model/checkpoints/v2 --app-dir model/checkpoints/v2/app --calib-out model/checkpoints/v2/model_calibration.json \
  --version cafetal-img-v2 --force fp16_weights --ortweb <onnxruntime-web dist dir>
mkdir -p model/checkpoints/v1 && cp app/model/cafetal.onnx app/model/labels.json model/checkpoints/v1/
python model/field_eval.py --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
  --model v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json \
  --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json
```

Seeds are fixed (`--seed 42`); TensorFlow on CPU with a parallel input pipeline is not bit-exact,
so numbers can move by a few tenths of a point between runs.

Optional, **untested** (the datasets are on Mendeley Data, which the build machine cannot reach):
`--bracol DIR` (BRACOL, doi:10.17632/yy2k5y8mxg.1) and `--rocole DIR` (RoCoLe,
doi:10.17632/c5yvn32dzg.2). Labels are mapped from CSV columns (`predominant_stress`,
`Multiclass.Label`) or folder names: healthy -> sano, rust / rust_level_1..4 -> roya, miner ->
minador, phoma / brown leaf spot -> phoma, cercospora -> cercospora, red spider mite -> acaro_rojo
(this adds a 7th class; the app reads the class list from labels.json).

## Key design choices

- **Split by near-duplicate group, not by image.** JMuBEN repeats each source photo many times
  (flipped, rotated, colour-shifted copies; burst shots). We hash a canonical form (grayscale +
  histogram equalisation, 9x9, 72-bit dHash, minimum over the 8 flips/rotations), link pairs with
  Hamming distance <= 8 and split by connected component. Result: 58,549 JMuBEN images are only
  ~880 groups; `sano` (18,983 images) is **11 groups** (14 exact source photos).
  `reports/model_eval.md` section (f) shows how much a random split would have inflated the score.
- **Round-robin subsampling**: up to 1,500 training images per coffee class (one per group per round),
  class-weighted loss.
- **Strong photometric augmentation on every class** (brightness, contrast, saturation, hue, haze,
  auto-contrast, blur, down/up-scaling, JPEG, noise, crops, flips, 90-degree rotations), because rust
  crops are often hazy and the model could otherwise learn "haze = rust".
- **"otro"** = PlantDoc leaves of 27 other crops (whole photo + a close-up crop, so "otro" is not just
  "a whole leaf in the frame") + 700 Imagenette photos.
- **Preprocessing is inside the model** (Keras `include_preprocessing=True`): the app feeds raw RGB
  0-255 floats, NHWC.
- **Thresholds are calibrated on validation only**, test is touched once by `evaluate.py`.
  Confidence threshold: the data-driven value (>= 95 % selective accuracy on clean and on
  phone-like degraded validation copies) is 0.50; we ship **0.70** (policy floor, PLAN default)
  because validation is the same Kenyan dataset as training. Blur threshold **4.2** = the 5th
  percentile of the hazy rust crops; it catches heavy blur on 128 px crops but will rarely fire on
  sharp high-resolution phone photos.

## What the model can and cannot do (read before the demo)

- It has only seen **128x128 close-up crops from Kenya**. On 200 real iNaturalist photos of coffee
  plants (whole plants, flowers, cherries) it answers **DUDA for 100 %**, and still ~90 % DUDA when
  zoomed to the centre 12 %. Expect "No estoy seguro" for most real photos: safe, not yet useful.
  Photograph the lesion so it **fills the frame**.
- **Field test (iNaturalist, labelled by taxon; `reports/field_eval.md`)**: of 219 photos of coffee leaf
  rust it answers **0** correctly (99.5 % DUDA, nearly all "not a coffee leaf"), also 0 of the 164 where
  the symptom is clearly visible; 0 of 30 leaf-miner and 0 of 30 Cercospora photos. It never called a
  diseased photo "sano". iNaturalist photos are a proxy (other countries, cameras, framing), not Chiapas.
- **Multicrop** (full view + 4 tiles, `multicrop.py`) finds no rust either, so it is not in the app.
- **v2 experiment** (same recipe + 147 screened iNaturalist field photos, split by observer): roya correct
  71.7 % [58-82] on the held-out field test (n=53) instead of 0 %, Kenyan test macro-F1 unchanged, but more
  false alarms: disease answers on 8.0 % of Coffea plant photos (cherries, flowers, healthy leaves; v1 0 %)
  and 95.7 % rejection of non-coffee test images (v1 99.8 %). It fails the pre-agreed ship rule, so it is
  **not shipped**; the missing piece is labelled healthy field leaves (officer confirmations from Chiapas).
- `sano` was learned from **7 distinct source photos** (JMuBEN ships 18,983 copies of 14 photos).
  A real healthy Chiapas leaf will most likely get DUDA, not "sano".
- Not covered: red spider mite (`acaro_rojo`), broca, nutrient deficiency, Robusta, night/flash
  photos, other phones and cameras.

## Dataset licenses

| dataset | license | use |
|---|---|---|
| JMuBEN + JMuBEN2 (Jepkoech et al. 2021, *Data in Brief* 36:107142), via the AgML public bucket | CC BY 4.0 | train/val/test (5 coffee classes) |
| PlantDoc (Singh et al., CoDS-COMAD 2020) | CC BY 4.0 (dataset); images were collected from the web, so the copyright of individual images varies | `otro` (other crops); not redistributed |
| Imagenette (fast.ai) | repo Apache-2.0; images are an ImageNet subset, ImageNet terms (non-commercial research) apply | `otro` (non-plant) |
| iNatAg-mini `coffea_arabica` (iNaturalist via AgML) | CC BY-NC 4.0 (per AgML) | evaluation only, not trained on, not shipped |
| iNaturalist field photos (768: rust, leaf miner, Cercospora, ojo de gallo, *Coffea arabica*), per-photo attribution in `reports/field_inat_attribution.csv` | CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA, CC BY-NC-ND, per photo | field evaluation; 147 photos trained the experimental v2 only (not shipped); images not redistributed |

The shipped `cafetal.onnx` contains weights learned from these datasets (and ImageNet-pretrained
MobileNetV3 weights, Apache-2.0 Keras applications). No dataset images are shipped in the app;
`model/demo_samples/` holds 11 JMuBEN test crops (CC BY 4.0, attributed in its README).
