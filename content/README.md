# Content: every sentence a farmer can see or hear

`content/cards.json` holds all farmer-facing text in Cafetal: phone app labels, diagnoses, advice, SMS replies
and the outbreak alert, in **Spanish (`es`)** and **Tseltal (`tzh`)**, the two languages of the co-op, plus
**English (`en`)** for international judges and visitors. Nothing a farmer sees or hears is written
anywhere else, and nothing is generated on the fly. The app and the hub only pick a card by its `id` and fill
slots such as `{fecha}` with numbers, dates and source names.

```
content/
  cards.json            83 cards (schema: PLAN.md §10; required ids: PLAN.md §11)
  audio/es/<id>.mp3     spoken Spanish, 74 files
  audio/tzh/<id>.mp3    spoken Tseltal (provisional), 74 files
  audio/en/<id>.mp3     spoken English (synthetic English voice), 74 files
  audio/manifest.json   what text each MP3 says (hash), so make_audio.py only redoes what changed
```

## Status: everything is UNVERIFIED

| Part | What it is now | Who must check it |
|---|---|---|
| Spanish advice (`diag_*`, `advice_*`, `limits_yield`) | Written by the team from public extension material (SENASICA, ANACAFÉ, Cenicafé; links in each card's `source`) | An **agronomist or extension officer** (the co-op's técnico, or the state plant-health committee) |
| Spanish UI and SMS text | Written by the team | **Co-op staff** (is it clear for members?) |
| **Tseltal text** | **An AI draft.** Words were checked one by one against a published dictionary (below), but no native speaker has read it | A **native Tseltal speaker** from the co-op's own area |
| Spanish audio | Piper offline TTS, voice `es-mls_10246-low` | Anyone: listen once |
| **Tseltal audio** | **A Spanish voice reading the Tseltal draft.** It drops glottal stops and other sounds and does not sound like a Tseltal speaker. It is there only so the demo can play something | Replace with **recordings by a native speaker** |
| English text | **An AI translation of the Spanish cards** (plain, short sentences), for judges and visitors | An **English speaker** checks that it is clear and says the same as the Spanish. The advice itself is verified in Spanish by the agronomist |
| English audio | Piper offline TTS, voice `en-us-lessac-medium` (a real English voice, slowed a little) | Anyone who speaks English: listen once |

The app shows an **UNVERIFIED / SIN VERIFICAR** badge next to any text or audio whose status is not `verified`.

Honest note on the Tseltal draft: it was written by an AI model, with vocabulary looked up in Polian (2018),
*Tseltal-Spanish multidialectal dictionary* (Dictionaria, CC BY 4.0,
https://dictionaria.clld.org/contributions/tseltal). The grammar (verb forms, word order, imperatives) is a
best guess. Tseltal varies a lot between towns; some choices below may sound foreign in a given community.
The two cards added last (`ui_member_not_registered`, `ui_consent_hub_text`) reuse words from other cards plus
loanwords (computadora, contraseña); only a few of their words were looked up in the dictionary.

## How to review and mark a card verified

1. Open the hub content page (linked from the hub home), which lists every card in all three languages and plays the audio.
2. Read (and listen to) the card in one language. If it is right, type your name and press the verify button. The hub calls
   `POST /api/cards/{id}/verify` and stores `status[lang] = "verified"` and `reviewed_by[lang]` (name and date).
   Each language is verified on its own: verifying English (`lang: "en"`) does not verify the Spanish or the Tseltal.
3. If the text is wrong, correct it in `cards.json` (keep it short), set that language back to `"unverified"`,
   and run `python3 scripts/make_audio.py`. **Any change to a verified text must reset it to unverified.**
   When the Spanish advice changes, change the English to match and set `status.en` back to `"unverified"` too.

Checklist for reviewers:
- **Agronomist / extension officer:** Is the common name right for Chiapas? Is the advice safe and doable this week
  with the farmer's own hands? Does it say when to call the técnico? The cards never name a pesticide or a dose on
  purpose: chemical control is the técnico's decision.
- **Native Tseltal speaker:** Is it natural and polite? Would an older woman who does not read Spanish understand it
  when it is played aloud? Are the loanwords (roya, técnico, cooperativa, abono, SMS) the ones people really use?
- **English speaker:** Does it say the same as the Spanish, nothing more? Is it plain enough to understand when heard once?

## How to record a native-speaker voice (replaces the synthetic audio)

- On the hub content page, use the upload button next to a card and choose an audio file (a phone voice recorder
  is fine: quiet room, phone 20 cm from the mouth, one card per file). The hub calls
  `POST /api/cards/{id}/audio/{lang}`, saves it as `audio/<lang>/<id>.mp3` and sets
  `audio_source[lang] = "native:<speaker name>"`.
- By hand: put the file at `content/audio/tzh/<id>.mp3` and set `"audio_source": {"tzh": "native:<name>"}`.
- `make_audio.py` **never overwrites** a file whose `audio_source` starts with `native`.
- The recording is reviewed like text: the speaker or another native speaker marks it verified.

## How to add a new language (no model retraining)

1. Add the language to `"languages"`, e.g. `"tzo": "Bats'i k'op (Tsotsil)"`.
2. Add a `"tzo"` text to every card: **83 cards, about 860 words**. The minimum is the 60 required ids in
   PLAN.md §11. Set `"status": {"tzo": "unverified"}` and `"reviewed_by": {"tzo": null}`.
3. Audio: record the 74 spoken cards (types `ui`, `diagnosis`, `advice`) with a native speaker, or run
   `python3 scripts/make_audio.py` to get provisional synthetic audio first (it uses the Spanish voice for any
   language other than `en`; add the language's own Piper voice in `voice_for()` if one exists).
4. SMS cards must stay one SMS after filling slots: run `python3 scripts/make_audio.py --check`.
5. Register members with that language at the co-op (add it to the `language` choice in `hub/main.py` and
   `hub/static/registro.html`); the hub replies in the member's language, and in Spanish for a card that lacks it.
6. The phone app offers every language in `"languages"` on its first screen and in Settings, with no code change.
   (A "Listen in …" button on the result screen exists for `tzh`, `es` and `en`.)

English was added exactly this way (plus the card `ui_play_en`).

The image model does not change: it outputs a label (`roya`, `minador`…), and the label points to a card.

## Writing rules (for anyone editing cards)

- Plain, warm, short. Spanish uses **usted**. UI labels 1–4 words; advice at most 3–4 short sentences.
- `diag_*` = what is said first ("Parece roya del cafeto."). `advice_*` = what to do this week.
- `diag_duda` (es) is exactly **"No estoy seguro — muestre la hoja al técnico."** (the fail-safe);
  in English exactly **"I'm not sure — show the leaf to the extension officer."**
- English: plain words, "you", the same meaning as the Spanish and no more. *técnico* = **extension officer**,
  *cooperativa* = **co-op**, *roya* = **leaf rust**, *mancha de hierro* = **brown eye spot**, *broca* = **berry borer**.
  English SMS cards advertise the keywords **PRICE, HELP, OFFICER** (the hub also accepts PRECIO, AYUDA, TECNICO).
- Never name pesticide products or doses. Say "pregunte al técnico".
- Common names: *Hemileia vastatrix* = **roya del cafeto**; *Leucoptera coffeella* = **minador de la hoja**;
  *Phoma costarricensis* = **phoma, quema o derrite**; *Cercospora coffeicola* = **mancha de hierro** (not "ojo de
  gallo", which is a different disease, *Mycena citricolor*); *Oligonychus yothersi* = **arañita roja / ácaro rojo**.
- **SMS cards** (`sms_*`, `alert_roya`): at most 160 characters after filling slots, and only GSM-7 characters.
  That is why they are written without á, í, ó, ú and without dashes ("tecnico", "codigo"): one accented letter
  would turn the message into a 70-character UCS-2 SMS. `make_audio.py --check` tests this with long sample values.
- Slots (`{fecha}`, `{precio_cafe}`, `{comunidad}`…) are filled only with numbers, dates, community and source names.
  `sms_precio` takes `{fuente}` from `data/prices.json` → `sms_fuente` (kept short, starts with DEMO while the prices
  are not verified).

## Where the advice comes from

Each card's `source` field gives the document title and URL. Main sources:
- SENASICA, *Ficha técnica Roya del cafeto* and *Manual técnico para el manejo preventivo de la roya del cafeto*
  (shade regulation, partial pruning for air, nutrition, weed control, weekly sampling).
- SENASICA, *Ficha técnica Minador de la hoja del cafeto*; ANACAFÉ/CEDICAFÉ technical bulletin, Feb 2020.
- SENASICA-CNRF, *Ficha técnica No. 47 Quema o derrite del cafeto (Phoma costarricensis)*, 2014.
- Cenicafé, *Mancha de hierro: manejo de la enfermedad* and *Avance técnico: La mancha de hierro del cafeto*.
- ANACAFÉ/CEDICAFÉ, *Manejo integrado de la araña roja del café*, Feb 2019; *Agronomía Costarricense* 44(1), 2020.

**Caveat:** the build machine could not open these PDFs (the sites are blocked by its network policy). The advice was
written from web-search summaries of them, so the reviewing agronomist should open each link once before marking
a card verified.

## Tseltal draft: conventions and key words

Spelling follows the common practical alphabet (INALI-style): `j` = h sound, `'` = glottal stop, `x` = "sh",
`ts' ch' k' p' t'` = glottalised consonants. Possessive prefixes: `j-/k-` my, `a-/aw-` your, `s-/y-` his/her/its.

| Tseltal (draft) | Meaning | Note |
|---|---|---|
| kajpe, kajpetal | coffee, coffee plot | dictionary: *kahpe / kajpe* |
| yabenal | its leaf | varies: *ya'malel* (Yajalón), *wamal* (central towns) |
| ta yanil | underneath | *yanil* "below" (central dialects) |
| ta nopol | near, close up | used in `alert_roya` and `ui_photo_tip_underside` |
| ya snojes | it fills it | *noj* "full" + causative *-es*; used in `ui_photo_tip_underside` |
| chamel | disease | |
| ila / lok'taya / tikuna / tup'a | look at it / photograph it / send it / erase it | imperatives (-a) |
| ik'a te técnico | call the técnico | *ik'* "call, invite" |
| ak'a yil | let (him) see it | used in `diag_duda` |
| ma jna' lek | I am not sure ("I don't know well") | |
| yilel | apparently, it seems | used in "Ja' roya yilel" = "it seems to be rust" |
| stojol | its price | |
| ixim, chenek' | maize, beans | |
| axinal, ik', k'aal, takin k'inal | shade, wind, sun, dry season | |
| k'an tan | yellow/orange powder (rust spores) | |
| bats'il k'op / kaxlan k'op | Tseltal / Spanish | |
| wokol awal | thank you | |

## Making the audio

```
python3 scripts/make_audio.py --check   # validate ids, slots, SMS length (no audio)
python3 scripts/make_audio.py           # render only what changed
python3 scripts/make_audio.py --force   # re-render all synthetic audio
```

- Piper (`PIPER_BIN`, default `/home/user/tools/piper/piper`), one voice per language:
  - `es` and `tzh`: the first `.onnx` voice in `/home/user/tools/voice-es/` (`PIPER_VOICE`). Text is turned into
    phonemes with espeak-ng **`es-419`** (Latin-American Spanish: "c/z" said as "s", as in Mexico) instead of the
    voice's default Castilian `es`.
  - `en`: the first `.onnx` voice in `/home/user/tools/voice-en/` (`PIPER_VOICE_EN`; default
    `en-us-lessac-medium`, espeak `en-us`), with `--length_scale 1.4` so it speaks at about 170 words a minute, like
    the Spanish audio. `audio_source.en = "synthetic:piper-en-us-lessac-medium"`.
- MP3 mono 22,050 Hz at **24 kbps** (`AUDIO_BITRATE`); long pauses are squeezed with ffmpeg. All 222 files take
  **about 3.5 MB** (es 1.17 MB, tzh 1.49 MB, en 0.87 MB). Before English, the 146 es + tzh files took 2.6 MB.
- `--check` validates every language listed in `"languages"`.
- For Tseltal the script respells the text only for the voice (drops `'`, `x` → `sh`, drops a word-initial `j`
  before a consonant) so the Spanish voice does not spell letters out. This is a stop-gap, not Tseltal speech.
- WAV files are temporary and never written to the repo.
