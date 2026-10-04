# Cafetal video script

**Length:** 4:10 as written, inside the required 2–5 minutes. Cutting the two rows marked *(optional)* gives about
3:54; a 25-second "our take" brings it to about 3:49. If nobody can check the extension-ratio clause of the problem
statement before recording, drop that clause: about 9 seconds shorter. Narration is paced at about 135–160 words a
minute, with a gap at 1:45 so the app's own Gĩkũyũ and Kiswahili voice is heard.
**Narration:** English, the app's main language. Where the app speaks or shows Gĩkũyũ or Kiswahili, the line goes on
screen with an English subtitle. **Clicks:** follow [DEMO.md](DEMO.md); each shot below gives the DEMO.md step and a
reference screenshot from [reports/screenshots/](reports/screenshots/).

The five parts the concept note asks for (§08):

| Required part | Section here | Time |
|---|---|---|
| 1. Problem statement, one sentence | [Part 1](#part-1--problem-statement-000044) | 0:00–0:44 |
| 2. AI capabilities, why a simpler tool would not do, guardrails | [Part 2](#part-2--what-the-ai-does-and-the-guardrails-044130) | 0:44–1:30 |
| 3. Tool demo, end to end | [Part 3](#part-3--demo-130309) | 1:30–3:09 |
| 4. Where it sits in the user's day, plus the tech stack | [Part 4](#part-4--where-it-fits-in-noors-week-and-the-tech-stack-309335) | 3:09–3:35 |
| 5. Our take: what localizing AI means to us | [Part 5](#part-5--our-take-335405--team-to-write) | 3:35–4:05 |
| End card | — | 4:05–4:10 |

## Honesty rules for this video

- **Say what the demo photo is.** `roya_field_1.jpg` is a real field photo of rust from **Latin America**
  (iNaturalist), from the held-out field test: the model never trained on that observer's photos. We picked it
  because the app answers it correctly, so it shows what the app can do, not how often. On the 53 held-out field rust
  photos the shipped model (v2) is right in 34 (64%) and says "I'm not sure" on the rest; our first model (v1) got 0
  ([reports/field_eval.md](reports/field_eval.md)). It also gives a disease answer to 2.5% of ordinary
  coffee-plant photos, so the officer confirms. **All those field photos are from the Americas: we have no accuracy
  figure for field photos from Kenya.** The script says this out loud. Do not promise a diagnosis of a live leaf. If
  you use the backup `roya_1.jpg` (the first DEMO sample photo in the app), say it is a Kenyan lab close-up from the
  test set.
- **Leave the labels visible:** DEMO, SIMULATED, UNVERIFIED. Do not crop them out.
- **Kiswahili and Gĩkũyũ:** the texts are AI drafts and the voice is a provisional synthetic one (an English voice
  reading Kiswahili phonemes; for Gĩkũyũ, reading the Gĩkũyũ text through them). Nobody has listened to it yet. If a
  native speaker records cards before you film, say who recorded them, and keep "UNVERIFIED" until someone has
  reviewed them.
- **Numbers:** quote only the numbers in this script. Each one traces to a file in [reports/](reports/) or to
  [docs/evidence.md](docs/evidence.md). Lines marked **S** come from search-result summaries: **open the source and
  check the figure before recording**, or drop the line.
- **Noor is fictional** (concept note, Annex B), and so are the Ondera co-op and its communities. If someone plays
  her, add the caption "Re-enactment".
- **No other iNaturalist photos on screen.** Their licences vary, and many are non-commercial or no-derivatives. The
  one exception is the demo photo `roya_field_1.jpg` (CC BY-NC: non-commercial use, with credit). Whenever it is on
  screen, show the caption "Photo: © jpgalvan, CC BY-NC, via iNaturalist". If the video could be used commercially,
  use `roya_1.jpg` instead. Otherwise use our own footage and the app's screens.

---

## Part 1 — Problem statement (0:00–0:44)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 0:00–0:09 | Our own footage of a coffee farm or leaves, or a plain title card "Cafetal" | "Noor grows coffee in Kirinyaga, on Mount Kenya, and speaks Gĩkũyũ at home. This season her yield dropped, and she can't say why." | Caption: "Noor is fictional. Her situation comes from the challenge brief (Annex B)." |
| 0:09–0:44 | Text card with the sentence below, words appearing as they are read | Read the problem statement below (the sources in brackets are on screen, not spoken). | The sentence, with the source tags "Concept note, Annex B" and "Ministry of Agriculture" |
| *(optional, +6 s)* | Same card, one more line | "In Kenya, a severe leaf-rust outbreak can cut a coffee harvest by more than three-quarters." | "Coffee leaf rust in Kenya, review, *Agronomy* 2021" — **S: check before recording** |

**The problem statement** (template from the concept note §08; wording from [docs/evidence.md](docs/evidence.md)):

> Because of Cafetal, **Noor** will **get a sick-looking coffee leaf onto the extension officer's visit list, with
> advice she can follow in Gĩkũyũ, Kiswahili or English while she waits,** by **the same weekend she notices it**,
> which she would otherwise **do late: whenever the officer next reaches her area, twice a year at best**; we know
> because **that is the gap the challenge brief describes for her (concept note, Annex B, 2026), and Kenya has about
> one public extension worker for every 1,380 farmers, against its own target of 1:600 (Ministry of Agriculture,
> 2023–2025; check before recording).**

Why this wording: it promises only what the shipped build does. A "not sure" answer still puts the farm on the
officer's list. It does **not** promise that Noor will know which disease she has: on held-out field photos the
shipped model names rust in about two of three rust photos (64%), rarely names the other diseases, and sometimes
gives a disease answer to a healthy-looking plant (2.5%), so the officer confirms. Those field photos are from the
Americas, not Kenya. The first half of the "we know because" clause cites the brief (code L), which we have read.
The extension ratio is code S: open its source first, and if you cannot, end the sentence after "(concept note,
Annex B, 2026)".

Evidence for "we know because", strongest first (codes from [docs/evidence.md](docs/evidence.md)):

| Figure | Code | Use it? |
|---|---|---|
| "The nearest extension officer visits the sub-county twice a year at best" (concept note, Annex B, 2026). This is a scenario, not a statistic. | L | Yes |
| The model learned from JMuBEN, Kenyan Arabica coffee leaves (AgML dataset metadata) | F | Yes |
| JMuBEN was photographed at Mutira, Kirinyaga, Noor's own county (Jepkoech et al. 2021, abstract seen in a search summary) | S | Only after opening the source |
| Gĩkũyũ has no Mozilla Common Voice data at all (v27.0, Sept 2026), while Kiswahili has 392 validated hours. Meta's MMS has Gĩkũyũ and Kiswahili voices, but only under a non-commercial licence and trained on Bible readings | F | Yes |
| Extension worker-to-farmer ratio about 1:1,380, against a target of 1:600 by 2029 and FAO's 1:400 (Ministry of Agriculture extension manual 2025 and/or the 2023 extension policy; which of the two states it is not confirmed) | S | Only after opening the source |
| Fewer than 5,000 public extension officers for over 8 million farmers (Kilimo Trust, 2025) | S | Only after opening the source |
| Leaf rust can cause yield losses above 75% in severe outbreaks, and chemical control of it takes 30–40% of production costs (*Agronomy* 2021 review of coffee leaf rust in Kenya) | S | Only after opening the source |
| Kenya's coffee output fell from 128,862 t (1987/88) to 48,700 t (2023), about 62% lower; about 71% of it comes through co-operative societies (KNBS, AFA; the percentages are our arithmetic) | S, and D for the percentages | Only after opening the sources |
| In rural Kenya, 21.7% of women use the internet vs 28.3% of men; one connected device in three is still a feature phone (CA/KNBS survey 2023/24; CA, June 2026; ratio ours) | S, and D for the ratio | Only after opening the sources |
| Kenya's coffee yield trend (FAOSTAT): **not fetched**, FAOSTAT was blocked on the build machine. Stand-in: AFA's 0.44 t/ha for 2022/23, labelled as an AFA figure | S | Only after opening the source |

---

## Part 2 — What the AI does, and the guardrails (0:44–1:30)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 0:44–1:03 | Diagram: phone → one SMS → co-op hub (redraw the one in [README.md](README.md)) | "Cafetal uses AI in two small places. On the phone, a two-megabyte image model looks at a leaf, offline, and picks one of six answers, including 'not a coffee leaf'. At the co-op, a tiny text model sorts free-text SMS, in English or Kiswahili, into five fixed intents." | "Image model: 1.97 MB, runs on the phone" ([model_eval.md](reports/model_eval.md)). "6 answers: healthy · leaf rust · leaf miner · Phoma · brown eye spot · not coffee". "SMS sorter: price · report · help · talk to officer · other". |
| 1:03–1:11 | Split screen: an SMS menu, a spreadsheet, a search box, each crossed out next to a leaf photo | "An SMS menu, a spreadsheet or a web search can't look at a leaf, and Noor rarely has mobile data." | "The SMS sorter lets members write the way they talk instead of learning codes." "Not AI, and we say so: the price lookup, the alert rule, the registry." |
| 1:11–1:30 | The fail-safe screen ([journey_09_blurred.png](reports/screenshots/journey_09_blurred.png)), then the "Approve" buttons ([journey_14_outbox_pending.png](reports/screenshots/journey_14_outbox_pending.png)), then the banner "You decide whom to visit." ([journey_18_officer.png](reports/screenshots/journey_18_officer.png)) | "The guardrails: blurry, not coffee, or under 90 percent sure, and it says 'I'm not sure, show the leaf to the extension officer.' Every word comes from a fixed set of cards. Nothing is sent without a tap, alerts wait for staff approval, and the officer decides who to visit." | "I'm not sure — show the leaf to the extension officer." |

---

## Part 3 — Demo (1:30–3:09)

Film the phone with a screen recorder or a second camera. Show the airplane-mode icon. The hub is the laptop browser.

| Time | Shot (DEMO.md step · screenshot) | Narration | On screen / what the app says |
|---|---|---|---|
| 1:30–1:37 | Airplane mode on, USB unplugged, app opens from the cache (DEMO.md §1.6–1.7 · [journey_01_offline_ready.png](reports/screenshots/journey_01_offline_ready.png)) | "Saturday. Her daughter's phone is home, in airplane mode. The app was loaded once at the co-op." | "Ready to use without internet" |
| 1:37–1:45 *(optional)* | Language, consent, member number (§2.1–2.3 · [journey_02_language.png](reports/screenshots/journey_02_language.png), [journey_03_consent.png](reports/screenshots/journey_03_consent.png), [journey_04_member.png](reports/screenshots/journey_04_member.png)) | "She picks English, Kiswahili or Gĩkũyũ, hears what is stored, agrees, and types her member number, not her name." | Three language buttons: English, Kiswahili, Gĩkũyũ. "Your permission" · sw: "Ruhusa yako" · kik: "Rũtha rwaku" |
| 1:45–2:02 | Choose `roya_field_1.jpg` (backup: tap the first DEMO sample photo on the Home screen, `roya_1.jpg`) → result. As soon as it appears, tap "Listen in Gĩkũyũ" (this stops the English audio that starts by itself), let about 3 s play, then "Listen in Kiswahili", about 3 s (§2.6–2.8 · [journey_06_result_roya.png](reports/screenshots/journey_06_result_roya.png); whole interface in Gĩkũyũ: [journey_11_result_kik.png](reports/screenshots/journey_11_result_kik.png)). **Editor:** leave about 6 s with no narration so the app's own voice is heard: kik `diag_roya` (2.8 s), then sw `diag_roya` (2.9 s), and cut there (the whole rust result runs about 50–56 s per language: en 49.9 s, sw 56.2 s, kik 51.8 s, *computed* from the MP3 lengths in [content/audio/](content/audio/)). | "A real field photo of rust, from Latin America; the model never trained on it. It says leaf rust." (With the backup photo: "A Kenyan lab close-up from our test set. It says leaf rust.") *(about 6 s: the app speaks, no narration)* "The Gĩkũyũ and Kiswahili are AI drafts, marked unverified." | Caption while the photo is visible: "Photo: © jpgalvan, CC BY-NC, via iNaturalist (held-out field test, Latin America)". (With the backup photo, the app shows "DEMO: sample data" and its own credit line, "JMuBEN, Kirinyaga (Jepkoech et al. 2021), CC BY 4.0": leave it in the shot.) "Leaf rust" · "It looks like coffee leaf rust." · kik: "Rĩonekana ta kutu ya mathangũ ma kahũa." · sw: "Inaonekana ni kutu ya majani ya kahawa." / EN subtitle: "It looks like coffee leaf rust." Point at **UNVERIFIED**. |
| 2:02–2:14 | Tap the second DEMO sample photo (`blurred_roya.jpg`) → fail-safe (§2.10 · [journey_09_blurred.png](reports/screenshots/journey_09_blurred.png)), then a stat card | "Blurry photos get the fail-safe. On field photos of rust, none from Kenya yet, it's right two times in three, unsure on the rest. The officer confirms." | "Not sure" · "I'm not sure — show the leaf to the extension officer." · "The photo is blurry." Stat card: "Shipped model, 53 held-out field photos of rust (all from the Americas, none from Kenya): 34 right (64 %) · 19 'not sure' · 0 called healthy. First model: 0 right. False alarms: 2.5 % of ordinary coffee-plant photos got a disease answer. Source: reports/field_eval.md" |
| 2:14–2:24 | "My checks" → Leaf rust row → "Send by SMS" → the phone's SMS app opens with the code; go back and tap "Cancel" (§2.12, §3.1–3.2 · [journey_06c_result_roya_sms.png](reports/screenshots/journey_06c_result_roya_sms.png)) | "Every check is saved and becomes one short SMS that works on 2G. Her own SMS app opens. Only she presses send." | `CAF1 M0123 RUST 99 20261004 - #K3F9` (your code will differ; `-` means no location, so the hub uses her registered plot). "One SMS, at most 160 characters". "Not sent yet". **Do not press send: the number is a DEMO placeholder.** |
| 2:24–2:32 *(optional)* | USB back in, `adb reverse`; "Send (SIMULATED)", then "Send photos to the co-op (Wi-Fi)" (§3.3–3.6 · [journey_12_simulated_send.png](reports/screenshots/journey_12_simulated_send.png), [journey_13_synced.png](reports/screenshots/journey_13_synced.png)). If you cut this row from the edit, still do the step off camera: the alert needs Noor's report to reach the hub. | "At the co-op, our simulated gateway delivers it, and the photo goes over the co-op's Wi-Fi." | Hub reply: "Cafetal: we got your report. Thank you…" Chip: "SIMULATED: no real SMS was sent". |
| 2:32–2:44 | Hub "Home" with the active alert, then "Outbox": type a name, "Approve all 24" (§4.1–4.2 · [journey_16_hub_home.png](reports/screenshots/journey_16_hub_home.png), [journey_14_outbox_pending.png](reports/screenshots/journey_14_outbox_pending.png), [journey_15_outbox_approved.png](reports/screenshots/journey_15_outbox_approved.png)) | "Hers is the third rust report within five kilometres this week. The hub drafts an alert for all 24 members, and sends nothing until staff press Approve." | "CO-OP ALERT: 3 leaf rust reports near Ondera Juu this week. Check under the leaves and tell the co-op." · sw: "TAHADHARI YA CHAMA: ripoti 3 za kutu ya majani karibu na Ondera Juu wiki hii…" Caption: "Each member gets it in their SMS language: English, Kiswahili or Gĩkũyũ." Badges: DEMO, UNVERIFIED. |
| 2:44–2:57 | "Map", then "Officer worklist": "Visit scheduled", later "Confirmed" (§4.4–4.5 · [journey_17_map.png](reports/screenshots/journey_17_map.png), [journey_18_officer.png](reports/screenshots/journey_18_officer.png)) | "The officer sees the cluster on the map, and a ranked list with a reason for each farm. He decides who to visit, and his confirmations are saved to retrain the model." | "You decide whom to visit." Row: "Rust 99% · alert area · … · with photo". |
| 2:57–3:09 | "SMS simulator": "PRICE", then the free text `there was hail yesterday and many berries fell` (§5.2–5.5 · [journey_21_simulator_price.png](reports/screenshots/journey_21_simulator_price.png), [journey_22_simulator_text.png](reports/screenshots/journey_22_simulator_text.png), [journey_23_officer_messages.png](reports/screenshots/journey_23_officer_messages.png)) | "At harvest, Noor texts PRICE from her basic phone: a reference price in shillings, with source and date. Demo numbers, not AI. What the sorter can't answer goes to the officer." | "Reference price 10/2026: coffee 139.00 KES/kg cherry, maize 51.11, beans 111.11 KES/kg. Source: DEMO county 25/26, KAMIS. Not the price at your factory." Caption: "In Kiswahili: BEI". Then "Cafetal: we are passing your message to the extension officer…" |

---

## Part 4 — Where it fits in Noor's week, and the tech stack (3:09–3:35)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 3:09–3:24 | A four-step timeline slide (below) | "Where it fits: on weekdays Noor is on the slope, so she brings leaves home. Saturday, she checks them and taps send. During the week, the co-op and the officer act. At harvest, she checks the price first." | The timeline |
| 3:24–3:35 | A tech-stack slide (below) | "Under the hood: a web app with a small ONNX model running in the browser, and one Python program with SQLite on the co-op's own computer. No cloud." | The stack |

**Timeline slide:**

| Weekday | Saturday | During the week | Harvest |
|---|---|---|---|
| Noor sees spots on the slope; her phone stays at the house. She brings a few leaves home in a bag (the app's tip says to). | Her daughter is home with the smartphone. Offline check, advice in Gĩkũyũ, Kiswahili or English, one tap to send the SMS. | The co-op hub stores the report. Staff approve the alert to members' basic phones. The officer sees the list, visits and confirms. | Noor texts PRICE (or BEI) from her basic phone, so she knows the county reference price before a buyer names his, or her factory announces its payout. |

**Tech-stack slide** (numbers from [reports/browser_metrics.md](reports/browser_metrics.md) and the test results;
speed and download are *emulated* in desktop Chromium, not measured on a phone):

| Part | What it uses |
|---|---|
| Phone | Web app (HTML/JS, no build step) with a service worker for offline use. onnxruntime-web 1.19.2 (WASM). MobileNetV3-Small fine-tuned, ONNX, fp16, **1.97 MB**, threshold 0.90. Interface in English, Kiswahili and Gĩkũyũ; 84 cards, audio pre-rendered with Piper TTS (Kiswahili and Gĩkũyũ voice provisional). Records in the browser's IndexedDB. |
| Speed *(emulated, CPU slowed 4×)* | First photo **3.7 s** (loading included; one cold run), then **62 ms** per photo |
| First download *(emulated 3G)* | Model alone **21 s**; everything needed offline **88 s** |
| SMS | `CAF1` code, at most 160 characters (45 in the end-to-end test), works on 2G. Gateway **SIMULATED** in this build. |
| Co-op hub | FastAPI + SQLite, one Python process. SMS sorter: character n-gram TF-IDF + logistic regression, stored as JSON and run in plain Python. Plain SVG map. |
| Tests | 76 hub tests pass (1 skipped); the 46-check end-to-end journey passes ([journey_results.json](reports/journey_results.json)) |

---

## Part 5 — Our take (3:35–4:05) — TEAM TO WRITE

> **PLACEHOLDER. The team writes and says this part in their own words. Do not have an AI write it.**
> About 25–30 seconds, roughly 70 spoken words. Film a team member on camera if you can.
>
> Prompts to start from (pick two or three):
>
> - **Her language.** What changes when advice is *spoken* in Gĩkũyũ, the language Noor speaks at home? Gĩkũyũ has no
>   Common Voice data at all. Why did we label our Kiswahili and Gĩkũyũ "UNVERIFIED" instead of pretending they were
>   finished, and who should own them (native speakers from Kirinyaga)? Is English as the main language right for
>   her?
> - **Her co-op.** Why do the consented registry, the staff "Approve" button and the officer's list matter as much as
>   the model? The brief says a missing registry, not a missing algorithm, is often what blocks farmers. Kenyan coffee
>   co-ops and their factories already know their members.
> - **The phones she already has.** A basic phone, a smartphone only on weekends, rarely any data: a 2 MB model,
>   offline, and one SMS.
> - **Data that admits its gaps.** Kenyan training photos from her own county, but lab close-ups from one plantation;
>   field photos only from the Americas; a first model that got 0 of 53 field rust photos right, a second that gets 34
>   of 53 but raises some false alarms, and was shipped against one of our own rules (we say so); 0 Kirinyaga field
>   photos so far; no way to see coffee berry disease. Why "not sure, ask a person" is the feature, and why the
>   officer's confirmations are the data we actually need.

## End card (4:05–4:10)

- "Cafetal — offline coffee leaf doctor for Noor's co-op (Kirinyaga, Kenya)" and the repository link.
- "DEMO data · SMS SIMULATED · Kiswahili and Gĩkũyũ UNVERIFIED (AI drafts, provisional voice)".
- Team names.

---

## Recording checklist

**Before (the same day you record):**
- [ ] Open the source of every **S** figure you plan to quote, or drop it ([docs/evidence.md](docs/evidence.md)).
      This includes the extension ratio in the problem statement.
- [ ] Write and rehearse Part 5.
- [ ] Start the hub (`./run.sh`) and press **"Reset DEMO data"**, so the neighbours' reports fall inside the
      7-day window (DEMO.md §1.2).
- [ ] Download the field photo (`python3 model/demo_samples.py --field`) and push `roya_field_1.jpg` to the phone
      (DEMO.md §1.3). The backup `roya_1.jpg` and `blurred_roya.jpg` are the first two DEMO sample photos on the
      app's Home screen. Use only these three.
- [ ] On the phone: "Settings" → "Delete all" if it was used before. Load http://localhost:8000/app/ online and wait
      for **"Ready to use without internet"** (DEMO.md §1.6).
- [ ] When Chrome asks for location, **block it**, or the alert will not fire (DEMO.md §2.4).
- [ ] Phone not on silent, volume up. If autoplay is blocked, tap the "Listen in…" buttons on camera.
- [ ] Hub browser: zoom about 125 %, hide bookmarks and other tabs. The DEMO and SMS SIMULATED badges must be
      visible.
- [ ] If anyone appears on camera (a farmer, co-op staff), get their written consent first. Caption a re-enactment.
- [ ] Music: none, or a track whose licence allows it.

**While recording:**
- [ ] Show airplane mode **and** the unplugged USB cable during the offline part (DEMO.md §1.7). `adb reverse`
      works over USB.
- [ ] Say the honesty line about the demo photo (Latin America) and show its credit caption (1:45), then show the
      field stat card (2:02).
- [ ] At 1:45, let the app speak for about 6 s (Gĩkũyũ, then Kiswahili) before the next narration line.
- [ ] Do not press send in the phone's SMS app: the number is a DEMO placeholder.
- [ ] Keep the UNVERIFIED badges in frame when the Gĩkũyũ and Kiswahili audio plays.

**After:**
- [ ] Check the total length: between 2:00 and 5:00.
- [ ] Add English subtitles for all narration and for the Gĩkũyũ and Kiswahili lines.
- [ ] Press "Reset DEMO data". If you verified or recorded cards only for practice, run
      `git checkout -- content/` (DEMO.md §6).
- [ ] Watch it once against this script: every number on screen must be one of the numbers above.
