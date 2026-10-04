# Cafetal data card

Every dataset and resource Cafetal uses, or chose not to use. For each one: source, licence, size, what we used it for,
how we processed it, and **what it does not cover**. Results are in [`METRICS.md`](METRICS.md). Numbers come from
[`reports/`](reports/), [`docs/evidence.md`](docs/evidence.md) (with its verification codes) or the data files named in
each section. Our users are smallholder coffee farmers of a (fictional) co-operative society in **Kirinyaga County,
central Kenya**.

**Network note.** The build machine could not reach Mendeley Data, Kaggle, iNaturalist's website, file downloads from
Hugging Face (only Hub metadata could be read, through a connector), or most statistics and press sites (KNBS, the
Communications Authority, KAMIS, AFA, KALRO, FAO, the World Bank and others; [`docs/evidence.md`](docs/evidence.md)).
It could reach PyPI/npm, GitHub and public S3 buckets. That decided several choices below.

## Summary

| # | dataset / resource | used for | licence | size used | in the shipped app? |
|---|---|---|---|---|---|
| 1 | JMuBEN + JMuBEN2 (Mutira, Kirinyaga, Kenya) | train / validate / test the image model (5 coffee classes); the main held-out test, from our users' county | CC BY 4.0 | 58,549 images, about 880 distinct groups | model weights only |
| 2 | PlantDoc | `otro` (not a coffee leaf) | CC BY 4.0 per the repo; AgML says CC BY-SA 4.0 (to be checked) | 2,569 images | model weights only |
| 3 | Imagenette | `otro` (not a plant) | ImageNet terms (non-commercial research) | 700 images | model weights only |
| 4 | iNaturalist field photos | **trains the shipped v2** (147 photos, none from East Africa); threshold calibration (400 *Coffea* photos); field test (every disease photo from the Americas) | per photo: CC0 to CC BY-NC-ND | 768 + 400 photos | model weights only (one CC BY demo photo is in the repo) |
| 5 | iNatAg-mini *Coffea arabica* | evaluation only | CC BY-NC 4.0 (to be checked) | 200 photos | no |
| 6 | BRACOL, RoCoLe | **not used** (Mendeley blocked) | to be checked | — | no |
| 7 | Amazon MASSIVE 1.1, en-US and sw-KE | `other` examples for the SMS intent classifier | CC BY 4.0 | 400 utterances (200 + 200) | classifier weights only |
| 8 | Hand-written SMS examples (team English and Kiswahili, AI-draft Gĩkũyũ) | SMS intent classifier | project | 472 messages | classifier weights only |
| 9 | Reference prices, KES | PRICE / BEI reply (not AI) | public sources, **all DEMO** | 3 prices | yes (DEMO) |
| 10 | Piper TTS, voice `en-us-lessac-medium`, with espeak-ng phonemes | English audio; **provisional** Kiswahili and Gĩkũyũ audio | Piper MIT; voice data: Lessac licence (to be checked) | 222 MP3 files, 2.91 MB | yes (MP3 only) |
| 11 | English card text (team-written, the main language) | every screen, diagnosis, advice and SMS | project | 83 cards | yes (UNVERIFIED) |
| 11b | Kiswahili and Gĩkũyũ card text (AI drafts) | the same cards in the national and the local language | project | 83 cards each | yes (UNVERIFIED) |
| 12 | Meta MMS Kiswahili and Gĩkũyũ models; other language resources | **not used** | CC BY-NC 4.0 (MMS) | — | no |
| 13 | Evidence sources (CA/KNBS, Findex, AFA, USDA, KALRO-CRI review, KAMIS, …) | problem evidence | various | see [`docs/evidence.md`](docs/evidence.md) | no |
| 14 | DEMO hub data | demo of the co-op hub | project | 24 fictional members in Kirinyaga | yes (DEMO) |

The image model also starts from **ImageNet-pretrained MobileNetV3-Small weights** from Keras Applications
(code Apache-2.0; the weights were trained on ImageNet). No dataset images ship in the app. For the demo,
[`model/demo_samples/`](model/demo_samples/README.md) holds 10 held-out JMuBEN test crops plus one blurred copy of one
of them (CC BY 4.0), and one held-out CC BY iNaturalist field photo (a whole rust-infected tree; the app answers
"I'm not sure", code `OTHR`). Two held-out CC BY-NC iNaturalist rust photos from Latin America (the app answers
`RUST`) are downloaded on the demo machine by `python3 model/demo_samples.py --field` and are not stored in the repo.
There is no East African field photo of a coffee disease to use instead (section 4).

---

## 1. JMuBEN and JMuBEN2 (Kirinyaga, Kenya, Arabica): the training data

- **Source:** Jepkoech, Mugo, Kenduiywo & Too (2021), "Arabica coffee leaf images dataset for coffee leaf disease
  detection and classification", *Data in Brief* 36:107142, doi:[10.1016/j.dib.2021.107142](https://doi.org/10.1016/j.dib.2021.107142).
  The originals are on Mendeley Data, which is blocked here. We downloaded the AgML public copy:
  `https://agdata-data.s3.us-west-1.amazonaws.com/datasets/arabica_coffee_leaf_disease_classification.zip`.
- **Where it was photographed:** in the **Mutira coffee plantation, Kirinyaga County**, "under real-world conditions"
  with a digital camera and the help of a pathologist. That place comes from a search snippet of the paper's abstract
  (code **S** in [`docs/evidence.md`](docs/evidence.md) §3b): check it in the paper before quoting it. That the dataset
  is Kenyan is read in AgML's metadata (code **F**, same section).
- **Why it matters for us:** the leaves come from **our users' own county**. A model trained and tested on leaves from
  another continent would leave a bigger question open. It still does not make the test a field test (see below).
- **Licence:** CC BY 4.0, per AgML's `source_citations.json` (read on GitHub, 2026-10-03).
- **Size:** 58,549 images. AgML lists the same number, and our scan found:
  - cercospora (brown eye spot) 7,681
  - minador (leaf miner) 16,978
  - phoma 6,571
  - roya (leaf rust) 8,336
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
  - **One plantation, one camera.** Smallholder farms differ from a single plantation photographed with a pathologist,
    and the dataset gives no varieties, altitude or season.
  - **Close-up 128 px crops, not phone photos.** It has no whole leaves, branches, backgrounds, hands, shadows or wet
    leaves. On field photos, v1 (trained on JMuBEN only) mostly said "not a coffee leaf"; that is why v2 adds field
    photos ([`METRICS.md`](METRICS.md) §4).
  - **Augmented copies.** The dataset repeats each photo as flipped, rotated and colour-shifted copies. 58,549 images
    are only about 880 distinct groups. A random split would leak copies into the test set ([`METRICS.md`](METRICS.md) §6).
  - **Very few healthy photos.** `sano` has 18,983 images, but only 14 exact source photos and 11 groups.
    The split puts 7 groups in train, 2 in validation and 2 in test, so the healthy class was learned from 7
    near-duplicate groups (about 7–10 distinct source photos). The field photos added for v2 are all diseased.
    A real healthy leaf photographed on a farm will most likely get the fail-safe, not "healthy": neither model said
    "healthy" for any of the 399 iNaturalist *Coffea* photos ([`METRICS.md`](METRICS.md) §4a).
  - **Hazy rust crops.** On validation images the median blur score for rust is 16.2, against 381 for healthy and 432 for leaf miner
    ([`reports/model_eval.md`](reports/model_eval.md), blur table). A model could learn "haze = rust". We add haze and
    blur to every class during training to fight this, but we cannot rule it out.
  - **No severity**, no red spider mite (`acaro_rojo`), no Robusta, and **no berries**: coffee berry disease, one of
    Kenya's two major coffee diseases ([`docs/evidence.md`](docs/evidence.md) §4, S), attacks the berries, and the
    model only sees leaves.
  - **Other field photos.** Besides JMuBEN, the shipped v2 has seen only 147 diseased iNaturalist field photos, none
    from East Africa (section 4).

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
  - Many plants a farmer could photograph by mistake around a coffee farm, such as banana, shade trees or weeds.
    PlantDoc has corn, but none of these.
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
  | *Hemileia vastatrix* and genus *Hemileia* | roya (leaf rust) |
  | *Leucoptera coffeella* | minador (leaf miner) |
  | *Cercospora coffeicola* | cercospora (brown eye spot) |
  | *Mycena citricolor* (American leaf spot, "ojo de gallo"; not a model class) | right answer is the fail-safe (UNSR) |
  | *Coffea arabica* | coffee plant, health unknown |

  Quality grades for rust: research 118, needs ID 100, casual 1.
- **Size of the field set:** 768 photos. One *Coffea* photo failed to download, so there are 399 *Coffea* photos
  instead of 400. From [`reports/field_eval.md`](reports/field_eval.md) (region rule: East Africa = the box lat −11.8 to
  15.0, lon 28.8 to 48.0; Kenya = a simplified 34-point outline; both on the 0.1° rounded coordinates):

  | label | photos | observers | field-train / field-test | symptom clearly visible (screened) | in East Africa | in Kenya |
  |---|---|---|---|---|---|---|
  | roya | 219 | 62 | 166 / 53 | 164 | **0** | **0** |
  | minador | 30 | 9 | 21 / 9 | 24 | **0** | **0** |
  | cercospora | 30 | 11 | 20 / 10 | 16 | **0** | **0** |
  | American leaf spot | 90 | 21 | 0 / 90 | 26 | **0** | **0** |
  | *Coffea arabica* | 399 | 399 | evaluation only | n/a | **6** | **3** |

  **No disease photo from East Africa, in any split.** All 162 diseased field-test photos are from the Americas (Latin
  America, the Caribbean and Hawaii). The whole iNaturalist export the photos were drawn from has 266 observations in
  the East Africa box, all *Coffea arabica* and none a disease (*computed*, `reports/field_eval.md`). The 6 East African
  *Coffea* photos are near Nakuru, near Limuru and in the Taita Hills (Kenya), on Kilimanjaro and Zanzibar (Tanzania)
  and on Lake Kivu (most likely Rwanda); places read by eye from the coordinates.
- **Where v2's 147 training photos come from** (*computed* from the coordinates in the attribution CSV; country or area
  read from the rounded coordinates): Latin America and the Caribbean 86 (southern Brazil and neighbouring areas 54,
  Central America 23, Colombia 5, Caribbean 4), Asia 30 (Taiwan 21, southern China 7, Sumatra 2), Hawaii 27, Florida 3,
  South Africa 1, **East Africa 0**.
- **Calibration sample (separate):** 400 more *Coffea arabica* photos, one per observer, from observers who appear
  nowhere in the field set ([`reports/field_v2_threshold_sweep.md`](reports/field_v2_threshold_sweep.md)). By licence
  (*computed* from the CSV): CC BY-NC 360, CC BY 22, CC BY-NC-SA 6, CC BY-SA 5, CC0 4, CC BY-NC-ND 3. 5 are in the
  East Africa box and **0 in Kenya** (*computed* with the same region rule).
- **Processing:**
  - **Split by observer** (seed 42). Every observer with any disease photo in a fixed box over Mexico and northern
    Central America (lat 14.5 to 32.7, lon −118.4 to −86.7) is held out for the field test, plus a random ~30 % of the
    other observers of each disease. The box was fixed before any v2 result and is kept so the test set stays the same;
    it has no special meaning for Kenya. American leaf spot is always test. *Coffea*: one photo per observer, and none
    of them is a field-train observer.
  - **Region subsets for the reports** (East Africa box, Kenya outline; `model/field_eval.py`) only describe where the
    photos come from. They never change the split, the training data or the threshold.
  - **Screening:** one person looked at every disease photo on contact sheets of thumbnails. "yes" means a leaf
    symptom is clearly visible ([`reports/field_inat_screening.csv`](reports/field_inat_screening.csv)).
  - **v2 training:** the 147 field-train photos screened "yes" (roya 122, minador 15, cercospora 10; 43 observers,
    none in the split box), 7 views each, oversampled ×2, added to the JMuBEN/PlantDoc/Imagenette training set.
  - **Threshold:** t = 0.90 was chosen on the calibration sample and the validation `otro` images only. 60 field-train
    photos screened "no" were looked at as a weak recall proxy and not used to choose t.
- **Used for:**
  - **training** the shipped v2 (147 photos);
  - **choosing its threshold** (the 400-photo calibration sample);
  - **the field test** (held out: rust 53, leaf miner 9, Cercospora 10, American leaf spot 90, *Coffea* 399). v2 shipped
    at 0.90 by a team decision that is an exception to the ship rule ([`METRICS.md`](METRICS.md) §4c). v1 never saw any
    of the 768 photos, so all of them count as a test for v1.
- **What it does NOT cover:**
  - **Kenya, or East Africa at all, for diseases.** It is a test of field photos in general, not of our users' photos.
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
  0.90 gives the fail-safe for 93.5 % of them and a disease answer for 6.5 % (roya 5.5 %, minador 1.0 %); v1 gave the
  fail-safe for 100 %. Their health is unknown, so these answers are false alarms or real symptoms we cannot check.
  Never trained on (neither v1 nor v2), not shipped.
- **What it does NOT cover:** any disease labels, close-ups of leaves, and any known location.

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
  - a second, independent labelled dataset, which would show whether the model works beyond one plantation;
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

## 7. Amazon MASSIVE 1.1, en-US and sw-KE: off-topic SMS examples

- **Source:** https://github.com/alexa/massive, file
  `https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz`, locales `en-US` and `sw-KE`
  (Kenyan Kiswahili), `train` partition.
- **Licence:** CC BY 4.0, © Amazon.com Inc. or its affiliates (the dataset's `LICENSE` file).
- **Size:** 400 utterances in [`data/intent/examples.csv`](data/intent/examples.csv), 200 per locale, source `MASSIVE`.
  The sw-KE locale has 16,521 utterances in all (F, [`docs/evidence.md`](docs/evidence.md) §8).
- **Used for:** `other` (off-topic) examples only. Intents (`qa_currency`, `qa_stock`, `iot_coffee`, `weather_query`,
  `takeaway_*`) and words that overlap ours (money, prices, coffee, crops, calls, visits, help, information) were
  filtered out ([`data/intent/README.md`](data/intent/README.md)).
- **What it does NOT cover:** farmer SMS style, sheng, typos, and Gĩkũyũ: MASSIVE has no Gĩkũyũ locale (F,
  [`docs/evidence.md`](docs/evidence.md) §8). It is smart-speaker commands in US English and Kenyan Kiswahili.

## 8. Hand-written SMS intent examples

- **Source:** written by the team, in [`data/intent/handwritten.csv`](data/intent/handwritten.csv), merged into `examples.csv`.
- **Licence:** project licence.
- **Size:** 472 messages:
  - 227 English and 228 Kiswahili messages (`team`), written in the style of Kenyan farmer SMS: sheng (e.g. "iko
    aje"), typos, no diacritics, abbreviations. The build team includes AI agents. **No native Kiswahili speaker has
    checked them**, and none comes from a real member ([`data/intent/README.md`](data/intent/README.md));
  - 17 Gĩkũyũ messages drafted with AI (`ai-draft-unverified`) that **nobody has checked**.
- **Intents:** `price`, `report`, `help`, `talk_to_officer`, `other`.
- **Used for:** the SMS intent classifier, with an 80/20 split ([`reports/intent_eval.md`](reports/intent_eval.md)).
- **What it does NOT cover:**
  - real member messages;
  - real Gĩkũyũ: 17 unverified drafts are too few to measure (4 in the test split);
  - mixing of English, Kiswahili and Gĩkũyũ beyond what the team wrote;
  - voice messages.

  The test split comes from the same writers as the training split, so real messages will score lower.

## 9. Reference prices (data/prices.json, DEMO)

- **Not AI.** All values are **DEMO** (`"demo": true`), in Kenyan shillings (KES). Every figure was seen only in
  web-search summaries on 2026-10-04. The source pages (KAMIS, the county government and press sites, Nairobi Coffee
  Exchange reports) are blocked here. A person must open each `source_url`, check the value and its date, and set
  `demo=false` before real use.
- **The values** ([`data/prices.json`](data/prices.json); background in [`docs/evidence.md`](docs/evidence.md) §9):

  | item | value | what it is |
  |---|---|---|
  | coffee cherry | 139.00 KES/kg of cherry | Kirinyaga County **average** paid to farmers over the 2025/26 season (range KES 104 to 157.40 across societies and factories), press reports of late April / May 2026 |
  | dry maize | 51.11 KES/kg | KAMIS **wholesale** price, Kirinyaga; market and date not shown in the summary |
  | beans (Rosecoco) | 111.11 KES/kg | KAMIS **wholesale** price, Kirinyaga; market and date not shown in the summary |

  The PRICE / BEI SMS names the source as "DEMO county 25/26, KAMIS" and the year as "2026" (`sms_fuente`,
  `sms_fecha`). The coffee item also records an **auction** reference, which the SMS does not send: Nairobi Coffee
  Exchange Sale 42 (2026-09-29), KES 38,140 per 50-kg bag of **clean** coffee; one other summary said about KES 47,000
  for the same sale, so the NCE report must be checked.
- **Reference, never farm-gate:** each factory pays its own rate per kg of cherry, months after delivery and after
  milling, marketing and society costs; maize and beans are wholesale, not what a trader pays at the farm. Auction
  prices are per bag of clean coffee, not cherry, and we do not convert one into the other. The SMS says "Reference
  price … Not the price at your factory." and names the source and date.
- **What it does NOT cover:** the rate at a member's own factory, payment dates, quality grades, price history, and
  dated quotes from named local markets. Maize snippets conflict with each other ([`docs/evidence.md`](docs/evidence.md) §9).

## 10. Piper TTS voice (English audio, provisional Kiswahili and Gĩkũyũ audio)

- **Source:** Piper offline TTS (https://github.com/rhasspy/piper) with the voice `en-us-lessac-medium`: 22,050 Hz,
  1 speaker, medium quality, trained from scratch (its `MODEL_CARD`). Piper turns text into phonemes with espeak-ng.
- **How each language is made** ([`scripts/make_audio.py`](scripts/make_audio.py), [`content/README.md`](content/README.md)):
  - **English:** the voice with its own `en-us` phonemes, `--length_scale 1.4` (about 170 words a minute).
    `audio_source` `synthetic:piper-en-us-lessac-medium`.
  - **Kiswahili, provisional:** the same English voice fed Kiswahili phonemes from espeak-ng `sw`, `--length_scale 1.25`,
    with `j` respelled `dy` for the voice. `synthetic-provisional:piper-en-us-lessac-medium-espeak-sw`.
  - **Gĩkũyũ, provisional:** the same voice and Kiswahili phonemes reading the Gĩkũyũ text with ĩ → e and ũ → o for
    the voice only (espeak-ng has no Gĩkũyũ dictionary, [`docs/evidence.md`](docs/evidence.md) §8, L). Tones are not
    produced. `synthetic-provisional:piper-en-us-lessac-medium-espeak-sw-reading-gikuyu`.
  - The Spanish Piper voice on the build machine was also tried for Kiswahili. It covers slightly more of the sounds
    (96.5 % vs 95.2 %) but spoke at 61 words a minute with 1.39 silent gaps per word, against 136 and 0.66 for the
    English voice. These are *computed* checks; nobody listened. It is not used in any shipped file.
- **Licence:** Piper is MIT (the repo's `LICENSE.md`, read 2026-10-03). The English voice's `MODEL_CARD` names the
  Blizzard Challenge 2013 Lessac dataset and links its licence page
  (https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html), which we could not open here,
  and gives no separate licence for the voice weights: **to be checked**. The espeak-ng licence was not checked here.
  Only the generated MP3 files ship, not the voice model.
- **Size:** 222 MP3s (74 per language), 24 kbps mono, **2.91 MB** in total: English 0.92 MB, Kiswahili 1.02 MB,
  Gĩkũyũ 0.97 MB ([`content/README.md`](content/README.md)). The 9 SMS and alert cards are text only.
- **What it does NOT cover:** a Kenyan English accent (the voice is American); Kiswahili and Gĩkũyũ as a native speaker
  says them: the English voice has no rolled *r* and no *ny* (computed phoneme check), Gĩkũyũ tones are missing, and
  the Kiswahili and Gĩkũyũ audio will have a foreign accent and mispronounced words. **Nobody has listened to the
  Kiswahili or Gĩkũyũ audio.**

## 11. English content (the main language)

- **What it is:** all 83 cards in [`content/cards.json`](content/cards.json), written by the team in plain, short
  sentences for low literacy, in Kenyan English (*extension officer*, *co-op*, *factory*, prices in *KES*). English is
  the app's default language. 74 cards are spoken (section 10). About 917 words.
- **Advice sources:** each card's `source` field. Mainly the KALRO Coffee Research Institute review of coffee leaf rust in
  Kenya (*Agronomy* 2021), CABI Plantwise factsheets, Infonet-Biovision and the Kenya Coffee Sustainability Manual
  ([`content/README.md`](content/README.md)). **These pages were seen only through search summaries** (every card says
  so). No card names a pesticide or a dose; the resistant varieties Ruiru 11 and Batian appear only as something to
  ask the officer about.
- **Fixed sentences:** the fail-safe reads exactly "I'm not sure — show the leaf to the extension officer."
  `limits_yield` says the app only looks at leaves and cannot see coffee berry disease on the berries, antestia bugs,
  berry borer, lack of fertiliser, drought, old trees or soil problems.
- **Status:** **83 of 83 cards are `unverified`** in every language. The app shows "UNVERIFIED" next to unverified text
  and audio. An agronomist or extension officer can verify a card on the hub's Content page.
- **SMS:** the English SMS cards advertise PRICE, HELP and OFFICER, and also the Kiswahili BEI, MSAADA and AFISA
  (`sms_ayuda`).
- **What it does NOT cover:** review by an agronomist (the advice) or by co-op staff (is it clear for members?).

## 11b. Kiswahili and Gĩkũyũ content (AI drafts)

- **Kiswahili** (`sw`, the national language): all 83 cards, an **AI draft** in standard Kiswahili, about 796 words.
  Nobody who speaks Kiswahili has read it. A few terms (*kutu ya majani*, *chule buni*, *afisa ugani*) were seen in
  Kiswahili extension writing through a search summary; the rest are the AI model's choices
  ([`content/README.md`](content/README.md)).
- **Gĩkũyũ** (`kik`, the local language of central Kenya): all 83 cards, an **AI draft, best effort, low confidence**,
  about 855 words. It was written without any Gĩkũyũ dictionary that the build machine could open. Expect wrong words,
  wrong noun-class agreement and unnatural phrasing.
- **SMS:** the Gĩkũyũ SMS cards write ĩ and ũ as i and u to stay in GSM-7. In Meta's Gĩkũyũ text counts, ĩ and ũ are
  17 % of all letters (F counts, D share; [`docs/evidence.md`](docs/evidence.md) §6), so SMS Gĩkũyũ merges vowels the
  language keeps apart. The app's screens and audio keep ĩ and ũ. There are no Gĩkũyũ SMS keywords; the Gĩkũyũ cards
  advertise the English and Kiswahili ones.
- **Status:** **83 of 83 cards `unverified`** in both languages, marked as AI drafts in
  [`content/README.md`](content/README.md). The app shows *HAIJAHAKIKIWA* (Kiswahili) or *NDĨRATHUTHURIO* (Gĩkũyũ),
  the drafts of "UNVERIFIED", next to them. A native speaker can verify a card or record it on the hub's Content page;
  a native recording is never overwritten by the audio script.
- **What it does NOT cover:**
  - review by native speakers, ideally from Kirinyaga;
  - whether the words are the ones farmers there really use (loanwords such as *afisa*, *sosaiti*, *kiwanda*, *kutu*
    are listed for the reviewer to check);
  - whether an older woman who reads little understands it when it is played once;
  - real Kiswahili or Gĩkũyũ audio.

## 12. Meta MMS and other language resources (not used)

What exists for our two non-English languages (all read on the source, code **F** in
[`docs/evidence.md`](docs/evidence.md) §8, checked 2026-10-04):

| resource | Kiswahili | Gĩkũyũ |
|---|---|---|
| Meta MMS text-to-speech | `facebook/mms-tts-swh`, VITS, about 145 MB | `facebook/mms-tts-kik`, VITS, about 145 MB |
| Meta MMS speech recognition (`facebook/mms-1b-all`) | adapter `swh` | adapter `kik` |
| FLORES-200 (NLLB-200 is trained and evaluated on it) | `swh_Latn` | `kik_Latn` |
| Google MADLAD-400 translation | lists `sw` | not listed |
| Mozilla Common Voice v27.0 | 392.2 validated hours | **absent** |
| Amazon MASSIVE 1.1 | `sw-KE`, 16,521 utterances | absent |

- **Licences and limits:** the MMS models and `facebook/nllb-200-distilled-600M` are **CC-BY-NC-4.0
  (non-commercial)**. MMS was trained on readings of religious texts, so its farming vocabulary is unknown. We did not
  measure the quality of any of them.
- **Community Gĩkũyũ data on the Hugging Face Hub** (metadata only, quality and provenance not checked):
  `DigiGreen/KikuyuASR_trainingdataset` (agricultural sentences recorded by extension workers and farmers) and
  `CGIAR/KikuyuEnglish_translation` (agricultural sentence pairs), both Apache-2.0.
- **Why not used:** model and dataset files cannot be downloaded from Hugging Face on the build machine. The MMS and
  NLLB licences are non-commercial, the TTS models are too big for the phone (fine for pre-rendering at the hub), and
  their quality on farming words is unknown.
- **Next step, with normal internet:** render the cards once with `mms-tts-swh` and `mms-tts-kik` on a laptop, have a
  native speaker compare them with the provisional audio, and keep everything **UNVERIFIED** until a person checks it.
  Native recordings remain the goal.

## 13. Evidence sources (problem statement)

Details, URLs and caveats are in [`docs/evidence.md`](docs/evidence.md). The codes mean: **F** = read on the primary
source; **L** = read from a local file; **S** = search snippet only, **unverified**; **D** = derived by us. Most rows are
S: the build machine could not open KNBS, CA, GSMA, World Bank, FAO, USDA, AFA, KALRO, KAMIS, the Kenyan press or
OpenCelliD pages.

| source | what we cite | verified? | gap |
|---|---|---|---|
| Hackathon concept note, Annex B | extension officer visits "twice a year at best" | **L** | a scenario, not a statistic |
| CA & KNBS ICT report on the 2023/24 Kenya Housing Survey | phone ownership 53.7 % (rural 48.6 %), Kirinyaga 65.0 %; rural women's internet use 21.7 % vs rural men's 28.3 % (about 23 % less likely, D) | S | read through press summaries only |
| Global Findex 2025; FinAccess 2024; CA | 87.5 % of adults have a mobile money account, women at parity; 84.8 % formally included | S | no rural Findex figure found |
| KNBS, AFA, USDA FAS, KIPPRA | output 128,862 t (1987/88) → 48,700 t (2023), about −62 % (D); about 71 % via co-operatives (D); USDA forecast 950,000 bags for 2026/27 | S / D | **no FAOSTAT pull**; USDA revises its own figures; KIPPRA's "70 %" does not match its endpoints |
| KALRO-CRI rust review (*Agronomy* 2021); variety and adoption sources | rust can cut yields by more than 75 % in severe outbreaks; spraying takes 30–40 % of costs; Ruiru 11 and Batian; 27.5 % adoption in one Nyeri sub-county | S | open each URL before quoting |
| Ministry extension manual / KASEP; Kilimo Trust | about 1 public extension worker per 1,380 farmers vs a 1:600 target; fewer than 5,000 officers for over 8 million farmers | S | which document states 1:1,380 is not confirmed; no Kirinyaga figure |
| Constitution Art. 7; KNBS 2019 census; 2006 literacy survey | Kiswahili national, Kiswahili and English official; 8.1 million Kikuyu (ethnicity, **not** a speaker count); 61.5 % tested minimum adult literacy | S | the literacy test is from 2006; no literacy figure in Gĩkũyũ |
| CA sector statistics, June 2026 | 4G covers 97.3 % of the population (operator-declared, **not measured signal**); 52.3 M smartphones vs 27.4 M feature phones, one device in three a feature phone (D) | S / D | devices, not people |
| OpenCelliD | cell towers around Ondera | **not queried** (blocked) | Kenya's mobile country code 639 is F; steps in [`docs/evidence.md`](docs/evidence.md), "How to close the gaps" |
| NCE sale reports, county payouts, KAMIS | price references (section 9) | S | dates often missing; maize snippets conflict |
| Hugging Face Hub, FLORES, Common Voice, MASSIVE, AgML metadata | language resources (section 12); JMuBEN is Kenyan | **F** | — |
| Mohanty, Hughes & Salathé 2016 | lab-to-field drop, 99.35 % → 31.4 % | **F** | other crops; context only |

Do not present an S figure as verified. Say "to be checked", or use the F/L/D rows.

## 14. DEMO hub data

- **Source:** [`hub/seed.py`](hub/seed.py). 24 fictional members, with made-up Kenyan (mostly Kikuyu) names, in the 4
  fictional communities Ondera Juu, Ondera Chini, Ondera Mto and Ondera Kilima, placed in Kirinyaga County between lat
  −0.45 and −0.58 and lon 37.20 and 37.40, with about 20 days of observations relative to today. Noor is member M0123
  in Ondera Juu, phone +254700000123, SMS language English. SMS languages: 8 English, 8 Kiswahili, 8 Gĩkũyũ. Every
  seeded row has `demo=1`, every name ends in "(DEMO)", and the phone numbers (+254700000101 to +254700000124) are
  placeholders.
- **Used for:** showing the outbreak alert, the map and the officer worklist in the demo. The app and hub show a DEMO badge.
- **What it does NOT cover:** real members, real reports, real locations. The SMS gateway is SIMULATED.
- **Future data:** officer confirmations are stored in the hub's `labels` table as examples for retraining. It holds
  no real confirmations yet.

---

## Gaps (what our data does not cover)

1. **No Kirinyaga phone photos of our own yet.** `data/field_test/` has **0** photos. The iNaturalist set has no
   labelled disease photo from East Africa, and only 6 East African *Coffea* plant photos (3 in Kenya). The only Kenyan
   test is JMuBEN.
2. **A single plantation.** JMuBEN comes from our users' county, but from one plantation, one camera and a pathologist,
   as 128 px close-up crops with many augmented copies; the healthy class rests on about 7–10 distinct photos.
3. **Field conditions are untested where it matters.** Smallholder farms in Kirinyaga, messy backgrounds, shade, wet
   leaves, cheap phone cameras and the photos Noor's daughter would take have never been tested. On the held-out
   iNaturalist proxy (photos from the Americas), the shipped v2 answers 34 of 53 rust photos correctly (64.2 %;
   v1: 0). The rest get "I'm not sure". It names leaf miner in 2 of 9 photos and Cercospora in 0 of 10.
4. **No labelled healthy field leaves.** Healthy leaves will mostly get the fail-safe, and some will get a false
   disease answer: v2 gives one for 2.5 % of the iNaturalist *Coffea* test photos, because all its field training
   photos are diseased.
5. **Leaf symptoms only.** The app cannot see **coffee berry disease**, which attacks the berries and is one of Kenya's
   two major coffee diseases ([`docs/evidence.md`](docs/evidence.md) §4, S), nor antestia bugs, berry borer, lack of
   fertiliser, drought, old trees or soil problems, any of which could explain Noor's lower yield. The card
   `limits_yield` says so on every result and points to the officer.
6. **Severity only in RoCoLe (not used).** The model has no severity output. BRACOL may have severity labels too, but it is not used either.
7. **`acaro_rojo` (red spider mite) is not in the model.** It is only in RoCoLe. The card exists, but the model never outputs it.
8. **Phoma has no field test.** Cercospora has 10 held-out field photos, and v2 got none of them right (2 called roya).
9. **Kiswahili and Gĩkũyũ are unverified.** Both texts are AI drafts, the Gĩkũyũ one low confidence, and their audio is
   an English voice reading Kiswahili phonemes that nobody has listened to. Gĩkũyũ has no Common Voice data, and the
   MMS voices that exist are non-commercial and trained on religious texts. SMS Gĩkũyũ is written without ĩ/ũ. The
   English cards are unverified too.
10. **Real SMS language is missing.** Intent examples are team-written English and Kiswahili; Gĩkũyũ free text is
    effectively untested (17 unverified drafts).
11. **Prices are references, not farm-gate.** A county-average cherry payout and KAMIS wholesale prices, all DEMO, all
    seen only in search snippets. Each factory pays its own rate (KES 104 to 157.40 per kg of cherry across Kirinyaga
    societies in 2025/26, S).
12. **All sample data is DEMO.** This covers members, observations, the outbreak and the SMS gateway (SIMULATED).
13. **Licences need a check before any product use.** These are: Imagenette (ImageNet terms), PlantDoc (CC BY vs CC BY-SA),
    the iNaturalist NC/ND photos **the shipped v2 was trained on** (105 of its 147 field photos), iNatAg-mini, the
    Piper voice weights and the Lessac data licence, espeak-ng, and the Meta MMS models (NC) if they are ever used.

**How these gaps close.** First, the extension officer confirms or rejects reports in the hub. Those confirmations
become labelled photos from Kirinyaga farms, healthy and diseased, taken with the app. They go into `data/field_test/`
and, later, into training. A faster start: ask a Kirinyaga co-op or KALRO-CRI for 50 to 100 consented phone photos of
rust, leaf miner and healthy leaves, labelled by an extension officer, and score the shipped model on them without
changing the threshold ([`docs/evidence.md`](docs/evidence.md), "How to close the gaps"). Then rerun the field protocol
and ship rule ([`model/README.md`](model/README.md)), and record any exception openly, as for the shipped v2@0.90
(`model/ship_decision.json`). In parallel, native Kiswahili and Gĩkũyũ speakers from the area review the 83 cards and
record the 74 spoken ones ([`content/README.md`](content/README.md)), and an agronomist checks the English advice.
