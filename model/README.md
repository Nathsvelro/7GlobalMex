# Image model (`model/`)

Small on-device coffee leaf classifier for the phone app: MobileNetV3-Small (ImageNet weights),
fine-tuned, exported to ONNX, run in the browser by onnxruntime-web (WASM). Shipped file:
`app/model/cafetal.onnx` = **cafetal-img-v2 at confidence threshold 0.90**, **1.97 MB (1,972,422 bytes), fp16
weights** (arithmetic in float32; top-1 agrees with fp32 on 2,945 of 2,946 test images). v2 = the v1 recipe plus 147 screened
iNaturalist field photos; its threshold 0.90 was chosen on calibration data only
(`reports/field_v2_threshold_sweep.md`). The contract with the app is `app/model/labels.json` (PLAN.md section 4).
Results: `reports/model_eval.md` (shipped v2, with v1 as a reference column) and `reports/field_eval.md` (field
photos, ship rule, decision).

**Shipped by explicit team decision, as an exception to the pre-registered ship rule** (`model/ship_decision.json`).
v2 at t = 0.90 passes 4 of the 5 conditions and misses condition (2) - JMuBEN test macro-F1 may drop at most 1 point -
by 0.04 points: the app-level macro-F1 drops 1.04 points (0.9670 vs 0.9774 for v1 at 0.70; argmax macro-F1 0.9850 vs
0.9845 passes). The team shipped it anyway because the Kenyan close-ups it no longer answers (mostly phoma: correct
98.4 % -> 86.8 %) go to the fail-safe "No estoy seguro" (DUDA), not to wrong answers, and because v2 is the only
model that finds rust in field photos (v1: 0 of 53). Rule, numbers and decision: `reports/field_eval.md` ("Result",
"Threshold trade-off").

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
| `demo_samples.py` | demo images: held-out lab crops (`--data`, venv), field photos (`--field`, plain python3: downloads the CC BY-NC ones, not redistributed), README (`--readme`) |
| `inat_field.py` | iNaturalist field photos: label mapping, Mexico rule, split by observer, download, attribution CSV, contact sheets, field training views |
| `multicrop.py` | test-time multi-crop (full view + tiles) and its conservative decision rule (not shipped, see below) |
| `field_eval.py` | field evaluation of one or more models, single view vs multicrop, ship rule -> `reports/field_eval.{json,md}` |
| `field_threshold.py` | v2 threshold re-chosen on calibration data only (new Coffea sample + validation `otro`), then one test evaluation with the same ship rule -> `reports/field_v2_threshold_{sweep,test}.*` + "Threshold trade-off" in `reports/field_eval.md`; `install` copies the decided model into `app/model/` with the calibrated threshold |
| `ship_decision.json` | the human ship decision (which model, threshold, date, why; the exception to the rule). Scripts only read it when they render reports; they never decide with it |
| `check_demo_samples.mjs` | checks every demo image in the real app logic (Chromium, `app/infer.js`) -> `reports/model_demo_samples_check.json` |

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

# 4. export + quantize + calibrate (~3 min) -> app/model/cafetal.onnx, app/model/labels.json  (this is v1; the
#    shipped v2 is built and installed by steps 9-11 below)
#    --ortweb = a folder with the onnxruntime-web 1.19.2 Node build (ort.node.min.mjs + ort-wasm-*.wasm).
#    app/vendor/ will NOT do: it holds only the browser build (ort.wasm.min.js).
npm i --prefix /tmp/ortweb onnxruntime-web@1.19.2
python model/export_onnx.py --data /home/user/data_proc/cafetal --ortweb /tmp/ortweb/node_modules/onnxruntime-web/dist

# 5. evaluate (~4 min) -> reports/model_eval.md, reports/model_eval.json, reports/confusion_matrix.png
#    (v1 only; for the shipped v2 use step 11)
python model/evaluate.py --data /home/user/data_proc/cafetal

# 6. optional: demo images -> model/demo_samples/ (see model/demo_samples/README.md)
python model/demo_samples.py --data /home/user/data_proc/cafetal   # re-pick held-out lab crops (venv)
python3 model/demo_samples.py --field                               # demo machine: fetch the CC BY-NC field photos
node model/check_demo_samples.mjs                                   # every sample, real app logic (Chromium)
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
# 10. v2 threshold on calibration data (~3 min): new Coffea sample from unused observers (~400 photos, ~60 MB,
#     <inat>/photos_calib/, attribution reports/field_calib_attribution.csv), sweep, then ONE test evaluation
M="--model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json"
python model/field_threshold.py sample --inat /home/user/data_raw/inat
python model/field_threshold.py sweep --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat $M
python model/field_threshold.py test  --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat $M
# 11. ship v2 at the calibrated t (only because model/ship_decision.json, a human decision, names v2@0.9),
#     then regenerate the reports for the shipped model (~12 min; v1 = reference column)
python model/field_threshold.py install --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json
python3 scripts/bump_sw_version.py
python model/evaluate.py --data /home/user/data_proc/cafetal --inat-field /home/user/data_raw/inat \
  --fp32 model/checkpoints/v2/cafetal_fp32.onnx --calib reports/field_v2_calibration.json \
  --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json:reports/model_calibration.json
python model/field_eval.py --render       # field_eval.md from field_eval.json + threshold test + ship_decision.json
#     (python model/evaluate.py --render rewrites model_eval.md from model_eval.json; no data needed)
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
- **Thresholds are never chosen on test data.** Export time (`export_onnx.py`, validation only): the data-driven
  value (>= 95 % selective accuracy on clean and on phone-like degraded validation copies) is 0.50, floored to
  0.70 (PLAN default) because validation is the same Kenyan dataset as training - v1 shipped with 0.70. The
  **shipped v2 threshold 0.90** was then re-chosen by `field_threshold.py` on separate calibration data (400 new
  *Coffea* photos from unseen observers + validation `otro`) as the lowest t with <= 5 % Coffea disease answers and
  >= 98 % `otro` rejection, fixed before the single test evaluation. Blur threshold **4.2** = the 5th percentile of
  the hazy rust crops; it catches heavy blur on 128 px crops but will rarely fire on sharp high-resolution phone
  photos (it fired on 0 of 768 iNaturalist photos).

## What the model can and cannot do (read before the demo)

Shipped v2 at t = 0.90, all numbers measured (`reports/model_eval.md`, `reports/field_eval.md`):

- **Field photos (iNaturalist, held-out field test; a proxy for Chiapas, labels = community identification)**:
  rust correct & accepted **64.2 % [51-76]** (34 of 53; v1: 0 of 53), 81.0 % (34 of 42) when the symptom is clearly
  visible, 74.2 % (23 of 31) in the Mexico+Guatemala box, **2 of 4 inside Mexico**. Leaf miner 2 of 9, Cercospora
  **0 of 10** (2 called roya). Ojo de gallo (not a model class) goes to DUDA 91.1 % (82 of 90). No diseased field
  photo was called "sano".
- **False alarms**: disease answers on 2.5 % [1.4-4.5] (10 of 399) of *Coffea* plant photos with unknown health
  (v1: 0 %), 6.5 % of the 200 iNatAg-mini coffee photos (v1: 0 %); non-coffee test images rejected 98.2 % (438 of
  446; v1 99.8 %) - the 8 accepted test views (7 distinct photos, mostly apple rust/scab leaves answered "roya") are
  listed in `reports/model_eval.md` (a); one is the PlantDoc apple-scab leaf (roya 0.98) the journey test used, so
  the journey now uses the first PlantDoc test image v2 rejects.
- **Kenyan test split (JMuBEN, same dataset as training)**: macro-F1 0.985 (argmax); as the app decides, 93.8 % of
  coffee close-ups answered, 100.0 % of the answers right, 0 diseased leaves called "sano". The higher threshold
  sends more close-ups to DUDA than v1 (phoma 13.2 % vs 1.6 %): that is condition (2) above.
- Photograph the leaf so the lesion **fills the frame**: whole trees and branches get DUDA (the in-repo demo photo
  `demo_samples/field_whole_tree.jpg` shows this).
- `sano` was learned from **7 distinct source photos** (JMuBEN ships 18,983 copies of 14 photos) and there are no
  labelled healthy field leaves: a real healthy Chiapas leaf will most likely get DUDA, not "sano".
- Not covered: red spider mite (`acaro_rojo`), broca, nutrient deficiency, Robusta, night/flash photos, other
  phones and cameras. The fix is labelled Chiapas photos, healthy and diseased (officer confirmations in the hub's
  `labels` table), then rerun steps 9-11.
- History: v1 (Kenyan crops only, t = 0.70) answered 0 of 219 iNaturalist rust photos (99.5 % DUDA); multicrop did
  not help it; v2 at its export threshold 0.70 found more rust (71.7 %) but failed the rule on false alarms
  (8.0 % Coffea disease answers, 95.7 % `otro` rejection). Full story: `reports/field_eval.md`.

## Dataset licenses

| dataset | license | use |
|---|---|---|
| JMuBEN + JMuBEN2 (Jepkoech et al. 2021, *Data in Brief* 36:107142), via the AgML public bucket | CC BY 4.0 | train/val/test (5 coffee classes) |
| PlantDoc (Singh et al., CoDS-COMAD 2020) | CC BY 4.0 (dataset); images were collected from the web, so the copyright of individual images varies | `otro` (other crops); not redistributed |
| Imagenette (fast.ai) | repo Apache-2.0; images are an ImageNet subset, ImageNet terms (non-commercial research) apply | `otro` (non-plant) |
| iNatAg-mini `coffea_arabica` (iNaturalist via AgML) | CC BY-NC 4.0 (per AgML) | evaluation only, not trained on, not shipped |
| iNaturalist field photos (768: rust, leaf miner, Cercospora, ojo de gallo, *Coffea arabica*), per-photo attribution in `reports/field_inat_attribution.csv` | CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA, CC BY-NC-ND, per photo | field evaluation; 147 screened field-train photos trained v2 (the shipped model); images not redistributed, except one CC BY field-test photo in `demo_samples/` (attributed there) |
| iNaturalist *Coffea arabica* calibration photos (400, observers not in any other set), per-photo attribution in `reports/field_calib_attribution.csv` | CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA, CC BY-NC-ND, per photo | choosing v2's threshold only (not trained on); images not redistributed |

The shipped `cafetal.onnx` contains weights learned from these datasets (and ImageNet-pretrained
MobileNetV3 weights, Apache-2.0 Keras applications). No dataset images are shipped in the app;
`model/demo_samples/` holds 11 JMuBEN files (10 held-out test crops + 1 blurred copy, CC BY 4.0) and 1 CC BY
iNaturalist field photo, attributed in its README; 2 CC BY-NC field photos are downloaded on the demo machine by
`python3 model/demo_samples.py --field` and are not redistributed (`model/demo_samples/field/` is gitignored).
