# Content: every sentence a farmer can see or hear

`content/cards.json` holds all farmer-facing text in Cafetal: phone app labels, diagnoses, advice, SMS replies
and the outbreak alert. It is written for coffee farmers of a co-operative society in **Kirinyaga County, central
Kenya**, in three languages:

| Code | Language | Role | Text | Audio |
|---|---|---|---|---|
| `en` | English | **main language** (default in the app; official language of Kenya) | written by the team | synthetic English voice |
| `sw` | Kiswahili | national language | **AI draft** | **provisional** synthetic voice |
| `kik` | Gĩkũyũ | local language of Kirinyaga | **AI draft** (best effort) | **provisional** synthetic voice |

Nothing a farmer sees or hears is written anywhere else, and nothing is generated on the fly. The app and the hub
only pick a card by its `id` and fill slots such as `{fecha}` with numbers, dates and source names. Card ids and
slot names are internal (several are Spanish words from the first version of the project); they are never shown.

```
content/
  cards.json            83 cards (schema: PLAN.md §10; required ids: PLAN.md §11)
  audio/en/<id>.mp3     spoken English, 74 files
  audio/sw/<id>.mp3     spoken Kiswahili (provisional), 74 files
  audio/kik/<id>.mp3    spoken Gĩkũyũ (provisional), 74 files
  audio/manifest.json   what text each MP3 says (hash), so make_audio.py only redoes what changed
```

Size: 83 cards, about 917 words in English, 796 in Kiswahili and 855 in Gĩkũyũ. 74 cards are spoken (types `ui`,
`diagnosis`, `advice`); the 9 SMS and alert cards are text only.

## Status: everything is UNVERIFIED

No card has been checked by a person, in any language (`status` is `"unverified"` and `reviewed_by` is `null`
everywhere).

| Part | What it is now | Who must check it |
|---|---|---|
| English advice (`diag_*`, `advice_*`, `limits_yield`) | Written by the team from public Kenyan and international extension material (KALRO Coffee Research Institute review, CABI Plantwise, Infonet-Biovision; links in each card's `source`) | An **agronomist or extension officer**: the county coffee extension officer or the co-operative's own field officer |
| English UI and SMS text | Written by the team, plain words for low literacy | **Co-op staff** (is it clear for members?) |
| **Kiswahili text** | **An AI draft** in standard Kiswahili. Nobody who speaks Kiswahili has read it | A **native Kiswahili speaker**, ideally from central Kenya |
| **Gĩkũyũ text** | **An AI draft, best effort, low confidence.** Written by an AI model without a dictionary it could open (Gĩkũyũ dictionaries and Wiktionary were blocked from the build machine; only a few words were seen in search summaries). Expect wrong words, wrong noun-class agreement and unnatural phrasing | A **native Gĩkũyũ speaker from Kirinyaga**; better still two, one older farmer |
| English audio | Piper offline TTS, voice `en-us-lessac-medium` (an American English voice, slowed a little) | Anyone who speaks English: listen once |
| **Kiswahili and Gĩkũyũ audio** | **Provisional synthetic speech:** the same English voice made to read Kiswahili phonemes (details below). It has a foreign accent and will mispronounce words. It is there only so the demo can play something | Replace with **recordings by native speakers** |

The app shows an **UNVERIFIED** badge next to any text or audio whose status is not `verified`. SMS sent to basic
phones cannot carry a badge; the hub outbox marks them.

Whatever the language, the advice itself must be checked once by the agronomist (in English). A translator checks
that the Kiswahili or Gĩkũyũ says the same as the English, nothing more.

## How to review and mark a card verified

1. Open the hub's content page (linked from the hub home). It lists every card in all three languages and plays
   the audio.
2. Read (and listen to) the card in one language. If it is right, type your name and press the verify button. The
   hub calls `POST /api/cards/{id}/verify` and stores `status[lang] = "verified"` and `reviewed_by[lang]` (name and
   date). Each language is verified on its own: verifying English does not verify the Kiswahili or the Gĩkũyũ.
3. If the text is wrong, correct it in `cards.json` (keep it short), set that language back to `"unverified"`, and
   run `python3 scripts/make_audio.py`. **Any change to a verified text must reset it to unverified.** When the
   English advice changes, change the Kiswahili and Gĩkũyũ to match and set them back to `"unverified"` too.

Checklist for reviewers:

- **Agronomist / extension officer:** Is the common name right for Kirinyaga? Is the advice safe and doable this
  week with the farmer's own hands? Does it say when to call the officer? The cards never name a pesticide or a dose
  on purpose: chemical control is the officer's decision ("ask the extension officer").
- **Native Kiswahili / Gĩkũyũ speaker:** Is it natural and polite? Would an older woman who reads little understand
  it when it is played once? Are the words for "extension officer", "co-operative", "factory", "leaf rust" the ones
  people really use (loanwords such as *afisa*, *sosaiti*, *kiwanda*, *kutu* may be better than invented words)?
- **Co-op staff:** Do the SMS replies make sense on a basic phone? Are the keywords easy to remember?

## How to record a native-speaker voice (replaces the synthetic audio)

- On the hub content page, use the record or upload button next to a card (a phone voice recorder is fine: quiet
  room, phone 20 cm from the mouth, one card per file). The hub calls `POST /api/cards/{id}/audio/{lang}`, saves it as
  `audio/<lang>/<id>.mp3` and sets `audio_source[lang] = "native:<speaker name>"`.
- By hand: put the file at `content/audio/kik/<id>.mp3` and set `"audio_source": {"kik": "native:<name>"}`.
- `make_audio.py` **never overwrites** a file whose `audio_source` starts with `native`.
- The recording is reviewed like text: the speaker or another native speaker marks it verified.
- Start with `diag_duda`, the six `diag_*` cards, the `advice_*` cards and `limits_yield`.

## How to add a language (no model retraining)

1. Add the language to `"languages"`, e.g. `"luo": "Dholuo"`.
2. Add a `"luo"` text to every card: **83 cards, about 800 to 900 words**. The minimum is the 60 required ids in
   PLAN.md §11. Set `"status": {"luo": "unverified"}` and `"reviewed_by": {"luo": null}`.
3. Audio: record the 74 spoken cards with a native speaker, or run `python3 scripts/make_audio.py` to get
   provisional synthetic audio first (any language other than `en` gets the provisional voice; add a real Piper voice
   for it in `voice_for()` if one exists).
4. SMS cards must stay one SMS after filling slots: run `python3 scripts/make_audio.py --check`.
5. Register members with that language at the co-op (the `language` choice in `hub/main.py` and
   `hub/static/registro.html`); the hub replies in the member's language, and in English for a card that lacks it.
6. The phone app offers every language in `"languages"` on its first screen and in Settings. A "Listen in …" button
   on the result screen needs a `ui_play_<code>` card.

The image model does not change: it outputs a label (`roya`, `minador`…), and the label points to a card.

## Writing rules (for anyone editing cards)

- Plain, warm, short. "You", not "the farmer". UI labels 1–4 words; advice at most 4–5 short sentences.
- `diag_*` = what is said first ("It looks like coffee leaf rust."). `advice_*` = what to do this week.
- `diag_duda` in English is exactly **"I'm not sure — show the leaf to the extension officer."** (the fail-safe;
  `make_audio.py --check` enforces it).
- Kenyan English: *extension officer*, *co-op* (the co-operative society), *factory* (its wet mill), *farm*,
  *fertiliser*, prices in *KES*.
- Never name pesticide products or doses. Say "ask the extension officer". Resistant varieties (Ruiru 11, Batian)
  may be mentioned as something to ask the officer about.
- `limits_yield` must keep saying that the app only sees leaf symptoms and cannot see coffee berry disease on the
  berries, antestia bugs, berry borer, lack of fertiliser, drought, old trees or soil problems.
- **SMS cards** (`sms_*`, `alert_roya`): at most 160 characters after filling slots, and only GSM-7 characters,
  so plain ASCII: no curly quotes, no dashes, no accents. One character outside GSM-7 turns the message into a
  70-character UCS-2 SMS. **The Gĩkũyũ SMS cards write ĩ and ũ as i and u.** This merges vowels that Gĩkũyũ
  keeps apart (in Meta's Gĩkũyũ text counts, ĩ and ũ are 17% of all letters; `docs/evidence.md` §6), so SMS
  Gĩkũyũ is harder to read than the app's. `make_audio.py --check` tests length and alphabet with long sample
  values (coffee 157.40 KES/kg cherry, a 24-letter community name).
- SMS keywords (one-word messages): **PRICE/PRICES** or **BEI**, **HELP** or **MSAADA**, **OFFICER** or
  **AFISA**. `sms_ayuda` advertises them and the CAF1 report code. There are no Gĩkũyũ keywords; the Gĩkũyũ
  cards advertise the English and Kiswahili ones.
- `sms_precio` says "reference price" (*bei elekezi*, *thogora wa kuonereria*), names the source `{fuente}` and
  the date `{fecha}` from `data/prices.json` (`sms_fuente`, `sms_fecha`; it starts with DEMO while the prices are
  not verified), and says it is not the price at your factory.
- Slots (`{fecha}`, `{precio_cafe}`, `{unidad_cafe}`, `{precio_maiz}`, `{precio_frijol}`, `{fuente}`,
  `{comunidad}`, `{n_reportes}`) are filled only with numbers, dates, community and source names. Keep their names.

### Key terms

| English | Kiswahili (draft) | Gĩkũyũ (draft, low confidence) |
|---|---|---|
| coffee leaf rust | kutu ya majani | kutu ya mathangũ (loan from Kiswahili) |
| coffee berry disease (CBD) | chule buni | mũrimũ wa matunda ma kahũa |
| leaf miner | mchimba majani | tũtambi tũrĩa mathangũ ("small insects that eat leaves") |
| brown eye spot | doa jicho kahawia | ndoa cia rangi wa ndaka |
| red spider mite | utitiri mwekundu | tũtambi tũtune |
| extension officer | afisa ugani | afisa wa ũrĩmi |
| co-operative / co-op | chama (cha ushirika) | sosaiti |
| factory (wet mill) | kiwanda | kiwanda |
| reference price | bei elekezi | thogora wa kuonereria |
| under the leaf | upande wa chini wa jani | mũhuro wa ithangũ |
| every week | kila wiki | o kiumia |
| prune / weed | pogoa / palilia | ceha / rĩmĩra mahuti |
| shade / fertiliser / manure | kivuli / mbolea / samadi | kĩĩruru / mbolea / thumu |
| I'm not sure | sina uhakika | ndiũĩ wega |
| UNVERIFIED | HAIJAHAKIKIWA | NDĨRATHUTHURIO |

Kiswahili *kutu ya majani*, *chule buni* and *afisa ugani* were seen in Swahili extension writing (search summary of
"Magonjwa makuu ya kahawa", http://mitiki.blogspot.com/2009/12/magonjwa-makuu-ya-kahawa.html). The other Kiswahili
terms and all Gĩkũyũ terms are the AI model's choices and need a native speaker. Public Gĩkũyũ agricultural
resources that a reviewer with normal internet could use (listed in `docs/evidence.md` §8, quality not checked by
us): Digital Green's Kikuyu ASR training sentences (recorded by extension workers and farmers) and CGIAR's
Kikuyu–English agricultural sentence pairs.

## Where the advice comes from

Each card's `source` field gives the document title and URL. Main sources:

- Gichuru, Alwora, Gimase & Kathurima (KALRO Coffee Research Institute, Ruiru) 2021, *Coffee Leaf Rust (Hemileia
  vastatrix) in Kenya: A Review*, Agronomy 11(12):2590: pruning and canopy management, shade, resistant varieties
  (Ruiru 11 highly resistant, Batian intermediate), fungicides tested by CRI for the Pest Control Products Board.
- Infonet-Biovision (Kenya): coffee leaf rust (open pruning, good weeding, spraying before the rains), spider mites
  and coffee pages.
- CABI Plantwise factsheets for farmers and PlantwisePlus Knowledge Bank: coffee leaf rust, brown eye spot
  (*Cercospora coffeicola*), red spider mite on coffee (*Oligonychus coffeae*).
- CABI Compendium, *Leucoptera meyricki* (the main coffee leaf miner in Kenya); Dantas et al. 2021 review
  (insecticides kill the leaf miner's natural enemies).
- Daily Nation *Seeds of Gold* (cold-weather coffee diseases in high-altitude central Kenya); Revista Cultivar
  (Phoma: cold wind, windbreaks, nutrition).
- Kenya Coffee Sustainability Manual (compiled by KALRO-CRI, 2020): general good practice.
- For `limits_yield`: Alliance of Bioversity International and CIAT, and Solidaridad, on why Kenyan coffee yields
  are low (berry disease, berry borer, rust, old trees, fertiliser access).

**Caveat:** the build machine could not open any of these pages (their sites are blocked by its network policy).
The advice was written from web-search summaries of them, so the reviewing agronomist should open each link once
before marking a card verified. `docs/evidence.md` §4 has more on Kenyan coffee diseases and resistant varieties.

## Making the audio

```
python3 scripts/make_audio.py --check   # validate ids, slots, languages, diag_duda, SMS length and alphabet (no audio)
python3 scripts/make_audio.py           # render only what changed
python3 scripts/make_audio.py --force   # re-render all synthetic audio
```

Piper (`PIPER_BIN`, default `/home/user/tools/piper/piper`), offline:

- `en`: voice `en-us-lessac-medium` (`PIPER_VOICE_EN`; espeak-ng `en-us`), `--length_scale 1.4` so it speaks at
  about 170 words a minute. `audio_source.en = "synthetic:piper-en-us-lessac-medium"`.
- `sw`: **provisional.** There is no Piper voice for Kiswahili (or Gĩkũyũ) in this build environment, but espeak-ng
  has a Kiswahili phonemizer (`sw`). The script copies the English voice's config with `"espeak": {"voice": "sw"}`,
  so the English voice reads Kiswahili phonemes. `--length_scale 1.25`. The text is respelled for the voice only:
  `j` → `dy` (espeak turns *j* into a sound the voice never learned). `audio_source.sw =
  "synthetic-provisional:piper-en-us-lessac-medium-espeak-sw"`.
- `kik`: **provisional.** The same voice and Kiswahili phonemes read the Gĩkũyũ text after mapping **ĩ → e** and
  **ũ → o** (in Gĩkũyũ spelling ĩ is the sound [e] and ũ is [o]; espeak's Kiswahili reader knows neither letter).
  Gĩkũyũ tones are not marked in writing and are not produced. `audio_source.kik =
  "synthetic-provisional:piper-en-us-lessac-medium-espeak-sw-reading-gikuyu"`.
- MP3 mono 22,050 Hz at **24 kbps** (`AUDIO_BITRATE`); long pauses are squeezed with ffmpeg. The 222 files take
  **2.91 MB** (en 0.92 MB, sw 1.02 MB, kik 0.97 MB). WAV files are temporary and never written to the repo.

**Why the English voice for Kiswahili and Gĩkũyũ.** Both Piper voices on the build machine were tried with espeak
`sw` phonemes. Nobody listened; these are *computed* checks (phoneme coverage on all 83 card texts; speech rate
and gaps on 35 rendered cards: the 7 diagnoses, 8 advice cards and the first 20 UI cards):

| Check (computed, not a listening test) | Spanish voice `es-mls_10246-low` | English voice `en-us-lessac-medium` |
|---|---|---|
| Kiswahili + Gĩkũyũ phoneme tokens that the voice's own language uses at least 20 times in 5,000 MASSIVE utterances (after the `j` respelling) | 96.5% (lacks *h*, *z*, *v*) | 95.2% (lacks the rolled *r*, *ny*) |
| Kiswahili speech after pause squeezing (length_scale 1.0) | 61 words/min, 1.39 silent gaps per word (choppy: words broken up) | 136 words/min, 0.66 gaps per word |
| Gĩkũyũ speech after pause squeezing (length_scale 1.0) | 91 words/min, 0.80 gaps per word | 159 words/min, 0.56 gaps per word |

The Spanish voice knows slightly more of the sounds but speaks Kiswahili slowly and in broken pieces; the English
voice is fluent but has no rolled *r* (Gĩkũyũ uses *r* a lot). We kept the English voice and slowed it
(length_scale 1.25). To compare, run with `PIPER_VOICE_SW=/home/user/tools/voice-es/es-mls_10246-low.onnx`. A
native speaker should listen to both before any field use.

**Better voices, for a teammate with normal internet.** Meta's MMS project has text-to-speech models for both
languages on Hugging Face: **`facebook/mms-tts-swh`** (Kiswahili) and **`facebook/mms-tts-kik`** (Gĩkũyũ). Both are
VITS models of about 145 MB each (too big to ship in the phone app, but fine for pre-rendering MP3s once on a
laptop), and both are licensed **CC-BY-NC-4.0 (non-commercial only)**; names, sizes and licence as listed in
`docs/evidence.md` §8. Hugging Face is blocked from this build machine, so we could not use them. MMS was trained on
readings of religious texts, so farming words may still come out wrong. Native-speaker recordings remain the goal.
