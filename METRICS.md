# Cafetal metrics

What we measured, how, and what we have not measured yet. Every number here comes from a file in
[`reports/`](reports/) (linked in each section) or from [`docs/evidence.md`](docs/evidence.md). Datasets are
described in [`DATA_CARD.md`](DATA_CARD.md).

How to read the labels:

| label | meaning |
|---|---|
| **measured** | we ran it and counted |
| **emulated** | measured in desktop Chromium with CPU or network throttling, **not on a phone or a real network** |
| **computed** | arithmetic from measured values or from the format (the arithmetic is shown) |

## The short version

- **Size:** the image model is **1.97 MB** (fp16 weights). The limit is 10 MB.
- **Lab test (Kenya, JMuBEN):** **98.5 %** accuracy and macro-F1 **0.985** on a test split grouped by source photo.
  The app answers 95.9 % of coffee test images. **99.9 %** of those answers are right. It never called a diseased leaf "sano".
- **Field test (iNaturalist photos, a stand-in for Chiapas):** the shipped model got **0 of 53** held-out rust photos right
  (95 % interval 0–7 %). For almost all of them it says "No estoy seguro — muestre la hoja al técnico" (DUDA).
  This is **safe but not useful**. An experimental v2, trained with field photos, finds rust (71.7 %) but raises
  false alarms. It failed our ship rule, so it is **not shipped**.
- **Our own photos:** **0**. We have not taken any yet.
- **Phone speed (emulated):** with the CPU slowed 4×, the first photo takes **2.6 s** (loading included). Each photo after that takes about **0.07 s**.
- **First download (emulated 3G, 750 kbps):** the model alone takes **21 s**. Everything the app needs offline takes **81 s** with gzip, which is how the hub serves it now.
- **SMS intents:** **91.3 %** accuracy on held-out messages. When the hub answers by itself, it is right **95.1 %** of the time.
  Anything it is unsure about goes to the extension officer.
- **SMS length:** the observation code was **46 characters** in the end-to-end test. Every SMS card fits in one 160-character GSM-7 SMS.

---

## 1. Model size

Source: [`reports/model_eval.md`](reports/model_eval.md), sections (d) and Calibration; [`model/README.md`](model/README.md).

MobileNetV3-Small, fine-tuned, exported to ONNX and run in the browser by onnxruntime-web (WASM, 1 thread).
We tried four versions of the same trained model:

| version | file size (measured) | validation accuracy | validation macro-F1 | same top-1 as fp32 | runs in onnxruntime-web | shipped? |
|---|---|---|---|---|---|---|
| INT8 static (QDQ, per-channel) | 1.38 MB | 15.1 % | 0.044 | 15.6 % | yes | no: broken |
| INT8 weights only | 1.12 MB | 96.1 % | 0.961 | 96.3 % | yes | no: loses 3.2 F1 points |
| **fp16 weights** | **1.97 MB (1,972,251 B)** | **99.3 %** | **0.993** | **100.0 %** | **yes** | **yes** |
| fp32 | 3.78 MB (3,782,909 B) | 99.3 % | 0.993 | 100.0 % | yes | no: twice the size, same answers |

**Why not INT8.** Static INT8 turns this model into a constant answer, with validation accuracy of 15 %.
[`model/README.md`](model/README.md) lists what was tried: per-tensor, percentile calibration, float bias, Conv-only.
All gave the same result. INT8 weights-only works but loses 3.2 points of validation macro-F1. fp16 weights halve the
download and change no answer: top-1 agreement with fp32 is 100 % on validation and on test. Quantization-aware training
would be the next thing to try.

The experimental **v2** model (section 4) has the same architecture and size: 1,972,422 B
([`reports/field_v2_calibration.json`](reports/field_v2_calibration.json)).

Decision settings in [`app/model/labels.json`](app/model/labels.json):
- **Confidence threshold 0.70.** The data-driven value was 0.50. We kept the 0.70 floor because the validation images
  come from the same Kenyan dataset as training, so confidence on real Chiapas photos will be less reliable.
- **Blur threshold 4.2.** This is the 5th percentile of the Laplacian variance on validation coffee images.
- If the top class is `otro`, confidence is below the threshold, or the photo fails the blur check, the app says DUDA.

## 2. Accuracy on the Kenyan held-out test (JMuBEN, group split)

Source: [`reports/model_eval.md`](reports/model_eval.md) section (a), [`reports/model_eval.json`](reports/model_eval.json),
[`reports/confusion_matrix.png`](reports/confusion_matrix.png).

The test set has 2,946 images: 500 per coffee class and 446 `otro` (PlantDoc and Imagenette). They are split **by
near-duplicate group**, so no copy of a test photo is in training (section 6). This is a lab-like test: the
images are 128×128 close-up crops from the same Kenyan dataset as training. **It is not a field test.**

| | accuracy | macro-F1 |
|---|---|---|
| fp32 | 98.5 % | 0.985 |
| shipped (fp16 weights) | 98.5 % | 0.985 |

Per class (shipped model, top class, before the threshold), measured:

| class | precision | recall | F1 | test images | distinct source groups in test |
|---|---|---|---|---|---|
| sano | 100.0 % | 100.0 % | 1.000 | 500 | **2** |
| roya | 100.0 % | 96.8 % | 0.984 | 500 | 65 |
| minador | 98.4 % | 95.6 % | 0.970 | 500 | 38 |
| phoma | 98.0 % | 98.8 % | 0.984 | 500 | 27 |
| cercospora | 100.0 % | 100.0 % | 1.000 | 500 | 12 |
| otro | 94.3 % | 99.8 % | 0.970 | 446 | 250 |

> `sano` = 100 % means little: its 500 test images come from **2** distinct photos. JMuBEN has only 14 distinct
> healthy photos (see [`DATA_CARD.md`](DATA_CARD.md)). Images inside a group are not independent, so we do not give
> confidence intervals for this test.

What the app does with these images (threshold + blur check, `otro` becomes DUDA), measured:

| true class | right answer | wrong answer accepted | DUDA (fail-safe) |
|---|---|---|---|
| sano | 100.0 % | 0.0 % | 0.0 % |
| roya | 88.4 % | 0.0 % | 11.6 % |
| minador | 92.2 % | 0.6 % | 7.2 % |
| phoma | 98.4 % | 0.0 % | 1.6 % |
| cercospora | 100.0 % | 0.0 % | 0.0 % |

- **Coverage** (coffee images the app answers): **95.9 %**.
- **Selective accuracy** (answers that are right): **99.9 %**.
- **Dangerous error** (a diseased leaf called "sano"): **0.0 %**.
- **`otro` sent to DUDA:** **99.8 %**. By source: Imagenette 100.0 % (n=54), PlantDoc close-up crops 99.5 % (n=196),
  PlantDoc full photos 100.0 % (n=196).

## 3. Robustness to phone-like damage (same test images, degraded)

Source: [`reports/model_eval.md`](reports/model_eval.md) section (b). Measured on degraded copies of the test split.
This is a rough stand-in for the field gap. Section 4 shows it is **not enough**: the real field gap is much larger.

| degradation | accuracy (top class) | macro-F1 | coffee sent to DUDA | of which by the blur check | selective accuracy | wrong and accepted | `otro` rejected |
|---|---|---|---|---|---|---|---|
| clean | 98.5 % | 0.985 | 8.2 % | 5.3 % | 99.9 % | 0.1 % | 99.8 % |
| JPEG quality 25 | 97.5 % | 0.975 | 4.4 % | 0.3 % | 99.7 % | 0.3 % | 99.8 % |
| Gaussian blur r=2 | 97.9 % | 0.979 | 26.4 % | 24.3 % | 99.7 % | 0.2 % | 99.3 % |
| Gaussian blur r=4 | 97.4 % | 0.973 | 90.9 % | 89.9 % | 97.4 % | 0.2 % | 98.0 % |
| brightness ×0.6 | 98.4 % | 0.984 | 13.7 % | 11.5 % | 99.6 % | 0.3 % | 100.0 % |
| brightness ×1.4 | 98.1 % | 0.981 | 5.1 % | 2.7 % | 99.4 % | 0.6 % | 99.8 % |
| rotate 90° | 97.6 % | 0.976 | 9.6 % | 5.3 % | 100.0 % | 0.0 % | 100.0 % |
| downscale to 64 px | 98.5 % | 0.985 | 28.5 % | 26.1 % | 100.0 % | 0.0 % | 99.1 % |

In this table the blur check runs on the 224 px cached view resized to 128 px. That is why "clean" DUDA (8.2 %)
is a little higher than in section 2.

## 4. Field test: iNaturalist photos (a stand-in for Chiapas)

Source: [`reports/field_eval.md`](reports/field_eval.md), [`reports/field_eval.json`](reports/field_eval.json),
per-photo results in [`reports/field_eval_photos.csv`](reports/field_eval_photos.csv). All measured. Intervals are
Wilson 95 % intervals, in percentage points.

**What this test is.** It uses 768 public iNaturalist photos of coffee leaf rust, leaf miner, Cercospora, ojo de gallo
(*Mycena citricolor*, not a model class, so the right answer is DUDA) and *Coffea arabica* plants (health unknown).
Labels are the iNaturalist community identification, not an agronomist's diagnosis. The photos are split **by
observer**. Every observer with a photo in a box around Mexico and Guatemala is held out, plus about 30 % of the other
observers. Every photo is decided exactly like the phone app: centre square, 224 px, blur check, threshold, `otro`
becomes DUDA. **Only 4 rust photos are from Mexico.** Data details: [`DATA_CARD.md`](DATA_CARD.md#4-inaturalist-field-photos-field-test-and-the-v2-experiment).

What the farmer sees for these photos: [DUDA screen](reports/screenshots/journey_08_not_plant.png) ("No estoy seguro").

### 4a. The shipped model (v1) on the held-out field test

| group (true label) | n | right answer and accepted [95 % CI] | DUDA [95 % CI] | called "sano" |
|---|---|---|---|---|
| roya, all | 53 | **0.0 %** [0–7] | 98.1 % [90–100] | 0 |
| roya, symptom clearly visible (screened) | 42 | **0.0 %** [0–8] | 97.6 % [88–100] | 0 |
| roya, Mexico + Guatemala box | 31 | **0.0 %** [0–11] | 96.8 % [84–99] | 0 |
| roya, inside Mexico | 4 | **0 of 4** [0–49] | 4 of 4 | 0 |
| minador | 9 | **0 of 9** [0–30] | 9 of 9 | 0 |
| cercospora | 10 | **0 of 10** [0–28] | 9 of 10 | 0 |
| ojo de gallo (right answer: DUDA) | 90 | n/a | **93.3 %** [86–97] | 0 |
| *Coffea* plants, health unknown: share given a disease answer | 399 | **0.0 %** [0–1] | 100.0 % [99–100] | 0 |
| *Coffea* plants inside Mexico: share given a disease answer | 37 | 0.0 % [0–9] | 100.0 % [91–100] | 0 |

v1 never saw any of these photos, so all 768 count as a test for it:
- **Rust:** 0 of 219 right [0–2]. 99.5 % got DUDA, in 217 cases because the model said "not a coffee leaf" (`otro`).
- **Rust with the symptom clearly visible:** 0 of 164 right.
- **Leaf miner:** 0 of 30. **Cercospora:** 0 of 30.
- **Safety:** no diseased photo was called "sano". The model only recognises close-ups that look like the 128 px Kenyan crops.

**The blur check fired on 0 of 768 photos.** These are sharp photos about 500 px wide. The blur check is meant for
shaky phone shots, which this test does not contain.

### 4b. Inside Mexico only (very small)

| group | n | v1 (shipped) | v2 (not shipped) | v2 + multicrop (not shipped) |
|---|---|---|---|---|
| roya, right and accepted | 4 | 0 of 4 [0–49] | 2 of 4 [15–85] | 3 of 4 [30–95] |
| minador, right and accepted | 2 | 0 of 2 [0–66] | 0 of 2 [0–66] | 0 of 2 [0–66] |
| cercospora | 0 | no photos | no photos | no photos |
| *Coffea* plants given a disease answer | 37 | 0.0 % [0–9] | 13.5 % [6–28] | 29.7 % [17–46] |

Four rust photos cannot tell us how the model does in Chiapas. They only show that the problem is not limited to
other countries.

### 4c. Can we do better? v2 and multicrop (experiments, not shipped)

- **v2:** the same recipe plus 147 screened field-train photos from iNaturalist, from observers who are never in the
  field test. Training ran 12 epochs, 14.8 min of epoch time on CPU ([`reports/field_v2_training_log.csv`](reports/field_v2_training_log.csv)).
- **Multicrop:** the full view plus 4 tiles (2×2), and at least 2 tiles must agree. We chose this scheme on validation data and
  field-train photos, **before** looking at the field test.

| metric (held-out field test unless noted) | v1 (shipped) | v1 + multicrop | v2 | v2 + multicrop |
|---|---|---|---|---|
| roya right and accepted (n=53) | 0.0 % [0–7] | 0.0 % [0–7] | **71.7 %** [58–82] | 79.2 % [67–88] |
| roya, symptom visible (n=42) | 0.0 % [0–8] | 0.0 % [0–8] | 88.1 % [75–95] | 97.6 % [88–100] |
| roya, Mexico + Guatemala box (n=31) | 0.0 % [0–11] | 0.0 % [0–11] | 83.9 % [67–93] | 90.3 % [75–97] |
| minador right (n=9) | 0 of 9 | 0 of 9 | 5 of 9 | 5 of 9 |
| cercospora right (n=10) | 0 of 10 | 0 of 10 | 0 of 10 (5 called roya) | 0 of 10 |
| ojo de gallo sent to DUDA (n=90, the right answer) | 93.3 % | 93.3 % | 75.6 % [66–83] | 70.0 % [60–78] |
| *Coffea* plants given a disease answer (n=399) | 0.0 % [0–1] | 0.0 % [0–1] | **8.0 %** [6–11] | 20.8 % [17–25] |
| non-coffee (`otro`) Kenyan-test images rejected (n=446) | 99.8 % | 99.3 % | **95.7 %** [93–97] | 93.5 % [91–95] |
| Kenyan test macro-F1 (top class / app-level) | 0.9845 / 0.9774 | 0.9845 / 0.9876 | 0.9850 / 0.9843 | 0.9850 / 0.9928 |
| diseased leaves called "sano" (field / Kenyan test) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

**Ship rule.** We fixed the rule before computing the v2 field results. A candidate must do all five of these, compared with v1:
1. gain ≥ 10 points on field rust;
2. lose ≤ 1 point of Kenyan macro-F1;
3. reject ≥ 98 % of `otro`;
4. call no more diseased leaves "sano";
5. raise the *Coffea* disease-answer rate by ≤ 5 points.

Results:
- **v2 and v2 + multicrop** fail (3) and (5).
- **v1 + multicrop** fails (1).
- So the app **keeps v1, single view**.

**Why v2 raises false alarms.** We looked at the 32 *Coffea* photos that v2 answers with a disease
([`reports/field_coffea_v2_alarms.csv`](reports/field_coffea_v2_alarms.csv)). 28 show no visible leaf symptom: cherries in
a hand, flowers, healthy leaves. Every field training photo is diseased, and there are no labelled healthy field
leaves, so v2 partly learned "field photo of a coffee plant = roya". The fix is labelled Chiapas photos, healthy
**and** diseased, confirmed by the extension officer. Then we rerun this protocol.

**Multicrop speed** was not built in JavaScript. *Computed* estimate: 5 inferences × 59.4 ms (`session.run` median at
4× CPU throttle, section 8) ≈ 0.3 s per photo. Not measured.

**Caveats.**
- iNaturalist photos are a proxy for Chiapas photos, not a substitute: other countries, other cameras, many severe textbook cases.
- One person screened the photos, from thumbnails.
- 8 rust-labelled training photos look like Cercospora to that person. They were kept as rust, which may add to v2 calling Cercospora "roya".
- Intervals are wide: minador n=9, cercospora n=10, Mexico n=4.

## 5. The lab-to-field gap in one table

Sources: sections 2 and 4. The metric is "right answer and accepted" as the app decides, so it is the same in both columns.

| | Kenyan test, v1 (lab-like crops) | iNaturalist field test, v1 (shipped) | iNaturalist field test, v2 (not shipped) |
|---|---|---|---|
| roya | 88.4 % (500 images, 65 source groups) | **0.0 %** [0–7] (n=53) | 71.7 % [58–82] (n=53) |
| minador | 92.2 % (500 images, 38 groups) | **0 of 9** [0–30] | 5 of 9 [27–81] |
| cercospora | 100.0 % (500 images, 12 groups) | **0 of 10** [0–28] | 0 of 10 [0–28] |
| roya sent to DUDA | 11.6 % | 98.1 % [90–100] | 28.3 % [18–42] |
| coffee plants (no visible disease expected) given a disease answer | not tested | 0.0 % [0–1] (n=399) | 8.0 % [6–11] (n=399) |
| diseased leaf called "sano" | 0.0 % | 0 | 0 |

This gap is a known pattern. A model trained on 54,306 controlled-condition leaf images scored 99.35 % on its own test
set and 31.4 % on images taken in other conditions (Mohanty, Hughes & Salathé 2016, arXiv:1604.03169; verified "F" in
[`docs/evidence.md`](docs/evidence.md) §10). Our field result is worse: the model mostly refuses to answer. That is
the safe failure, and it is why the fail-safe exists.

## 6. Leakage check: group split vs naive split

Source: [`reports/model_eval.md`](reports/model_eval.md) section (f) and "Data". Measured.

JMuBEN ships each source photo many times: flipped, rotated and colour-shifted copies, plus burst shots. We grouped near-duplicates with a
72-bit difference hash (minimum over 8 flips/rotations, Hamming distance ≤ 8) and split 70/15/15 by group.
The 58,549 JMuBEN images form about 880 groups (cercospora 78, minador 246, phoma 171, roya 373, sano 11).

| test set | images | accuracy | macro-F1 |
|---|---|---|---|
| group split (what we report) | 2,946 | 98.5 % | 0.985 |
| unused copies of **training** photos (what a random split would have tested) | 1,800 | 99.5 % | 0.995 |

A random split would have looked about 1 point better. The bigger lesson is the group count: `sano` has 18,983 images but only 11
groups, so it was learned from 7 distinct training photos.

## 7. The team's own photos (`data/field_test/`)

**0 images. Not collected yet.** The folders exist ([`data/field_test/README.md`](data/field_test/README.md)), and
`model/evaluate.py` scores whatever is there, separately from everything else (section (c) of
[`reports/model_eval.md`](reports/model_eval.md)). Until then the iNaturalist test (section 4) is our only field evidence.
Officer confirmations saved by the hub (`labels` table) are meant to fill this folder over time.

## 8. Phone response time (emulated)

Source: [`reports/browser_metrics.md`](reports/browser_metrics.md) / [`.json`](reports/browser_metrics.json),
run 2026-10-03. **Emulated:** headless Chromium 141, Pixel 5 profile, on a 4-CPU Intel Xeon 2.10 GHz build server with no GPU.
CPU throttling (CDP `Emulation.setCPUThrottlingRate`) slows the page thread as a rough stand-in for a low-end Android
phone. It does not model a phone's memory, heat or WASM speed exactly.

| CPU throttle | first photo, cold (runtime + model load + run) | each later photo: 12 MP photo, median of 10 | each later photo: 128 px crop, median of 10 | model run only, median of 10 |
|---|---|---|---|---|
| ×1 (none) | 0.65 s | 15.5 ms | 19.1 ms | 12.9 ms |
| ×4 | **2.65 s** | **68.5 ms** | 66.3 ms | 59.4 ms |
| ×6 | **4.06 s** | **80.5 ms** | 101.8 ms | 68.7 ms |

- "Each later photo" is the app's own `diagnose()` from `app/infer.js`: blur check, centre crop, resize and model.
- The 12 MP case starts from an already-decoded 4000×3000 image, so **JPEG decoding of a real camera photo is not included**.
- On the build server, outside the browser: onnxruntime Python, 1 thread, 2.83 ms; onnxruntime-web in Node, 13.7 ms.
  Measured, but not a phone ([`reports/model_eval.md`](reports/model_eval.md) section (d)).

## 9. First-load download (emulated)

Source: [`reports/browser_metrics.md`](reports/browser_metrics.md). **Emulated** with CDP `Network.emulateNetworkConditions`.
Project-defined profiles (not the DevTools presets):
- **3G:** 750 kbps down, 250 kbps up, 100 ms latency.
- **slow 3G:** 400 kbps down, 400 kbps up, 400 ms latency.

| network | model file alone (1.97 MB) | whole offline bundle, no compression (15.70 MB on the wire) | whole offline bundle, gzip (7.43 MB on the wire) |
|---|---|---|---|
| 3G | **21.2 s** | 169.2 s (2.8 min) | **81.1 s (1.4 min)** |
| slow 3G | **39.9 s** | 318.3 s (5.3 min) | **153.1 s (2.6 min)** |

- **What the hub does now.** It gzips text, JS and WASM files ([`hub/main.py`](hub/main.py), `StaticGZip`), so the gzip column is the current setup.
  The model and the audio are not gzipped.
- **What the bundle is.** 171 files, 15.65 MB decoded. The biggest parts are:
  - the onnxruntime WASM runtime: `app/vendor/ort-wasm-simd-threaded.wasm`, 11,018,731 B on disk;
  - the model: 1.97 MB;
  - 142 MP3 files: about 2.4 MB ([`content/README.md`](content/README.md)).
  The 10 MB limit is for model files. The model is 1.97 MB. The full bundle is larger, mostly because of the runtime.
- **How it was measured.** The page fetched the files in the same four groups as the service worker's `precache()`.
  The real service-worker install could not be throttled, because Chromium does not apply CDP throttling to service-worker fetches.
  The page's own first 13 requests come on top: 134 KB uncompressed, 33 KB with gzip.
- **Once cached**, nothing is downloaded again until a file changes.
- **Computed, for comparison:** 1,972,251 B × 8 / 384 kbps = 41.1 s for the model, with no protocol overhead
  ([`reports/model_eval.md`](reports/model_eval.md) section (d)).

## 10. SMS intent classifier (free-text SMS at the hub)

Source: [`reports/intent_eval.md`](reports/intent_eval.md) / [`.json`](reports/intent_eval.json). Measured.

- **Data:** 575 messages in [`data/intent/examples.csv`](data/intent/examples.csv). By intent: precio 54, reporte 82, ayuda 49,
  hablar_con_tecnico 48, otro 342. By source: team-written 259, Amazon MASSIVE (only as `otro`) 300,
  unverified AI-drafted Tseltal 16. Stratified 80/20 split: 460 train / 115 test.
- **Model:** TF-IDF on character 2–4-grams (4,457 features) + logistic regression. It runs in pure Python in the hub
  (`hub/intent.py`, model file `hub/intent_model.json`).
- **Threshold 0.45.** This is the lowest value that gives ≥ 95 % precision on auto-answered messages, using out-of-fold predictions on the
  training split. Below it, the hub replies "Le paso su mensaje al técnico" and forwards the SMS to the officer.
- **Keywords first.** The exact one-word messages PRECIO/PRECIOS, AYUDA and TECNICO skip the classifier (`hub/sms.py`).

| held-out test (n) | accuracy | macro-F1 |
|---|---|---|
| top class, no threshold (115) | 92.2 % | 0.897 |
| **with threshold, as deployed (115)** | **91.3 %** | **0.866** |
| with threshold, Spanish only (111) | 91.9 % | 0.871 |
| with threshold, without MASSIVE messages (57) | 84.2 % | 0.820 |

- **Auto-answered:** 35.6 % of test messages. **95.1 %** of those answers were right.
- **On-topic messages** (true intent is not `otro`) answered with the right card automatically: 83.0 %. The rest go to the officer.
- **Per class, with threshold:**
  - precio: precision 1.00, recall 0.82
  - reporte: 1.00 / 1.00
  - ayuda: 0.67 / 0.40 (the weakest)
  - hablar_con_tecnico: 1.00 / 1.00
  - otro: 0.89 / 0.97
- **Probes:** 15 hand-made messages that are not in the data, e.g. "cuanto pagan x kilo" → precio 0.88, "mis matas tienen polvo naranja" →
  reporte 0.60, "asdf qwerty" → otro. One was missed: "a como esta el pergamino en la cooperativa" got precio at 0.33,
  below the threshold, so it goes to the officer. That is a safe miss.
- **Tseltal:** only 16 unverified examples, too few to measure. Tseltal free text will mostly go to the officer.

## 11. SMS lengths

One SMS is 160 GSM-7 characters. A single accented letter switches the whole message to UCS-2, which allows only 70 characters,
so SMS cards are written without accents.

**Observation code** (phone → co-op):
- **Measured:** 46 characters in the end-to-end test: `CAF1 M0123 ROYA 99 20261003 16.91,-92.11 #WO6V`
  ([`reports/journey_results.json`](reports/journey_results.json)).
- **Computed** from the format in [`app/sms.js`](app/sms.js): the longest possible code is 48 characters.
  Location is rounded to 2 decimals (about 1 km).

**Replies sent in the end-to-end test** (measured, [`reports/journey_results.json`](reports/journey_results.json)):

| reply card | trigger | length | encoding | SMS segments |
|---|---|---|---|---|
| `sms_precio` | "PRECIO" and "cuanto estan pagando el kilo de cafe" | 157 | GSM-7 | 1 |
| `sms_reporte_instrucciones` | "mis matas tienen polvo naranja" | 137 | GSM-7 | 1 |
| `sms_pasar_tecnico` | "asdf qwerty" | 79 | GSM-7 | 1 |

**Every SMS card, worst-case slot values** (computed). This fills the slots with the long sample values in
`scripts/make_audio.py`, for example a 22-letter community name and price "100.50", then counts GSM-7 characters.
`python3 scripts/make_audio.py --check` reports "80 cards checked, 0 problem(s)".

| card | es | tzh |
|---|---|---|
| `sms_obs_recibida` | 117 | 109 |
| `sms_codigo_invalido` | 79 | 66 |
| `sms_no_registrado` | 80 | 79 |
| `sms_precio` | **160** | 157 |
| `sms_precio_sin_datos` | 73 | 81 |
| `sms_reporte_instrucciones` | 137 | 140 |
| `sms_ayuda` | 132 | 116 |
| `sms_pasar_tecnico` | 79 | 80 |
| `alert_roya` | 146 | 133 |

`sms_precio` in Spanish is exactly at the limit with worst-case values. Keep `sms_fuente` in `data/prices.json` short.

## 12. What we have not measured

- **A real phone.** All speed numbers are emulated in desktop Chromium. We have not measured JPEG decoding of a real camera photo,
  memory, battery or heat on a low-end Android phone.
- **A real network.** Download times are emulated. We have not tested a real 3G or 2G link, the real service-worker install
  over a slow link, or real SMS delivery: the SMS gateway is SIMULATED.
- **Real Chiapas photos.** We have 0 of our own and only 4 iNaturalist rust photos from Mexico. There are no
  agronomist-confirmed labels and no labelled healthy field leaves. We do not know how often the model says DUDA on a
  real healthy Chiapas leaf. The training data suggests it will be most of the time.
- **Real Tseltal listeners.** No native speaker has read the Tseltal text, and no one has tested whether the provisional
  audio is understood. That audio is a Spanish voice reading Tseltal.
- **Real member SMS.** The intent test set was written by the same people who wrote the training set.
- **Multicrop in the app.** It was not built, so its speed is only an estimate (section 4c).
- **Outbreak rule and worklist weights** (≥ 3 members, 5 km, 7 days). These are design choices, not tested against real outbreaks.
- **Prices.** All values are DEMO. None was checked on the official source page (see [`DATA_CARD.md`](DATA_CARD.md#9-reference-prices-datapricesjson-demo)).

## 13. How to reproduce

From the repo root (`/home/user/7GlobalMex`). The training venv is `/home/user/venv-train`. The hub venv `.venv` is
created by `./run.sh`.

```bash
# Hub tests (61 passed, 1 skipped on 2026-10-03)
.venv/bin/python -m pytest tests -q

# SMS card check: ids, slots, GSM-7, <= 160 characters after filling slots
python3 scripts/make_audio.py --check

# Image model: data, training, export and evaluation. Full steps with download URLs in model/README.md
source /home/user/venv-train/bin/activate
python model/prepare_data.py --jmuben /home/user/data_raw/arabica/arabica_coffee_leaf_disease_classification \
  --plantdoc /home/user/data_raw/plantdoc/plant_doc_classification \
  --negatives /home/user/data_raw/imagenette/imagenette2-160 \
  --inat /home/user/data_raw/inatag/mini/coffea_arabica --out /home/user/data_proc/cafetal
python model/train.py --data /home/user/data_proc/cafetal --out model/checkpoints          # resumable; --max-minutes 9
python model/export_onnx.py --data /home/user/data_proc/cafetal --ortweb app/vendor       # -> app/model/
python model/evaluate.py --data /home/user/data_proc/cafetal --inat-field /home/user/data_raw/inat
#   -> reports/model_eval.md|json, reports/confusion_matrix.png

# Field test (iNaturalist) and the v2 experiment: exact commands in model/README.md, "Field evaluation"
python model/field_eval.py --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
  --model v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json \
  --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json
#   -> reports/field_eval.md|json, reports/field_eval_photos.csv

# Intent classifier -> hub/intent_model.json, reports/intent_eval.md|json
/home/user/venv-train/bin/python -m hub.train_intent

# Browser checks (need Node 22 + Playwright; Chromium at /opt/pw-browsers; never run "playwright install")
node tests/e2e/app_offline.mjs                     # offline phone flow; starts its own throw-away hub
./run.sh &                                         # hub on :8000 (seeds DEMO data if hub/cafetal.db is missing)
node tests/e2e/journey.mjs                         # whole journey -> reports/journey_results.json + screenshots
node tests/e2e/browser_metrics.mjs inference       # speed under CPU throttling
LABEL="gzip for text/JS/WASM (hub after integration fix)" node tests/e2e/browser_metrics.mjs network   # ~10 min
#   -> reports/browser_metrics.md|json
# afterwards: stop the hub and delete the DB so the next run seeds fresh DEMO dates
rm -f hub/cafetal.db*
```

TensorFlow on CPU is not bit-exact with a parallel input pipeline, so model numbers can move by a few tenths of a point between runs.
The seed is 42. The iNaturalist images are not in the repo. `model/inat_field.py` downloads them again from the public
`inaturalist-open-data` S3 bucket, using [`reports/field_inat_attribution.csv`](reports/field_inat_attribution.csv).
