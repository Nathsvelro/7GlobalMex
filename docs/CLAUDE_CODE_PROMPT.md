# Prompt for Claude Code

*Before you paste this, put `PROJECT_BRIEF.md` in the root of an empty repo. If you can, also add the World Bank concept note PDF as `docs/concept-note.pdf`. Fill in the `[FILL IN]` fields, then paste everything below the line into Claude Code.*

---

You are the lead engineer on a hackathon team. We are building **Cafetal** for the World Bank × Hack-Nation **"Small AI for Development"** hackathon, **Agriculture track**. It's an offline coffee crop doctor for a smallholder farmer (Noor) and her cooperative.

**Read `PROJECT_BRIEF.md` before doing anything else.** It is the source of truth for the user, the rules, the guardrails, the data and the judging criteria. If `docs/concept-note.pdf` exists, read the agriculture section (Annex B) and sections 05–09 as well. **Where the official rules conflict with a default in this prompt, the rules win.**

## The user and the setting
- Noor has a **basic phone** (calls, texts, mobile money).
- Her daughter's **Android smartphone** is available only on weekends.
- There's no Wi-Fi at home, and mobile data is bought only now and then.
- Her cooperative is the trusted local institution.
- Local language: **[FILL IN, default: Tseltal]**. National language: **Spanish**. Region: **[FILL IN, default: coffee highlands of Chiapas, Mexico]**.

## Hard constraints (from the official rules)
- **Deadline:** [FILL IN the exact submission time on Oct 4, 2026]. A 2–5 minute video is required.
- **Devices people already have:** the smartphone app, SMS to and from a basic phone, and a hub on the co-op's existing computer.
- **Core feature works offline:** after the first load, diagnosis plus spoken advice must work in airplane mode.
- **Small model:** the image model must be ≤10 MB. Report its size and how long it takes to download over 3G.
- **Local language:** at least one interaction by **voice in the local language**, plus Spanish.
- **Human in the loop:** the tool informs and flags uncertainty. It **never acts on anyone's behalf**: no SMS goes out without a user tap, and the extension officer decides on visits.
- **No hallucinations:** farmers only ever see or hear text from a **fixed list of checked advice cards**. No free-form generated text goes to farmers.
- **Fail-safe:** when the model isn't confident, or the photo isn't a coffee leaf, it says "No estoy seguro — muestre la hoja al técnico" ("I'm not sure, show the leaf to the extension officer") and adds the farm to the officer's worklist.
- **No cloud services or paid APIs** in the demo path.
- User-facing text in Spanish and the local language. Code and docs in English.

## Architecture (default choices; change one only if it blocks you, and tell me why)

### 1. Smartphone web app, served by the hub
An offline-capable PWA. A service worker caches the app, the model, the advice cards and the audio.
- **Consent screen** on first use.
- **Camera/upload screen**, with a tip to photograph the leaf's underside.
- **Image model:**
  - Runs on the device via onnxruntime-web or TF.js.
  - Shows the result and confidence.
  - Includes an "other / not coffee" class plus a confidence threshold.
- **Advice card and audio** in the local language or Spanish.
- **Observations** are stored in IndexedDB under a member ID. Add an optional PIN and a "delete everything" button.
- **"Enviar por SMS" ("Send by SMS") button:**
  - Builds an `sms:` link holding a compact, single-SMS code (≤160 characters, versioned, documented), e.g., `CAF1 M0123 ROYA 87 20261004 16.7,-92.6`.
  - The user taps Send in their own SMS app.
- Photos and full records upload to the hub only when it's reachable over Wi-Fi.

### 2. Co-op hub
FastAPI + SQLite, served on `0.0.0.0`.
- **Member registry** with consent records (member ID, phone number, community, plot location).
- **SMS inbox endpoint:**
  - Parses observation codes.
  - Sends free-text messages to the intent sorter.
  - Accepts input from an **SMS simulator page** and, as a stretch goal, from an Android SMS-gateway app webhook.
- **SMS simulator page:** a basic-phone mockup ("Noor's phone") to show incoming and outgoing texts in the demo without a network. Label it SIMULATED.
- **Outbreak rule:** N or more rust reports within X km over 7 days → an alert SMS to every member in the outbox. Show it on an offline map with OpenStreetMap tiles or a simple SVG.
- **Extension officer worklist:**
  - Farms ranked by severity, confidence and clustering, with photos when available.
  - Buttons for "visit scheduled" and "confirmed / not confirmed". The officer decides.
  - Officer confirmations are stored as **labeled examples for later retraining**.
- **"PRECIO" reply:**
  - Reference price for parchment coffee (plus maize and beans) from a cached table.
  - Always includes the source, the date and "precio de referencia" (reference price).
  - Not AI; say so in the docs.
- **Intent sorting for free-text SMS:**
  - A small multilingual sentence-embedding model, or a tiny classifier.
  - Fixed intents: `precio`, `reporte`, `ayuda`, `hablar_con_tecnico`, `otro`.
  - Replies only from the checked advice cards. If it's unsure → "Le paso su mensaje al técnico" ("I'll pass your message to the extension officer").

### 3. Content
`content/cards.json` holds **every sentence the system can say**. Each card has:
- `id`
- Spanish text
- local-language text
- an audio file per language
- the manual or source it came from
- a `status` of `verified` or `unverified`

Rules for the content:
- Machine-translated local-language text stays `unverified` until a native speaker checks it, and the UI marks it as such.
- For voice: check whether **Meta MMS** text-to-speech supports the local language (e.g., `tzh` for Tseltal). If it doesn't, use recordings by a native speaker, and fall back to Spanish audio from an offline TTS such as Piper.

### 4. Image model training
- **Data scripts:** BRACOL (doi:10.17632/yy2k5y8mxg.1) and RoCoLe (doi:10.17632/c5yvn32dzg.2). Map both to shared labels: `sano`, `roya`, `minador`, `phoma`, `cercospora`, `acaro_rojo`, `otro`.
- **"Not coffee" examples** for `otro` come from PlantDoc or similar images.
- **Training:**
  - Fine-tune MobileNetV3-Small (or EfficientNet-Lite0).
  - Quantize to INT8 and export.
- **Evaluation**, reported **separately** for:
  - (a) the held-out test split
  - (b) `data/field_test/`, our own photos (could be empty at first)
  Include the confusion matrix, model size and response time on the phone.
- If a dataset needs a manual download, give me the exact steps and keep working with a small placeholder set meanwhile.

### 5. Data and sync scripts
- Cached price tables: InfoAserca coffee, SNIIM maize and beans.
- *Stretch:* NASA POWER weather by coordinates, for a rust-risk / spray-timing flag. Cite the source of any thresholds.
- All sample data is labeled `DEMO` in the UI.

### 6. One command to start everything
`./run.sh` or `make demo`.

## Milestones (in this order; demo-critical path first)
1. **Plan and scaffold (≤30 min):** write `PLAN.md`, scaffold the repo, and start the model training early, since it can run in the background.
2. **Image model:** data scripts, training, export, evaluation report. Start `DATA_CARD.md`.
3. **Offline diagnosis on the phone:** photo → result → advice card → audio (Spanish first, then the local language). Verify it works in airplane mode.
4. **Save-and-send-later:** the observation SMS code, the hub's SMS inbox, the simulator, and Wi-Fi sync of photos.
5. **Hub features:** registry and consent, outbreak alert, officer worklist, PRECIO reply, intent sorting, DEMO data seeding.
6. **Guardrails and privacy pass:**
   - threshold and "not coffee" handling
   - no automatic sending
   - consent, PIN and delete
   - DEMO and UNVERIFIED labels
   - nothing outside the advice cards ever reaches a farmer
7. **Ship:** write the documents below with real content.
   - `README.md`: setup in under 10 steps.
   - `DEMO.md`: the click-by-click demo of the whole journey.
   - `METRICS.md`: model size, accuracy on the test split vs. our field photos, phone response time, 3G download time. Measured, not estimated.
   - `DATA_CARD.md`: every dataset with its source, license, size, how we used it, and **what it does not cover**.
   - `RESPONSIBLE_AI.md`:
     - fail-safe
     - human in the loop
     - consent
     - where data lives and who can read it
     - what happens if a phone is lost or shared
     - bias
     - how it would do in a less-supported language
   - `VIDEO_SCRIPT.md`: 2–5 minutes, with the five required parts: problem statement (one sentence, template in the brief), AI capabilities and why a simpler tool wouldn't work plus guardrails, the demo, where it fits in Noor's day plus tech stack, and "our take" (leave that part for the team to write).

## How to work
- Start by reading the brief and writing `PLAN.md`. Ask me at most 3 questions, and only if something truly blocks you; otherwise use the defaults above and keep going.
- Keep the main branch demo-able at all times. Commit after each milestone.
- Don't over-engineer: no auth beyond the PIN, no Docker unless needed, no microservices.
- If something takes more than ~45 minutes without progress, stop, tell me the options, and move to the next milestone.
- After each milestone, give me a 3-line status: what works, how to try it, what's next.

## Definition of done (check every item before saying you're finished)
- [ ] `./run.sh` starts the hub from a fresh clone, following the README.
- [ ] The phone loads the app once, then **in airplane mode** diagnoses a leaf photo and plays advice in the local language and in Spanish.
- [ ] A blurry photo or a non-coffee photo gives "No estoy seguro — muestre la hoja al técnico."
- [ ] "Enviar por SMS" prepares a valid ≤160-character code. When it's sent through the simulator, the observation appears on the hub.
- [ ] Rust reports trigger an outbreak alert in the outbox, and the farm appears on the officer's worklist.
- [ ] Texting "PRECIO" from the simulated basic phone returns a reference price with its source and date.
- [ ] Free-text SMS in Spanish is sorted into the right intent, and unknown messages go to the officer.
- [ ] Every sentence a farmer can see or hear comes from `content/cards.json`.
- [ ] `METRICS.md`, `DATA_CARD.md`, `RESPONSIBLE_AI.md` and `VIDEO_SCRIPT.md` are filled with real content.
