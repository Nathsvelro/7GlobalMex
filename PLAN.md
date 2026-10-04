# Cafetal — build plan and shared contracts

Hack-Nation × World Bank "Small AI for Development", **Agriculture track (Annex B)**.
Source of truth for the user, rules and judging: `PROJECT_BRIEF.md` and `docs/concept-note.pdf`.

**One decision we improve:** *"Is something attacking my coffee, and what do I do this week:
handle it myself, or get the extension officer to come?"* Plus a non-AI reference price (PRICE / BEI).

Setting: **Kirinyaga County, central Kenya** (the Mt Kenya coffee belt). Languages: **English** (`en`, the main
and default language), **Kiswahili** (`sw`, the national language) and **Gĩkũyũ** (`kik`, the local language).
Noor, the **Ondera Farmers' Co-operative Society** (with its coffee factory, the wet mill) and its four communities,
**Ondera Juu, Ondera Chini, Ondera Mto and Ondera Kilima**, are fictional.

Design rule: **keep it simple.** Vanilla HTML/JS (no build step), FastAPI + SQLite, one command to start.

> **As built (2026-10-04).** This plan was written before the build; where it differs, the build wins:
> - The shipped image model is **v2** (`cafetal-img-v2`), **fp16 weights** (1.97 MB), at confidence threshold
>   **0.90**. INT8 broke the model ([METRICS.md](METRICS.md) §1). v2 = JMuBEN (Kenya) + PlantDoc/Imagenette `otro`
>   + 147 iNaturalist field photos. It shipped by an explicit team decision, as an exception to the pre-registered ship
>   rule (it misses one of five conditions by 0.04 points; [METRICS.md](METRICS.md) §4c, `model/ship_decision.json`).
> - **Re-localized to Kenya on 2026-10-04** (team decision): languages, SMS codes and keywords, DEMO members, prices
>   (KES) and the hub's staff pages (now English). The image model, its threshold, the ship decision and every model
>   metric are unchanged: no retraining. The SMS intent classifier was retrained on English and Kiswahili. Earlier
>   versions are in git history.
> - JMuBEN, the training and main test data, was photographed at Mutira, **Kirinyaga** (Jepkoech et al. 2021), the
>   county of our users. That place comes from a search snippet of the paper's abstract (code S in
>   [docs/evidence.md](docs/evidence.md) §3b); that JMuBEN is Kenyan is read in its metadata (F). BRACOL and RoCoLe were
>   never downloaded (Mendeley is blocked). v2's 147 iNaturalist field photos come from Latin America and the
>   Caribbean (86), Asia (30, mostly Taiwan), Hawaii (27), Florida (3) and South Africa (1); **none from East Africa**
>   (*computed* from the coordinates in `reports/field_inat_attribution.csv`).
> - **84 cards** in three languages (`en`, `sw`, `kik`), 75 of them spoken (225 MP3s, 2.97 MB). Adding a language means
>   84 card texts (about 800–950 words; 60 required ids) and 75 recordings, with no model retraining.
> - The blur threshold (4.2) is calibrated on **validation** images. The "too little leaf colour" check in §3 was
>   **not built**; the `otro` class does that job.
> - SMS keywords: PRICE/PRICES, HELP, OFFICER (English) and BEI, MSAADA, AFISA (Kiswahili). There are no Gĩkũyũ
>   keywords; the Gĩkũyũ SMS cards advertise the English and Kiswahili ones.

---

## 1. Decisions taken (and why)

| Topic | Decision | Why |
|---|---|---|
| Setting | **Kirinyaga County, central Kenya**. English main language, Kiswahili national, Gĩkũyũ local | Team decision (2026-10-04). Our training data is Kenyan (F) and was photographed in Kirinyaga (S), so the main held-out test comes from the users' own county, though from one plantation and as close-up crops ([DATA_CARD.md](DATA_CARD.md) §1). Kiswahili is the national language, and Kiswahili and English are the official ones (Constitution Art. 7, S). Gĩkũyũ is spoken mainly in central Kenya (S). About 71 % of Kenyan coffee came through co-operative societies in 2022/23 (AFA figures, S; arithmetic D), so a co-op hub fits. Codes and URLs: [docs/evidence.md](docs/evidence.md) §3, §6. |
| Training data | **JMuBEN/JMuBEN2** (Kenya, Arabica, CC BY 4.0) via the AgML public bucket, plus **PlantDoc** and Imagenette for "not coffee"; the shipped v2 adds 147 screened **iNaturalist** field photos (`DATA_CARD.md` §4) | Mendeley (BRACOL, RoCoLe) and Kaggle are blocked by this build environment's network policy, and so are file downloads from Hugging Face (only Hub metadata could be read). `model/prepare_data.py` also accepts BRACOL/RoCoLe folders if the team downloads them by hand (steps in `DATA_CARD.md`). |
| Image model | Keras **MobileNetV3-Small** (ImageNet weights) fine-tuned → ONNX → **fp16 weights** (planned INT8; static INT8 broke the model) | Weights reachable from storage.googleapis.com; ONNX runs in the browser with onnxruntime-web (WASM). |
| Phone runtime | **onnxruntime-web 1.19.2**, vendored in `app/vendor/` (WASM, 1 thread) | No CDN at run time; works offline once cached by the service worker. |
| Card text | **English** written by the team; **Kiswahili** and **Gĩkũyũ** are **AI drafts**. Every card in every language is **UNVERIFIED** | No native speaker or agronomist has checked them yet. The Gĩkũyũ draft is low confidence: no Gĩkũyũ dictionary could be opened from the build machine ([content/README.md](content/README.md)). |
| English voice | **Piper** TTS, voice `en-us-lessac-medium`, pre-rendered to MP3 | Offline, free, good enough. |
| Kiswahili and Gĩkũyũ voices | **Provisional synthetic audio**: the same English Piper voice reading Kiswahili phonemes from espeak-ng `sw` (Gĩkũyũ text respelled ĩ → e, ũ → o for the voice only), marked `synthetic-provisional` and **UNVERIFIED**, plus a hub page where a native speaker records each card and the recording replaces the file | There is no Piper voice for either language here; espeak-ng has a Kiswahili phonemizer and no Gĩkũyũ one. The Spanish Piper voice was also tried: it covers slightly more of the sounds but speaks slowly and in broken pieces (*computed* checks, nobody listened; [content/README.md](content/README.md)). Meta MMS text-to-speech models **`facebook/mms-tts-swh`** and **`facebook/mms-tts-kik`** exist (about 145 MB each, CC-BY-NC-4.0, trained on readings of religious texts; F in [docs/evidence.md](docs/evidence.md) §8), but their files could not be downloaded to the build machine. |
| Text intents | Tiny **char n-gram TF-IDF + logistic regression**, exported to JSON, pure-Python inference in the hub. Trained on team-written English and Kiswahili, 17 unverified AI-draft Gĩkũyũ messages, and Amazon MASSIVE en-US / sw-KE as off-topic examples | Multilingual embedding models are not reachable here; this is small, fast, explainable. |
| Hub pages | **English** UI for co-op staff and the extension officer | English is an official language of Kenya (S) and the project's main language; members never see these pages. Everything a member sees or hears still comes only from `content/cards.json`. |
| SMS gateway | **Simulator page** (labeled SIMULATED); real Android gateway is a stretch goal | Brief allows it. |
| Map | Plain **SVG** map (no tiles) | OSM tiles blocked; SVG works offline. |
| Weather rust risk | Not built (stretch); NASA POWER is blocked here | Keep scope small. |

## 2. Repository layout

```
README.md  PLAN.md  DEMO.md  METRICS.md  DATA_CARD.md  RESPONSIBLE_AI.md  VIDEO_SCRIPT.md
PROJECT_BRIEF.md   docs/ (concept-note.pdf, CLAUDE_CODE_PROMPT.md, evidence.md)
run.sh                    # one command: venv + deps + seed DEMO data + start hub on 0.0.0.0:8000
requirements.txt          # hub runtime only (fastapi, uvicorn, python-multipart)
requirements-train.txt    # model + intent training (tensorflow-cpu, tf2onnx, onnx, onnxruntime, pillow, scikit-learn)
content/
  cards.json              # EVERY sentence a farmer can see or hear (UI strings, advice, SMS replies)
  audio/en/<card_id>.mp3
  audio/sw/<card_id>.mp3  # provisional synthetic
  audio/kik/<card_id>.mp3 # provisional synthetic
scripts/make_audio.py     # Piper → MP3; never overwrites a native-speaker recording
app/                      # phone PWA (static). Served by the hub at /app/ ; also deployable to any HTTPS static host
  index.html app.js style.css sw.js manifest.webmanifest config.json icons/
  model/cafetal.onnx      # image model v2, fp16 weights, 1.97 MB (limit 10 MB)
  model/labels.json       # model metadata (contract §4)
  vendor/                 # onnxruntime-web files
hub/                      # co-op hub (FastAPI + SQLite)
  main.py db.py sms.py intent.py outbreak.py seed.py train_intent.py intent_model.json
  static/                 # hub pages (English UI for co-op staff + extension officer)
model/                    # image-model training code (prepare_data.py train.py export_onnx.py evaluate.py)
reports/                  # evaluation outputs (json/md/png) used by METRICS.md
data/
  prices.json             # cached reference prices in KES (DEMO-labeled unless verified)
  intent/examples.csv     # labeled SMS examples (en, sw, a few kik)
  field_test/<label>/*.jpg  # the team's own photos (may be empty)
tests/                    # pytest for the hub; tests/e2e/ browser tests
```

Paths are relative so `app/` can fetch `../content/cards.json` both from the hub and from a static host.

## 3. Labels and codes (shared by model, app, SMS and hub)

| label (model/app, internal) | SMS code | diagnosis card | in the model (v1 and v2)? |
|---|---|---|---|
| `sano` (healthy) | `HLTH` | `diag_sano` | yes |
| `roya` (leaf rust) | `RUST` | `diag_roya` | yes |
| `minador` (leaf miner) | `MINR` | `diag_minador` | yes |
| `phoma` (Phoma leaf spot) | `PHOM` | `diag_phoma` | yes |
| `cercospora` (brown eye spot) | `CERC` | `diag_cercospora` | yes |
| `acaro_rojo` (red spider mite) | `MITE` | `diag_acaro_rojo` | no (only in RoCoLe, not reachable) |
| `otro` (not a coffee leaf) | `OTHR` | `diag_duda` | yes |
| *(fail-safe: unsure / blurry / low confidence)* | `UNSR` | `diag_duda` | n/a |

Model labels, card ids and slot names are internal identifiers (several are Spanish words from the project's first
version). Members never see them (they see and hear the card text); co-op staff see card ids and slot names on the
hub's Content page. The codes table lives in `app/sms.js` (`CODES`) and `hub/sms.py`; codes of the first version
are not accepted (no device ever used them).

Fail-safe: if the photo is blurry, top-1 < threshold, or top-1 is `otro`,
the app shows/plays **`diag_duda`** = "I'm not sure — show the leaf to the extension officer." and the
observation is sent as `UNSR`/`OTHR`, which puts the farm on the officer's worklist.

## 4. Model contract (`app/model/labels.json`)

```json
{
  "version": "cafetal-img-v2",
  "classes": ["sano", "roya", "minador", "phoma", "cercospora", "otro"],
  "input":  {"name": "<onnx input name>", "size": 224, "layout": "NHWC", "dtype": "float32", "range": "0-255 RGB, no normalisation (preprocessing is inside the model)"},
  "output": {"name": "<onnx output name>", "type": "probabilities"},
  "threshold": 0.9,
  "blur_threshold": 4.2,
  "file": "cafetal.onnx",
  "size_bytes": 1972422,
  "trained_on": "JMuBEN/JMuBEN2 (Kenya, Arabica) + 147 screened iNaturalist field photos ... + PlantDoc and Imagenette as 'otro'; see DATA_CARD.md",
  "threshold_note": "0.90 chosen on calibration data only; see reports/field_v2_threshold_sweep.md"
}
```
(Values as shipped; the planned defaults were threshold 0.70 and INT8.)
The app center-crops the photo to a square, resizes to `size`, feeds raw RGB 0–255 floats NHWC
`[1,size,size,3]`, reads probabilities in `classes` order. Class order is defined ONLY by this file.

**Blur check (same algorithm in app and in the calibration script):** center-square crop → resize to 128×128 →
grey = 0.299R + 0.587G + 0.114B (0–255) → 3×3 Laplacian `[0,1,0; 1,-4,1; 0,1,0]` on interior pixels →
variance. If variance < `blur_threshold` → fail-safe `UNSR` without trusting the model.
`blur_threshold` is calibrated on validation images by `model/` and written to labels.json.

**App config (`app/config.json`):** `{"gateway_number": "+254700000000", "gateway_label": "DEMO"}` — the co-op's SMS
gateway number used in the `sms:` link (a placeholder; the `DEMO` label shows a DEMO badge).

## 5. Observation SMS code v1 (≤160 chars, one SMS, works on 2G)

```
CAF1 <member> <code> <conf> <yyyymmdd> <lat>,<lon> #<obs>
CAF1 M0123 RUST 99 20261004 -0.52,37.32 #K3F9
```
- `CAF1` format/version tag. `member` = `M` + 4 digits. `code` from §3 (4 letters).
- `conf` = top-1 probability as integer percent 0–99 (for `UNSR` the model's top-1, or 0 if no model run).
- date `YYYYMMDD` (phone local date). Location rounded to **2 decimals (~1 km)** for privacy, or `-` if unknown
  (the hub then uses the member's registered plot location).
- `#<obs>` = 4-char base36 id of the record on the phone, to match photos synced later over Wi-Fi.
- Parsing is case-insensitive and tolerant of extra spaces. Anything else is free text.
- Longest possible code: 48 characters (*computed* from `CODE_RE` in `app/sms.js`); 45 in the end-to-end test.

## 6. Hub HTTP API (FastAPI, port 8000, `0.0.0.0`)

| Method | Path | What |
|---|---|---|
| GET | `/` | Hub home (links to pages) |
| static | `/app/`, `/content/`, `/hub/` | phone PWA, cards+audio, hub pages |
| GET | `/api/health` | `{"ok": true}` (the phone uses this to know the hub is reachable) |
| GET/POST | `/api/members` | registry list / register (name, phone, community, lat, lon, language `en`/`sw`/`kik`, consent=true required, consent_by) → assigns `M####` |
| DELETE | `/api/members/{member_id}` | remove a member and their records |
| POST | `/api/sms/inbound` | `{"from": "+2547…", "body": "…"}` → routes the SMS (§7), returns `{"replies": [...], "actions": [...]}`. Kenyan national numbers (`07xx…`) are normalised to `+2547…`. For the SIMULATED send button in the phone app, `{"member_id": "M0123", "body": "…"}` is accepted instead of `from` (hub looks up the phone). |
| GET | `/api/sms/thread?phone=` | messages in + out for one phone (simulator) |
| GET | `/api/outbox` ; POST `/api/outbox/{id}/approve` ; POST `/api/outbox/{id}/reject` | outgoing SMS queue |
| GET | `/api/observations` ; POST `/api/observations/sync` | list ; Wi-Fi sync of full record + photo (JPEG data URL) |
| GET | `/api/worklist` ; POST `/api/worklist/{obs_id}/action` | ranked farms ; `{"action": "visit_scheduled"|"confirmed"|"not_confirmed", "true_label": "...", "note": "..."}` |
| GET | `/api/alerts` ; GET `/api/map` | outbreak alerts ; members+observations+alerts for the SVG map |
| GET | `/api/prices` | reference price table (KES) |
| GET | `/api/cards` ; POST `/api/cards/{id}/verify` ; POST `/api/cards/{id}/audio/{lang}` | content review: mark a card's language verified (reviewer name) ; upload native recording |
| GET | `/api/officer/messages` | free-text SMS forwarded to the officer |
| POST | `/api/demo/reset` | wipe and re-seed DEMO data |

## 7. SMS routing (hub)

1. Sender not registered → reply card `sms_no_registrado`; nothing else stored except the raw message log.
   **Exception (family phone):** a `CAF1` code from an unregistered phone is accepted if the member in the code
   exists (the daughter's smartphone): the observation is stored and `sms_obs_recibida` goes back to that number.
   A registered phone cannot send a code for another member. See RESPONSIBLE_AI.md §9 (fake-report risk).
2. Body starts with `CAF1` → parse (§5). Invalid → `sms_codigo_invalido`. Valid → store observation,
   reply `sms_obs_recibida`, run the outbreak rule (§8). Worklist is computed from observations.
3. Body is an exact keyword (any case, punctuation ignored): `PRICE`/`PRICES`/`BEI` → `sms_precio` filled from
   `data/prices.json`; `HELP`/`MSAADA` → `sms_ayuda`; `OFFICER`/`AFISA` → `sms_pasar_tecnico` + forward to officer.
4. Otherwise → intent classifier (threshold 0.55): `price` → `sms_precio`; `report` → `sms_reporte_instrucciones` +
   forward to officer; `help` → `sms_ayuda`; `talk_to_officer` → `sms_pasar_tecnico` + forward to officer;
   `other` or confidence < threshold → `sms_pasar_tecnico` + forward to officer.
5. Replies to a member who just texted are recorded in the outbox as `sent_simulated`
   (the member asked). **Broadcasts (alerts) are queued as `pending_approval` and go out only when co-op
   staff tap Approve.** Every reply text comes from `content/cards.json` (slots filled with numbers, dates and names
   only; in SMS cards a slot value's accents are dropped, e.g. ĩ → i, so the SMS stays GSM-7: `hub/cards.py` `gsm_safe`).
6. The reply language follows the member's registered language (`en` default, `sw` or `kik` if registered so;
   a card without text in that language is sent in `en`).

## 8. Outbreak rule (not AI, a transparent rule)

`RUST` reports from **≥3 different members**, **within 5 km** of each other, in the **last 7 days**
(confidence ≥ model threshold, 0.90 now) → create an alert (at most one per 7 days per area) and queue card
`alert_roya` to every consenting member as `pending_approval`. Parameters are design choices,
shown in the UI and documented; they are not agronomic thresholds.

## 9. Worklist ranking (not AI; the officer decides)

Per farm, last 30 days: score = result weight × confidence + cluster bonus.
Weights: `RUST` 3; `UNSR`/`OTHR` 2 (fail-safe: needs a person); `CERC`/`PHOM`/`MINR`/`MITE` 2; `HLTH` 0.
Confidence factor = conf/100 (1.0 for `UNSR`/`OTHR`). +2 if inside an active alert area.
The UI shows the reason ("Rust 99% · alert area · 2 reports in 30 days"). Officer actions are stored;
`confirmed`/`not_confirmed` with a true label are saved in a `labels` table as **examples for later retraining**.

## 10. Content (`content/cards.json`)

```json
{
  "version": 2,
  "languages": {"en": "English", "sw": "Kiswahili", "kik": "Gĩkũyũ"},
  "cards": [
    {
      "id": "diag_roya",
      "type": "ui | diagnosis | advice | sms | alert",
      "en": "…", "sw": "…", "kik": "…",
      "slots": [],
      "audio": {"en": "audio/en/diag_roya.mp3", "sw": "audio/sw/diag_roya.mp3", "kik": "audio/kik/diag_roya.mp3"},
      "audio_source": {"en": "synthetic:piper-en-us-lessac-medium",
                       "sw": "synthetic-provisional:piper-en-us-lessac-medium-espeak-sw",
                       "kik": "synthetic-provisional:piper-en-us-lessac-medium-espeak-sw-reading-gikuyu"},
      "source": "where the content comes from (manual, URL)",
      "status": {"en": "unverified", "sw": "unverified", "kik": "unverified"},
      "reviewed_by": {"en": null, "sw": null, "kik": null}
    }
  ]
}
```
- Languages: `en` (English) is the main language and the app's default; `sw` (Kiswahili) and `kik` (Gĩkũyũ) are AI
  drafts with provisional synthetic audio.
- Every card starts `unverified` in every language; a person marks it verified in the hub (name + date).
  The app shows an **UNVERIFIED** badge next to unverified text and audio (in Kiswahili *HAIJAHAKIKIWA · UNVERIFIED*,
  in Gĩkũyũ *NDĨRATHUTHURIO · UNVERIFIED*: the English word stays in case the drafted word is wrong; likewise
  *SIMULATED*).
- Slots (e.g. `{precio_cafe}`, `{fecha}`, `{fuente}`) are filled only with numbers, dates and source names.
- SMS cards (`sms_*`, `alert_roya`) are plain GSM-7 text, ≤ 160 characters after filling slots; the Gĩkũyũ SMS
  cards write ĩ/ũ as i/u (the UI and audio keep ĩ/ũ). `python3 scripts/make_audio.py --check` enforces this.
- Required card ids are listed in §11; content may add more.

## 11. Required card ids

UI (`type: ui`): `ui_app_name`, `ui_choose_language`, `ui_consent_title`, `ui_consent_text`, `ui_consent_accept`,
`ui_consent_decline`, `ui_member_id_prompt`, `ui_pin_optional`, `ui_pin_prompt`, `ui_continue`, `ui_take_photo`,
`ui_photo_tip_underside`, `ui_analyzing`, `ui_confidence`, `ui_play_kik`, `ui_play_sw`, `ui_play_en`, `ui_send_sms`,
`ui_simulate_send`, `ui_saved`, `ui_history`, `ui_settings`, `ui_delete_all`, `ui_delete_confirm`, `ui_sync_photos`,
`ui_synced`, `ui_back`, `ui_unverified`, `ui_demo`, `ui_simulated`, `ui_offline_ready`, `ui_limits_note`,
`ui_language`, `ui_pending_sms`, `ui_sent`, `ui_no_records`.

Diagnosis/advice: `diag_sano`, `diag_roya`, `diag_minador`, `diag_phoma`, `diag_cercospora`, `diag_acaro_rojo`, `diag_duda`,
`advice_roya`, `advice_minador`, `advice_phoma`, `advice_cercospora`, `advice_sano`, `advice_acaro_rojo`,
`advice_call_officer`, `limits_yield` (the app only sees leaf symptoms; it cannot see coffee berry disease on the
berries, antestia bugs, berry borer, lack of fertiliser, drought, old trees or soil problems).

SMS/alerts: `sms_obs_recibida`, `sms_codigo_invalido`, `sms_no_registrado`, `sms_precio` (slots: `precio_cafe`, `unidad_cafe`,
`precio_maiz`, `precio_frijol`, `fuente`, `fecha`), `sms_precio_sin_datos`, `sms_reporte_instrucciones`, `sms_ayuda`,
`sms_pasar_tecnico`, `alert_roya` (slots: `comunidad`, `n_reportes`).

That is 60 required ids (`REQUIRED_IDS` in `scripts/make_audio.py`); `cards.json` has 83.

## 12. Milestones

1. Plan + scaffold (this file). ✔
2. Image model: data → train → ONNX (fp16 as built) → evaluation report (`reports/`), `DATA_CARD.md` started. ✔
3. Offline diagnosis on the phone: photo → result → card → audio. Airplane mode. ✔
4. Save-and-send-later: SMS code, hub inbox, simulator, Wi-Fi photo sync. ✔
5. Hub: registry + consent, outbreak alert, officer worklist, reference price, intent sorting, DEMO seed. ✔
6. Guardrails + privacy pass. ✔
7. Ship docs: README, DEMO, METRICS, DATA_CARD, RESPONSIBLE_AI, VIDEO_SCRIPT. ✔
8. Re-localize to Kirinyaga, Kenya: English main language, Kiswahili and Gĩkũyũ drafts, English SMS codes and
   keywords, KES prices, Kenyan DEMO seed, intent classifier retrained (2026-10-04). ✔

## 13. Known limits (short; details in DATA_CARD.md / RESPONSIBLE_AI.md)

- No field photos from Kenya. JMuBEN is from Kirinyaga, but from one plantation, as 128×128 crops with many
  augmented near-duplicates (we split by near-duplicate group to limit leakage). v2's 147 field photos and all 162
  labelled disease photos of the field test come from outside East Africa. `acaro_rojo` is not in the model, and
  the app cannot see coffee berry disease, which attacks the berries.
- Kiswahili and Gĩkũyũ text are AI drafts and their audio is provisional synthetic speech until native speakers
  review and record them. The English text is team-written and also unverified.
- Prices are DEMO reference values in KES until replaced with checked official figures; never a farm-gate price.
- Service workers need a secure origin: for the demo the phone opens the hub via `adb reverse` (localhost)
  or a static HTTPS host; see README.
