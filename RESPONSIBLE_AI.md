# Responsible AI, data and safety

This is the pass/fail part of the judging: are the limits respected, and is the account of privacy, consent, bias
and human oversight credible? Every statement below points to the code that does it. Every number points to a file
in [reports/](reports/) or to [docs/evidence.md](docs/evidence.md).

Labels used here: **measured** (we ran it and counted), **computed** (arithmetic on measured counts, shown),
**DEMO** (invented data), **SIMULATED** (no real SMS), **UNVERIFIED** (no person has checked it).

## Summary

| Guardrail | What the code does | Where |
|---|---|---|
| Fail-safe | Blurry photo, "not a coffee leaf", confidence below 70 %, or any error → *"No estoy seguro — muestre la hoja al técnico."* The report puts the farm on the officer's list. | [app/infer.js](app/infer.js), [hub/outbreak.py](hub/outbreak.py) |
| Human in the loop | No SMS leaves the phone without the user's tap. Alerts wait for staff to press "Aprobar". The officer decides visits. | [app/app.js](app/app.js), [hub/main.py](hub/main.py) |
| No hallucinations | No generative model runs in the app or the hub. Both models only pick a card from [content/cards.json](content/cards.json). Slots take only numbers, dates and names that pass a strict filter. | [hub/cards.py](hub/cards.py), [app/content.js](app/content.js) |
| Consent | The hub refuses to register a member without consent and the name of the person who explained it. The app asks before storing anything. | [hub/main.py](hub/main.py), [app/index.html](app/index.html) |
| Data location | Records and photos stay on the phone until the user taps send or sync. The hub runs on the co-op's computer. No cloud. | [app/store.js](app/store.js), [hub/db.py](hub/db.py) |
| Honest gaps | The hub has **no login**. The shipped model **does not work on field photos** yet. **No card is verified**. Tseltal is an **AI draft** read by a **provisional synthetic voice**. | sections 5, 7, 8 |

---

## 1. Fail-safe: "No estoy seguro — muestre la hoja al técnico"

### 1.1 Exact triggers

The app checks these in order ([app/infer.js](app/infer.js) `diagnose()`, [app/app.js](app/app.js) `onPhoto()`).
Thresholds come from [app/model/labels.json](app/model/labels.json).

| # | Trigger | Exact rule | Code in the SMS | Confidence in the SMS | Reason line (card) |
|---|---|---|---|---|---|
| 1 | The photo cannot be read | the image does not decode, or anything throws before the model runs | `DUDA` | 0 | "La app no está segura." (`ui_reason_low_conf`) |
| 2 | Blurry photo | Laplacian variance of the 128×128 centre square < **4.2** (`blur_threshold`). The model does not run. | `DUDA` | 0 | "La foto salió borrosa." (`ui_reason_blurry`) |
| 3 | Model error | the runtime or the model fails to load or run | `DUDA` | 0 | "La app no está segura." |
| 4 | Not a coffee leaf | the top class is `otro` (checked before the threshold) | `OTRO` | the `otro` probability | "No parece hoja de café." (`ui_reason_not_coffee`) |
| 5 | Low confidence | top-1 probability < **0.70** (`threshold`) | `DUDA` | the top-1 % | "La app no está segura." |

[PLAN.md](PLAN.md) §3 also mentions a "too little leaf colour" check. **It was not built.** The `otro` class does
that job.

### 1.2 What Noor sees and hears

- The title **"No seguro"** with a question-mark icon.
- **"No estoy seguro — muestre la hoja al técnico."** (`diag_duda`), then the reason line.
- The advice card `advice_call_officer`: call the officer or the co-op, and keep a leaf in a closed bag to show
  them.
- The limits card `limits_yield`: the app only sees leaves, not broca, fertiliser, drought, old trees or soil.
- The same cards play aloud in her language if the browser allows autoplay. Two buttons replay them in Tseltal or
  Spanish.
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

| Test set (shipped model v1) | Result | Source |
|---|---|---|
| Kenyan held-out test, 2,500 coffee images | 95.9 % answered, 99.9 % of answers right. Diseased leaf called "sano": **0.0 %** | [model_eval.md](reports/model_eval.md) (a) |
| Non-coffee test images (n = 446) | **99.8 %** sent to the fail-safe | [model_eval.md](reports/model_eval.md) (a) |
| Same Kenyan test, blurred (radius 4) | 90.9 % of coffee images sent to the fail-safe. 0.2 % wrong and accepted | [model_eval.md](reports/model_eval.md) (b) |
| iNaturalist field photos of diseased leaves, none seen in training (rust 219, leaf miner 30, Cercospora 30, ojo de gallo 90 = 369) | **360 of 369** sent to the fail-safe (218 + 30 + 28 + 84; 97.6 %, *computed*). **9** wrong but accepted (1 + 0 + 2 + 6; 2.4 %, *computed*). Called "sano": **0** | per-group counts, "v1 on ALL photos" in [field_eval.md](reports/field_eval.md) |
| iNaturalist *Coffea* plant photos, health unknown (n = 399) | 100 % fail-safe. 0 disease answers, 0 "sano" | [field_eval.md](reports/field_eval.md) |
| Held-out field rust photos (n = 53) | **0.0 %** right [95 % CI 0–7]. 98.1 % fail-safe | [field_eval.md](reports/field_eval.md) |

**The dangerous error** (a diseased leaf called healthy, so the farm never reaches the officer) was **0** in every
test above.

The 9 wrong answers were 1 rust photo and 2 Cercospora photos called phoma, and 6 ojo de gallo photos called leaf
miner (4) or phoma (2). Those answers still put the farm on the list (weight 2), and no advice card names a pesticide
or a dose ([content/README.md](content/README.md), writing rules).

**In plain words:** the fail-safe works in the field because the model refuses almost everything there. That is
safe, not useful. 217 of the 219 rust photos were refused as "not a coffee leaf".

**Why we did not ship a more confident model.** An experimental v2, trained with 147 field photos, got 71.7 % of
held-out rust photos right [58–82]. But it gave a disease answer for 8.0 % of the *Coffea* plant photos [6–11], and
28 of those 32 photos show no symptom. It also rejected only 95.7 % of non-coffee images. It failed the ship rule we
fixed before computing the field results, so the app keeps v1
([field_eval.md](reports/field_eval.md), [METRICS.md](METRICS.md) §4c). More answers would have meant more
confident wrong answers.

### 1.5 Where the fail-safe does not reach

- **A "sano" answer has no safety net.** `SANO` has weight 0, so the farm does not go on the list. The healthy class
  was learned from only **7 distinct source photos** ([model_eval.md](reports/model_eval.md), "Data"). On the field
  photos v1 never answered "sano", but we cannot call that answer reliable. The `advice_sano` card still says to
  check the leaves every week, and `limits_yield` plays on every result.
- **Unsent reports** never reach the hub (1.3).
- **The blur check never fired on the 768 field photos.** They are sharp, about 500 px wide. It was calibrated on the
  Kenyan crops and has not been tested on shaky real phone shots.
- **The 0.70 threshold is a policy floor.** The value the Kenyan validation data suggested was 0.5. Neither was
  calibrated on Chiapas photos ([model_eval.md](reports/model_eval.md), "Calibration").

---

## 2. Human in the loop: nothing acts on anyone's behalf

| Step | Who decides | How the code makes sure | Checked by |
|---|---|---|---|
| Send the report by SMS | Noor or her daughter | "Enviar por SMS" is an `sms:` link: the phone's own SMS app opens with the code filled in, and the user presses send there. Back in Cafetal, the app asks "Enviado / Cancelar" and marks the report sent only on "Enviado". | [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs), [journey_results.json](reports/journey_results.json) |
| Send photos to the co-op | Noor | Only on a tap ("Mandar fotos a la cooperativa (Wi-Fi)"), and the button only shows when the hub answers. A record is marked sent only if the hub says it stored it; otherwise it stays on the phone to retry, and an unknown member ID gets *"Este número de socio no está registrado en la cooperativa"* (checked in [tests/e2e/app_offline.mjs](tests/e2e/app_offline.mjs)). | [app/app.js](app/app.js) `syncPhotos`, `checkHub` |
| Reply to her own SMS | automatic, fixed card | She asked. The reply is a card (price, help, "your report arrived"). | [tests/test_routing.py](tests/test_routing.py) |
| Outbreak alert to all members | co-op staff | The rule (3 members, 5 km, 7 days) queues one card per member as `pending_approval`. Nothing goes out until someone presses "Aprobar" in "Bandeja de salida". The hub stores who approved and when. "Rechazar" also exists. | [tests/test_outbreak.py](tests/test_outbreak.py) `test_broadcast_waits_for_approval`. End to end: 24 queued, 1 approved, 23 still pending ([journey_results.json](reports/journey_results.json)) |
| Who gets a visit | the extension officer | The list only ranks, with the reason written out. Banner: *"Usted decide a quién visitar… La app del teléfono puede equivocarse."* The officer marks "Visita programada", "Confirmado" or "No confirmado". | [tests/test_worklist.py](tests/test_worklist.py) |
| What the model learns next | the officer | "Confirmado" / "No confirmado" with a true label saves the example and its photo path in the `labels` table. Turning these into training data is still a manual step (no export script yet). | `test_officer_actions_and_training_labels` |
| Free text the sorter is unsure of | the officer | Confidence below 0.45, or intent `otro`, gives the reply *"le paso su mensaje al técnico"* and puts the message in the officer's inbox. The officer calls back. The hub never sends free text to members. | `test_unknown_text_goes_to_officer` |
| What counts as checked content | a named person | "Marcar verificado" needs the reviewer's name, and stores it with the date. A new recording sets the card back to unverified. | [tests/test_content.py](tests/test_content.py) `test_verify_card`, `test_upload_native_audio` |

The system handles no money, books no visits and buys nothing. The SMS gateway is **SIMULATED** in this build: hub
replies are logged as `sent_simulated`.

---

## 3. No hallucinations

- **No generative model** runs anywhere, in the app or in the hub. Generative AI was used only offline, while
  building: an AI model drafted the Tseltal card text (unverified, section 8), and Piper TTS rendered the audio once.
- **The image model** outputs one of 6 labels. A fixed table maps each label to card ids
  ([app/app.js](app/app.js) `DIAG`, `adviceCards`).
- **The SMS sorter** outputs one of 5 intents. A fixed table maps each intent to one card
  ([hub/sms.py](hub/sms.py) `INTENT_CARD`). The exact words PRECIO, AYUDA and TECNICO are matched before it runs.
- **Slots** exist only in SMS cards. Their values come from [data/prices.json](data/prices.json), the alert count
  and the registered community name. Each value must pass a whitelist: at most 40 characters, letters, digits,
  space and `. , / : - ( ) % '`, no braces. An undeclared or empty slot raises an error, and then **nothing is
  sent**; the error is logged ([hub/cards.py](hub/cards.py) `render`, [hub/sms.py](hub/sms.py) `_reply`).
  Registration checks community names with the same rule.
- **The phone app** fills each screen from card ids. A missing card shows as `[card_id]`; the app never writes a
  sentence itself ([app/content.js](app/content.js)).
- **Tests that enforce it:**
  - [tests/test_content.py](tests/test_content.py) `test_every_outbound_message_is_a_card_template`: every
    outgoing SMS, in both languages, matches a card with only allowed slot values, in one SMS.
  - `test_render_rejects_free_text_in_slots`.
  - [tests/e2e/journey.mjs](tests/e2e/journey.mjs): "all 51 outbox + 7 thread messages are cards.json templates
    with only slot values filled", and a check that the visible text on 10 phone screens comes from cards.json
    ([journey_results.json](reports/journey_results.json)).
- **Limit: fixed is not the same as correct.** **0 of 82 cards** have been checked by a person, in either language.
  The team wrote the advice from public extension material; some sources were seen only through search summaries
  (each card's `source` field). The cards never name a pesticide or a dose. The hub pages for staff have their own
  Spanish text, which farmers do not see.

---

## 4. Consent

**At the co-op (registry).**
- `POST /api/members` refuses a member without `consent = true` (HTTP 400). It also needs `consent_by`, the staff
  member who explained it, and stores the date and the consent text version ([hub/main.py](hub/main.py)). Test:
  [tests/test_members_sync.py](tests/test_members_sync.py) `test_registration_requires_consent`.
- The "Registro de socios" page shows two consent cards in Spanish and Tseltal, with SIN VERIFICAR badges: what the
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
- The consent text is **UNVERIFIED in both languages**. For a member who reads neither, consent is only as good as
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
| **The SMS** (only if she sends it) | `CAF1 M0123 ROYA 87 20261004 16.91,-92.11 #K3F9`: member ID, code, confidence, date, location about 1 km or `-`, a 4-character record ID. No name. ([PLAN.md](PLAN.md) §5, [tests/test_parse.py](tests/test_parse.py)) | The mobile carrier (SMS is not encrypted). A copy stays in the phone's SMS app. |
| **Co-op hub**, the co-op's own computer: SQLite file `hub/cafetal.db` | Members: name, phone, community, plot location rounded to 3 decimals (about 100 m), SMS language, consent record. Reports, including the raw SMS. Every SMS in and out, including the numbers of unregistered senders. Alerts, officer actions and notes, labels, members' free-text messages to the officer ([hub/db.py](hub/db.py)) | Meant for co-op staff and the extension officer. See the gap below. |
| **Co-op hub**: photos | Files in `hub/uploads/`. Served only through `/api/photos/{id}` with `no-store`, never as a static folder ([hub/main.py](hub/main.py)) | Same as above |

**No cloud.** The hub calls no outside service. The app only talks to the server it was loaded from, and the
service worker never caches `/api/` answers ([app/sw.js](app/sw.js)).

**The honest gap: the hub has no login yet.**
- `./run.sh` listens on all network interfaces (`0.0.0.0`) so that phones on the co-op Wi-Fi can sync.
- So **anyone on that network** can read member names, phones, reports and photos. They can also approve or reject
  alerts, delete members, upload audio for any card, and wipe everything through `/api/demo/reset`.
- This is fine for a demo on a closed network. It is **not fine for real use**.
- Before real use: put a password in front of the hub (for example a reverse proxy with login), or keep it on
  `localhost` and reach it over a VPN. Remove the DEMO reset. Serve the app over HTTPS. Make encrypted backups.
  There are no backups today.

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

- **Training data is Kenyan.** JMuBEN: Arabica leaves from Kenya, 128 px crops. No Mexican images. Local
  varieties, light, backgrounds and cheap cameras are not represented ([DATA_CARD.md](DATA_CARD.md)).
- **The healthy class** comes from only 7 distinct source photos (section 1.5).
- **Field result:** v1 got 0 of 219 iNaturalist rust photos right and refused almost all of them. A well-known
  study shows the same lab-to-field drop: 99.35 % on its own test set, 31.4 % on photos taken in other conditions
  (Mohanty et al. 2016, code **F** in [docs/evidence.md](docs/evidence.md) §10).
- **Data bias shows up directly.** v2 saw only diseased field photos and partly learned "field photo of a coffee
  plant = rust". The fix is healthy **and** diseased Chiapas photos confirmed by the officer, which the hub's
  `labels` table starts to collect.
- **The field test is a proxy:** iNaturalist photos from other countries, labelled by the iNaturalist community,
  screened by one person. **Only 4 rust photos are from Mexico** ([field_eval.md](reports/field_eval.md)).
- **What the model cannot see:** red spider mite (`acaro_rojo`, no data) and ojo de gallo (not a class; 93.3 % of
  those photos went to the fail-safe). It sees only leaves: not broca, nutrients, drought, old trees or soil. The
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

- **Languages:** Tseltal (*Bats'il k'op*, `tzh`) and Spanish. All 82 cards have text in both. 73 cards have audio in
  both; the 9 SMS and alert cards are text only ([content/README.md](content/README.md)).
- **Tseltal text is an AI draft.** Vocabulary was checked word by word against Polian (2018), *Tseltal–Spanish
  multidialectal dictionary* (CC BY 4.0). The grammar is a best guess, and Tseltal differs between towns.
- **Tseltal audio is provisional:** a Spanish synthetic voice (Piper) reading the Tseltal text. It drops glottal
  stops and does not sound like a Tseltal speaker. Spanish audio is the same Piper voice.
- **Everything is marked UNVERIFIED / SIN VERIFICAR:** on the phone, in the outbox and on the content page.
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

1. Write about **82 card texts** (about 860 words; the minimum is the 59 required ids).
2. Record the **73 spoken cards** with a native speaker.
3. **No image-model retraining:** the model outputs a label, and the label points to a card.
4. Two small extras:
   - The hub's registration accepts only `es` and `tzh` today: one line each in [hub/main.py](hub/main.py)
     (`MemberIn.language`) and [hub/static/registro.html](hub/static/registro.html).
   - The SMS sorter needs examples in the new language and a retrain with `hub/train_intent.py`. Until then, free
     text in that language goes to the officer, which is the safe default.

**Free text in Tseltal today:** there are too few examples to measure. Most of it falls below the threshold and goes
to the officer ([intent_eval.md](reports/intent_eval.md)). The exact words PRECIO, AYUDA and TECNICO work whatever
language the member speaks.

---

## 9. Misuse and risks

| Risk | What could happen | In place today | Still needed |
|---|---|---|---|
| **Fake reports** | Member IDs are sequential and easy to guess. The hub accepts a CAF1 code from an unregistered phone if the member exists, so the daughter's phone works ([hub/sms.py](hub/sms.py) `route`). Anyone on the LAN can also post to `/api/sms/inbound` or `/api/observations/sync`. Fake reports put farms on the list, and 3 fake members within 5 km can create an alert. | Alerts wait for staff approval. At most one alert per area per 7 days. A registered phone cannot send a code for another member (`test_code_for_another_member_from_registered_phone_is_rejected`). IDs of deleted members are never reused. Every SMS is logged with the sender's number. The officer decides visits. | Accept codes only from the member's phone or a registered family phone. Hub login. Show the sender's number on the worklist. |
| **Open hub on the LAN** | Everything in section 5, plus replacing a card's audio: phones would download it and play it, marked SIN VERIFICAR | The hub is on the co-op network only | Password or VPN, no DEMO reset, HTTPS, backups |
| **Alert fatigue** | Too many alerts, so members stop reading them | 3 members, 5 km, 7 days; one alert per area per week; staff approve or reject each one; the rule is shown on the hub home page | Tune the rule with the officer; count rejected alerts |
| **Farmer over-trust** | She treats "Roya 99 %" as a diagnosis and buys a fungicide | The card says *"Parece…"* (looks like). The confidence bar is shown. The rust advice always comes with the "call the officer" card. No card names a pesticide or a dose. Limits card. SIN VERIFICAR badges. | Agronomist review of the cards; a model validated on Chiapas photos |
| **Officer over-trust** | Visits by rank only and ignores "Duda" | Banner: the app can be wrong, *"Usted decide"*. Reasons are shown. `DUDA` ranks as "a person must look". | A short briefing for the officer |
| **Confusing fail-safe** | A real coffee leaf gets *"No parece hoja de café"* next to "Seguridad 99 %" (the bar shows the confidence of the "not coffee" answer). She may stop trusting the app. | The main message is still "show the leaf to the officer", and the farm still reaches the list | Reword that reason and hide the bar for `OTRO`, after testing with members |
| **Price misread** | PRECIO taken as what the buyer must pay | The card says "precio de referencia", "No es el precio de su comunidad", with source and date. Prices are marked DEMO. | Official source checked, `demo` set to false |
| **Location exposure** | Member ID + about 1 km location in the SMS | Rounded to 2 decimals; `-` if location is refused | Coarser rounding where communities are small |
| **Sharing beyond the co-op** | Registry or reports passed to buyers or agencies | Nothing leaves the hub automatically | A written data-use rule, in a reviewed consent v2 |

---

## 10. Before real use: checklist

- [ ] An agronomist or the extension officer checks every Spanish advice card on the "Contenido" page (0 of 82 today).
- [ ] A native Tseltal speaker from the co-op's area reviews the Tseltal text and records the 73 spoken cards.
- [ ] Collect officer-confirmed Chiapas photos, **healthy and diseased**. Rerun the field protocol
      ([model/README.md](model/README.md)). Ship a new model only if it passes the ship rule.
- [ ] Decide how a "sano" answer is handled until healthy Chiapas photos exist (today it does not reach the officer).
- [ ] Reword the "not a coffee leaf" reason and hide the confidence bar for `OTRO`; test it with members.
- [ ] Hub login (password or VPN). Remove `/api/demo/reset`. Serve the app over HTTPS.
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
- Tests: [tests/](tests/) (hub: 62 passed, 1 skipped on 2026-10-03), [tests/e2e/](tests/e2e/),
  [reports/journey_results.json](reports/journey_results.json) (43 of 43 checks passed)
- Model results: [reports/model_eval.md](reports/model_eval.md), [reports/field_eval.md](reports/field_eval.md),
  [METRICS.md](METRICS.md)
- SMS sorter: [reports/intent_eval.md](reports/intent_eval.md)
- Language resources and the lab-to-field study: [docs/evidence.md](docs/evidence.md) §8 and §10
- Datasets and licences: [DATA_CARD.md](DATA_CARD.md)
