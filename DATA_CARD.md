# Cafetal data card

Every dataset and resource Cafetal uses, or chose not to use. For each one: source, licence, size, what we used it for,
how we processed it, and **what it does not cover**. Results are in [`METRICS.md`](METRICS.md). Numbers come from
[`reports/`](reports/), [`docs/evidence.md`](docs/evidence.md) or the data files named in each section.

**Network note.** The build machine could not reach Mendeley Data, Hugging Face, Kaggle, iNaturalist's website or most
statistics sites. It could reach PyPI/npm, GitHub and public S3 buckets. That decided several choices below.

## Summary

| # | dataset / resource | used for | licence | size used | in the shipped app? |
|---|---|---|---|---|---|
| 1 | JMuBEN + JMuBEN2 (Kenya) | train / validate / test the image model (5 coffee classes) | CC BY 4.0 | 58,549 images, about 880 distinct groups | model weights only |
| 2 | PlantDoc | `otro` (not a coffee leaf) | CC BY 4.0 per the repo; AgML says CC BY-SA 4.0 (to be checked) | 2,569 images | model weights only |
| 3 | Imagenette | `otro` (not a plant) | ImageNet terms (non-commercial research) | 700 images | model weights only |
| 4 | iNaturalist field photos | **trains the shipped v2** (147 photos); threshold calibration (400 *Coffea* photos); field test | per photo: CC0 to CC BY-NC-ND | 768 + 400 photos | model weights only (one CC BY demo photo is in the repo) |
| 5 | iNatAg-mini *Coffea arabica* | evaluation only | CC BY-NC 4.0 (to be checked) | 200 photos | no |
| 6 | BRACOL, RoCoLe | **not used** (Mendeley blocked) | to be checked | — | no |
| 7 | Amazon MASSIVE 1.1 es-ES | `otro` examples for the SMS intent classifier | CC BY 4.0 | 300 utterances | classifier weights only |
| 8 | Hand-written SMS examples (team + AI-draft Tseltal) | SMS intent classifier | project | 275 messages | classifier weights only |
| 9 | Reference prices | PRECIO reply (not AI) | public sources, **all DEMO** | 3 prices | yes (DEMO) |
| 10 | Piper TTS, voices `es-mls_10246-low` and `en-us-lessac-medium` | Spanish audio; provisional Tseltal audio; English audio | Piper MIT; voice data: CC BY 4.0 (es), Lessac licence (en, to be checked) | 222 MP3 files | yes (MP3 only) |
| 11 | Tseltal card text (AI draft, Polian 2018 dictionary) | Tseltal text | dictionary CC BY 4.0 | 83 cards | yes (UNVERIFIED) |
| 11b | English card text (AI translation of the Spanish cards) | English text for judges and visitors | project | 83 cards | yes (UNVERIFIED) |
| 12 | Meta MMS Tseltal models | **not used** | CC BY-NC 4.0 | — | no |
| 13 | Evidence sources (GSMA, Findex, FAOSTAT, INEGI, OpenCelliD, …) | problem evidence | various | see [`docs/evidence.md`](docs/evidence.md) | no |
| 14 | DEMO hub data | demo of the co-op hub | project | 24 fictional members | yes (DEMO) |

The image model also starts from **ImageNet-pretrained MobileNetV3-Small weights** from Keras Applications
(code Apache-2.0; the weights were trained on ImageNet). No dataset images ship in the app. For the demo,
[`model/demo_samples/`](model/demo_samples/README.md) holds 10 held-out JMuBEN test crops plus one blurred copy of one
of them (CC BY 4.0), and one held-out CC BY iNaturalist field photo (a whole rust-infected tree; the app answers
"No estoy seguro"). Two held-out CC BY-NC iNaturalist rust photos from Mexico (the app answers "roya") are downloaded on
the demo machine by `python3 model/demo_samples.py --field` and are not stored in the repo.

---

## 1. JMuBEN and JMuBEN2 (Kenya, Arabica): the training data

- **Source:** Jepkoech, Mugo, Kenduiywo & Too (2021), "Arabica coffee leaf images dataset for coffee leaf disease
  detection and classification", *Data in Brief* 36:107142, doi:[10.1016/j.dib.2021.107142](https://doi.org/10.1016/j.dib.2021.107142).
  The originals are on Mendeley Data, which is blocked here. We downloaded the AgML public copy:
  `https://agdata-data.s3.us-west-1.amazonaws.com/datasets/arabica_coffee_leaf_disease_classification.zip`.
- **Licence:** CC BY 4.0, per AgML's `source_citations.json` (read on GitHub, 2026-10-03).
- **Size:** 58,549 images. AgML lists the same number, and our scan found:
  - cercospora 7,681
  - minador (leaf miner) 16,978
  - phoma 6,571
  - roya (rust) 8,336
  - sano (healthy) 18,983

  Most images are 128×128 px close-up crops ([`model/README.md`](model/README.md)); a few are up to 256 px on one side.
- **Used for:** training, validation and test of the five coffee classes.
- **Processing** ([`model/prepare_data.py`](model/prepare_data.py)):
  1. **Near-duplicate grouping.** We took a 72-bit difference hash of an equalised 9×9 greyscale thumbnail, kept the
     minimum over the 8 flips/rotations, linked pairs with Hamming distance ≤ 8, and treated each connected component
     as one group. The 58,549 images collapse to **about 880 groups**: cercospora 78, minador 246, phoma 171, roya 373, **sano 11**.
  2. **Split 70/15/15 by group** within each class, seed 42.
  3. **Round-robin sub-sampling**, one image per group per round: up to 1,500 train, 300 validation and 500 test images per class.
  4. Centre square, resized to 224 px. Strong photometric augmentation during training.
- **What it does NOT cover:**
  - **Kenya only.** JMuBEN has no images from Mexico or Latin America. The brief planned BRACOL (Brazil) and RoCoLe
    (Ecuador). We could not download them (section 6). Besides JMuBEN, the shipped v2 has seen only 147 diseased
    iNaturalist field photos, about 86 of them from Latin America (Brazil, Central America, Colombia, Caribbean;
    *computed* from the coordinates in the attribution CSV) and none from Mexico or the Mexico+Guatemala box (section 4).
  - **Close-up 128 px crops, not phone photos.** It has no whole leaves, branches, backgrounds, hands, shadows or wet
    leaves. On field photos, v1 (trained on JMuBEN only) mostly said "not a coffee leaf"; that is why v2 adds field
    photos ([`METRICS.md`](METRICS.md) §4).
  - **Augmented copies.** The dataset repeats each photo as flipped, rotated and colour-shifted copies. 58,549 images
    are only about 880 distinct groups. A random split would leak copies into the test set ([`METRICS.md`](METRICS.md) §6).
  - **Very few healthy photos.** `sano` has 18,983 images, but only 14 exact source photos and 11 groups.
    The split puts 7 groups in train, 2 in validation and 2 in test, so the healthy class was learned from 7
    near-duplicate groups (about 7–10 distinct source photos). The field photos added for v2 are all diseased.
    A real healthy Chiapas leaf will most likely get DUDA, not "sano".
  - **Hazy rust crops.** On validation images the median blur score for rust is 16.2, against 381 for healthy and 432 for leaf miner
    ([`reports/model_eval.md`](reports/model_eval.md), blur table). A model could learn "haze = rust". We add haze and
    blur to every class during training to fight this, but we cannot rule it out.
  - **No severity**, no red spider mite (`acaro_rojo`), no Robusta, and no information on varieties, altitude or season.

## 2. PlantDoc: "not a coffee leaf" examples

- **Source:** Singh et al. (2020), "PlantDoc: A Dataset for Visual Plant Disease Detection", CoDS-COMAD,
  doi:[10.1145/3371158.3371196](https://doi.org/10.1145/3371158.3371196); https://github.com/pratikkayal/PlantDoc-Dataset.
  We used the AgML copy `plant_doc_classification.zip` from the same S3 bucket.
- **Licence:** the repo's `LICENSE.txt` is CC BY 4.0 (read on GitHub, 2026-10-03). AgML's metadata says CC BY-SA 4.0
  instead: **to be checked** before redistributing. The images were collected from the web, so the copyright of
  individual images is unclear. We do not redistribute any.
- **Size:** 2,569 images read (AgML lists 2,598), 28 classes, 13 crops: apple, bell pepper, blueberry, cherry, corn,
  grape, peach, potato, raspberry, soybean, squash, strawberry, tomato. The classes include healthy and diseased leaves.
- **Used for:** the `otro` class. These are hard negatives: they include rust on apple and corn, and spider mites on tomato.
- **Processing:**
  - every class maps to `otro`;
  - near-duplicate grouping gives 2,440 groups;
  - the split is by group;
  - each image gives two views, the whole photo and one random close-up crop (35–60 % of the short side), so `otro` is
    not just "a whole leaf in the frame".
- **What it does NOT cover:**
  - The plants around a Chiapas coffee plot: shade trees, banana, citrus, beans, local weeds. These are not in PlantDoc.
  - Phone photos taken by farmers. PlantDoc images come from web searches.
  - **Enough hard negatives.** The shipped v2 accepts 8 of 446 `otro` test images (7 distinct PlantDoc photos), mostly
    apple rust and apple scab leaves answered "roya" ([`reports/model_eval.md`](reports/model_eval.md) section (a)).

## 3. Imagenette: "not a plant" examples

- **Source:** fast.ai, https://github.com/fastai/imagenette, file `imagenette2-160.tgz`
  (`https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-160.tgz`).
- **Licence:** the repo is Apache-2.0, but the images are a subset of ImageNet, so **ImageNet terms apply
  (non-commercial research and education)**. If Cafetal is ever used commercially, retrain without Imagenette or replace
  it with openly licensed photos.
- **Size:** 700 photos, 70 from each of the 10 classes, with 160 px on the short side. They form 689 groups after near-duplicate grouping.
- **Used for:** the `otro` class.
- **What it does NOT cover:** the 10 classes are tench, English springer, cassette player, chain saw, church, French horn,
  garbage truck, gas pump, golf ball and parachute. None are the things a farmer is likely to photograph by mistake, such
  as soil, hands, sacks, tarps, cherries or flowers.

## 4. iNaturalist field photos: training of the shipped v2, threshold calibration, field test

- **Source:** iNaturalist open data. The metadata export was filtered to six taxa. The images come from the public
  `inaturalist-open-data` S3 bucket, at the `medium` size (about 500 px on the long side). Code:
  [`model/inat_field.py`](model/inat_field.py) (field set) and [`model/field_threshold.py`](model/field_threshold.py)
  (calibration sample).
- **Licence:** **per photo**: CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA or CC BY-NC-ND. Attribution for every photo
  (observer, licence, link) is in [`reports/field_inat_attribution.csv`](reports/field_inat_attribution.csv) (field set)
  and [`reports/field_calib_attribution.csv`](reports/field_calib_attribution.csv) (calibration sample). The images are
  **not** in the repo, because many are NC or ND. The only exception is one CC BY field-test photo in
  [`model/demo_samples/`](model/demo_samples/README.md), attributed there; the two CC BY-NC demo photos are downloaded
  on the demo machine and not redistributed.
- **The shipped model was trained on some of these photos.** Its 147 field-train photos are, by licence (*computed*
  from the two CSVs above): CC BY-NC 89, CC BY 38, CC BY-NC-ND 14, CC0 4, CC BY-NC-SA 2. Whether model weights trained
  on NC and ND photos may be shared or used commercially is **to be checked** before any product use; the fallback is
  to retrain v2 on the 42 CC0 / CC BY photos only.
- **Labels:** the taxon of each observation, which is the iNaturalist **community identification**, not an agronomist's
  diagnosis:

  | taxon | label |
  |---|---|
  | *Hemileia vastatrix* and genus *Hemileia* | roya |
  | *Leucoptera coffeella* | minador |
  | *Cercospora coffeicola* | cercospora |
  | *Mycena citricolor* (ojo de gallo; not a model class) | right answer is DUDA |
  | *Coffea arabica* | coffee plant, health unknown |

  Quality grades for rust: research 118, needs ID 100, casual 1.
- **Size of the field set:** 768 photos. One *Coffea* photo failed to download, so there are 399 *Coffea* photos instead of 400. From [`reports/field_eval.md`](reports/field_eval.md):

  | label | photos | observers | field-train / field-test | symptom clearly visible (screened) | inside Mexico | in Mexico+Guatemala box |
  |---|---|---|---|---|---|---|
  | roya | 219 | 62 | 166 / 53 | 164 | **4** | 31 |
  | minador | 30 | 9 | 21 / 9 | 24 | **2** | 2 |
  | cercospora | 30 | 11 | 20 / 10 | 16 | **0** | 5 |
  | ojo de gallo | 90 | 21 | 0 / 90 | 26 | **2** | 5 |
  | *Coffea arabica* | 399 | 399 | evaluation only | n/a | **37** | 46 |

  **Mexico subset:** 45 of the 768 photos fall inside Mexico (4 + 2 + 0 + 2 + 37, computed from the table). Only
  8 of them show a disease: 4 rust, 2 leaf miner and 2 ojo de gallo. All 45 are test photos; none was used for training.
- **Calibration sample (separate):** 400 more *Coffea arabica* photos, one per observer, from observers who appear
  nowhere in the field set ([`reports/field_v2_threshold_sweep.md`](reports/field_v2_threshold_sweep.md)). By licence
  (*computed* from the CSV): CC BY-NC 360, CC BY 22, CC BY-NC-SA 6, CC BY-SA 5, CC0 4, CC BY-NC-ND 3; 40 are inside Mexico.
- **Processing:**
  - **Split by observer** (seed 42). Every observer with any photo in the Mexico+Guatemala box is held out for the field test,
    plus a random ~30 % of the other observers of each disease. Ojo de gallo is always test. *Coffea*: one photo per
    observer, and none of them is a field-train observer.
  - **Mexico rule:** a point-in-polygon test on a simplified 52-vertex outline of Mexico, accurate to about 5–15 km at the
    borders. Checked on known towns: Unión Juárez, Ocosingo and Tapachula count as Mexico; Huehuetenango
    and Tecún Umán do not. It uses the observation's public coordinates. The attribution CSV stores them rounded.
  - **Screening:** one person looked at every disease photo on contact sheets of thumbnails. "yes" means a leaf
    symptom is clearly visible ([`reports/field_inat_screening.csv`](reports/field_inat_screening.csv)).
  - **v2 training:** the 147 field-train photos screened "yes" (roya 122, minador 15, cercospora 10; 43 observers,
    none in the Mexico+Guatemala box), 7 views each, oversampled ×2, added to the JMuBEN/PlantDoc/Imagenette training set.
  - **Threshold:** t = 0.90 was chosen on the calibration sample and the validation `otro` images only. 60 field-train
    photos screened "no" were looked at as a weak recall proxy and not used to choose t.
- **Used for:**
  - **training** the shipped v2 (147 photos);
  - **choosing its threshold** (the 400-photo calibration sample);
  - **the field test** (held out: rust 53, leaf miner 9, Cercospora 10, ojo de gallo 90, *Coffea* 399). v2 shipped at
    0.90 by a team decision that is an exception to the ship rule ([`METRICS.md`](METRICS.md) §4c). v1 never saw any of
    the 768 photos, so all of them count as a test for v1.
- **What it does NOT cover:**
  - **Chiapas.** Most photos are from other countries. Only 4 rust photos are from Mexico, and all are test photos.
  - **Photos taken the way the app asks**, with the leaf underside filling the frame. Many show whole plants, branches,
    microscope slides or very severe, textbook infections.
  - **Labelled healthy field leaves.** *Coffea* photos have unknown health, so we never used them as `sano`.
    This is why v2 gives false alarms: a disease answer for 2.5 % of the *Coffea* test photos at 0.90 (8.0 % at 0.70).
  - **Phoma.** No Phoma taxon was included, so the field test has no phoma photos and v2 saw no field phoma.
  - **A second rater.** Screening was done by one person, from thumbnails. 8 rust-labelled training photos look like
    Cercospora to that person; they were kept as rust.
  - **Blurry phone shots.** The blur check fired on 0 of the 768 photos.

## 5. iNatAg-mini *Coffea arabica* (evaluation only)

- **Source:** AgML iNatAg-mini, `https://agdata-data.s3.us-west-1.amazonaws.com/datasets/iNatAg-mini/coffea_arabica.zip`.
  The photos are from iNaturalist.
- **Licence:** recorded as CC BY-NC 4.0 in our evaluation code ([`model/evaluate.py`](model/evaluate.py)). The AgML
  `annotations.json` has no per-photo licence field. **To be checked.**
- **Size:** 200 photos of whole plants, flowers and cherries. Their disease status is unknown.
- **Used for:** evaluation only, section (e) of [`reports/model_eval.md`](reports/model_eval.md). The shipped v2 at
  0.90 answers DUDA for 93.5 % of them and gives a disease answer for 6.5 % (roya 5.5 %, minador 1.0 %); v1 answered
  DUDA for 100 %. Their health is unknown, so these answers are false alarms or real symptoms we cannot check.
  Never trained on (neither v1 nor v2), not shipped.
- **What it does NOT cover:** any disease labels, and close-ups of leaves.

## 6. BRACOL and RoCoLe: named in the brief, NOT used

- **Why not used:** both are on Mendeley Data, which the build machine cannot reach. The shipped model contains neither.
- **What they are** (from [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) §8.2; not checked by us):

  | | BRACOL | RoCoLe |
  |---|---|---|
  | citation | Esgario et al. 2020 | Parraga-Alava et al. 2019 |
  | DOI | doi:10.17632/yy2k5y8mxg.1 | doi:10.17632/c5yvn32dzg.2 |
  | crop | Arabica, Brazil | Robusta, Ecuador |
  | size | 1,747 images | 1,560 images |
  | classes | healthy, leaf miner, rust, phoma, cercospora | healthy, red spider mite, rust levels 1–4 |

- **Licence:** shown on each Mendeley page, which we could not open. **To be checked.**
- **What we lose without them:**
  - a labelled Latin-American lab dataset (v2 has only about 86 iNaturalist field photos from the region);
  - Robusta;
  - red spider mite (`acaro_rojo`);
  - rust **severity** levels. RoCoLe has rust levels 1–4. BRACOL's paper is about "severity estimation" too, but we have
    not seen its labels.
- **Manual download steps** (on a computer with normal internet):
  1. Open https://data.mendeley.com/datasets/yy2k5y8mxg/1 (BRACOL) and https://data.mendeley.com/datasets/c5yvn32dzg/2
     (RoCoLe). Write down the licence shown on each page, and click "Download All".
  2. Copy the zips to the build machine and unzip them to `/home/user/data_raw/bracol` and `/home/user/data_raw/rocole`.
  3. Rerun data preparation into a **new** output folder:
     ```bash
     python model/prepare_data.py --jmuben ... --plantdoc ... --negatives ... \
       --bracol /home/user/data_raw/bracol --rocole /home/user/data_raw/rocole --out /home/user/data_proc/cafetal_v3
     ```
  4. Train, export with `--app-dir` to a separate folder (not `app/model/`), evaluate, and run `model/field_eval.py`
     with the same ship rule ([`model/README.md`](model/README.md)). Copy to `app/model/` only if it passes, or record
     an explicit team exception in `model/ship_decision.json`, as was done for the shipped v2@0.90 ([`METRICS.md`](METRICS.md) §4c).
- **What the flags do (UNTESTED: they have never run on the real files):**
  - `--bracol` and `--rocole` accept class sub-folders whose names contain a keyword, or a CSV with a file column and a label column.
  - BRACOL's `predominant_stress` codes map as: 0 → sano, 1 → minador, 2 → roya, 3 → phoma, 4 → cercospora.
  - RoCoLe's `Multiclass.Label` maps as: healthy → sano, rust_level_1..4 → roya (**the severity level is dropped**),
    red_spider_mite → `acaro_rojo`. This adds a 7th class. The app reads the class list from `labels.json`.

## 7. Amazon MASSIVE 1.1, es-ES: off-topic SMS examples

- **Source:** https://github.com/alexa/massive, file
  `https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz`, locale `es-ES`, `train` partition.
- **Licence:** CC BY 4.0, © Amazon.com Inc. or its affiliates (the dataset's `LICENSE` file).
- **Size:** 300 utterances in [`data/intent/examples.csv`](data/intent/examples.csv), source `MASSIVE`.
- **Used for:** `otro` (off-topic) examples only. Intents and words that overlap ours (money, prices, coffee, calls,
  appointments, help, information) were filtered out ([`data/intent/README.md`](data/intent/README.md)).
- **What it does NOT cover:** Mexican Spanish, rural SMS style, typos, Tseltal. It is Spain Spanish about
  smart-speaker commands.

## 8. Hand-written SMS intent examples

- **Source:** written by the team, in [`data/intent/handwritten.csv`](data/intent/handwritten.csv), merged into `examples.csv`.
- **Licence:** project licence.
- **Size:** 275 messages:
  - 259 Spanish messages (`team`), written in a rural Mexican SMS style with typos, no accents and abbreviations;
  - 16 Tseltal messages drafted with AI (`ai-draft-unverified`) that **nobody has checked**.
- **Used for:** the SMS intent classifier, with an 80/20 split ([`reports/intent_eval.md`](reports/intent_eval.md)).
- **What it does NOT cover:**
  - real member messages;
  - real Tseltal: 16 unverified drafts are too few to measure;
  - mixed Spanish–Tseltal messages;
  - voice messages.

  The test split comes from the same writers as the training split, so real messages will score lower.

## 9. Reference prices (data/prices.json, DEMO)

- **Not AI.** All values are **DEMO** (`"demo": true`). Every figure was seen only in web-search summaries on 2026-10-03.
  The official pages (InfoAserca, SNIIM, Banxico, ICE) are blocked here. A person must check each value and set
  `demo=false` before real use.
- **How the values were derived:**

  | item | value | how |
  |---|---|---|
  | café pergamino | 94.0 MXN/kg (2026-09-30) | **International equivalent, not a market quote:** ICE "C" arabica 294.85 US¢/lb × 2.20462 lb/kg = 6.50 USD/kg green × 18.0710 MXN/USD (Banxico FIX) = 117.47 MXN/kg green × 0.80 kg green per kg parchment (**assumed**: 57.5 kg pergamino = 46 kg oro) = 93.97 → 94 |
  | maíz blanco | 9.0 MXN/kg (2026-09-09) | midpoint of the SNIIM wholesale range 8.00–10.00 MXN/kg (market not named in the summary) |
  | frijol negro | 24.9 MXN/kg (2026-09-17) | SNIIM wholesale modal price, Estado de México markets (range 17.00–46.47) |

- **Farm-gate vs reference:** these are national or international **reference** prices. They are **never** the price
  a buyer pays in Noor's valley, because quality, processing, transport and margin are not deducted. The press reported
  Chiapas producers being paid **45–48 MXN/kg** in Jan–Apr 2026, with the product form not stated
  ([`docs/evidence.md`](docs/evidence.md) §9, search snippet "S", unverified). The PRECIO SMS says "Precio de referencia
  … No es el precio de su comunidad" and names the source and date.
- **What it does NOT cover:** farm-gate prices, quality grades, local markets in the Chiapas highlands, price history,
  and an official coffee reference price (a committee created by a December 2025 law is due to publish one, per the
  context note in `prices.json`).

## 10. Piper TTS voices (Spanish, provisional Tseltal and English audio)

- **Source:** Piper offline TTS (https://github.com/rhasspy/piper) with two voices:
  - `es-mls_10246-low`: 16 kHz, 1 speaker, low quality, fine-tuned from the US-English "Ryan" voice (its `MODEL_CARD`).
  - `en-us-lessac-medium`: 22,050 Hz, 1 speaker, medium quality, trained from scratch (its `MODEL_CARD`). It is read
    with `--length_scale 1.4`, so it speaks at about 170 words a minute, like the Spanish audio.
- **Licence:** Piper is MIT (the repo's `LICENSE.md`, read 2026-10-03). The Spanish voice's `MODEL_CARD` names its
  training data as Multilingual LibriSpeech Spanish (http://www.openslr.org/94/, **CC BY 4.0**). The English voice's
  `MODEL_CARD` names the Blizzard Challenge 2013 Lessac dataset and links its licence page
  (https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html), which we could not open here.
  Neither card gives a separate licence for the voice weights: **to be checked**, for both voices.
  Piper uses espeak-ng to turn text into phonemes (`es-419` for Spanish and Tseltal, `en-us` for English). Only the
  generated MP3 files ship, not the 63 MB voice models.
- **Size:** 74 Spanish, 74 provisional Tseltal and 74 English MP3s (222 files), 24 kbps mono, about 3.5 MB in total
  ([`content/README.md`](content/README.md)). The 9 SMS and alert cards are text only.
- **Used for:** spoken Spanish for every UI, diagnosis and advice card. It is also a **stop-gap** for Tseltal: the
  Spanish voice reads the Tseltal text, marked `synthetic-provisional`. The English voice reads the English cards
  (section 11b).
- **What it does NOT cover:** a Mexican-accented speaker; we only switched phonemes to Latin-American `es-419`. It does not
  cover Tseltal sounds either: glottal stops and glottalised consonants are dropped, so it does not sound like a Tseltal speaker.

## 11. Tseltal content (AI draft)

- **Source:** all 83 cards in [`content/cards.json`](content/cards.json) have Tseltal text **drafted by an AI model**.
  The vocabulary was looked up word by word in Polian (2018), *Tseltal–Spanish multidialectal dictionary*, Dictionaria,
  https://dictionaria.clld.org/contributions/tseltal (**CC BY 4.0**). The grammar is a best guess
  ([`content/README.md`](content/README.md)). Exception: the two cards added on 2026-10-03
  (`ui_member_not_registered`, `ui_consent_hub_text`) reuse words from other cards plus loanwords; only a few of
  their words were looked up.
- **Status:** **83 of 83 cards are `unverified`** in Tseltal, and in Spanish and English as well. The app shows "SIN VERIFICAR" next to every
  unverified text and audio. A native speaker can verify a card or upload a recording on the hub's content page. A
  native recording is never overwritten by the audio script.
- **What it does NOT cover:**
  - review by a native speaker;
  - dialect variation: Tseltal differs a lot between towns, e.g. three words for "leaf" (*yabenal*, *ya'malel*, *wamal*);
  - whether an older woman who does not read Spanish understands it when it is played aloud;
  - real Tseltal audio.

## 11b. English content (AI translation, for judges and visitors)

- **What it is:** a third UI language, added so that international judges and visitors can follow the demo. Tseltal
  and Spanish remain the co-op's languages; no member is expected to use English.
- **Source:** all 83 cards have English text, an **AI translation of the Spanish cards** in plain, short sentences
  ([`content/README.md`](content/README.md)). The fail-safe reads exactly "I'm not sure — show the leaf to the
  extension officer." The 74 spoken cards have English audio from the Piper voice `en-us-lessac-medium` (section 10).
- **Status:** **83 of 83 English cards are `unverified`**. The app shows the UNVERIFIED badge next to them.
- **SMS:** English SMS cards advertise the keywords **PRICE, HELP, OFFICER**; the hub accepts them as well as PRECIO,
  AYUDA, TECNICO ([`hub/sms.py`](hub/sms.py) `KEYWORDS`). The co-op can register a member with language `en`, and the
  hub then replies in English. The SMS intent classifier has no English training examples, so English free text will
  mostly go to the officer.
- **What it does NOT cover:** review by an English speaker; the advice itself is only as good as the Spanish card it
  translates, which is unverified too.

## 12. Meta MMS Tseltal models (not used)

- **What exists** (read on the Hugging Face Hub, verified "F" in [`docs/evidence.md`](docs/evidence.md) §8):
  - **TTS:** `facebook/mms-tts-tzh` does **not** exist. Tseltal is available as two dialect checkpoints:
    `facebook/mms-tts-tzh-dialect_tenejapa` and `facebook/mms-tts-tzh-dialect_bachajon`. They are VITS models with 36.3 M
    parameters and a 145 MB file each, licence **CC BY-NC 4.0**.
  - **ASR:** `facebook/mms-1b-all` has Tseltal adapters for the same two dialects.
  - **Training data:** readings of religious texts, so the vocabulary is far from coffee and farming.
- **Why not used:** model files cannot be downloaded from Hugging Face on the build machine. The licence is also
  non-commercial, and the quality on farming words is unknown. A next step with normal internet: render the cards with
  the Tenejapa checkpoint, have a native speaker judge them, and keep them **UNVERIFIED** until then.
- **Other language resources checked, not used** (all "F" in [`docs/evidence.md`](docs/evidence.md) §8):
  - FLORES-200 / NLLB-200: Tseltal is not included.
  - Mozilla Common Voice: Tseltal is absent.
  - Google MADLAD-400: lists `tzh`, but at 2.94 B parameters it is too big for the phone, and we did not measure its quality.
  - `danvazquez20/tseltal`: Spanish–Tseltal sentence pairs, with no stated licence or provenance.

## 13. Evidence sources (problem statement)

Details, URLs and caveats are in [`docs/evidence.md`](docs/evidence.md). The codes mean: **F** = read on the primary
source; **L** = read from a local file; **S** = search snippet only, **unverified**; **D** = derived by us. Most rows are S:
the build machine could not open INEGI, World Bank, FAO, GSMA, USDA, ICO, IFT, SNIIM or OpenCelliD pages.

| source | what we cite | verified? | gap |
|---|---|---|---|
| Hackathon concept note, Annex B | extension officer visits "twice a year at best" | **L** | a scenario, not a statistic |
| GSMA Mobile Gender Gap 2025/2026; Connected Women blog | LMIC smartphone gaps; rural Mexican women 26 % less likely than rural men to own a phone (2021 survey) | S | no Chiapas or indigenous-women figure; the Mexico figure is from 2021 |
| World Bank Global Findex 2021/2025 | Mexico account ownership (49 % of adults, 2021) | S | no Mexico 2025 headline by gender found; mobile money not found |
| FAOSTAT | Mexico coffee yield trend | **not reached** | secondary sources disagree for 2022 (174,341 t vs 181,700 t); USDA attaché **forecasts** used instead (S/D) |
| INEGI: Census 2020, ENDUTIH 2025, ENA 2019, Censo Agropecuario 2007 | 589,144 Tseltal speakers; Chiapas households with internet 53.9 %; ~3 % of farms got technical assistance | S | figures not opened on INEGI; no Chiapas-highlands breakdown |
| IFT coverage diagnostics | mobile coverage of Tseltal localities | S | operator-declared maps, **modelled, not measured signal** |
| OpenCelliD | cell towers in Los Altos de Chiapas | **not queried** (blocked) | steps to check in [`docs/evidence.md`](docs/evidence.md), "How to close the gaps" |
| USDA FAS, SENASICA, SADER, INCAFECH, press | rust impact, producer counts, 77 campaign specialists | S | estimates and press reports; open each URL before quoting |
| Hugging Face Hub, FLORES, Common Voice | Tseltal AI support (section 12) | **F** | — |
| Mohanty, Hughes & Salathé 2016 | lab-to-field drop, 99.35 % → 31.4 % | **F** | other crops; context only |

Do not present an S figure as verified. Say "to be checked", or use the F/L/D rows.

## 14. DEMO hub data

- **Source:** [`hub/seed.py`](hub/seed.py). 24 fictional members in 4 fictional "Ondera" communities in the Chiapas highlands,
  with about 20 days of observations relative to today. Every seeded row has `demo=1`, and every name ends in "(DEMO)".
  Phone numbers are placeholders.
- **Used for:** showing the outbreak alert, the map and the officer worklist in the demo. The app and hub show a DEMO badge.
- **What it does NOT cover:** real members, real reports, real locations. The SMS gateway is SIMULATED.
- **Future data:** officer confirmations are stored in the hub's `labels` table as examples for retraining. It holds
  no real confirmations yet.

---

## Gaps (what our data does not cover)

1. **No Chiapas photos.** The model is trained on Kenyan Arabica crops plus 147 diseased iNaturalist field photos from
   other countries. The field test has 768 iNaturalist photos, but only 4 rust and 2 leaf-miner photos from Mexico,
   and **0** photos taken by the team.
2. **Field conditions are untested where it matters.** Messy backgrounds, shade, wet leaves, cheap phone cameras and
   the photos Noor's daughter would take have never been tested. On held-out iNaturalist field photos the shipped v2
   answers 34 of 53 rust photos correctly (64.2 %; v1: 0). The rest get "No estoy seguro". It names leaf miner in 2 of
   9 photos and Cercospora in 0 of 10.
3. **No labelled healthy field leaves.** `sano` was learned from 7 near-duplicate groups of Kenyan photos (about 7–10
   distinct source photos). Healthy Chiapas leaves will mostly get DUDA, and some will get a false disease answer:
   v2 gives one for 2.5 % of the iNaturalist *Coffea* test photos, because all its field training photos are diseased.
4. **Leaf symptoms only.** The app cannot see coffee berry borer (*broca*), nutrient deficiency, drought, old trees or
   soil problems, any of which could explain Noor's lower yield. The card `limits_yield` says so and points to the officer.
5. **Severity only in RoCoLe (not used).** The model has no severity output. BRACOL may have severity labels too, but it is not used either.
6. **`acaro_rojo` (red spider mite) is not in the model.** It is only in RoCoLe. The card exists, but the model never outputs it.
7. **Phoma has no field test.** Cercospora has 10 held-out field photos, and v2 got none of them right (2 called roya).
8. **Tseltal speech data is scarce.** There is no Common Voice data and no FLORES. MMS has only two dialects, non-commercial and
   trained on Bible readings. Our Tseltal text is an AI draft, and our Tseltal audio is a Spanish voice. Everything is
   UNVERIFIED, including the English cards for visitors.
9. **Real SMS language is missing.** Intent examples are team-written. Tseltal free text is effectively untested.
10. **Prices are references, not farm-gate.** They are international or wholesale equivalents, all DEMO, all seen only in search
    snippets. Reported Chiapas farm-gate prices (45–48 MXN/kg, unverified) are far below the reference.
11. **All sample data is DEMO.** This covers members, observations, the outbreak and the SMS gateway (SIMULATED).
12. **Licences need a check before any product use.** These are: Imagenette (ImageNet terms), PlantDoc (CC BY vs CC BY-SA),
    the iNaturalist NC/ND photos **the shipped v2 was trained on** (105 of its 147 field photos), iNatAg-mini, both
    Piper voices' weights (and the Lessac data licence for English), and the Meta MMS models (NC).

**How these gaps close.** First, the extension officer confirms or rejects reports in the hub. Those confirmations become
labelled Chiapas photos, healthy and diseased, taken with the app. They go into `data/field_test/` and, later, into
training. Then rerun the field protocol and ship rule ([`model/README.md`](model/README.md)), and record any exception
openly, as for the shipped v2@0.90 (`model/ship_decision.json`). In parallel, a native Tseltal
speaker from the co-op's area reviews the 83 cards and records the 74 spoken ones ([`content/README.md`](content/README.md)).
