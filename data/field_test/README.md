# Field test photos (the team's own)

This folder is the **field test set**: photos of coffee leaves on farms in **Kirinyaga County, central Kenya** (the
Mt Kenya coffee belt, where the app's users farm), taken with the phone the app runs on, the way a farmer would take
them. They are never used for training. `model/evaluate.py` evaluates every image here automatically and
reports it separately from the held-out test split (section (c) of `reports/model_eval.md`).

Status: **0 images - not yet collected.**

What we have instead:

- The model's training and main test images (JMuBEN) were photographed in the Mutira coffee plantation, **Kirinyaga
  County** (Jepkoech et al. 2021) - the same county. But they are 128 px close-up crops from one plantation and one
  camera, with many augmented copies; they are not photos taken with the app on a farm.
- A **proxy field test** of 768 labelled iNaturalist photos (leaf rust, leaf miner, Cercospora, American leaf spot,
  coffee plants). **None of the labelled disease photos is from East Africa** (all disease test photos are from the
  Americas); only 6 coffee-plant photos are from East Africa, 3 of them from Kenya. Those images are NOT in this
  folder (CC BY-NC / ND licences; attribution in `reports/field_inat_attribution.csv`); see `reports/field_eval.md`
  and `model/README.md` to rebuild them. Result for the shipped model (v2 at threshold 0.90) on the held-out field
  test: 34 of 53 rust photos answered correctly (64.2 %), the rest got the fail-safe "I'm not sure" (UNSR). The
  previous model v1 got 0 of 219 (`reports/field_eval.md`).

Photos taken here, in Kirinyaga, with the app, remain the real test.

## What to collect first (Kirinyaga)

| priority | what | why |
|---|---|---|
| 1 | **healthy leaves** (`sano/`), upper side and underside, from several farms and coffee varieties grown locally | the model learned "healthy" from 7 near-duplicate groups (JMuBEN has only 14 distinct healthy source photos); no healthy field leaf has been tested |
| 2 | **leaf rust** (`roya/`), underside with the orange powder filling most of the frame; early (small yellow spots) and late stages | the main disease of the outbreak alert; no East African rust photo has been tested |
| 3 | **brown eye spot** (`cercospora/`) | the shipped model got 0 of 10 iNaturalist Cercospora photos right (several called rust) |
| 4 | leaf miner (`minador/`), Phoma leaf spot (`phoma/`) | classes in the model, few field photos tested |
| 5 | red spider mite (`acaro_rojo/`), coffee berry disease, berry borer damage, nutrient deficiency, drought | not in the model: the right answer is the fail-safe; checks that the app does not invent a disease |
| 6 | "bad" photos (`otro/` if not a coffee leaf, otherwise the true label): blurred, far away, whole tree, a cup, a maize leaf, a hand | the fail-safe path |

Take them across the year (long rains, short rains, dry season), morning and midday light, and with the phones the
co-operative's members actually use.

## How to add photos

1. Take the photo as a farmer would with the app: the leaf (underside for rust) filling most of the frame, in
   daylight, not blurred. Also take a few "bad" ones (blurred, far away, not coffee).
2. Put each photo in the folder of its **true** label (PLAN.md section 3; the folder names are the model's internal
   labels):

   | folder | what | SMS code the app should send |
   |---|---|---|
   | `sano/` | healthy coffee leaf | HLTH |
   | `roya/` | coffee leaf rust | RUST |
   | `minador/` | coffee leaf miner | MINR |
   | `phoma/` | Phoma leaf spot | PHOM |
   | `cercospora/` | brown eye spot (Cercospora) | CERC |
   | `acaro_rojo/` | red spider mite (not in the model, v1 or v2: the right answer is the fail-safe) | UNSR or OTHR (any disease code is an error) |
   | `otro/` | anything that is not a coffee leaf (the right answer is the fail-safe) | OTHR or UNSR |

   Only label a disease when an agronomist or the extension officer confirmed it. If unsure, do not add the photo.
3. Formats: `.jpg`, `.jpeg`, `.png`, `.webp`. Remove location metadata (EXIF GPS) and faces before committing, and
   ask the farmer's consent before photographing on their farm.
4. Run `python model/evaluate.py --data /home/user/data_proc/cafetal` (see `model/README.md`).

Extension officer confirmations stored by the hub (`labels` table) can later be exported into these folders, which
is how the field test set grows over time.
