# Field test photos (the team's own)

This folder is the **field test set**: photos the team takes itself, ideally of coffee leaves in
Chiapas, with the phone the app runs on. They are never used for training. `model/evaluate.py`
evaluates every image here automatically and reports it separately from the held-out test split
(section (c) of `reports/model_eval.md`).

Status: **0 images - not yet collected.**

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
   | `acaro_rojo/` | red spider mite (not in model v1: the right answer is the fail-safe DUDA) |
   | `otro/` | anything that is not a coffee leaf (the right answer is DUDA) |

   Only label a disease when an agronomist or the extension officer confirmed it. If unsure, do not
   add the photo.
3. Formats: `.jpg`, `.jpeg`, `.png`, `.webp`. Remove location metadata (EXIF GPS) and faces before
   committing.
4. Run `python model/evaluate.py --data /home/user/data_proc/cafetal` (see `model/README.md`).

Officer confirmations stored by the hub (`labels` table) can later be exported into these folders,
which is how the field test set grows over time.
