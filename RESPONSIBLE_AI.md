# Responsible AI, data and safety

This is the pass/fail part of the judging: are the limits respected, and is the account of privacy, consent, bias
and human oversight credible? Every statement below points to the code that does it. Every number points to a file
in [reports/](reports/) or to [docs/evidence.md](docs/evidence.md).

Labels used here: **measured** (we ran it and counted), **computed** (arithmetic on measured counts, shown),
**DEMO** (invented data), **SIMULATED** (no real SMS), **UNVERIFIED** (no person has checked it).

## Summary

| Guardrail | What the code does | Where |
|---|---|---|
| Fail-safe | Blurry photo, "not a coffee leaf", confidence below 90 %, or an error while reading the photo or running the model → *"No estoy seguro — muestre la hoja al técnico."* The report puts the farm on the officer's list. | [app/infer.js](app/infer.js), [hub/outbreak.py](hub/outbreak.py) |
| Human in the loop | No SMS leaves the phone without the user's tap. Alerts wait for staff to press "Aprobar". The officer decides visits. People, not a script, decided which model ships. | [app/app.js](app/app.js), [hub/main.py](hub/main.py), [model/ship_decision.json](model/ship_decision.json) |
| No hallucinations | No generative model runs in the app or the hub. Both models only pick a card from [content/cards.json](content/cards.json). Slots take only numbers, dates and names that pass a strict filter. | [hub/cards.py](hub/cards.py), [app/content.js](app/content.js) |
| Consent | The hub refuses to register a member without consent and the name of the person who explained it. The app asks before storing anything. | [hub/main.py](hub/main.py), [app/index.html](app/index.html) |
| Data location | Records and photos stay on the phone until the user taps send or sync. The hub runs on the co-op's computer. No cloud. | [app/store.js](app/store.js), [hub/db.py](hub/db.py) |
| Honest gaps | The hub has **no login**. The shipped model was shipped as an **exception to our own ship rule** (section 1.4), and it gives **disease answers on 2.5 % of coffee-plant photos of unknown health** (9 "roya", 1 leaf miner; most such photos showed no visible symptom in a one-rater check). **No card is verified**. Tseltal is an **AI draft** read by a **provisional synthetic voice**. | sections 1, 5, 7, 8 |

---

## 1. Fail-safe: "No estoy seguro — muestre la hoja al técnico"

### 1.1 Exact triggers

The app checks these in order ([app/infer.js](app/infer.js) `diagnose()`, [app/app.js](app/app.js) `onPhoto()`).
Thresholds come from [app/model/labels.json](app/model/labels.json).

| # | Trigger | Exact rule | Code in the SMS | Confidence in the SMS | Reason line (card) |
|---|---|---|---|---|---|
| 1 | The photo cannot be read | the image does not decode, or anything throws before the model runs | `DUDA` | 0 | "La app no está segura." (`ui_reason_low_conf`) |
| 2 | Blurry photo | Laplacian variance of the 128×128 centre square < **4.2** (`blur_threshold`). The model does not run. | `DUDA` | 0 | "La foto salió borrosa." (`ui_reason_blurry`) |
| 3 | Model error | the runtime or the model fails to load or run, or `model/labels.json` (the thresholds) cannot be read: the app then fails closed and retries on the next photo | `DUDA` | 0 | "La app no está segura." |
| 4 | Not a coffee leaf | the top class is `otro` (checked before the threshold) | `OTRO` | the `otro` probability | "No parece hoja de café." (`ui_reason_not_coffee`) |
| 5 | Low confidence | top-1 probability < **0.90** (`threshold`) | `DUDA` | the top-1 % | "La app no está segura." |

The early plan ([PLAN.md](PLAN.md) §3) also listed a "too little leaf colour" check. **It was not built.** The `otro`
class does that job. A storage error *after* the diagnosis is not caught (section 1.5).

### 1.2 What Noor sees and hears

- The title **"No seguro"** with a question-mark icon.
- **"No estoy seguro — muestre la hoja al técnico."** (`diag_duda`), then the reason line.
- The advice card `advice_call_officer`: call the officer or the co-op, and keep a leaf in a closed bag to show
  them.
- The limits card `limits_yield`: the app only sees leaves, not broca, fertiliser, drought, old trees or soil.
- The same cards play aloud in her language if the browser allows autoplay. Two buttons replay them in Tseltal or
  Spanish (a third replays them in English when the app is set to English).
- Screens: [blurry photo](reports/screenshots/journey_09_blurred.png),
  [not a coffee leaf](reports/screenshots/journey_08_not_plant.png).

### 1.3 How the farm reaches the officer

- The fail-safe result is saved and gets an SMS code like any other result. The home screen counts unsent checks.
- When the code reaches the hub (she taps send, or syncs at the co-op), the farm goes on the officer's list.
  `DUDA` and `OTRO` have weight 2 with the confidence factor fixed at 1.0, so the score is 2, or 4 inside an active
  alert area ([hub/outbreak.py](hub/outbreak.py) `WEIGHTS`, `base_score`).
- The list shows the reason: *"Duda (la app no está segura)"* or *"No es hoja de café"*. For a farm with several
  reports, a `DUDA`/`OTRO` counts as more serious than a leaf miner, phoma or Cercospora answer (`SEVERITY`).
- Test: [tests/test_worklist.py](tests/test_worklist.py) `test_ranking_scores_and_reasons` (a `DUDA` at 41 %
  scores 2.0).
- **Limit:** if she never sends the code, nobody sees it.

### 1.4 Evidence: unknown cases mostly go to the fail-safe

The shipped model is **v2 at threshold 0.90** ([app/model/labels.json](app/model/labels.json)). The previous model,
v1 at 0.70, is shown for comparison. All numbers are measured.

| Test set | Shipped v2@0.90 | v1@0.70 (previous) | Source |
|---|---|---|---|
| Kenyan held-out test, 2,500 coffee images | 93.8 % answered, **100.0 %** of answers right, 6.2 % fail-safe. Diseased leaf called "sano": **0.0 %** | 95.9 % answered, 99.9 % right. "sano": 0.0 % | [model_eval.md](reports/model_eval.md) (a) |
| Non-coffee test images (n = 446) | **98.2 %** sent to the fail-safe. 8 accepted (7 distinct photos), mostly apple rust or apple scab leaves answered "roya" | 99.8 % (1 accepted) | [model_eval.md](reports/model_eval.md) (a) |
| Same Kenyan test, blurred (radius 4) | 94.4 % of coffee images sent to the fail-safe. 0.0 % wrong and accepted | 90.9 %; 0.2 % wrong and accepted | [model_eval.md](reports/model_eval.md) (b) |
| Held-out iNaturalist photos of diseased leaves (rust 53, leaf miner 9, Cercospora 10, ojo de gallo 90 = 162) | **116** sent to the fail-safe (19 + 7 + 8 + 82; 71.6 %, *computed*). **36** right (34 rust, 2 leaf miner). **10** wrong but accepted (2 Cercospora called "roya"; 8 ojo de gallo: 6 "roya", 1 leaf miner, 1 phoma; 6.2 %, *computed*). Called "sano": **0** | 154 fail-safe, 0 right, 8 wrong but accepted. "sano": 0 | per-group counts in [model_eval.md](reports/model_eval.md) (g) and [field_eval.md](reports/field_eval.md) |
| iNaturalist *Coffea* plant photos, health unknown (n = 399) | 97.5 % fail-safe. **10 disease answers (2.5 %, 95 % CI 1.4–4.5)**: 9 "roya", 1 leaf miner. 0 "sano" | 100 % fail-safe | [field_eval.md](reports/field_eval.md) |
| Held-out field rust photos (n = 53) | **64.2 %** right [51–76]. 35.8 % fail-safe | 0.0 % right [0–7]. 98.1 % fail-safe | [field_eval.md](reports/field_eval.md) |

**The dangerous error** (a diseased leaf called healthy, so the farm never reaches the officer) was **0** in every
test above, for both models.

**What a false alarm causes.** v2 sometimes says "roya" where there is no rust: it gave disease answers on 2.5 % of
the coffee-plant photos of unknown health (9 "roya", 1 leaf miner; in a one-rater check of the 32 v2@0.70 alarms, 28
showed no visible leaf symptom, [field_coffea_v2_alarms.csv](reports/field_coffea_v2_alarms.csv)), and said "roya" for
some apple-rust leaves, 6 of 90 ojo de gallo photos and 2 of 10 Cercospora photos. Then:
- The phone shows *"Parece roya del cafeto."* with the confidence bar, the rust advice **and** the card
  `advice_call_officer` (call the officer, keep a leaf in a closed bag), then `limits_yield`
  ([app/app.js](app/app.js) `adviceCards`: a rust answer always adds the call-the-officer card). No card names a
  pesticide or a dose ([content/README.md](content/README.md), writing rules).
- If the code reaches the hub, the farm goes on the officer's list with weight 3 (`ROYA`), above a fail-safe report.
  The officer looks at the leaf and marks "Confirmado" or "No confirmado".
- An accepted rust answer always has confidence ≥ 90 %, so it also counts toward the outbreak rule (3 members within
  5 km in 7 days, confidence ≥ the model threshold; [hub/outbreak.py](hub/outbreak.py)). False alarms can therefore
  help create an alert. The alert SMS still waits for staff to press "Aprobar" (section 2).

**In plain words:** v1 was safe but not useful in the field: it refused 217 of 219 rust photos as "not a coffee
leaf". v2 at 0.90 finds rust in about two of three held-out field rust photos and still says "No estoy seguro" when
unsure, but it also gives some false "roya" answers. The officer decides.

**Why v2 at 0.90 shipped: a human exception to our own ship rule.**
- **The rule.** Before computing the v2 field results we fixed five conditions a new model must meet against v1
  ([METRICS.md](METRICS.md) §4c). At its export threshold 0.70, v2 failed two of them: it gave a disease answer for
  8.0 % of the *Coffea* photos and rejected only 95.7 % of non-coffee images. So it was not shipped.
- **The threshold.** We then re-chose v2's threshold on calibration data only (400 new *Coffea* photos from unseen
  observers, plus validation non-coffee images): t = 0.90 ([field_v2_threshold_sweep.md](reports/field_v2_threshold_sweep.md)).
  The v2@0.70 test results had been seen before this step. Evaluated once on the test sets, v2@0.90 passed 4 of the 5
  conditions.
- **What missed.** Condition (2): lose at most 1 point of macro-F1 on the Kenyan lab test. The app-level macro-F1
  dropped **1.04 points** (0.9670 vs 0.9774), so it missed by **0.04 points**. The rule's verdict is "DO NOT SHIP",
  and the reports keep it ([field_v2_threshold_test.json](reports/field_v2_threshold_test.json)).
- **Who decided, and why.** The Cafetal team decided on 2026-10-03 to ship v2@0.90 anyway, recorded in
  [model/ship_decision.json](model/ship_decision.json). The Kenyan close-ups it no longer answers (mostly phoma:
  13.2 % fail-safe vs 1.6 %) get "No estoy seguro", not a wrong answer, and it never called a diseased leaf "sano".
  v2 is the only model that finds rust in field photos. The script that installs the model into the app
  (`model/field_threshold.py install`) does so only because that file names v2@0.90.

### 1.5 Where the fail-safe does not reach

- **A "sano" answer has no safety net.** `SANO` has weight 0, so the farm does not go on the list. The healthy class
  was learned from only **7 near-duplicate groups** of Kenyan photos (about 7–10 distinct source photos;
  [model_eval.md](reports/model_eval.md), "Data"). On the field photos neither v1 nor v2 answered "sano" (0 of 162
  diseased photos, 0 of 399 *Coffea* photos), but we cannot call that answer reliable. The `advice_sano` card still
  says to check the leaves every week, and `limits_yield` plays on every result.
- **A false "roya" is not a fail-safe.** It does reach the officer, but it also tells the farmer her coffee looks
  like it has rust (section 1.4).
- **Unsent reports** never reach the hub (1.3).
- **A storage error after the diagnosis.** If the phone cannot save the record (for example full storage, or browser
  storage blocked), the app stays on "Revisando la hoja…" (`ui_analyzing`) with no result and no fail-safe message: in
  [app/app.js](app/app.js) `onPhoto`, `S.newObsId()` and `S.putObs()` run outside the `try`/`catch` that covers
  reading the photo and running the model.
- **The blur check never fired on the 768 field photos.** They are sharp, about 500 px wide. It was calibrated on the
  Kenyan crops and has not been tested on shaky real phone shots. It only catches blur that is still visible after the
  photo's centre square is shrunk to 128 px, so a moderately blurred full-size photo goes on to the model and its
  0.90 threshold instead (it may then get an answer). For the demo of this trigger, use `blurred_roya.jpg`
  ([DEMO.md](DEMO.md)).
- **The 0.90 threshold was chosen on iNaturalist calibration photos**, not on Chiapas photos. On the test it keeps
  non-coffee rejection at 98.2 %, exactly the 98 % limit with no margin (438 of 446).

---

## 2. Human in the loop: nothing acts on anyone's behalf

| Step | Who decides | How the code makes sure | Checked by |
|---|---|---|---|
| Send the report by SMS | Noor or her daughter | "Enviar por SMS" is an `sms:` link: the phone's own SMS app opens with the code filled in, and the user presses send there. Back in Cafetal, the app asks "Enviado / Cancelar" and marks the report sent only on "Enviado". | [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs), [journey_results.json](reports/journey_results.json) |
| Send photos to the co-op | Noor | Only on a tap ("Mandar fotos a la cooperativa (Wi-Fi)"), and the button only shows when the hub answers. **One tap sends every unsent record of the member with its photo**, including "not a coffee leaf" photos (which might show a person); there is no per-photo choice. A record is marked sent only if the hub says it stored it; otherwise it stays on the phone to retry, and an unknown member ID gets *"Este número de socio no está registrado en la cooperativa"* (checked in [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs)). | [app/app.js](app/app.js) `syncPhotos`, `checkHub` |
| Reply to her own SMS | automatic, fixed card | She asked. The reply is a card (price, help, "your report arrived"). No person checks it before it goes, and the SMS carries no SIN VERIFICAR badge (section 8). | [tests/test_routing.py](tests/test_routing.py) |
| Outbreak alert to all members | co-op staff | The rule (3 members, 5 km, 7 days, rust answers with confidence ≥ the 90 % model threshold) queues one card per member as `pending_approval`. Nothing goes out until someone presses "Aprobar" in "Bandeja de salida". The hub stores when, and the name typed in "Quién aprueba"; that name is optional and defaults to *"personal de la cooperativa"* ([hub/main.py](hub/main.py) `_decide`), so it does not prove who approved. "Rechazar" also exists. | [tests/test_outbreak.py](tests/test_outbreak.py) `test_broadcast_waits_for_approval`. End to end: 24 queued, 1 approved, 23 still pending ([journey_results.json](reports/journey_results.json)) |
| Who gets a visit | the extension officer | The list only ranks, with the reason written out. Banner: *"Usted decide a quién visitar… La app del teléfono puede equivocarse."* The officer marks "Visita programada", "Confirmado" or "No confirmado". | [tests/test_worklist.py](tests/test_worklist.py) |
| What the model learns next | the officer | "Confirmado" / "No confirmado" with a true label saves the example and its photo path in the `labels` table. Turning these into training data is still a manual step (no export script yet). | `test_officer_actions_and_training_labels` |
| Free text the sorter is unsure of, and free-text symptom reports | the officer | Confidence below 0.45, or intent `otro`, gives the reply *"le paso su mensaje al técnico"* and puts the message in the officer's inbox. A text sorted as `reporte` (for example *"mi cafe tiene manchas amarillas"*) gets the how-to-report card **and** goes to the officer's inbox, because a basic-phone member cannot send a CAF1 code. The officer calls back. The hub never sends free text to members. | `test_unknown_text_goes_to_officer`, `test_intents_route_to_the_right_card` |
| What counts as checked content | a named person | "Marcar verificado" needs the reviewer's name, and stores it with the date. A new recording sets the card back to unverified. | [tests/test_content.py](tests/test_content.py) `test_verify_card`, `test_upload_native_audio` |
| Which image model ships | the team | The ship rule is computed by scripts. v2@0.90 failed one condition by 0.04 points and was shipped by an explicit team decision, recorded in `model/ship_decision.json`; `model/field_threshold.py install` writes `app/model/` only when that file names the model (section 1.4). | [field_eval.md](reports/field_eval.md) "Result" |

The system handles no money, books no visits and buys nothing. The SMS gateway is **SIMULATED** in this build: hub
replies are logged as `sent_simulated`.

---

## 3. No hallucinations

- **No generative model** runs anywhere, in the app or in the hub. Generative AI was used only offline, while
  building: an AI model drafted the Tseltal card text and translated the Spanish cards into English (both unverified,
  section 8), and Piper TTS rendered the audio once.
- **The image model** outputs one of 6 labels. A fixed table maps each label to card ids
  ([app/app.js](app/app.js) `DIAG`, `adviceCards`).
- **The SMS sorter** outputs one of 5 intents. A fixed table maps each intent to one card
  ([hub/sms.py](hub/sms.py) `INTENT_CARD`). The exact words PRECIO, AYUDA and TECNICO (and PRICE, HELP, OFFICER) are matched before it runs.
- **Slots** exist only in SMS cards. Their values come from [data/prices.json](data/prices.json), the alert count
  and the registered community name. Each value must pass a whitelist: at most 40 characters, letters, digits,
  space and `. , / : - ( ) % '`, no braces. An undeclared or empty slot raises an error, and then **nothing is
  sent** ([hub/cards.py](hub/cards.py) `render`). Registration checks community names with the same rule.
  - **How a failure shows:** for a reply, the error is only added to the `actions` list of the API response
    ([hub/sms.py](hub/sms.py) `_reply`); it is not stored or written to a log. In an alert broadcast, a member whose
    card fails is skipped with no record ([hub/outbreak.py](hub/outbreak.py) `queue_alert_broadcast`), so staff are
    not told. Because registration uses the same filter, we have not seen this happen.
- **The phone app** fills each screen from card ids. A missing card shows as `[card_id]`; the app never writes a
  sentence itself ([app/content.js](app/content.js)).
- **Tests that enforce it:**
  - [tests/test_content.py](tests/test_content.py) `test_every_outbound_message_is_a_card_template`: every
    outgoing SMS, in all three languages, matches a card with only allowed slot values, in one SMS.
  - `test_render_rejects_free_text_in_slots`.
  - [tests/e2e/journey.mjs](tests/e2e/journey.mjs): "all 51 outbox + 7 thread messages are cards.json templates
    with only slot values filled", and a check that the visible text on 10 phone screens comes from cards.json
    ([journey_results.json](reports/journey_results.json)).
- **Limit: fixed is not the same as correct.** **0 of 83 cards** have been checked by a person, in any of the three
  languages.
  The team wrote the advice from public extension material; some sources were seen only through search summaries
  (each card's `source` field). The cards never name a pesticide or a dose. The hub pages for staff have their own
  Spanish text, which farmers do not see.

---

## 4. Consent

**At the co-op (registry).**
- `POST /api/members` refuses a member without `consent = true` (HTTP 400). It also needs `consent_by`, the staff
  member who explained it, and stores the date and the consent text version ([hub/main.py](hub/main.py)). Test:
  [tests/test_members_sync.py](tests/test_members_sync.py) `test_registration_requires_consent`. A `consent_by` or
  a name of only spaces is refused too (HTTP 400).
- The "Registro de socios" page shows two consent cards in Spanish and Tseltal (and English for visitors), with SIN VERIFICAR badges: what the
  app does (`ui_consent_text`) and what the co-op hub stores and who can read it (`ui_consent_hub_text`, which also
  says the hub has no password yet, section 5). It tells staff to read both aloud in the member's language. Staff
  tick "El socio entendió y está de acuerdo" and type "¿Quién le explicó?" ([hub/static/registro.html](hub/static/registro.html),
  [screenshot](reports/screenshots/journey_20_registro.png)).

**On the phone (first use).**
- The "Su permiso" screen reads itself aloud if the browser allows. It says what is stored on the phone, that the
  photo stays on the phone, that records use the member number and not the name, that nothing is sent without
  "Enviar", that photos go to the co-op only over its Wi-Fi, and that she can delete everything
  ([screenshot](reports/screenshots/app_02_consent.png)).
- "Sí, acepto" stores the time of consent on the phone. "No, gracias" stores nothing and goes back to the start
  (checked in [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs)).
- **Location** is a separate browser permission, asked once. If she refuses, the SMS carries `-` and the hub uses
  her registered plot.

**Taking consent back.** At the co-op, "Borrar" deletes the member with their reports, messages, officer messages,
labels and photos; alerts keep only counts (`test_delete_member_cascades`). The deleted member's ID is never given
out again: the hub keeps only the ID, in `retired_member_ids` ([hub/db.py](hub/db.py),
`test_member_ids_of_deleted_members_are_never_reused`). So codes and photos from the old phone are refused, not filed
under a new member; the app then says *"Este número de socio no está registrado en la cooperativa"* and keeps the
records. On the phone: "Ajustes" → "Borrar todo".

**Gaps.**
- The consent text is **UNVERIFIED in every language**. For a member who reads neither Spanish nor Tseltal, consent is only as good as
  the staff member's spoken explanation.
- The text version is a fixed `"v1"`. The language used to explain it is not recorded.
- The hub card says the data is for staff and the officer, but nothing enforces that yet: the hub has no login
  (section 5). The card says so to the member.
- There is no retention period: nothing is deleted automatically.

---

## 5. Where data lives and who can read it

| Where | What is stored | Who can read it |
|---|---|---|
| **Daughter's phone**, in the browser storage of the app | Settings (localStorage): language, member ID, time of consent, PIN hash, whether location was allowed. Records (IndexedDB, under the member ID): result code, probabilities, confidence, reason, date and time, location rounded to 2 decimals (about 1 km), the photo (JPEG, at most 640 px), the SMS code, sent and synced flags, model version ([app/store.js](app/store.js), [app/app.js](app/app.js)) | Anyone who opens the app on that phone, unless a PIN is set. The app does not encrypt this storage (section 6). |
| **The SMS** (only if she sends it) | `CAF1 M0123 ROYA 96 20261004 16.91,-92.11 #K3F9`: member ID, code, confidence, date, location about 1 km or `-`, a 4-character record ID. No name. ([PLAN.md](PLAN.md) §5, [tests/test_parse.py](tests/test_parse.py)) | The mobile carrier (SMS is not encrypted). A copy stays in the phone's SMS app. |
| **Co-op hub**, the co-op's own computer: SQLite file `hub/cafetal.db` | Members: name, phone, community, plot location rounded to 3 decimals (about 100 m), SMS language, consent record. Reports, including the raw SMS. Every SMS in and out, including the numbers of unregistered senders. Alerts, officer actions and notes, labels, members' free-text messages to the officer ([hub/db.py](hub/db.py)) | Meant for co-op staff and the extension officer. See the gap below. |
| **Co-op hub**: photos | Files in `hub/uploads/`: every photo of every record she syncs, including photos the app judged "not a coffee leaf" (section 2). Served only through `/api/photos/{id}` with `no-store`, never as a static folder ([hub/main.py](hub/main.py)) | Same as above |

**No cloud.** The hub calls no outside service. The app only talks to the server it was loaded from, and the
service worker never caches `/api/` answers ([app/sw.js](app/sw.js)). FastAPI's default API pages (`/docs`,
`/redoc`, `/openapi.json`), which would load Swagger UI and ReDoc from a CDN, are switched off
([hub/main.py](hub/main.py); test `test_no_api_docs_pages`).

**The honest gap: the hub has no login yet.**
- `./run.sh` listens on all network interfaces (`0.0.0.0`) so that phones on the co-op Wi-Fi can sync.
- So **anyone on that network** can read member names, phones, reports and photos. They can also approve or reject
  alerts, delete members, upload audio for any card, and wipe everything through `/api/demo/reset`.
- **Not only people on the network: web pages too.** Approve, reject and `/api/demo/reset` accept a POST with no body
  or a `text/plain` body, which a browser sends to another site without asking (cross-site request forgery). So any
  web page open in the staff computer's browser could approve every pending alert or wipe the hub.
- This is fine for a demo on a closed network. It is **not fine for real use**.
- Before real use: put a password in front of the hub (for example a reverse proxy with login), or keep it on
  `localhost` and reach it over a VPN. Remove the DEMO reset. Accept state-changing
  requests only as `application/json` from the hub's own pages (check `Origin`). Serve the app over HTTPS. Make
  encrypted backups. There are no backups today.

---

## 6. Shared or lost phone

- **Member ID, not name.** The phone stores `M` + 4 digits. It never stores a name, a phone number, money or
  mobile-money data, and the app never asks for them.
- **One member at a time.** To switch member, use "Borrar todo".
- **Optional 4-digit PIN** ([app/store.js](app/store.js) `pinHash`).
  - Only a SHA-256 hash of the PIN, mixed with the member ID, is stored.
  - The app locks when it opens, or when the lock button is tapped. It does not lock itself after a while.
  - **It is weak.** There are only 10,000 PINs, so anyone who can read the browser storage can find it at once.
    It does not encrypt the records. It stops a family member from looking casually, not a thief with tools.
- **"Borrar todo"** deletes the settings, every record and every photo in the app, and keeps the offline app so it
  still works without internet (checked in [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs)).
- **What "Borrar todo" cannot delete:**
  - a photo picked from the gallery stays in the gallery; the camera may also keep a copy, depending on the phone;
  - sent SMS stay in the phone's SMS app;
  - what was already sent or synced to the hub: the co-op deletes that on request.
- **If the phone is lost,** the finder can learn the member ID, dates, results, locations to about 1 km, and the leaf
  photos. Linking the member ID to a person needs the co-op's registry.

---

## 7. Bias and limits

- **Training data is mostly Kenyan.** JMuBEN: Arabica leaves from Kenya, 128 px crops, plus 147 diseased iNaturalist
  field photos from other countries (none from the Mexico+Guatemala box). No Mexican training images. Local
  varieties, light, backgrounds and cheap cameras are not represented ([DATA_CARD.md](DATA_CARD.md)).
- **The healthy class** comes from only 7 near-duplicate groups of photos (section 1.5).
- **Field result:** on held-out iNaturalist photos the shipped v2 at 0.90 got 34 of 53 rust photos right (64.2 %),
  but only 2 of 9 leaf-miner and 0 of 10 Cercospora photos; v1 got 0 of 219 rust photos right. A well-known study
  shows the same lab-to-field drop: 99.35 % on its own test set, 31.4 % on photos taken in other conditions
  (Mohanty et al. 2016, code **F** in [docs/evidence.md](docs/evidence.md) §10).
- **Data bias shows up directly.** v2 saw only diseased field photos and partly learned "field photo of a coffee
  plant = rust": at its export threshold 0.70 it gave a disease answer for 8.0 % of the *Coffea* photos; at the
  shipped 0.90, 2.5 %. It also calls some apple-rust and apple-scab leaves "roya". The fix is healthy **and** diseased
  Chiapas photos confirmed by the officer, which the hub's `labels` table starts to collect.
- **The field test is a proxy:** iNaturalist photos from other countries, labelled by the iNaturalist community,
  screened by one person. **Only 4 rust photos are from Mexico** ([field_eval.md](reports/field_eval.md)).
- **What the model cannot see:** red spider mite (`acaro_rojo`, no data) and ojo de gallo (not a class; with v2 at
  0.90, 91.1 % of those photos went to the fail-safe and 6 of 90 were called "roya"). It sees only leaves: not broca, nutrients, drought, old trees or soil. The
  `limits_yield` card says so on every result.
- **Who is left out:**
  - Diagnosis needs a smartphone. Noor has one only on weekends.
  - With a basic phone she gets SMS only. SMS replies and alerts are text, so reading is needed; voice exists only
    in the smartphone app.
  - Free text in Tseltal mostly goes to the officer, which adds to the officer's work (section 8).
- **The SMS sorter** was trained and tested on messages written by the team. Real member messages will score lower
  ([intent_eval.md](reports/intent_eval.md)).
- **The outbreak rule** (3 members, 5 km, 7 days) and the worklist weights are design choices, not agronomic
  thresholds. They have not been tested against real outbreaks.

---

## 8. Local language: Tseltal, and less-supported languages

- **Languages:** Tseltal (*Bats'il k'op*, `tzh`) and Spanish are the co-op's languages. **English** (`en`) is a third
  UI language for international judges and visitors only. All 83 cards have text in all three. 74 cards have audio in
  each language (222 MP3s, about 3.5 MB); the 9 SMS and alert cards are text only ([content/README.md](content/README.md)).
- **Tseltal text is an AI draft.** Vocabulary was checked word by word against Polian (2018), *Tseltal–Spanish
  multidialectal dictionary* (CC BY 4.0). The grammar is a best guess, and Tseltal differs between towns.
- **Tseltal audio is provisional:** a Spanish synthetic voice (Piper) reading the Tseltal text. It drops glottal
  stops and does not sound like a Tseltal speaker. Spanish audio is the same Piper voice.
- **English is an AI translation of the Spanish cards**, read by the Piper voice `en-us-lessac-medium`. No English
  speaker has checked it. English SMS cards advertise the keywords PRICE, HELP and OFFICER, and the co-op can register
  a member with language `en`; the SMS sorter has no English examples, so English free text goes to the officer.
- **Everything is marked UNVERIFIED / SIN VERIFICAR**, in all three languages: on the phone, in the outbox and on the
  content page. **SMS on a basic phone carry no badge:** the 9 SMS and alert cards (all unverified, including the
  AI-draft Tseltal) reach members as plain text; only the hub outbox shows SIN VERIFICAR.
- **How it gets fixed:** on the hub's "Contenido" page a native speaker records each card ("● Grabar" or "Subir
  archivo"), and a reviewer marks it verified with name and date. Phones download the new audio the next time they
  are online at the co-op ([app/sw.js](app/sw.js)). The audio script never overwrites a native recording.

**How it fares in a less-supported language.** Tseltal already is one. What exists for it (all code **F**,
[docs/evidence.md](docs/evidence.md) §8):

| Resource | Tseltal status | Used? |
|---|---|---|
| Meta MMS text-to-speech | Two dialect checkpoints only (Tenejapa, Bachajón). 145 MB each, CC BY-NC 4.0, trained on readings of religious texts | No: could not be downloaded here, non-commercial licence, too big for the phone, quality on farm words unknown |
| NLLB-200 / FLORES-200 | Not included | No |
| Mozilla Common Voice (v27.0) | Absent | No |
| Google MADLAD-400 | Lists `tzh`. 2.94 B parameters; quality not measured | No |

So Cafetal does not depend on a language model for anything a farmer hears. A language is a set of cards plus
recordings. To add one (say Tsotsil):

1. Write about **83 card texts** (about 860 words; the minimum is the 60 required ids).
2. Record the **74 spoken cards** with a native speaker.
3. **No image-model retraining:** the model outputs a label, and the label points to a card.
4. Two small extras:
   - The hub's registration accepts `es`, `tzh` and `en` today: add the new code in [hub/main.py](hub/main.py)
     (`MemberIn.language`) and [hub/static/registro.html](hub/static/registro.html).
   - The SMS sorter needs examples in the new language and a retrain with `hub/train_intent.py`. Until then, free
     text in that language goes to the officer, which is the safe default.

English was added exactly this way, plus one card (`ui_play_en`) for its replay button
([content/README.md](content/README.md)).

**Free text in Tseltal today:** there are too few examples to measure. Most of it falls below the threshold and goes
to the officer ([intent_eval.md](reports/intent_eval.md)). The exact words PRECIO, AYUDA and TECNICO (and PRICE, HELP,
OFFICER) work whatever language the member speaks.

---

## 9. Misuse and risks

| Risk | What could happen | In place today | Still needed |
|---|---|---|---|
| **Fake reports** | Member IDs are sequential and easy to guess. The hub accepts a CAF1 code from an unregistered phone if the member exists, so the daughter's phone works ([hub/sms.py](hub/sms.py) `route`). Anyone on the LAN can also post to `/api/sms/inbound` or `/api/observations/sync`. Fake reports put farms on the list, and 3 fake members within 5 km can create an alert. False "roya" answers from the model (section 1.4) can add to an alert in the same way. | Alerts wait for staff approval. At most one alert per area per 7 days. A registered phone cannot send a code for another member (`test_code_for_another_member_from_registered_phone_is_rejected`). IDs of deleted members are never reused. Every SMS is logged with the sender's number. The officer decides visits. | Accept codes only from the member's phone or a registered family phone. Hub login. Show the sender's number on the worklist. |
| **Open hub on the LAN** | Everything in section 5, plus replacing a card's audio: phones would download it and play it, marked SIN VERIFICAR. A web page open on the staff computer could approve alerts or wipe the hub (cross-site requests, section 5) | The hub is on the co-op network only | Password or VPN, no DEMO reset, JSON-only or Origin-checked POSTs, a required approver name, HTTPS, backups |
| **Alert fatigue** | Too many alerts, so members stop reading them | 3 members, 5 km, 7 days; one alert per area per week; staff approve or reject each one; the rule is shown on the hub home page | Tune the rule with the officer; count rejected alerts |
| **Farmer over-trust** | She treats "Roya 99 %" as a diagnosis and buys a fungicide, although v2 also gives disease answers on 2.5 % of coffee-plant photos of unknown health (9 "roya", 1 leaf miner; most such photos showed no visible symptom in a one-rater check) | The card says *"Parece…"* (looks like). The confidence bar is shown. The rust advice always comes with the "call the officer" card. No card names a pesticide or a dose. Limits card. SIN VERIFICAR badges. | Agronomist review of the cards; a model validated on Chiapas photos |
| **Officer over-trust** | Visits by rank only and ignores "Duda" | Banner: the app can be wrong, *"Usted decide"*. Reasons are shown. `DUDA` ranks as "a person must look". | A short briefing for the officer |
| **Confusing fail-safe** | A real coffee leaf gets *"No parece hoja de café"* next to "Seguridad 99 %" (the bar shows the confidence of the "not coffee" answer). She may stop trusting the app. | The main message is still "show the leaf to the officer", and the farm still reaches the list | Reword that reason and hide the bar for `OTRO`, after testing with members |
| **Price misread** | PRECIO taken as what the buyer must pay | The card says "precio de referencia", "No es el precio de su comunidad", with source and date. Prices are marked DEMO. | Official source checked, `demo` set to false |
| **Location exposure** | Member ID + about 1 km location in the SMS | Rounded to 2 decimals; `-` if location is refused | Coarser rounding where communities are small |
| **Sharing beyond the co-op** | Registry or reports passed to buyers or agencies | Nothing leaves the hub automatically | A written data-use rule, in a reviewed consent v2 |

---

## 10. Before real use: checklist

- [ ] An agronomist or the extension officer checks every Spanish advice card on the "Contenido" page (0 of 83 today).
- [ ] A native Tseltal speaker from the co-op's area reviews the Tseltal text and records the 74 spoken cards.
- [ ] Collect officer-confirmed Chiapas photos, **healthy and diseased**. Rerun the field protocol
      ([model/README.md](model/README.md)). Ship a new model only if it passes the ship rule, or record any exception
      openly, the way v2@0.90's is recorded in `model/ship_decision.json`. Measure false "roya" answers on healthy
      Chiapas leaves before relying on the outbreak alert.
- [ ] Decide whether the 105 NC/ND iNaturalist photos in v2's training set are acceptable, or retrain on CC0/CC BY
      photos only ([DATA_CARD.md](DATA_CARD.md) §4).
- [ ] Decide how a "sano" answer is handled until healthy Chiapas photos exist (today it does not reach the officer).
- [ ] Reword the "not a coffee leaf" reason and hide the confidence bar for `OTRO`; test it with members.
- [ ] Hub login (password or VPN). Remove `/api/demo/reset`. Refuse body-less or
      `text/plain` POSTs (or check `Origin`). Require the approver's name to approve an alert. Serve the app over HTTPS.
- [ ] Store card errors (today they are only in the API response, and a failed alert card skips the member silently).
- [ ] In the app, catch a storage error after the diagnosis and still show the fail-safe and the SMS code.
- [ ] Let the member choose which photos to send, or do not upload "not a coffee leaf" photos.
- [ ] `./run.sh` loads DEMO data when the database is missing: turn that off.
- [ ] Accept CAF1 codes only from registered phones (the member's own, or a listed family phone).
- [ ] Encrypted backups of `hub/cafetal.db` and `hub/uploads/`, and a retention period.
- [ ] Consent v2: reviewed in both languages, with a data-use rule. Record which language it was explained in.
      Train the staff who explain it.
- [ ] Replace the DEMO prices with checked official values and set `demo` to false ([DATA_CARD.md](DATA_CARD.md) §9).
- [ ] Review the outbreak rule with the officer.
- [ ] A real SMS gateway: test delivery and cost. Keep alerts in `pending_approval`.
- [ ] Test on a real low-end Android phone: offline install, speed, battery ([METRICS.md](METRICS.md) §12).

## Sources

- Code: [app/](app/), [hub/](hub/), [content/cards.json](content/cards.json), [app/model/labels.json](app/model/labels.json)
- Tests: [tests/](tests/) (hub: 65 passed, 1 skipped on 2026-10-03), [tests/e2e/](tests/e2e/),
  [reports/journey_results.json](reports/journey_results.json) (43 of 43 checks passed)
- Model results: [reports/model_eval.md](reports/model_eval.md), [reports/field_eval.md](reports/field_eval.md),
  [reports/field_v2_threshold_sweep.md](reports/field_v2_threshold_sweep.md), [METRICS.md](METRICS.md); ship decision:
  [model/ship_decision.json](model/ship_decision.json)
- SMS sorter: [reports/intent_eval.md](reports/intent_eval.md)
- Language resources and the lab-to-field study: [docs/evidence.md](docs/evidence.md) §8 and §10
- Datasets and licences: [DATA_CARD.md](DATA_CARD.md)
