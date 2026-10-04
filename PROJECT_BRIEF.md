# Cafetal — Coffee Crop Doctor for Noor's Cooperative

> **2026-10-04, team decision: the setting was changed to Kenya** (Kirinyaga County; English main, Kiswahili national, Gĩkũyũ local); this brief was updated to match, and the earlier version is in git history.

*Working name. Hack-Nation × World Bank, "Small AI for Development," **Agriculture track (Annex B)**. Updated after reviewing the official concept note.*

---

## 1. The challenge

**Timeline**
- Competition weekend: **Oct 3–4, 2026**. Everything must be submitted by the end of the weekend.
- Expert evaluators pick a shortlist on Oct 5–6. A World Bank panel then picks one winner per sector, three in total.
- The winning teams present an Ignite Talk on **Oct 21** at the Global AI & Digital Summit in Seoul (Oct 19–22).
- Ages 18–35.

**The central question:** *What does localizing AI development mean for you?*

**Agriculture challenge (Annex B, paraphrased):** help Noor make, communicate or act on **one better agricultural decision**. Examples from the brief:
- identifying a crop or post-harvest problem
- timing a farming activity
- getting localized advice
- documenting a field observation
- connecting evidence to a pricing, market or extension-service next step

**Scenario:**
- Noor's coffee yields dropped this season and she doesn't know why.
- The extension officer (the government farm advisor) visits her area twice a year at best.
- At harvest she sells her parchment coffee to whichever middleman drives up the valley, at whatever price he names.

*(Scenario as the brief writes it. In Kenya, about 71% of coffee comes through co-operative societies, whose factories pay members per kg of cherry after the sales; search-snippet figures, `docs/evidence.md` §3 and §9. So our price reply gives the Kirinyaga cherry payout as the reference.)*

**What the brief says about the problem:**
- Farmers lack timely, local advice and independent price information.
- Extension services are short-staffed and rely on manual data and late alerts.
- Often the real bottleneck is the lack of a **farmer registry**, not the lack of an algorithm.
- The model example is Wadhwani AI's cotton pest tool: a farmer photographs a pest trap, and offline computer vision on a basic smartphone tells them whether and when to spray.
- Voice advice in local languages is the second promising direction.

## 2. Who we build for: Noor

| Noor's reality (from the brief) | What it means for the design |
|---|---|
| 38, farms 2 ha: coffee on the upper slope, maize and beans below | Coffee is the focus; maize and beans prices are a bonus |
| Member of the Ondera Coffee Cooperative for 11 years | The co-op is the trusted local institution, so we build on it |
| Speaks her local language at home, the national language when needed | At least one interaction **by voice in the local language** |
| Her own phone: calls, texts, mobile money | Treat it as a **basic phone**: anything that must reach her goes by **SMS** |
| Her daughter's smartphone, used only on weekends when the daughter is home | The camera and offline AI run there, on weekends |
| No Wi-Fi at home; buys 3G data bundles only occasionally | The core feature needs **no data**; records travel by SMS, which works on 2G |
| Out on the slope most of the day, phone left at the house | Don't assume a phone in the field: she can bring affected leaves home and photograph them |
| Literacy and screen literacy are constraints (Annex B) | Voice first, icons, very little text |

**Setting:** Ondera is fictional. We localize it to **Kirinyaga County, central Kenya**, on the coffee slopes of Mount Kenya:
- **English** is the app's main language (an official language of Kenya).
- **Kiswahili** is the national language.
- **Gĩkũyũ** is the local language: Noor speaks it at home.
- Her co-op is the fictional **Ondera Farmers' Co-operative Society**, with its own coffee factory (wet mill), as Kenyan coffee co-ops are organised. Its communities are Ondera Juu, Ondera Chini, Ondera Mto and Ondera Kilima (all fictional).
- Our training data (JMuBEN) was photographed in Kirinyaga too (Jepkoech et al. 2021; place seen in a search summary, see `docs/evidence.md` §3b).

The team chose this setting on 2026-10-04; the brief requires us to *name* the language.

## 3. The one decision we improve

**"Is something attacking my coffee, and what do I do this week: handle it myself, or get the extension officer to come?"**

There is also a secondary, **non-AI** module: an independent reference price for coffee at harvest (in Kenya: what co-ops paid per kg of cherry, and the Nairobi Coffee Exchange auction price), in Kenyan shillings (KES).

**Problem statement for the video** (using the brief's template; fill in the evidence):
> Because of Cafetal, **Noor** will **know whether leaf rust or another leaf problem is hurting her coffee and get onto the extension officer's visit list** by **the same weekend she notices it**, which she would otherwise only discover **at harvest, after the yield is already lost**. We know because **[cite: extension visits twice a year (concept note, Annex B); impact of coffee leaf rust on yields in Kenya (source + year); FAOSTAT coffee yield trend for Kenya]**.

*(This is the pre-build draft. The final statement, worded to promise only what was built, is in `docs/evidence.md` and `VIDEO_SCRIPT.md`.)*

## 4. The solution: three parts, all on devices people already have

### 1. On the daughter's smartphone (weekends, fully offline)
- Photograph the **underside** of a leaf, where rust shows as orange powder.
- An on-device image model (≤10 MB) identifies the problem.
- The phone plays spoken advice in **Gĩkũyũ, Kiswahili or English**. The advice comes from a **fixed set of advice cards** that people have checked.
- If the model isn't confident, or the photo isn't a coffee leaf → **"I'm not sure — show the leaf to the extension officer."**
- Every diagnosis is saved as a **field observation**: date, rough location, result, confidence, and the photo (kept on the phone).

### 2. Save now, send later by SMS
- The app prepares a **one-SMS summary**: member ID, result code, confidence, date, rough location.
- The user taps Send. It works on 2G and needs no data bundle.
- The app never sends anything by itself.
- Photos are uploaded only when the phone is on co-op Wi-Fi.

### 3. Co-op hub (the cooperative's existing computer; a ~$100 Raspberry Pi if it has none)
- **Member registry with consent.** This addresses the "no farmer registry" bottleneck the brief names.
- Receives the observation texts through a gateway phone.
- **Outbreak map and alert:** when several rust reports come in nearby in one week, an alert goes by SMS to every member's basic phone.
- **Extension officer's worklist:** farms ranked by severity and clustering, with photos when available. **The officer decides** who to visit.
- **Price check:** a member texts "PRICE" (or "BEI" in Kiswahili) and gets the latest reference price for coffee (plus maize and beans) in KES. The reply shows the source and date. This part is not AI, and we say so.
- **Text understanding:** a small model sorts free-text SMS in English or Kiswahili (and Gĩkũyũ, as far as examples allow) into a fixed list of intents (price, report, help, talk to the officer). Replies come **only from the checked answers**.
- *Stretch goal:* a small LLM drafts a weekly summary for the extension officer, and a person reviews it before it's sent.

## 5. Why AI, and not just SMS, a spreadsheet or a search

- Telling rust from leaf miner, phoma or cercospora in a photo is **pattern recognition**. Noor, an SMS menu and a web search can't do it. This is the same kind of AI as the Wadhwani AI example in the brief.
- **Voice in a local language** gets past literacy barriers.
- **Understanding free-text SMS** in English and Kiswahili, so members don't have to memorize codes.
- **Not AI, and we say so:** the price lookup, the alert routing and the registry. They're simple, useful, and they make the AI part actually reach people.

## 6. How we meet the rules

| Rule (Section 06) | How we meet it |
|---|---|
| Runs on a device the user already has | Daughter's Android phone, Noor's basic phone, the co-op's computer |
| Core feature works offline | Model, advice and audio all run on the phone with no signal |
| Model files small enough to side-load or send over a weak connection | Target ≤10 MB. We measure the download time over 3G. It can also be shared by Bluetooth or SD card |
| At least one local-language interaction, named | Gĩkũyũ voice advice, plus Kiswahili and English |
| "How would it fare in a less-supported language?" | Advice is a fixed set of cards. Adding a language means translating about 30 cards and recording them with a native speaker; no model retraining. Gĩkũyũ is itself such a language: Mozilla Common Voice has no Gĩkũyũ data at all (`docs/evidence.md` §8) |
| A person makes the final call | The tool informs and flags uncertainty. Farmers and the officer decide. Nothing is sent without a tap |
| Avoid hallucinations | Farmers only ever see a **fixed list of checked answers**; no free-form generated text |

## 7. Responsible AI (judged pass/fail)

- **Fail-safe:** low confidence, not a coffee leaf, or a severe case → "ask a person," and the farm is added to the officer's worklist.
- **Consent and privacy:**
  - Consent is recorded when a member registers at the co-op.
  - Texts carry a member ID, not a name.
  - Photos stay on the phone unless shared at the co-op.
  - Hub data stays at the co-op. Only co-op staff and the extension officer can read it.
- **Shared or lost phone:**
  - The daughter's phone is shared, so records are stored under a member ID.
  - Optional PIN and a "delete everything" button.
  - No financial data is ever stored on the phone.
- **Bias:**
  - The planned training images (BRACOL, RoCoLe) come from Brazil (Arabica) and Ecuador (Robusta), not Kenya. (As built: JMuBEN, Kenyan Arabica photographed in Kirinyaga, but close-ups from one plantation; see `DATA_CARD.md`.)
  - Accuracy may drop with local varieties, lighting and cheap cameras.
  - We say this openly, test on local photos, and use a confidence threshold.
- **Language content:** machine-translated Kiswahili and Gĩkũyũ are marked **UNVERIFIED** until a native speaker reviews them.

## 8. Data (worth 15% for data grounding; the gaps are scored too)

### 8.1 Evidence the problem is real (cite source, year and country)
- **GSMA Mobile Gender Gap Report:** smartphone vs. basic phone ownership among women in Kenya or Sub-Saharan Africa (plus the CA/KNBS ICT survey 2023/24 for Kenya's rural women).
- **Global Findex (World Bank):** account and mobile money use by gender in Kenya.
- **OpenCelliD:** actual cell coverage in Kirinyaga, on the slopes of Mount Kenya.
- **FAOSTAT:** Kenya's coffee yield and production trend.
- *Optional:* World Bank Data360 / World Development Indicators for the rural population and agricultural jobs.
- Pull the exact figures with their year. If a figure comes from a model rather than a measurement, say so.

### 8.2 Data we build with (check every license)
| Dataset | Source | What it is | Use |
|---|---|---|---|
| **JMuBEN / JMuBEN2** (found during the build) | AgML public bucket; Jepkoech et al. 2021, *Data in Brief* 36:107142 | Arabica, Kenya (Mutira, Kirinyaga, per the dataset paper); 58,549 images; rust, leaf miner, phoma, cercospora, healthy; CC BY 4.0 | The training set as built (BRACOL and RoCoLe could not be downloaded) |
| **BRACOL** (listed in Annex B) | Mendeley Data, doi:10.17632/yy2k5y8mxg.1 | Arabica, Brazil; 1,747 images; rust, leaf miner, phoma, cercospora, healthy | Main training set |
| **RoCoLe** | Mendeley Data, doi:10.17632/c5yvn32dzg.2 | Robusta, Ecuador; 1,560 images; healthy, red spider mite, rust levels 1–4 | Extra rust examples; severity |
| **PlantDoc** (listed in Annex B) | Annex B link | About 2,600 field-condition images of other crops | "Not a coffee leaf" examples, so the model can say "not sure" |
| **Our own photos** | Taken by the team, labeled, with permission | Local test set | Shows how it performs in real conditions |
| Coffee price | Co-operative cherry payouts (Kirinyaga); Nairobi Coffee Exchange auction results; ICO composite price (international) | Reference prices | "PRICE" / "BEI" replies |
| Maize and beans prices | KAMIS (Ministry of Agriculture market information, Kenya); WFP food prices via HDX (Kenya covered, but only to March 2025) | Reference prices | "PRICE" / "BEI" replies |
| Weather | **NASA POWER** (no registration, by coordinates); **CHIRPS** (rainfall history) | Rain and temperature | *Stretch:* weather-based rust risk and spray timing |
| Map | **OpenStreetMap** offline extract | Base map | Outbreak map |
| Language | **MMS** (Meta): check Gĩkũyũ (`kik`) and Kiswahili (`swh`) support; Common Voice; NLLB-200; MASSIVE `sw-KE` | Speech, translation and SMS examples | Voice output; otherwise native-speaker recordings |

### 8.3 What our data does NOT cover (this is scored, so state it plainly)
- **Few images like Noor's.** The planned sets are Brazilian Arabica and Ecuadorian Robusta, so local varieties aren't represented. (As built, JMuBEN is Kenyan and from Kirinyaga, but lab-like close-ups from one plantation, not phone photos from smallholder farms.)
- **Field conditions are untested:** messy backgrounds, shadows, wet leaves, cheap cameras. We test on our own photos and report the gap.
- **The model only sees leaf symptoms.** It can't detect coffee berry disease (CBD, one of Kenya's two major coffee diseases, on the berries), coffee berry borer, antestia bugs, nutrient deficiency, drought, aging trees or soil problems, any of which could explain Noor's lower yields. The app says this and points her to the officer.
- Rust severity labels exist only in RoCoLe (Robusta).
- **Gĩkũyũ** has little speech data (none in Common Voice); Kiswahili has more. Advice audio is recorded or checked by people, not freely generated.
- **Prices** are county, auction or wholesale reference prices, not the price at Noor's factory or farm gate. They're labeled "reference price."
- All sample data is labeled **DEMO**.

## 9. Architecture

```
[Daughter's smartphone — offline web app]
  leaf photo → on-device model (≤10 MB) → result + confidence
  → checked advice card, spoken in Gĩkũyũ / Kiswahili / English
  → field observation saved on the phone
        │ user taps "Send" → 1 SMS (works on 2G, no data)
        ▼
[Co-op hub — the co-op's existing computer + a gateway phone]
  • member registry with consent
  • SMS inbox → observations → outbreak map → SMS alert to all members
  • extension officer's worklist (the officer decides)
  • "PRICE" / "BEI" → reference price reply (source + date)
  • free-text SMS → small model picks a fixed intent → checked reply
        │ once a day, whenever internet is available
        ▼
[Internet — optional]  prices, weather, model and content updates

[Noor's basic phone] ←→ SMS only: alerts, prices, confirmations
```

## 10. Weekend scope

**Build for real**
- Image model with an evaluation report.
- Offline phone app with the advice cards and English audio, plus Kiswahili and at least a few Gĩkũyũ recordings.
- The observation SMS format.
- Hub with:
  - registry
  - SMS inbox (a simulator is fine)
  - outbreak alert
  - officer worklist
  - price reply
  - text-intent sorting

**Fake, labeled DEMO**
- Other members' records.
- The SMS gateway (use the simulator).
- Price history.

**Stretch goals**
- A real Android SMS gateway.
- Rust risk from NASA POWER weather data.
- LLM-drafted weekly summary for the officer.
- Rust severity levels.

## 11. Video (2–5 min; required, or the entry won't be shortlisted)

1. **Problem statement:** the one sentence in section 3.
2. **AI capabilities:**
   - computer vision plus intent sorting
   - why SMS, a spreadsheet or a search can't do this
   - the guardrails
3. **Demo of the whole journey:**
   - Saturday: photograph a leaf with the phone in airplane mode → spoken diagnosis in Gĩkũyũ (and Kiswahili).
   - The observation goes out as an SMS → the co-op map and alert → the officer's worklist.
   - At harvest: Noor texts "PRICE" (or "BEI") from her basic phone.
4. **Where it fits in Noor's day,** plus the tech stack.
5. **Our take:** what localizing AI means to us. The team should write this in their own words: her language, her co-op, the phones she already has, and data that admits its gaps.

## 12. How we score on each judging criterion

| Criterion | Weight | Our answer |
|---|---|---|
| Built solution (Small AI fidelity) | 25% | The whole journey works in airplane mode, plus SMS |
| Development relevance and impact | 20% | Taken directly from the Annex B scenario: diagnosis, extension officer, price |
| Data grounding | 15% | Evidence table, data card and honest gaps (section 8) |
| Evidence it works | 15% | Results on the held-out test set **and** on our own field photos, showing the gap |
| Clarity, design, inclusivity, value of AI | 15% | Voice first, Gĩkũyũ and Kiswahili, works with a basic phone, a clear "why AI" |
| Scalability, replicability, what's next | 10% | Any crop with a leaf dataset, any co-op, any language by adding cards; connects to co-op registries and national programs |
| Responsible AI, data and safety | Pass/fail | Section 7 |

## 13. Open questions

- Region and local language: Kirinyaga + Gĩkũyũ (with Kiswahili and English), decided on 2026-10-04. Do we have a native Gĩkũyũ and Kiswahili speaker to record or review the advice?
- Hardware: an Android phone for the demo, a laptop as the co-op hub, and a spare phone as the SMS gateway?
- The exact submission time and platform.
- Can we get real coffee leaves, or field photos, for a local test set?
