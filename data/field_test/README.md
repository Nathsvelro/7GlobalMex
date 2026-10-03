# Field test photos (the team's own)

This folder is the **field test set**: photos the team takes itself, ideally of coffee leaves in
Chiapas, with the phone the app runs on. They are never used for training. `model/evaluate.py`
evaluates every image here automatically and reports it separately from the held-out test split
(section (c) of `reports/model_eval.md`).

Status: **0 images - not yet collected.**

Meanwhile a **proxy field test** uses 768 labelled iNaturalist photos (leaf rust, leaf miner,
Cercospora, ojo de gallo, coffee plants; only 4 rust photos are from Mexico). Those images are NOT in
this folder (CC BY-NC / ND licenses; attribution in `reports/field_inat_attribution.csv`); see
`reports/field_eval.md` and `model/README.md` to rebuild them. Result for the shipped model (v2 at
threshold 0.90) on the held-out field test: 34 of 53 rust photos answered correctly (64.2 %), the rest
DUDA. The previous model v1 got 0 of 219 (`reports/field_eval.md`). Photos taken here, in Chiapas, with
the app, remain the real test.

## How to add photos

1. Take the photo as a farmer would with the app: the leaf (underside for rust) filling most of the
   frame, in daylight, not blurred. Also take a few "bad" ones (blurred, far away, not coffee).
2. Put each photo in the folder of its **true** label (PLAN.md section 3):

   | folder | what |
   |---|---|
   | `sano/` | healthy coffee leaf |
   | `roya/` | coffee leaf rust |
   | `minador/` | coffee leaf miner |
   | `phoma/` | brown leaf spot (Phoma) |
   | `cercospora/` | Cercospora leaf spot |
   | `acaro_rojo/` | red spider mite (not in the model, v1 or v2: the right answer is the fail-safe DUDA) |
   | `otro/` | anything that is not a coffee leaf (the right answer is DUDA) |

   Only label a disease when an agronomist or the extension officer confirmed it. If unsure, do not
   add the photo.
3. Formats: `.jpg`, `.jpeg`, `.png`, `.webp`. Remove location metadata (EXIF GPS) and faces before
   committing.
4. Run `python model/evaluate.py --data /home/user/data_proc/cafetal` (see `model/README.md`).

Officer confirmations stored by the hub (`labels` table) can later be exported into these folders,
which is how the field test set grows over time.
