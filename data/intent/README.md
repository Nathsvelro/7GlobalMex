# SMS intent examples

`examples.csv` (`text,intent,lang,source`) trains the free-text SMS classifier (`hub/train_intent.py`).
Intents: `precio`, `reporte`, `ayuda`, `hablar_con_tecnico`, `otro`.

| source | what | licence |
|---|---|---|
| `team` | Written by the team in the style of rural Mexican SMS (typos, no accents, abbreviations). Kept in `handwritten.csv`. | project licence |
| `ai-draft-unverified` | A few Tseltal messages drafted with AI. Nobody has checked them. | project licence |
| `MASSIVE` | 300 utterances from Amazon MASSIVE 1.1, locale es-ES, `train` partition, used only as `otro` (off-topic). Intents and words that overlap ours (money, prices, coffee, calls, appointments, help, information) are filtered out. | CC BY 4.0, © Amazon.com Inc. or its affiliates, https://github.com/alexa/massive |

Rebuild and retrain:

```
python3 -m hub.build_intent_examples          # handwritten.csv + MASSIVE sample -> examples.csv
python -m hub.train_intent                    # needs scikit-learn (requirements-train.txt)
```

MASSIVE download: https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz
(the builder reads `1.1/data/es-ES.jsonl`; pass `--massive <path>`).
