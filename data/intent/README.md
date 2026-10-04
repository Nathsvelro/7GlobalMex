# SMS intent examples

`examples.csv` (`text,intent,lang,source`) trains the free-text SMS classifier (`hub/train_intent.py`).
Intents: `price`, `report`, `help`, `talk_to_officer`, `other`. Languages: `en` (English), `sw` (Kiswahili),
`kik` (Gĩkũyũ, typed without diacritics as on a basic phone).

| source | what | licence |
|---|---|---|
| `team` | Written by the build team (which includes AI agents) in the style of Kenyan farmer SMS: English and Kiswahili, sheng (e.g. "iko aje", "how much"), typos, no diacritics, abbreviations. About 50 per intent per language for `price`, `report`, `help`, `talk_to_officer`, plus about 30 everyday `other` messages per language. Nobody has checked the Kiswahili with a native speaker, and none of it comes from real members. Kept in `handwritten.csv`. | project licence |
| `ai-draft-unverified` | A few Gĩkũyũ messages (3-4 per intent) drafted with AI. Nobody has checked them. | project licence |
| `MASSIVE` | 200 utterances each from Amazon MASSIVE 1.1, locales en-US and sw-KE, `train` partition, used only as `other` (off-topic). Intents (`qa_currency`, `qa_stock`, `iot_coffee`, `weather_query`, `takeaway_*`) and words that overlap ours (money, prices, coffee, crops, calls, visits, help, information) are filtered out. | CC BY 4.0, © Amazon.com Inc. or its affiliates, https://github.com/alexa/massive |

Rebuild and retrain:

```
python3 -m hub.build_intent_examples          # handwritten.csv + MASSIVE sample -> examples.csv
python -m hub.train_intent                    # needs scikit-learn (requirements-train.txt)
```

MASSIVE download: https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz
(the builder reads `1.1/data/en-US.jsonl` and `1.1/data/sw-KE.jsonl`; pass `--massive-dir <folder>`).

The fixed probe messages in `hub/train_intent.py` (e.g. "how much are you paying for a kilo of cherry",
"bei ya kahawa ni ngapi") are kept out of this data on purpose.
