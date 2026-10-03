# Cafetal video script

**Length:** 4:00 as written, inside the required 2–5 minutes. Cutting the two rows marked *(optional)* gives about
3:45; a 25-second "our take" brings it to about 3:40. Narration is paced at about 135–160 words a minute, with a gap at 1:35 so the app's own Tseltal and Spanish voice is
heard.
**Narration:** English. Where the app speaks or shows text, the Spanish and Tseltal lines go on screen with an English
subtitle. **Clicks:** follow [DEMO.md](DEMO.md); each shot below gives the DEMO.md step and a reference screenshot
from [reports/screenshots/](reports/screenshots/).

The five parts the concept note asks for (§08):

| Required part | Section here | Time |
|---|---|---|
| 1. Problem statement, one sentence | [Part 1](#part-1--problem-statement-000034) | 0:00–0:34 |
| 2. AI capabilities, why a simpler tool would not do, guardrails | [Part 2](#part-2--what-the-ai-does-and-the-guardrails-034120) | 0:34–1:20 |
| 3. Tool demo, end to end | [Part 3](#part-3--demo-120259) | 1:20–2:59 |
| 4. Where it sits in the user's day, plus the tech stack | [Part 4](#part-4--where-it-fits-in-noors-week-and-the-tech-stack-259325) | 2:59–3:25 |
| 5. Our take: what localizing AI means to us | [Part 5](#part-5--our-take-325355--team-to-write) | 3:25–3:55 |
| End card | — | 3:55–4:00 |

## Honesty rules for this video

- **Say what the demo photo is.** `roya_1.jpg` is a held-out test close-up from the Kenyan dataset. On real field
  photos the shipped model almost always says "No estoy seguro" ([reports/field_eval.md](reports/field_eval.md)).
  The script says this out loud. Do not promise a diagnosis of a live leaf.
- **Leave the labels visible:** DEMO, SIMULADO, SIN VERIFICAR. Do not crop them out.
- **Tseltal:** the text is an AI draft and the voice is a provisional synthetic one (a Spanish voice reading Tseltal).
  If a native speaker records cards before you film, say who recorded them, and keep "SIN VERIFICAR" until someone
  has reviewed them.
- **Numbers:** quote only the numbers in this script. Each one traces to a file in [reports/](reports/) or to
  [docs/evidence.md](docs/evidence.md). Lines marked **S** come from search-result summaries: **open the source and
  check the figure before recording**, or drop the line.
- **Noor is fictional** (concept note, Annex B). If someone plays her, add the caption "Re-enactment".
- **No iNaturalist photos on screen.** Their licences vary, and many are non-commercial or no-derivatives. Use our own
  footage and the app's screens.

---

## Part 1 — Problem statement (0:00–0:34)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 0:00–0:08 | Our own footage of a coffee slope or leaves, or a plain title card "Cafetal" | "Noor grows coffee in the Chiapas highlands and speaks Tseltal. This season her yield dropped, and she can't say why." | Caption: "Noor is fictional. Her situation comes from the challenge brief (Annex B)." |
| 0:08–0:34 | Text card with the sentence below, words appearing as they are read | Read the problem statement below (the source in brackets is on screen, not spoken). | The sentence, with the source tag "Concept note, Annex B". |
| *(optional, +6 s)* | Same card, one more line | "In Mexico's 2007 farm census, only about three in a hundred farms got any technical assistance." | "INEGI farm census 2007, via *Rev. Mex. Cienc. Agríc.* 2012" — **S: check before recording** |

**The problem statement** (template from the concept note §08):

> Because of Cafetal, **Noor** will **get a sick-looking coffee leaf onto her extension officer's visit list, with
> spoken advice in Tseltal while she waits,** by **the same weekend she notices it**, which she would otherwise **do
> late: whenever the officer next comes by, twice a year at best**; we know because **that is the gap the challenge
> brief describes for her (concept note, Annex B, 2026).**

Why this wording: it promises only what the shipped build does. A "not sure" answer still puts the farm on the
officer's list. It does **not** promise that Noor will know which disease she has, because on field photos the
shipped model almost always says "No estoy seguro".

Evidence for "we know because", strongest first (codes from [docs/evidence.md](docs/evidence.md)):

| Figure | Code | Use it? |
|---|---|---|
| "The nearest extension officer visits the sub-county twice a year at best" (concept note, Annex B, 2026). This is a scenario, not a statistic. | L | Yes |
| About 3 % of agricultural production units received technical assistance (INEGI farm census 2007, analysed in *Rev. Mex. Cienc. Agríc.* 2012) | S | Only after opening the source |
| Mexico's coffee production fell from 4.3 to 2.2 million 60-kg bags between 2012 and 2016 (USDA estimates, cited in *Rev. Mex. Sociología* 2019); USDA's 2016 Mexico report names rust as the main cause | S | Only after opening the sources |
| 77 SENASICA coffee-pest specialists across 8 states in 2026, about 1 per 6,600 registered producers | S, and D for the ratio | Only after opening the sources |
| 28.4 % of Tseltal speakers do not speak Spanish (INEGI census 2020, via a secondary source) | S | Only after opening the source |

---

## Part 2 — What the AI does, and the guardrails (0:34–1:20)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 0:34–0:53 | Diagram: phone → one SMS → co-op hub (redraw the one in [README.md](README.md)) | "Cafetal uses AI in two small places. On the phone, a two-megabyte image model looks at a leaf, offline, and picks one of six answers, including 'not a coffee leaf'. At the co-op, a tiny text model sorts free-text SMS into five fixed intents." | "Image model: 1.97 MB, runs on the phone" ([model_eval.md](reports/model_eval.md)). "6 answers: sano · roya · minador · phoma · cercospora · not coffee". "SMS sorter: precio · reporte · ayuda · hablar con técnico · otro". |
| 0:53–1:01 | Split screen: an SMS menu, a spreadsheet, a search box, each crossed out next to a leaf photo | "An SMS menu, a spreadsheet or a web search can't look at a leaf, and Noor rarely has mobile data." | "The SMS sorter lets members write the way they talk instead of learning codes." "Not AI, and we say so: the price lookup, the alert rule, the registry." |
| 1:01–1:20 | The fail-safe screen ([journey_09_blurred.png](reports/screenshots/journey_09_blurred.png)), then the "Aprobar" button ([journey_14_bandeja_pending.png](reports/screenshots/journey_14_bandeja_pending.png)), then the banner "Usted decide a quién visitar" ([journey_18_tecnico.png](reports/screenshots/journey_18_tecnico.png)) | "The guardrails: blurry, not coffee, or under 70 percent sure, and it says 'I'm not sure, show the leaf to the officer.' Every word comes from a fixed set of cards. Nothing is sent without a tap, alerts wait for staff approval, and the officer decides who to visit." | "No estoy seguro — muestre la hoja al técnico." / EN: "I'm not sure — show the leaf to the extension officer." |

---

## Part 3 — Demo (1:20–2:59)

Film the phone with a screen recorder or a second camera. Show the airplane-mode icon. The hub is the laptop browser.

| Time | Shot (DEMO.md step · screenshot) | Narration | On screen / what the app says |
|---|---|---|---|
| 1:20–1:27 | Airplane mode on, USB unplugged, app opens from the cache (DEMO.md §1.6–1.7 · [journey_01_offline_ready.png](reports/screenshots/journey_01_offline_ready.png)) | "Saturday. Her daughter's phone is home, in airplane mode. The app was loaded once at the co-op." | "Listo para usar sin internet" / EN: "Ready to use without internet" |
| 1:27–1:35 *(optional)* | Language, consent, member number (§2.1–2.3 · [journey_02_language.png](reports/screenshots/journey_02_language.png), [journey_03_consent.png](reports/screenshots/journey_03_consent.png), [journey_04_member.png](reports/screenshots/journey_04_member.png)) | "She picks Tseltal or Spanish, hears what is stored, agrees, and types her member number, not her name." | "Su permiso" · tzh: "Ya jk'anbat apermiso" / EN: "Your permission" |
| 1:35–1:52 | Choose `roya_1.jpg` → result → tap "Escuchar en tseltal", let about 3 s play, then "Escuchar en español", about 3 s (§2.6–2.8 · [journey_06_result_roya.png](reports/screenshots/journey_06_result_roya.png), [journey_11_result_tzh.png](reports/screenshots/journey_11_result_tzh.png)). **Editor:** leave about 6 s with no narration so the app's own voice is heard: tzh `diag_roya` (2.0 s), es `diag_roya` (2.1 s), then 1–2 s of the advice, and cut the advice audio there (the whole rust result runs about 46–48 s per language; file lengths in [content/audio/](content/audio/)). | "Here is a Kenyan test close-up the model never trained on. It says rust." *(about 6 s: the app speaks, no narration)* "The Tseltal is an AI draft in a provisional voice, marked 'not verified'." | tzh: "Ja' roya yilel ta kajpe." · es: "Parece roya del cafeto." / EN: "Looks like coffee leaf rust." Then es: "Revise cada semana por debajo de las hojas, en varias matas…" / EN: "Check under the leaves of several plants every week…" Point at **SIN VERIFICAR**. |
| 1:52–2:04 | Choose `blurred_roya.jpg` → fail-safe (§2.10 · [journey_09_blurred.png](reports/screenshots/journey_09_blurred.png)), then a stat card | "A blurry photo gets the fail-safe. And honestly: on real field photos our model does this almost every time. Zero of 53 rust photos right, 98 percent 'not sure', none called healthy." | es: "No estoy seguro — muestre la hoja al técnico." "La foto salió borrosa." · tzh: "Ma jna' lek — ak'a yil yabenal te técnico." / EN: "The photo is blurry." Stat card: "Shipped model, 53 held-out field photos of rust: 0 right · 98.1 % 'not sure' · 0 called healthy. Source: reports/field_eval.md" |
| 2:04–2:14 | "Mis revisiones" → Roya row → "Enviar por SMS" → the phone's SMS app opens with the code; go back and tap "Cancelar" (§2.12, §3.1–3.2 · [journey_06c_result_roya_sms.png](reports/screenshots/journey_06c_result_roya_sms.png)) | "Every check is saved and becomes one short SMS that works on 2G. Her own SMS app opens. Only she presses send." | `CAF1 M0123 ROYA 99 20261003 - #K3F9` (your code will differ; `-` means no location, so the hub uses her registered plot). "One SMS, at most 160 characters". "Por enviar" / EN: "To send". **Do not press send: the number is a DEMO placeholder.** |
| 2:14–2:22 *(optional)* | USB back in, `adb reverse`; "Enviar (SIMULADO)", then "Mandar fotos a la cooperativa (Wi-Fi)" (§3.3–3.6 · [journey_12_simulated_send.png](reports/screenshots/journey_12_simulated_send.png), [journey_13_synced.png](reports/screenshots/journey_13_synced.png)). If you cut this row from the edit, still do the step off camera: the alert needs Noor's report to reach the hub. | "At the co-op, our simulated gateway delivers it, and the photo goes over the co-op's Wi-Fi." | Hub reply: "Cafetal: recibimos su reporte. Gracias…" / EN: "Cafetal: we received your report. Thank you…" Chip: "SIMULADO: no se mandó un SMS de verdad". |
| 2:22–2:34 | Hub "Inicio" with the active alert, then "Bandeja de salida": type a name, "Aprobar los 24" (§4.1–4.2 · [journey_16_hub_home.png](reports/screenshots/journey_16_hub_home.png), [journey_14_bandeja_pending.png](reports/screenshots/journey_14_bandeja_pending.png), [journey_15_bandeja_approved.png](reports/screenshots/journey_15_bandeja_approved.png)) | "Hers is the third rust report within five kilometres this week. The hub drafts an alert for all 24 members, and sends nothing until staff press Approve." | es: "AVISO DE LA COOPERATIVA: 3 reportes de roya cerca de Ondera Alto esta semana. Revise por debajo de las hojas y avise a la cooperativa." / EN: "CO-OP NOTICE: 3 rust reports near Ondera Alto this week. Check under the leaves and tell the co-op." Badges: DEMO, SIN VERIFICAR. |
| 2:34–2:47 | "Mapa", then "Técnico": "Visita programada", later "Confirmado" (§4.4–4.5 · [journey_17_mapa.png](reports/screenshots/journey_17_mapa.png), [journey_18_tecnico.png](reports/screenshots/journey_18_tecnico.png)) | "The officer sees the cluster on the map, and a ranked list with a reason for each farm. He decides who to visit, and his confirmations are saved to retrain the model." | "Usted decide a quién visitar." / EN: "You decide whom to visit." Row: "Roya 99 % · zona de alerta · … · con foto". |
| 2:47–2:59 | "Simulador SMS": "PRECIO", then the free text `se secaron mis matas con el calor que hago` (§5.2–5.4 · [journey_21_simulador_precio.png](reports/screenshots/journey_21_simulador_precio.png), [journey_22_simulador_texto.png](reports/screenshots/journey_22_simulador_texto.png), [journey_23_tecnico_mensajes.png](reports/screenshots/journey_23_tecnico_mensajes.png)) | "At harvest, Noor texts PRECIO from her basic phone: a reference price, with source and date. Demo numbers, and not AI. Anything the sorter doesn't understand goes to the officer." | "Precio de referencia sept 2026: cafe pergamino 94.00 MXN/kg… Fuente: DEMO ICE/Banxico/SNIIM. No es el precio de su comunidad." / EN: "Reference price… Not the price in your community." Then "Cafetal: le paso su mensaje al tecnico…" / EN: "I'll pass your message to the officer." |

---

## Part 4 — Where it fits in Noor's week, and the tech stack (2:59–3:25)

| Time | Shot | Narration | On screen |
|---|---|---|---|
| 2:59–3:14 | A four-step timeline slide (below) | "Where it fits: on weekdays Noor is on the slope, so she brings leaves home. Saturday, she checks them and taps send. During the week, the co-op and the officer act. At harvest, she checks the price first." | The timeline |
| 3:14–3:25 | A tech-stack slide (below) | "Under the hood: a web app with a small ONNX model running in the browser, and one Python program with SQLite on the co-op's own computer. No cloud." | The stack |

**Timeline slide:**

| Weekday | Saturday | During the week | Harvest |
|---|---|---|---|
| Noor sees spots on the slope; her phone stays at the house. She brings a few leaves home in a bag (the app's tip says to). | Her daughter is home with the smartphone. Offline check, advice in Tseltal or Spanish, one tap to send the SMS. | The co-op hub stores the report. Staff approve the alert to members' basic phones. The officer sees the list, visits and confirms. | Noor texts PRECIO from her basic phone before the buyer names a price. |

**Tech-stack slide** (numbers from [METRICS.md](METRICS.md); speed and download are *emulated* in desktop Chromium, not
measured on a phone):

| Part | What it uses |
|---|---|
| Phone | Web app (HTML/JS, no build step) with a service worker for offline use. onnxruntime-web 1.19.2 (WASM). MobileNetV3-Small fine-tuned, ONNX, fp16, **1.97 MB**. Audio pre-rendered with Piper TTS. Records in the browser's IndexedDB. |
| Speed *(emulated, CPU slowed 4×)* | First photo **2.6 s** (loading included), then **66 ms** per photo |
| First download *(emulated 3G)* | Model alone **21 s**; everything needed offline **81 s** |
| SMS | `CAF1` code, at most 160 characters (46 in the end-to-end test), works on 2G. Gateway **SIMULATED** in this build. |
| Co-op hub | FastAPI + SQLite, one Python process. SMS sorter: character n-gram TF-IDF + logistic regression, stored as JSON and run in plain Python. Plain SVG map. |
| Tests | 62 hub tests pass (1 skipped); the 43-check end-to-end journey passes ([journey_results.json](reports/journey_results.json)) |

---

## Part 5 — Our take (3:25–3:55) — TEAM TO WRITE

> **PLACEHOLDER. The team writes and says this part in their own words. Do not have an AI write it.**
> About 25–30 seconds, roughly 70 spoken words. Film a team member on camera if you can.
>
> Prompts to start from (pick two or three):
>
> - **Her language.** What changes when advice is *spoken* in Tseltal? Why did we label our Tseltal "SIN VERIFICAR"
>   instead of pretending it was finished, and who should own it (a native speaker from her area)?
> - **Her co-op.** Why do the consented registry, the staff "Aprobar" button and the officer's list matter as much as
>   the model? The brief says a missing registry, not a missing algorithm, is often what blocks farmers.
> - **The phones she already has.** A basic phone, a smartphone only on weekends, rarely any data: a 2 MB model,
>   offline, and one SMS.
> - **Data that admits its gaps.** Kenyan training photos, 0 of 53 field rust photos right, 0 Chiapas photos so far.
>   Why "not sure, ask a person" is the feature, and why the officer's confirmations are the data we actually need.

## End card (3:55–4:00)

- "Cafetal — offline coffee crop doctor for Noor's co-op" and the repository link.
- "DEMO data · SMS SIMULADO · Tseltal SIN VERIFICAR (AI draft, provisional voice)".
- Team names.

---

## Recording checklist

**Before (the same day you record):**
- [ ] Open the source of every **S** figure you plan to quote, or drop it ([docs/evidence.md](docs/evidence.md)).
- [ ] Write and rehearse Part 5.
- [ ] Start the hub (`./run.sh`) and press **"Reiniciar datos DEMO"**, so the neighbours' reports fall inside the
      7-day window (DEMO.md §1.2).
- [ ] Push the demo photos to the phone (DEMO.md §1.3). Use `roya_1.jpg` and `blurred_roya.jpg` only.
- [ ] On the phone: "Ajustes" → "Borrar todo" if it was used before. Load http://localhost:8000/app/ online and wait
      for **"Listo para usar sin internet"** (DEMO.md §1.5–1.6).
- [ ] When Chrome asks for location, **block it**, or the alert will not fire (DEMO.md §2.4).
- [ ] Phone not on silent, volume up. If autoplay is blocked, tap the "Escuchar…" buttons on camera.
- [ ] Hub browser: zoom about 125 %, hide bookmarks and other tabs. The DEMO and SIMULADO badges must be visible.
- [ ] If anyone appears on camera (a farmer, co-op staff), get their written consent first. Caption a re-enactment.
- [ ] Music: none, or a track whose licence allows it.

**While recording:**
- [ ] Show airplane mode **and** the unplugged USB cable during the offline part (DEMO.md §1.7). `adb reverse`
      works over USB.
- [ ] Say the honesty line about the test photo (1:35) and show the field stat card (1:52).
- [ ] At 1:35, let the app speak for about 6 s (Tseltal, then Spanish) before the next narration line.
- [ ] Do not press send in the phone's SMS app: the number is a DEMO placeholder.
- [ ] Keep the SIN VERIFICAR badges in frame when the Tseltal audio plays.

**After:**
- [ ] Check the total length: between 2:00 and 5:00.
- [ ] Add English subtitles for all narration and for the Spanish and Tseltal lines.
- [ ] Press "Reiniciar datos DEMO". If you verified or recorded cards only for practice, run
      `git checkout -- content/` (DEMO.md §6).
- [ ] Watch it once against this script: every number on screen must be one of the numbers above.
