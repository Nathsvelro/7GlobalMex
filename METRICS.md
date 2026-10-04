# Cafetal metrics

What we measured, how, and what we have not measured yet. Every number here comes from a file in
[`reports/`](reports/) (linked in each section), from [`docs/evidence.md`](docs/evidence.md) (with its verification
code), or from the data and code files named in each section. Datasets are described in [`DATA_CARD.md`](DATA_CARD.md).

How to read the labels:

| label | meaning |
|---|---|
| **measured** | we ran it and counted |
| **emulated** | measured in desktop Chromium with CPU or network throttling, **not on a phone or a real network** |
| **computed** | arithmetic from measured values or from the format (the arithmetic is shown) |

Words used below: **UNSR** is the app's fail-safe answer, *"I'm not sure — show the leaf to the extension officer."*
(card `diag_duda`); the observation SMS then carries the code `UNSR`, or `OTHR` when the model said "not a coffee
leaf". Class names are the model's internal labels: `sano` healthy, `roya` leaf rust, `minador` leaf miner, `phoma`
Phoma leaf spot, `cercospora` brown eye spot, `otro` not a coffee leaf.

## The short version

- **Shipped model:** image model **v2** (`cafetal-img-v2`) at confidence threshold **0.90**. This is an **exception to
  our own ship rule**, decided by the team: v2 passes 4 of the 5 pre-registered conditions. It misses condition (2),
  "lose at most 1 point of Kenyan lab-test macro-F1", by **0.04 points**: its app-level macro-F1 drops 1.04 points,
  because more Kenyan close-ups now get "I'm not sure". Those extra answers are fail-safe, not wrong answers, and
  v2 is the only model that finds rust in field photos (section 4c). The previous model, v1, is shown for comparison.
- **Size:** the image model is **1.97 MB** (1,972,422 B, fp16 weights). The limit is 10 MB.
- **Lab test (JMuBEN, photographed in Kirinyaga, our users' county):** **98.6 %** accuracy and macro-F1 **0.985** on a
  test split grouped by source photo (v1: 98.5 %, 0.9845). The app answers **93.8 %** of coffee test images (v1:
  95.9 %). **100.0 %** of those answers are right (v1: 99.9 %). It never called a diseased leaf "healthy". These are
  close-up crops from one plantation, not phone photos from farms (section 2).
- **Field test (iNaturalist photos, a proxy):** v2 got **34 of 53** held-out rust photos right, **64.2 %** (95 %
  interval 51–76). v1 got 0 of 53. The other 19 got "I'm not sure — show the leaf to the extension officer" (UNSR).
  Leaf miner: 2 of 9. Cercospora: 0 of 10. No diseased photo was called "healthy". **All 162 diseased test photos are
  from the Americas; none is from East Africa.**
- **Kenyan field photos:** **none with a disease label.** Only 6 of the 399 *Coffea* plant photos are from East
  Africa (3 from Kenya). The shipped model gives all 6 the fail-safe. Too few to mean anything (section 4b).
- **False alarms:** v2 gives a disease answer for **2.5 %** of *Coffea* plant photos (10 of 399, interval 1.4–4.5;
  v1: 0 %). It accepts **8 of 446** non-coffee test images, mostly apple rust or scab leaves answered "roya" (v1: 1 of 446).
- **Our own photos:** **0**. We have not taken any yet.
- **Phone speed (emulated):** each photo after the first takes about **0.06 s** with the CPU slowed 4×. The first
  photo (loading included) took **3.7 s** at 4× in this run and 2.5 s in the previous run: one cold sample each, so
  this number is noisy (section 8).
- **First download (emulated 3G, 750 kbps):** the model alone takes **21 s**. Everything the app needs offline takes
  **87.6 s (1.5 min)**, with gzip as the hub serves it.
- **SMS intents (English and Kiswahili):** **95.4 %** accuracy on held-out messages. When the hub answers by itself
  (42.3 % of messages), it was right **100.0 %** of the time. Anything it is unsure about goes to the extension
  officer. The test messages were written by the same team as the training messages.
- **SMS length:** the observation code was **45 characters** in the end-to-end test. Every SMS card fits in one
  160-character GSM-7 SMS with our long sample values, in English, Kiswahili and Gĩkũyũ; community names up to the
  40 characters registration allows still fit (section 11).

---

## 1. Model size

Source: [`reports/model_eval.md`](reports/model_eval.md), sections (d) and Calibration;
[`reports/field_v2_calibration.json`](reports/field_v2_calibration.json); [`model/README.md`](model/README.md).

MobileNetV3-Small, fine-tuned, exported to ONNX and run in the browser by onnxruntime-web (WASM, 1 thread).
The shipped v2 was exported in four versions (validation split, measured):

| version | file size (measured) | validation accuracy | validation macro-F1 | same top-1 as fp32 | runs in onnxruntime-web | shipped? |
|---|---|---|---|---|---|---|
| INT8 static (QDQ, per-channel) | 1.38 MB | 15.1 % | 0.044 | 14.3 % | yes | no: broken |
| INT8 weights only | 1.12 MB | 97.1 % | 0.971 | 97.6 % | yes | no: changes 2.4 % of answers |
| **fp16 weights** | **1.97 MB (1,972,422 B)** | **97.8 %** | **0.978** | **100.0 %** | **yes** | **yes** |
| fp32 | 3.78 MB (3,783,080 B) | 97.8 % | 0.978 | 100.0 % | yes | no: twice the size, same answers |

**Why not INT8.** Static INT8 turns this model into a constant answer, with validation accuracy of 15 %. It did the
same for v1. [`model/README.md`](model/README.md) lists what was tried: per-tensor, percentile calibration, float bias,
Conv-only. All gave the same result. INT8 weights-only works but changes 2.4 % of the answers (for v1 it lost 3.2
points of validation macro-F1). fp16 weights halve the download and change almost nothing: on the test split, 1 of
2,946 images gets a different top class than with fp32 (99.97 % agreement). v2 was exported straight to fp16
weights (`--force fp16_weights`), the format v1 shipped in. Quantization-aware training would be the next thing to try.

v1 has the same architecture and size: 1,972,251 B.

Decision settings in [`app/model/labels.json`](app/model/labels.json):
- **Confidence threshold 0.90.** `model/field_threshold.py` chose it on calibration data only: the lowest t in
  [0.700, 0.995] with at most 5 % disease answers on 400 new *Coffea arabica* photos (from observers used nowhere else)
  and at least 98 % `otro` rejection on the validation split
  ([`reports/field_v2_threshold_sweep.md`](reports/field_v2_threshold_sweep.md)). The *Coffea* condition alone is met
  from t = 0.795; the `otro` condition sets 0.90. v2's export-time value was 0.70, a policy floor over a data-driven
  0.50 that came from Kenyan validation images only. v1 shipped at 0.70. None of the 400 calibration photos is in
  Kenya and 5 are in East Africa (*computed* with the region rule of section 4b on
  [`reports/field_calib_attribution.csv`](reports/field_calib_attribution.csv)).
- **Blur threshold 4.2.** This is the 5th percentile of the Laplacian variance on validation coffee images (the same for v1 and v2).
  It is measured on the photo's centre square shrunk to 128 px, so it only catches blur still visible at that size: a
  moderately blurred full-size photo goes on to the model and its confidence threshold.
- If the top class is `otro`, confidence is below the threshold, or the photo fails the blur check, the app gives the
  fail-safe (UNSR).

## 2. Accuracy on the Kenyan held-out test (JMuBEN, group split)

Source: [`reports/model_eval.md`](reports/model_eval.md) section (a), [`reports/model_eval.json`](reports/model_eval.json),
[`reports/confusion_matrix.png`](reports/confusion_matrix.png).

The test set has 2,946 images: 500 per coffee class and 446 `otro` (PlantDoc and Imagenette). They are split **by
near-duplicate group**, so no copy of a test photo is in training (section 6).

**Where these photos come from.** JMuBEN was photographed in the Mutira coffee plantation in **Kirinyaga County**, with
a digital camera and a pathologist's help (Jepkoech et al. 2021; the place is from a search snippet of the paper's
abstract, code S in [`docs/evidence.md`](docs/evidence.md) §3b; that the dataset is Kenyan is read in its metadata,
code F). That is the county of our users, so this is the closest thing to a local test we have. **It is still not a
field test:** one plantation, one camera, 128×128 close-up crops, many augmented copies of each photo, and only 2
distinct healthy source groups in the test split.

| model | threshold | accuracy (top class) | macro-F1 (top class, 6 classes) | app-level macro-F1 (5 coffee classes, UNSR = miss) |
|---|---|---|---|---|
| v2 fp32 (same weights) | – | 98.6 % | 0.9854 | – |
| **shipped v2 (fp16 weights)** | **0.90** | **98.6 %** | **0.9850** | **0.9670** |
| v1 (previous model) | 0.70 | 98.5 % | 0.9845 | 0.9774 |

The top-class columns do not depend on the threshold. The app-level column does: a photo sent to UNSR counts as a
miss. So v2 at 0.90 scores **1.04 points lower** than v1 on app-level macro-F1. This is the drop that misses ship-rule
condition (2) by 0.04 points (section 4c).

Per class (shipped v2, top class, before the threshold), measured:

| class | precision | recall | F1 | test images | near-duplicate groups in test |
|---|---|---|---|---|---|
| sano | 100.0 % | 100.0 % | 1.000 | 500 | **2** |
| roya | 95.1 % | 100.0 % | 0.975 | 500 | 65 |
| minador | 99.0 % | 100.0 % | 0.995 | 500 | 38 |
| phoma | 99.6 % | 98.8 % | 0.992 | 500 | 27 |
| cercospora | 99.4 % | 100.0 % | 0.997 | 500 | 12 |
| otro | 98.6 % | 91.9 % | 0.951 | 446 | 250 |

> `sano` = 100 % means little: its 500 test images come from **2** near-duplicate groups. JMuBEN's 18,983 healthy
> images form only 14 exact-duplicate groups and 11 near-duplicate groups: 7 in train, 2 in validation, 2 in test
> (see [`DATA_CARD.md`](DATA_CARD.md)). Images inside a group are not independent, so we do not give confidence
> intervals for this test.

What the app does with these images (threshold + blur check, `otro` becomes UNSR), measured:

| true class | v2@0.90 right answer | v2@0.90 wrong answer accepted | v2@0.90 UNSR (fail-safe) | v1@0.70 right | v1@0.70 wrong accepted | v1@0.70 UNSR |
|---|---|---|---|---|---|---|
| sano | 100.0 % | 0.0 % | 0.0 % | 100.0 % | 0.0 % | 0.0 % |
| roya | 89.4 % | 0.0 % | 10.6 % | 88.4 % | 0.0 % | 11.6 % |
| minador | 92.6 % | 0.0 % | 7.4 % | 92.2 % | 0.6 % | 7.2 % |
| phoma | **86.8 %** | 0.0 % | **13.2 %** | 98.4 % | 0.0 % | 1.6 % |
| cercospora | 100.0 % | 0.0 % | 0.0 % | 100.0 % | 0.0 % | 0.0 % |

- **Coverage** (coffee images the app answers): **93.8 %** (v1: 95.9 %).
- **Selective accuracy** (answers that are right): **100.0 %** (v1: 99.9 %).
- **Dangerous error** (a diseased leaf called "healthy"): **0.0 %** (v1: 0.0 %).
- **The cost of the 0.90 threshold** is mostly phoma: 13.2 % of phoma close-ups now get "I'm not sure" (v1: 1.6 %).
  They get the fail-safe, not a wrong answer.
- **`otro` sent to UNSR:** **98.2 %** (438 of 446; v1: 99.8 %). By source: Imagenette 100.0 % (n=54), PlantDoc
  close-up crops 97.5 % (n=196), PlantDoc full photos 98.5 % (n=196).
- **The 8 accepted non-coffee images** are 7 distinct PlantDoc photos (one appears both as a full photo and as a
  crop). They are listed in [`reports/model_eval.md`](reports/model_eval.md) section (a): 6 answered "roya" (apple
  rust and apple scab leaves, and one cherry leaf), 1 "phoma" (a cherry leaf that v1 also accepted) and 1 "minador"
  (tomato bacterial spot). Rust on other plants can look like coffee rust to v2. The old PlantDoc image of the journey
  test is one of them, so that test now uses the first PlantDoc test image the shipped model rejects
  ([`tests/e2e/journey.mjs`](tests/e2e/journey.mjs)); this table, not that test, is the false-alarm rate.

## 3. Robustness to phone-like damage (same test images, degraded)

Source: [`reports/model_eval.md`](reports/model_eval.md) section (b). Measured on degraded copies of the test split,
shipped v2 at 0.90. This is a rough stand-in for the field gap. Section 4 shows it is **not enough**: the real field
gap is much larger.

| degradation | accuracy (top class) | macro-F1 | coffee sent to UNSR | of which by the blur check | selective accuracy | wrong and accepted | `otro` rejected |
|---|---|---|---|---|---|---|---|
| clean | 98.6 % | 0.985 | 10.4 % | 5.3 % | 100.0 % | 0.0 % | 98.2 % |
| JPEG quality 25 | 97.5 % | 0.974 | 7.2 % | 0.3 % | 100.0 % | 0.0 % | 99.1 % |
| Gaussian blur r=2 | 97.9 % | 0.978 | 30.6 % | 24.3 % | 100.0 % | 0.0 % | 98.0 % |
| Gaussian blur r=4 | 95.5 % | 0.953 | 94.4 % | 89.9 % | 100.0 % | 0.0 % | 99.3 % |
| brightness ×0.6 | 98.6 % | 0.985 | 17.9 % | 11.5 % | 100.0 % | 0.0 % | 98.4 % |
| brightness ×1.4 | 98.6 % | 0.986 | 12.8 % | 2.7 % | 100.0 % | 0.0 % | 99.1 % |
| rotate 90° | 98.7 % | 0.987 | 10.5 % | 5.3 % | 100.0 % | 0.0 % | 98.0 % |
| downscale to 64 px | 97.5 % | 0.974 | 28.7 % | 26.1 % | 100.0 % | 0.0 % | 98.2 % |

- Compared with v1 at 0.70 on the same images (second table in section (b)): v2 at 0.90 sends between 0.2 and 7.7
  points more coffee images to UNSR (*computed*, e.g. clean 10.4 % vs 8.2 %, brightness ×1.4 12.8 % vs 5.1 %), and
  accepts no wrong answer under any degradation (v1: 0.0–0.6 %).
- In this table the blur check runs on the 224 px cached view resized to 128 px. That is why "clean" UNSR (10.4 %)
  is higher than in section 2 (6.2 %).

## 4. Field test: iNaturalist photos (a proxy, not from our users' region)

Source: [`reports/field_eval.md`](reports/field_eval.md) ("Result", "Threshold trade-off", "East Africa and Kenya" and
the per-model tables), [`reports/field_eval.json`](reports/field_eval.json),
[`reports/field_v2_threshold_test.json`](reports/field_v2_threshold_test.json), section (g) of
[`reports/model_eval.md`](reports/model_eval.md), per-photo results in
[`reports/field_eval_photos.csv`](reports/field_eval_photos.csv). All measured. Intervals are Wilson 95 % intervals,
in percentage points.

**What this test is.** It uses 768 public iNaturalist photos of coffee leaf rust, leaf miner, Cercospora, American
leaf spot (*Mycena citricolor*, key `ojo_de_gallo`; not a model class, so the right answer is UNSR) and *Coffea arabica*
plants (health unknown). Labels are the iNaturalist community identification, not an agronomist's diagnosis. The
photos are split **by observer**: every observer with a photo in a fixed box over Mexico and northern Central America
is held out, plus about 30 % of the other observers. The box was fixed before any v2 result and is kept so the test
set stays the same; it has no special meaning for Kenya. The 147 field photos that trained v2 come only from the
other observers. Every photo is decided exactly like the phone app: centre square, 224 px, blur check, threshold,
`otro` becomes UNSR. Data details: [`DATA_CARD.md`](DATA_CARD.md#4-inaturalist-field-photos-training-of-the-shipped-v2-threshold-calibration-field-test).

**Where the photos come from.** All 162 diseased test photos are from the Americas (Latin America, the Caribbean and
Hawaii). None of the 369 disease photos in any split (rust 219, leaf miner 30, Cercospora 30, American leaf spot 90)
is from East Africa. The whole iNaturalist export they were drawn from has 266 observations in the East Africa box,
all of them *Coffea arabica* plants and none a disease (*computed*, `reports/field_eval.md`). **So this test says
nothing specific about Noor's photos.** It tests the gap between close-up crops and real field photos.

What the farmer sees: a [rust result](reports/screenshots/journey_06c_result_roya_sms.png) or the
[fail-safe screen](reports/screenshots/journey_08_not_plant.png) ("I'm not sure").

### 4a. The shipped model (v2 at 0.90) on the held-out field test

| group (true label) | n | v2@0.90: right answer and accepted [95 % CI] | v2@0.90: UNSR [95 % CI] | v2@0.90: wrong but accepted | called "healthy" | v1@0.70, same measure |
|---|---|---|---|---|---|---|
| roya, all | 53 | **64.2 %** [51–76] (34) | 35.8 % [24–49] | 0 | 0 | 0.0 % [0–7] |
| roya, symptom clearly visible (screened) | 42 | **81.0 %** [67–90] (34) | 19.0 % [10–33] | 0 | 0 | 0.0 % [0–8] |
| roya, East Africa | 0 | no photos | no photos | – | – | no photos |
| minador | 9 | **2 of 9** [6–55] | 7 of 9 | 0 | 0 | 0 of 9 |
| cercospora | 10 | **0 of 10** [0–28] | 8 of 10 | 2 (called roya) | 0 | 0 of 10 |
| American leaf spot (right answer: UNSR) | 90 | n/a | **91.1 %** [83–95] | 8 (6 roya, 1 minador, 1 phoma) | 0 | UNSR 93.3 % |
| *Coffea* plants, health unknown: share given a disease answer | 399 | **2.5 %** [1.4–4.5] (10: 9 roya, 1 minador) | 97.5 % | n/a | 0 | 0.0 % [0–1] |
| *Coffea* plants in East Africa: share given a disease answer | 6 | 0 of 6 [0–39] | 6 of 6 | n/a | 0 | 0 of 6 [0–39] |
| *Coffea* plants in Kenya: share given a disease answer | 3 | 0 of 3 [0–56] | 3 of 3 | n/a | 0 | 0 of 3 [0–56] |

- **All 162 diseased held-out photos** (53 + 9 + 10 + 90): 116 went to UNSR (71.6 %, *computed*), 36 got the right
  disease name, and 10 got a wrong one (6.2 %, *computed*: 2 Cercospora and 8 American leaf spot photos). None was
  called "healthy".
- **What this means in a live demo.** A clear, close photo of a rust leaf can now get "It looks like coffee leaf rust."
  instead of the fail-safe. A photo of a whole plant usually still gets "I'm not sure". In
  [`model/demo_samples/`](model/demo_samples/README.md), the two held-out rust photos from Latin America (CC BY-NC,
  downloaded on the demo machine) get `RUST`, and the CC BY whole-tree photo gets the fail-safe (`OTHR`)
  ([`reports/model_demo_samples_check.json`](reports/model_demo_samples_check.json): 14 of 14 samples answered as
  expected, run 2026-10-04 with the English SMS codes). Those photos were picked because the app gets them right; they
  are not a measure of accuracy. There is no East African rust photo to use instead. A leaf without rust can also get
  a "roya" answer: 2.5 % of the *Coffea* photos of unknown health got a disease answer (9 roya, 1 minador). Every rust
  answer comes with the "call the officer" card, and the officer decides ([`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) §1).

**v1, the previous model, on all 768 photos** (it never saw any of them):
- **Rust:** 0 of 219 right [0–2]. 99.5 % got UNSR, in 217 cases because the model said "not a coffee leaf" (`otro`).
- **Rust with the symptom clearly visible:** 0 of 164 right.
- **Leaf miner:** 0 of 30. **Cercospora:** 0 of 30.
- **Safety:** no diseased photo was called "healthy". v1 only recognises close-ups that look like the 128 px Kenyan crops.

**The blur check fired on 0 of 768 photos.** These are sharp photos about 500 px wide. The blur check is meant for
shaky phone shots, which this test does not contain.

### 4b. East Africa and Kenya (no disease photos; 6 coffee-plant photos)

Rule ([`reports/field_eval.md`](reports/field_eval.md), "East Africa and Kenya"): East Africa = a box, lat −11.8 to
15.0, lon 28.8 to 48.0, meant for Kenya, Uganda, Tanzania, Rwanda, Burundi and Ethiopia (it also takes in parts of
neighbouring countries, so every photo inside it is listed); Kenya = inside a simplified 34-point outline of Kenya.
Both use the coordinates rounded to 0.1° in the attribution CSV. These are report subsets only: they change nothing
in the split, the training data or the threshold.

| group | n | v1@0.70 | v2@0.70 (not shipped) | **v2@0.90 (shipped)** | v2@0.70 + multicrop (not shipped) |
|---|---|---|---|---|---|
| rust, leaf miner, Cercospora, American leaf spot photos from East Africa | 0 | no photos | no photos | no photos | no photos |
| *Coffea* plants in East Africa given a disease answer | 6 | 0 of 6 [0–39] | 1 of 6 [3–56] | **0 of 6** [0–39] | 2 of 6 [10–70] |
| *Coffea* plants in Kenya given a disease answer | 3 | 0 of 3 [0–56] | 0 of 3 [0–56] | **0 of 3** [0–56] | 0 of 3 [0–56] |

The 6 photos one by one (place read by eye from the coordinates, not computed):

| photo | where | v1@0.70 | v2@0.70 | **v2@0.90 (shipped)** |
|---|---|---|---|---|
| [92700141](https://www.inaturalist.org/photos/92700141) | Kenya, near Nakuru | UNSR (otro 1.000) | UNSR (otro 1.000) | **UNSR** (otro 1.000) |
| [631362214](https://www.inaturalist.org/photos/631362214) | Kenya, Kiambu County near Limuru | UNSR (otro 1.000) | UNSR (otro 0.937) | **UNSR** (otro 0.937) |
| [717871095](https://www.inaturalist.org/photos/717871095) | Kenya, Taita Hills | UNSR (otro 1.000) | UNSR (otro 0.961) | **UNSR** (otro 0.961) |
| [672111499](https://www.inaturalist.org/photos/672111499) | Tanzania, Kilimanjaro slopes north of Moshi | UNSR (otro 0.999) | UNSR (otro 0.485) | **UNSR** (otro 0.485) |
| [710570289](https://www.inaturalist.org/photos/710570289) | Tanzania, Zanzibar (Unguja) | UNSR (otro 0.995) | roya (0.758) | **UNSR** (roya 0.758) |
| [621748067](https://www.inaturalist.org/photos/621748067) | Lake Kivu shore, most likely Rwanda | UNSR (otro 1.000) | UNSR (otro 0.997) | **UNSR** (otro 0.997) |

Six photos of plants with unknown health cannot give a false-alarm rate for Kenya, and there is no labelled disease
photo from the region at all. The only Kenyan evidence is the JMuBEN test split (section 2). The next step is
labelled phone photos from Kirinyaga farms, confirmed by the extension officer
([`data/field_test/README.md`](data/field_test/README.md)).

### 4c. How v2 was built, how its threshold was chosen, and why it shipped

- **v2:** the v1 recipe plus 147 screened field-train photos from iNaturalist (roya 122, minador 15, cercospora 10),
  from observers who are never in the field test, 7 views each, oversampled ×2. Training ran 12 epochs, 14.8 min of
  epoch time on CPU ([`reports/field_v2_training_log.csv`](reports/field_v2_training_log.csv)).
- **Multicrop** (tested, not shipped): the full view plus 4 tiles (2×2), and at least 2 tiles must agree. We chose this
  scheme on validation data and field-train photos, **before** looking at the field test.

**What happened, in order:**
1. **First comparison**, each model at its export threshold (0.70). The pre-registered rule said **keep v1**: v2 failed
   condition (3) (`otro` rejection 95.7 %) and condition (5) (*Coffea* disease answers +8.0 points).
2. **v2's threshold was re-chosen on calibration data only** (400 new *Coffea* photos from unseen observers, plus the
   validation `otro` images): t = 0.90 (section 1). The script checks that no test photo or test observer is used.
   The v2@0.70 test results had already been seen before this step, so the test sets are not untouched for v2@0.90.
3. **v2@0.90 was evaluated once** on the same held-out test sets. The rule said **DO NOT SHIP**: 4 of 5 conditions pass, (2) fails.
4. **The team shipped v2@0.90 anyway** (2026-10-03), as an explicit, documented exception ([`model/ship_decision.json`](model/ship_decision.json)).

| metric (held-out field test unless noted) | v1@0.70 (previous) | v2@0.70 (not shipped) | **v2@0.90 (shipped)** | v2@0.70 + multicrop (not shipped) |
|---|---|---|---|---|
| roya right and accepted (n=53) | 0.0 % [0–7] | 71.7 % [58–82] | **64.2 %** [51–76] | 79.2 % [67–88] |
| roya, symptom visible (n=42) | 0.0 % [0–8] | 88.1 % [75–95] | **81.0 %** [67–90] | 97.6 % [88–100] |
| roya, East Africa | n = 0 | n = 0 | **n = 0** | n = 0 |
| minador right (n=9) | 0 of 9 | 5 of 9 | **2 of 9** | 5 of 9 |
| cercospora right (n=10) | 0 of 10 | 0 of 10 (5 called roya) | **0 of 10** (2 called roya) | 0 of 10 |
| American leaf spot sent to UNSR (n=90, the right answer) | 93.3 % | 75.6 % [66–83] | **91.1 %** [83–95] | 70.0 % [60–78] |
| diseased field photos with a wrong answer accepted (count) | 8 | 30 | **10** | 36 |
| *Coffea* plants given a disease answer (n=399) | 0.0 % [0–1] | 8.0 % [6–11] | **2.5 %** [1.4–4.5] | 20.8 % [17–25] |
| *Coffea* plants in East Africa given a disease answer (n=6) | 0 of 6 | 1 of 6 | **0 of 6** | 2 of 6 |
| non-coffee (`otro`) Kenyan-test images rejected (n=446) | 99.8 % | 95.7 % [93–97] | **98.2 %** [96.5–99.1] | 93.5 % [91–95] |
| Kenyan test macro-F1 (top class / app-level) | 0.9845 / 0.9774 | 0.9850 / 0.9843 | **0.9850 / 0.9670** | 0.9850 / 0.9928 |
| Kenyan test coffee close-ups sent to UNSR | 4.1 % | 3.0 % | **6.2 %** | not reported |
| diseased leaves called "healthy" (field / Kenyan test) | 0 / 0 | 0 / 0 | **0 / 0** | 0 / 0 |

**Ship rule.** We fixed the rule before computing the v2 field results. A candidate must do all five of these, compared with v1:
1. gain ≥ 10 points on field rust;
2. lose ≤ 1 point of Kenyan macro-F1 (top class **and** app-level);
3. reject ≥ 98 % of `otro`;
4. call no more diseased leaves "healthy" (`sano`);
5. raise the *Coffea* disease-answer rate by ≤ 5 points.

| condition | v2@0.70 | **v2@0.90 (shipped)** | v2@0.90 value |
|---|---|---|---|
| (1) field rust +10 points | pass | pass | +64.2 points |
| (2) Kenyan macro-F1 drop ≤ 1 point | pass | **FAIL** | top class +0.05 points (passes); app-level −1.04 points (limit −1.00) |
| (3) `otro` rejection ≥ 98 % | **FAIL** | pass | 98.2 % (438 of 446): exactly at the limit, one more accepted image would fail |
| (4) no more diseased leaves called "healthy" | pass | pass | field 0 vs 0; Kenyan 0 vs 0 |
| (5) *Coffea* disease answers +5 points at most | **FAIL** | pass | +2.5 points |

v1 + multicrop failed (1). v2 + multicrop failed (3) and (5).

**The exception, in plain words.**
- **What missed:** condition (2). On the Kenyan test, v2@0.90's app-level macro-F1 is 0.9670 against v1's 0.9774, a
  drop of **1.04 points** where the rule allows 1.00. It misses by **0.04 points**. The top-class macro-F1 passes
  (0.9850 vs 0.9845).
- **Why the score drops:** at 0.90 more Kenyan close-ups go to the fail-safe, mostly phoma (13.2 % vs 1.6 %, section
  2). They get "I'm not sure — show the leaf to the extension officer.", not a wrong answer. Selective accuracy is
  100.0 %, and no diseased leaf was called "healthy" on either test set.
- **Who decided:** the Cafetal team, on 2026-10-03. It is a human decision, recorded in
  [`model/ship_decision.json`](model/ship_decision.json), not the output of the scripts. The reports keep the rule's
  own verdicts as computed ("KEEP v1" for the first comparison, "DO NOT SHIP" in
  [`reports/field_v2_threshold_test.json`](reports/field_v2_threshold_test.json)).
- **Why:** the extra answers it gives up are fail-safe "I'm not sure" answers, and v2 is the only model that finds
  rust in field photos (v1: 0 of 53).
- **Post-hoc check** (validation split, computed after the test; it changes nothing): on validation, v2@0.90's
  app-level drop is 0.78 points, so adding condition (2) to the calibration rule would not have changed t
  ([`reports/field_eval.md`](reports/field_eval.md)).
- **Not offered:** any further change of the threshold. It would now be chosen with test knowledge. The move to Kenya
  changed nothing here: same model file, same threshold, same numbers.

**Why v2 raises false alarms.** At 0.70, v2 answered 32 *Coffea* photos with a disease
([`reports/field_coffea_v2_alarms.csv`](reports/field_coffea_v2_alarms.csv)). 28 of them show no visible leaf symptom:
cherries in a hand, flowers, healthy leaves. Every field training photo is diseased, and there are no labelled healthy
field leaves, so v2 partly learned "field photo of a coffee plant = roya". At 0.90, 10 of 399 remain. The fix is
labelled phone photos from Kirinyaga farms, healthy **and** diseased, confirmed by the extension officer. Then we rerun
this protocol.

**Multicrop speed** was not built in JavaScript. *Computed* estimate: 5 inferences × 54.3 ms (`session.run` median at
4× CPU throttle, section 8) ≈ 0.27 s per photo. Not measured.

**Caveats.**
- iNaturalist photos are a proxy for our users' photos, not a substitute: all the disease photos come from the
  Americas, taken with other cameras, and many are severe textbook cases.
- One person screened the photos, from thumbnails.
- 8 rust-labelled training photos look like Cercospora to that person. They were kept as rust, which may add to v2 calling Cercospora "roya".
- Intervals are wide: minador n=9, cercospora n=10, East Africa *Coffea* n=6.
- Condition (3) passes with no margin, and condition (2) fails by a margin that a handful of close-ups decides.

## 5. The lab-to-field gap in one table

Sources: sections 2 and 4. The metric is "right answer and accepted" as the app decides, so it is the same in all columns.

| | Kenyan test (Kirinyaga plantation, lab-like crops), shipped v2@0.90 | iNaturalist field test (the Americas), shipped v2@0.90 | iNaturalist field test, v1@0.70 (previous) |
|---|---|---|---|
| roya | 89.4 % (500 images, 65 source groups) | **64.2 %** [51–76] (n=53) | 0.0 % [0–7] (n=53) |
| minador | 92.6 % (500 images, 38 groups) | **2 of 9** [6–55] | 0 of 9 [0–30] |
| cercospora | 100.0 % (500 images, 12 groups) | **0 of 10** [0–28] | 0 of 10 [0–28] |
| roya sent to UNSR | 10.6 % | 35.8 % [24–49] | 98.1 % [90–100] |
| coffee plants (no visible disease expected) given a disease answer | not tested | 2.5 % [1.4–4.5] (n=399) | 0.0 % [0–1] (n=399) |
| diseased leaf called "healthy" | 0.0 % | 0 | 0 |

This gap is a known pattern. A model trained on 54,306 controlled-condition leaf images scored 99.35 % on its own test
set and 31.4 % on images taken in other conditions (Mohanty, Hughes & Salathé 2016, arXiv:1604.03169; code F in
[`docs/evidence.md`](docs/evidence.md) §10). v1 mostly refused to answer on field photos. v2, trained with 147 field
photos, closes part of the gap for rust (89 % → 64 %) but not for leaf miner (93 % → 2 of 9) or Cercospora
(100 % → 0 of 10), and it pays with false alarms. Where it is unsure, it still falls back to the fail-safe. Coming
from the same county does not close this gap: the Kenyan test images are close-ups from one plantation, not phone
photos from farms.

## 6. Leakage check: group split vs naive split

Source: [`reports/model_eval.md`](reports/model_eval.md) section (f) and "Data". Measured.

JMuBEN ships each source photo many times: flipped, rotated and colour-shifted copies, plus burst shots. We grouped near-duplicates with a
72-bit difference hash (minimum over 8 flips/rotations, Hamming distance ≤ 8) and split 70/15/15 by group.
The 58,549 JMuBEN images form about 880 groups (cercospora 78, minador 246, phoma 171, roya 373, sano 11).

| test set (shipped v2) | images | accuracy | macro-F1 |
|---|---|---|---|
| group split (what we report) | 2,946 | 98.6 % | 0.985 |
| unused copies of **training** photos (what a random split would have tested) | 1,800 | 98.9 % | 0.989 |

A random split would have looked a little better (0.3 points for v2; for v1, 0.995 vs 0.985 in
[`reports/model_eval.md`](reports/model_eval.md) at commit 0c402f7). The bigger lesson is the
group count: `sano` has 18,983 images but only 11 near-duplicate groups (14 exact-duplicate groups), and 7 of those
groups are in training. So the healthy class was learned from 7 near-duplicate groups, about 7–10 distinct source
photos (*computed*: the 11 groups hold 14 exact-duplicate groups). The 147 field photos added for v2 are all diseased,
so this did not change.

## 7. The team's own photos (`data/field_test/`)

**0 images. Not collected yet.** The folders exist ([`data/field_test/README.md`](data/field_test/README.md), which
says what to collect in Kirinyaga), and `model/evaluate.py` scores whatever is there, separately from everything else
(section (c) of [`reports/model_eval.md`](reports/model_eval.md)). Until then the Kenyan lab test (section 2) and the
iNaturalist proxy (section 4) are our only evidence. Officer confirmations saved by the hub (`labels` table) are meant
to fill this folder over time.

## 8. Phone response time (emulated)

Source: [`reports/browser_metrics.md`](reports/browser_metrics.md) / [`.json`](reports/browser_metrics.json),
run 2026-10-04 with the shipped v2 (1,972,422 B, threshold 0.9; service-worker cache `cafetal-841334ea01`).
**Emulated:** headless Chromium 141, Pixel 5 profile, on a 4-CPU Intel Xeon 2.10 GHz build server with no GPU. CPU
throttling (CDP `Emulation.setCPUThrottlingRate`) slows the page thread as a rough stand-in for a low-end Android
phone. It does not model a phone's memory, heat or WASM speed exactly.

| CPU throttle | first photo, cold (runtime + model load + run) | each later photo: 12 MP photo, median of 10 | each later photo: 128 px crop, median of 10 | model run only, median of 10 |
|---|---|---|---|---|
| ×1 (none) | 0.65 s | 22.2 ms | 18.4 ms | 10.0 ms |
| ×4 | **3.69 s** | **64.0 ms** | 61.9 ms | 54.3 ms |
| ×6 | **3.65 s** | **105.4 ms** | 98.0 ms | 83.5 ms |

- "Each later photo" is the app's own `diagnose()` from `app/infer.js`: blur check, centre crop, resize and model.
- The 12 MP case starts from an already-decoded 4000×3000 image, so **JPEG decoding of a real camera photo is not included**.
- **The cold first photo is one sample per setting and is noisy.** In this run ×6 came out slightly faster than ×4.
  The previous run, with the same model file, measured 2.50 s at ×4 and 3.74 s at ×6
  (`reports/browser_metrics.md` at commit 6891b8c). Read it as "a few seconds", not as a precise figure.
- On the build server, outside the browser: onnxruntime Python, 1 thread, 3.19 ms; onnxruntime-web in Node, 12.5 ms
  (measured at export time). Measured, but not a phone ([`reports/model_eval.md`](reports/model_eval.md) section (d)).

## 9. First-load download (emulated)

Source: [`reports/browser_metrics.md`](reports/browser_metrics.md). **Emulated** with CDP `Network.emulateNetworkConditions`.
Project-defined profiles (not the DevTools presets):
- **3G:** 750 kbps down, 250 kbps up, 100 ms latency.
- **slow 3G:** 400 kbps down, 400 kbps up, 400 ms latency.

| network | model file alone (1.97 MB) | whole offline bundle, as the hub serves it (gzip; 7.98 MB on the wire) |
|---|---|---|
| 3G | **21.2 s** | **87.6 s (1.5 min)** |
| slow 3G | **39.9 s** | **165.7 s (2.8 min)** |

- **What the hub does.** It gzips text, JS and WASM files ([`hub/main.py`](hub/main.py), `StaticGZip`): 26 gzip
  responses in this run. The model and the audio are not gzipped.
- **What the bundle is.** 251 files, 16.21 MB decoded. The biggest parts are:
  - the onnxruntime WASM runtime: `app/vendor/ort-wasm-simd-threaded.wasm`, 11,018,731 B on disk;
  - the model: 1.97 MB;
  - 222 MP3 files (74 per language, English, Kiswahili and Gĩkũyũ): 2.95 MB ([`content/README.md`](content/README.md)).

  The 10 MB limit is for model files. The model is 1.97 MB. The full bundle is larger, mostly because of the runtime.
  The previous run measured 16.81 MB decoded, 8.59 MB on the wire and 94.0 s on 3G (`reports/browser_metrics.md` at
  commit 6891b8c). The difference, 0.6 MB, is about what the audio lost when it was re-made for the new languages
  (about 3.5 MB before, 2.95 MB now).
- **How it was measured.** The page fetched the files in the same four groups as the service worker's `precache()`.
  The real service-worker install could not be throttled, because Chromium does not apply CDP throttling to service-worker fetches.
  The page's own first 13 requests come on top: 173 KB decoded, 39 KB with gzip (measured, unthrottled).
- **Once cached**, nothing is downloaded again until a file changes.
- **Computed, for comparison:** 1,972,422 B × 8 / 384 kbps = 41.1 s for the model, with no protocol overhead
  ([`reports/model_eval.md`](reports/model_eval.md) section (d)).

## 10. SMS intent classifier (free-text SMS at the hub)

Source: [`reports/intent_eval.md`](reports/intent_eval.md) / [`.json`](reports/intent_eval.json), trained 2026-10-04.
Measured.

- **Data:** 872 messages in [`data/intent/examples.csv`](data/intent/examples.csv). By intent: price 101, report 108,
  help 99, talk_to_officer 99, other 465. By language: English 427, Kiswahili 428, Gĩkũyũ 17. By source:
  - team-written 455 (English 227, Kiswahili 228), in a Kenyan SMS style with sheng, typos and no diacritics. The
    team includes AI agents; no native Kiswahili speaker checked them and none come from real members
    ([`data/intent/README.md`](data/intent/README.md));
  - Amazon MASSIVE 1.1, 200 en-US + 200 sw-KE utterances, used only as `other`;
  - 17 unverified AI-drafted Gĩkũyũ messages.

  Stratified 80/20 split: 697 train / 175 test.
- **Model:** TF-IDF on character 2–4-grams (6,490 features) + logistic regression (C = 30). It runs in pure Python in
  the hub (`hub/intent.py`, model file `hub/intent_model.json`).
- **Threshold 0.55.** This is the lowest value that gives ≥ 95 % precision on auto-answered messages, using
  out-of-fold predictions on the training split. Below it, the hub replies "we are passing your message to the
  extension officer" (`sms_pasar_tecnico`) and forwards the SMS to the officer.
- **Keywords first.** The exact one-word messages PRICE/PRICES, HELP and OFFICER, and in Kiswahili BEI, MSAADA and
  AFISA, skip the classifier (`hub/sms.py` `KEYWORDS`). The SMS cards advertise them; there are no Gĩkũyũ keywords.

| held-out test (n) | accuracy | macro-F1 |
|---|---|---|
| top class, no threshold (175) | 97.1 % | 0.970 |
| **with threshold, as deployed (175)** | **95.4 %** | **0.950** |
| with threshold, English only (82) | 100.0 % | 1.000 |
| with threshold, Kiswahili only (89) | 92.1 % | 0.917 |
| with threshold, Gĩkũyũ only (4; too few to mean anything) | 3 of 4 | 0.778 |
| with threshold, without MASSIVE messages (98) | 91.8 % | 0.918 |

- **Auto-answered:** 42.3 % of test messages. **100.0 %** of those answers were right.
- **On-topic messages** (true intent is not `other`) answered with the right card automatically: 90.2 %. The rest go to the officer.
- **Per class, with threshold:**
  - price: precision 1.00, recall 0.95
  - report: 1.00 / 0.95
  - help: 1.00 / 0.85
  - talk_to_officer: 1.00 / 0.85
  - other: 0.92 / 1.00
- **Every miss was a safe miss:** in the confusion matrix with the threshold, the 8 errors are all on-topic messages
  sent to `other`, so they go to the officer; no message got the wrong card.
- **Probes:** 15 hand-made messages that are not in the data, all routed as intended, e.g. "how much are you paying for
  a kilo of cherry" → price 0.99, "majani ya kahawa yana unga wa rangi ya machungwa" → report 1.00, "nataka kuongea na
  afisa ugani" → talk_to_officer 1.00, "asdf qwerty" → other 0.87.
- **Gĩkũyũ:** only 17 unverified examples, too few to measure. Gĩkũyũ free text will mostly fall below the threshold
  and go to the officer: safe, not smart.
- **End to end** ([`reports/journey_results.json`](reports/journey_results.json)): "how much are you paying for a kilo of
  cherry" → price 0.9935; "majani ya kahawa yana unga wa rangi ya machungwa" → report 0.9956, forwarded to the
  officer; "asdf qwerty" → other 0.8716, forwarded to the officer.

## 11. SMS lengths

One SMS is 160 GSM-7 characters. A single character outside GSM-7 (an accent such as ĩ, or a curly quote) switches the
whole message to UCS-2, which allows only 70 characters, so SMS cards are plain ASCII. The Gĩkũyũ SMS cards write ĩ/ũ
as i/u ([`content/README.md`](content/README.md)); the hub also strips accents from slot values in SMS cards
(`hub/cards.py` `gsm_safe`, tested with the community name "Ondera Kĩlĩma" in
`test_accented_community_keeps_alert_in_one_gsm_sms`).

**Observation code** (phone → co-op):
- **Measured:** 45 characters in the end-to-end test: `CAF1 M0123 RUST 99 20261004 -0.52,37.32 #Z854`
  ([`reports/journey_results.json`](reports/journey_results.json)).
- **Computed** from the format in [`app/sms.js`](app/sms.js): the longest possible code is 48 characters.
  Location is rounded to 2 decimals (about 1 km).

**Replies sent in the end-to-end test** (measured, [`reports/journey_results.json`](reports/journey_results.json); Noor's
language is English):

| reply card | trigger | length | encoding | SMS segments |
|---|---|---|---|---|
| `sms_precio` | "PRICE", "BEI" and "how much are you paying for a kilo of cherry" | 152 | GSM-7 | 1 |
| `sms_reporte_instrucciones` | "majani ya kahawa yana unga wa rangi ya machungwa" | 124 | GSM-7 | 1 |
| `sms_pasar_tecnico` | "asdf qwerty" | 104 | GSM-7 | 1 |

The PRICE reply read: *"Reference price 10/2026: coffee 139.00 KES/kg cherry, maize 51.11, beans 111.11 KES/kg. Source:
DEMO county 25/26, KAMIS. Not the price at your factory."* All prices are DEMO ([`DATA_CARD.md`](DATA_CARD.md#9-reference-prices-datapricesjson-demo)).

**Every SMS card with long sample values** (computed). This fills the slots with the sample values in
`scripts/make_audio.py` (coffee 157.40 KES/kg cherry, maize 105.50, beans 180.00, date "2026-09-30", the 40-character
community name "Ondera Kilima Upper Ward, by the factory", 120 reports, and the `sms_fuente` text from
`data/prices.json`), then counts GSM-7 characters. The community name is the longest registration allows; the other
values are long, **not the worst case**. `python3 scripts/make_audio.py --check` reports "83 cards checked, 0
problem(s)".

| card | en | sw | kik |
|---|---|---|---|
| `sms_obs_recibida` | 117 | 117 | 128 |
| `sms_codigo_invalido` | 82 | 75 | 84 |
| `sms_no_registrado` | 81 | 80 | 77 |
| `sms_precio` | **156** | 152 | 151 |
| `sms_precio_sin_datos` | 67 | 61 | 71 |
| `sms_reporte_instrucciones` | 124 | 120 | 129 |
| `sms_ayuda` | 146 | 119 | 147 |
| `sms_pasar_tecnico` | 104 | 75 | 91 |
| `alert_roya` | 134 | 148 | **159** |

**Real limits** (computed with the same counting as `hub/cards.py`):
- **`alert_roya`**: registration accepts community names of up to 40 characters (`SLOT_VALUE_RE` in
  [`hub/cards.py`](hub/cards.py), checked in [`hub/main.py`](hub/main.py)). With a 40-character name and 120 reports
  (the table above) the alert is 134 characters in English, 148 in Kiswahili and **159 in Gĩkũyũ**: one SMS in every
  language. Gĩkũyũ has only 1 character to spare.
- **`sms_precio` in English** has 4 characters to spare with the sample values. Keep `sms_fuente` in
  `data/prices.json` short: 5 more characters in the slots make it longer than one SMS.
- **At send time** the hub refuses any SMS card that would be longer than one SMS ([`hub/cards.py`](hub/cards.py)
  `render`). A price reply that does not fit is replaced by `sms_precio_sin_datos` ("we have no reference price
  today"); it is never sent in two parts.

## 12. What we have not measured

- **A real phone.** All speed numbers are emulated in desktop Chromium. We have not measured JPEG decoding of a real camera photo,
  memory, battery or heat on a low-end Android phone.
- **A real network.** Download times are emulated. We have not tested a real 3G or 2G link, the real service-worker install
  over a slow link, or real SMS delivery: the SMS gateway is SIMULATED.
- **Kenyan field photos.** We have 0 of our own, and the iNaturalist set has no labelled disease photo from East
  Africa (section 4b). There are no agronomist-confirmed labels and no labelled healthy field leaves. We do not know
  how often the shipped model gives a false disease answer, or says "I'm not sure", on a real healthy leaf from a
  Kirinyaga farm. The closest proxy is the iNaturalist *Coffea* sample: 2.5 % disease answers, 97.5 % UNSR, 0
  "healthy" (section 4a). The 0.90 threshold was chosen on iNaturalist calibration photos, none of them from Kenya.
- **Coffee berry disease.** The model looks only at leaves, so it cannot see this disease of the berries at all
  ([`docs/evidence.md`](docs/evidence.md) §4).
- **Real Kiswahili and Gĩkũyũ listeners and readers.** No native speaker has read the Kiswahili or Gĩkũyũ text, and no
  one has listened to the provisional audio (an English voice reading Kiswahili phonemes). The English cards have not
  been checked by an agronomist or by co-op staff either.
- **Real member SMS.** The intent test set was written by the same people who wrote the training set. Gĩkũyũ free text
  is effectively untested (4 test messages).
- **Multicrop in the app.** It was not built, so its speed is only an estimate (section 4c).
- **Outbreak rule and worklist weights** (≥ 3 members, 5 km, 7 days). These are design choices, not tested against real outbreaks.
- **Prices.** All values are DEMO, in KES, and were seen only in search summaries. None was checked on the official
  source page (see [`DATA_CARD.md`](DATA_CARD.md#9-reference-prices-datapricesjson-demo)).

## 13. How to reproduce

From the repo root (`/home/user/7GlobalMex`). The training venv is `/home/user/venv-train`. The hub venv `.venv` is
created by `./run.sh`.

```bash
# Hub tests (76 passed, 1 skipped on 2026-10-04; the skipped test needs scikit-learn, which .venv does not have)
.venv/bin/python -m pytest tests -q

# Card check: ids, slots, languages, diag_duda, GSM-7, <= 160 characters after filling slots
python3 scripts/make_audio.py --check

# Image model: data, training, export and evaluation. Full steps with download URLs in model/README.md
source /home/user/venv-train/bin/activate
python model/prepare_data.py --jmuben /home/user/data_raw/arabica/arabica_coffee_leaf_disease_classification \
  --plantdoc /home/user/data_raw/plantdoc/plant_doc_classification \
  --negatives /home/user/data_raw/imagenette/imagenette2-160 \
  --inat /home/user/data_raw/inatag/mini/coffea_arabica --out /home/user/data_proc/cafetal
python model/train.py --data /home/user/data_proc/cafetal --out model/checkpoints          # resumable; --max-minutes 9
npm i --prefix /tmp/ortweb onnxruntime-web@1.19.2   # the Node build; app/vendor/ holds only the browser build
python model/export_onnx.py --data /home/user/data_proc/cafetal --ortweb /tmp/ortweb/node_modules/onnxruntime-web/dist  # -> app/model/
#   (that first export is v1; v1 is kept in model/checkpoints/v1/ as the reference)

# Field test (iNaturalist), v2 training, threshold calibration and install: exact commands in model/README.md
python model/field_eval.py --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat \
  --model v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json \
  --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json
#   -> reports/field_eval.md|json, reports/field_eval_photos.csv (incl. the East Africa and Kenya subsets)
M="--model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json"
python model/field_threshold.py sample --inat /home/user/data_raw/inat          # 400 calibration Coffea photos
python model/field_threshold.py sweep --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat $M
python model/field_threshold.py test  --data /home/user/data_proc/cafetal --inat /home/user/data_raw/inat $M
#   -> reports/field_v2_threshold_sweep.md|json, reports/field_v2_threshold_test.json
#   (rerunning "test" today would fail on the renamed report groups: see the note below)
python model/field_threshold.py install --model v2=model/checkpoints/v2/app/cafetal.onnx:model/checkpoints/v2/app/labels.json
#   writes app/model/ only because model/ship_decision.json (the team's decision) names v2@0.9
python model/evaluate.py --data /home/user/data_proc/cafetal --inat-field /home/user/data_raw/inat \
  --fp32 model/checkpoints/v2/cafetal_fp32.onnx --calib reports/field_v2_calibration.json \
  --ref v1=model/checkpoints/v1/cafetal.onnx:model/checkpoints/v1/labels.json:reports/model_calibration.json
#   -> reports/model_eval.md|json, reports/confusion_matrix.png (shipped v2, v1 as reference column)
python model/evaluate.py --render                  # rebuild model_eval.md from its JSON, no data needed
python model/field_eval.py --render                # rebuild field_eval.md from its JSON, no data needed
python3 model/demo_samples.py --field              # demo machine: fetch the 2 CC BY-NC field rust photos
node model/check_demo_samples.mjs                  # every demo sample in the real app logic (14 of 14)

# Intent classifier -> hub/intent_model.json, reports/intent_eval.md|json
python3 -m hub.build_intent_examples --massive-dir /home/user/data_raw/massive/1.1/data   # handwritten + MASSIVE en-US/sw-KE
/home/user/venv-train/bin/python -m hub.train_intent

# Browser checks (need Node 22 + Playwright; Chromium at /opt/pw-browsers; never run "playwright install")
node tests/e2e/app_offline.mjs                     # offline phone flow; starts its own throw-away hub (89 of 89 checks)
./run.sh &                                         # hub on :8000 (seeds DEMO data if hub/cafetal.db is missing)
node tests/e2e/journey.mjs                         # whole journey -> reports/journey_results.json + screenshots (46 of 46)
node tests/e2e/browser_metrics.mjs inference       # speed under CPU throttling
LABEL="as built (gzip for text/JS/WASM)" node tests/e2e/browser_metrics.mjs network   # ~10 min
#   -> reports/browser_metrics.md|json
# afterwards: stop the hub and delete the DB so the next run seeds fresh DEMO dates
rm -f hub/cafetal.db*
```

TensorFlow on CPU is not bit-exact with a parallel input pipeline, so model numbers can move by a few tenths of a point between runs.
The seed is 42. The iNaturalist images are not in the repo. `model/inat_field.py` downloads them again from the public
`inaturalist-open-data` S3 bucket, using [`reports/field_inat_attribution.csv`](reports/field_inat_attribution.csv).

**Note on `model/field_threshold.py test`.** It still reads the report group names used before the move to Kenya, so
rerunning it would fail or write outdated wording into `reports/field_eval.md`. `model/field_eval.py --render` rebuilds
the reports correctly from the stored JSON. This only matters if someone retrains.
