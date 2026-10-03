# Cafetal — build plan and shared contracts

Hack-Nation × World Bank "Small AI for Development", **Agriculture track (Annex B)**.
Source of truth for the user, rules and judging: `PROJECT_BRIEF.md` and `docs/concept-note.pdf`.

**One decision we improve:** *"Is something attacking my coffee, and what do I do this week:
handle it myself, or get the extension officer to come?"* Plus a non-AI reference price ("PRECIO").

Setting: Chiapas highlands, Mexico. Local language **Tseltal** (`tzh`), national language **Spanish** (`es`).

Design rule: **keep it simple.** Vanilla HTML/JS (no build step), FastAPI + SQLite, one command to start.

---

## 1. Decisions taken (and why)

| Topic | Decision | Why |
|---|---|---|
| Training data | **JMuBEN/JMuBEN2** (Kenya, Arabica, real field, CC BY 4.0) via the AgML public bucket, plus **PlantDoc** for "not coffee" | Mendeley (BRACOL, RoCoLe), Hugging Face and Kaggle are blocked by this build environment's network policy. `model/prepare_data.py` also accepts BRACOL/RoCoLe folders if the team downloads them by hand (steps in `DATA_CARD.md`). |
| Image model | Keras **MobileNetV3-Small** (ImageNet weights) fine-tuned → ONNX → INT8 | Weights reachable from storage.googleapis.com; ONNX runs in the browser with onnxruntime-web (WASM). |
| Phone runtime | **onnxruntime-web 1.19.2**, vendored in `app/vendor/` (WASM, 1 thread) | No CDN at run time; works offline once cached by the service worker. |
| Spanish voice | **Piper** TTS, voice `es-mls_10246-low`, pre-rendered to MP3 | Offline, free, good enough. |
| Tseltal voice | Meta MMS has no reachable `tzh` model here, so: **provisional synthetic audio** (Spanish Piper voice reading Tseltal text) clearly marked **UNVERIFIED**, plus a hub page where a native speaker records each card and it replaces the file | Honest, and shows how a less-supported language is added: translate ~40 cards + record them; no retraining. |
| Text intents | Tiny **char n-gram TF-IDF + logistic regression**, exported to JSON, pure-Python inference in the hub | Multilingual embedding models are not reachable here; this is small, fast, explainable. |
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
  audio/es/<card_id>.mp3
  audio/tzh/<card_id>.mp3
scripts/make_audio.py     # Piper → MP3; never overwrites a native-speaker recording
app/                      # phone PWA (static). Served by the hub at /app/ ; also deployable to any HTTPS static host
  index.html app.js style.css sw.js manifest.webmanifest config.json icons/
  model/cafetal.onnx      # INT8 image model (≤10 MB)
  model/labels.json       # model metadata (contract §4)
  vendor/                 # onnxruntime-web files
hub/                      # co-op hub (FastAPI + SQLite)
  main.py db.py sms.py intent.py outbreak.py seed.py train_intent.py intent_model.json
  static/                 # hub pages (Spanish UI for co-op staff + extension officer)
model/                    # image-model training code (prepare_data.py train.py export_onnx.py evaluate.py)
reports/                  # evaluation outputs (json/md/png) used by METRICS.md
data/
  prices.json             # cached reference prices (DEMO-labeled unless verified)
  intent/examples.csv     # labeled SMS examples
  field_test/<label>/*.jpg  # the team's own photos (may be empty)
tests/                    # pytest for the hub
```

Paths are relative so `app/` can fetch `../content/cards.json` both from the hub and from a static host.

## 3. Labels and codes (shared by model, app, SMS and hub)

| label (model/app) | SMS code | diagnosis card | in model v1? |
|---|---|---|---|
| `sano` | `SANO` | `diag_sano` | yes |
| `roya` (leaf rust) | `ROYA` | `diag_roya` | yes |
| `minador` (leaf miner) | `MINA` | `diag_minador` | yes |
| `phoma` (brown leaf spot) | `PHOM` | `diag_phoma` | yes |
| `cercospora` | `CERC` | `diag_cercospora` | yes |
| `acaro_rojo` (red spider mite) | `ACAR` | `diag_acaro_rojo` | no (only in RoCoLe, not reachable) |
| `otro` (not a coffee leaf) | `OTRO` | `diag_duda` | yes |
| *(fail-safe: unsure / blurry / low confidence)* | `DUDA` | `diag_duda` | n/a |

Fail-safe: if the photo is blurry, has too little leaf colour, top-1 < threshold, or top-1 is `otro`,
the app shows/plays **`diag_duda`** = "No estoy seguro — muestre la hoja al técnico." and the
observation is sent as `DUDA`/`OTRO`, which puts the farm on the officer's worklist.

## 4. Model contract (`app/model/labels.json`)

```json
{
  "version": "cafetal-img-v1",
  "classes": ["sano", "roya", "minador", "phoma", "cercospora", "otro"],
  "input":  {"name": "<onnx input name>", "size": 224, "layout": "NHWC", "dtype": "float32", "range": "0-255 RGB, no normalisation (preprocessing is inside the model)"},
  "output": {"name": "<onnx output name>", "type": "probabilities"},
  "threshold": 0.70,
  "blur_threshold": 0.0,
  "file": "cafetal.onnx",
  "size_bytes": 0,
  "trained_on": "JMuBEN (Kenya) + PlantDoc; see DATA_CARD.md"
}
```
The app center-crops the photo to a square, resizes to `size`, feeds raw RGB 0–255 floats NHWC
`[1,size,size,3]`, reads probabilities in `classes` order. Class order is defined ONLY by this file.

**Blur check (same algorithm in app and in the calibration script):** center-square crop → resize to 128×128 →
grey = 0.299R + 0.587G + 0.114B (0–255) → 3×3 Laplacian `[0,1,0; 1,-4,1; 0,1,0]` on interior pixels →
variance. If variance < `blur_threshold` → fail-safe `DUDA` without trusting the model.
`blur_threshold` is calibrated on training images by `model/` and written to labels.json.

**App config (`app/config.json`):** `{"gateway_number": "+520000000000", "gateway_label": "DEMO"}` — the co-op's SMS
gateway number used in the `sms:` link.

## 5. Observation SMS code v1 (≤160 chars, one SMS, works on 2G)

```
CAF1 <member> <code> <conf> <yyyymmdd> <lat>,<lon> #<obs>
CAF1 M0123 ROYA 87 20261004 16.91,-92.11 #K3F9
```
- `CAF1` format/version tag. `member` = `M` + 4 digits. `code` from §3.
- `conf` = top-1 probability as integer percent 0–99 (for `DUDA` the model's top-1, or 0 if no model run).
- date `YYYYMMDD` (phone local date). Location rounded to **2 decimals (~1 km)** for privacy, or `-` if unknown
  (the hub then uses the member's registered plot location).
- `#<obs>` = 4-char base36 id of the record on the phone, to match photos synced later over Wi-Fi.
- Parsing is case-insensitive and tolerant of extra spaces. Anything else is free text.

## 6. Hub HTTP API (FastAPI, port 8000, `0.0.0.0`)

| Method | Path | What |
|---|---|---|
| GET | `/` | Hub home (links to pages) |
| static | `/app/`, `/content/`, `/hub/` | phone PWA, cards+audio, hub pages |
| GET | `/api/health` | `{"ok": true}` (the phone uses this to know the hub is reachable) |
| GET/POST | `/api/members` | registry list / register (name, phone, community, lat, lon, consent=true required, consent_by) → assigns `M####` |
| DELETE | `/api/members/{member_id}` | remove a member and their records |
| POST | `/api/sms/inbound` | `{"from": "+52…", "body": "…"}` → routes the SMS (§7), returns `{"replies": [...], "actions": [...]}`. For the SIMULATED send button in the phone app, `{"member_id": "M0123", "body": "…"}` is accepted instead of `from` (hub looks up the phone). |
| GET | `/api/sms/thread?phone=` | messages in + out for one phone (simulator) |
| GET | `/api/outbox` ; POST `/api/outbox/{id}/approve` ; POST `/api/outbox/{id}/reject` | outgoing SMS queue |
| GET | `/api/observations` ; POST `/api/observations/sync` | list ; Wi-Fi sync of full record + photo (JPEG data URL) |
| GET | `/api/worklist` ; POST `/api/worklist/{obs_id}/action` | ranked farms ; `{"action": "visit_scheduled"|"confirmed"|"not_confirmed", "true_label": "...", "note": "..."}` |
| GET | `/api/alerts` ; GET `/api/map` | outbreak alerts ; members+observations+alerts for the SVG map |
| GET | `/api/prices` | reference price table |
| GET | `/api/cards` ; POST `/api/cards/{id}/verify` ; POST `/api/cards/{id}/audio/{lang}` | content review: mark a card's language verified (reviewer name) ; upload native recording |
| GET | `/api/officer/messages` | free-text SMS forwarded to the officer |
| POST | `/api/demo/reset` | wipe and re-seed DEMO data |

## 7. SMS routing (hub)

1. Sender not registered → reply card `sms_no_registrado`. Nothing else stored except the raw message log.
2. Body starts with `CAF1` → parse (§5). Invalid → `sms_codigo_invalido`. Valid → store observation,
   reply `sms_obs_recibida`, run the outbreak rule (§8). Worklist is computed from observations.
3. Body is `PRECIO`/`PRECIOS` (any case/accents) → `sms_precio` filled from `data/prices.json`.
4. Otherwise → intent classifier: `precio` → `sms_precio`; `reporte` → `sms_reporte_instrucciones`;
   `ayuda` → `sms_ayuda`; `hablar_con_tecnico` → `sms_pasar_tecnico` + forward to officer;
   `otro` or confidence < threshold → `sms_pasar_tecnico` + forward to officer.
5. Replies to a member who just texted are recorded in the outbox as `sent_simulated`
   (the member asked). **Broadcasts (alerts) are queued as `pending_approval` and go out only when co-op
   staff tap Approve.** Every reply text comes from `content/cards.json` (slots filled with numbers/dates only).
6. The reply language follows the member's registered language (`es` default, `tzh` if registered so).

## 8. Outbreak rule (not AI, a transparent rule)

`ROYA` reports from **≥3 different members**, **within 5 km** of each other, in the **last 7 days**
(confidence ≥ model threshold) → create an alert (at most one per 7 days per area) and queue card
`alert_roya` to every consenting member as `pending_approval`. Parameters are design choices,
shown in the UI and documented; they are not agronomic thresholds.

## 9. Worklist ranking (not AI; the officer decides)

Per farm, last 30 days: score = result weight × confidence + cluster bonus.
Weights: `ROYA` 3; `DUDA`/`OTRO` 2 (fail-safe: needs a person); `CERC`/`PHOM`/`MINA`/`ACAR` 2; `SANO` 0.
Confidence factor = conf/100 (1.0 for `DUDA`/`OTRO`). +2 if inside an active alert area.
The UI shows the reason ("Roya 87% · zona de alerta"). Officer actions are stored; `confirmed`/`not_confirmed`
with a true label are saved in a `labels` table as **examples for later retraining**.

## 10. Content (`content/cards.json`)

```json
{
  "version": 1,
  "languages": {"es": "Español", "tzh": "Bats'il k'op (Tseltal)"},
  "cards": [
    {
      "id": "diag_roya",
      "type": "ui | diagnosis | advice | sms | alert",
      "es": "…", "tzh": "…",
      "slots": [],
      "audio": {"es": "audio/es/diag_roya.mp3", "tzh": "audio/tzh/diag_roya.mp3"},
      "audio_source": {"es": "synthetic:piper-es-mls_10246-low", "tzh": "synthetic-provisional"},
      "source": "where the content comes from (manual, URL)",
      "status": {"es": "unverified", "tzh": "unverified"},
      "reviewed_by": {"es": null, "tzh": null}
    }
  ]
}
```
- Every card starts `unverified` in every language; a person marks it verified in the hub (name + date).
  The app shows an **UNVERIFIED / SIN VERIFICAR** badge next to unverified text and audio.
- Slots (e.g. `{precio_cafe}`, `{fecha}`, `{fuente}`) are filled only with numbers, dates and source names.
- Required card ids are listed in §11; content may add more.

## 11. Required card ids

UI (`type: ui`): `ui_app_name`, `ui_choose_language`, `ui_consent_title`, `ui_consent_text`, `ui_consent_accept`,
`ui_consent_decline`, `ui_member_id_prompt`, `ui_pin_optional`, `ui_pin_prompt`, `ui_continue`, `ui_take_photo`,
`ui_photo_tip_underside`, `ui_analyzing`, `ui_confidence`, `ui_play_tzh`, `ui_play_es`, `ui_send_sms`,
`ui_simulate_send`, `ui_saved`, `ui_history`, `ui_settings`, `ui_delete_all`, `ui_delete_confirm`, `ui_sync_photos`,
`ui_synced`, `ui_back`, `ui_unverified`, `ui_demo`, `ui_simulated`, `ui_offline_ready`, `ui_limits_note`,
`ui_language`, `ui_pending_sms`, `ui_sent`, `ui_no_records`.

Diagnosis/advice: `diag_sano`, `diag_roya`, `diag_minador`, `diag_phoma`, `diag_cercospora`, `diag_acaro_rojo`, `diag_duda`,
`advice_roya`, `advice_minador`, `advice_phoma`, `advice_cercospora`, `advice_sano`, `advice_acaro_rojo`,
`advice_call_officer`, `limits_yield` (the app only sees leaf symptoms; it cannot see broca, nutrients, drought, old trees, soil).

SMS/alerts: `sms_obs_recibida`, `sms_codigo_invalido`, `sms_no_registrado`, `sms_precio` (slots: `precio_cafe`, `unidad_cafe`,
`precio_maiz`, `precio_frijol`, `fuente`, `fecha`), `sms_precio_sin_datos`, `sms_reporte_instrucciones`, `sms_ayuda`,
`sms_pasar_tecnico`, `alert_roya` (slots: `comunidad`, `n_reportes`).

## 12. Milestones

1. Plan + scaffold (this file). ✔
2. Image model: data → train → ONNX INT8 → evaluation report (`reports/`), `DATA_CARD.md` started.
3. Offline diagnosis on the phone: photo → result → card → audio (es, tzh). Airplane mode.
4. Save-and-send-later: SMS code, hub inbox, simulator, Wi-Fi photo sync.
5. Hub: registry + consent, outbreak alert, officer worklist, PRECIO, intent sorting, DEMO seed.
6. Guardrails + privacy pass.
7. Ship docs: README, DEMO, METRICS, DATA_CARD, RESPONSIBLE_AI, VIDEO_SCRIPT.

## 13. Known limits (short; details in DATA_CARD.md / RESPONSIBLE_AI.md)

- No Mexican images; JMuBEN is Kenyan, 128×128 crops, with many augmented near-duplicates (we split by
  near-duplicate group to limit leakage). `acaro_rojo` is not in model v1.
- Tseltal text and audio are AI drafts / synthetic until a native speaker reviews and records them.
- Prices are DEMO reference values until replaced with the official table; never a farm-gate price.
- Service workers need a secure origin: for the demo the phone opens the hub via `adb reverse` (localhost)
  or a static HTTPS host; see README.
