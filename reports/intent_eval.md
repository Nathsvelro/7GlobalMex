# Intent classifier evaluation (free-text SMS)

Date: 2026-10-03. Produced by `hub/train_intent.py`; raw numbers in `reports/intent_eval.json`.

## Data

- `data/intent/examples.csv`: 575 messages. Per intent: precio 54, reporte 82, ayuda 49, hablar_con_tecnico 48, otro 342.
- Sources: MASSIVE 300, ai-draft-unverified 16, team 259. `team` = written by the team (Mexican rural SMS style, typos, no accents); `ai-draft-unverified` = Tseltal drafts nobody has checked; `MASSIVE` = Amazon MASSIVE 1.1 es-ES utterances (CC BY 4.0) used only as 'otro' (off-topic) examples, after removing intents/words that overlap ours.
- Split: stratified 80/20, random_state=42 -> 460 train / 115 test.

## Model

- TF-IDF char_wb (2, 4), sublinear_tf, l2 + LogisticRegression multinomial, class_weight=balanced, C=1.0 (5-fold CV macro-F1 by C: {'1.0': 0.8769, '3.0': 0.867, '10.0': 0.8615, '30.0': 0.8479}). 4457 n-gram features.
- Confidence threshold **0.45** (lowest t with >= 95% precision on auto-answered messages, out-of-fold predictions on the 80% split). Below it the hub replies `sms_pasar_tecnico` and forwards the message to the officer.
- Exported to `hub/intent_model.json`; `hub/intent.py` runs it in pure Python (a test checks it matches scikit-learn on the test split).

## Results on the held-out 20% split

| | n | accuracy | macro-F1 |
|---|---|---|---|
| argmax (no threshold) | 115 | 0.922 | 0.897 |
| with threshold (as deployed) | 115 | 0.913 | 0.866 |
| with threshold, Spanish only | 111 | 0.919 | 0.871 |
| with threshold, excluding MASSIVE | 57 | 0.842 | 0.820 |

Auto-answered share: 35.6% of test messages; precision of those answers: 95.1%. On-topic test messages (true intent is not 'otro') answered with the right card automatically: 83.0%; the rest go to the officer.

Confusion matrix (with threshold; rows = true, columns = predicted):

| true \ pred | precio | reporte | ayuda | hablar_con_tecnico | otro |
|---|---|---|---|---|---|
| precio | 9 | 0 | 0 | 0 | 2 |
| reporte | 0 | 16 | 0 | 0 | 0 |
| ayuda | 0 | 0 | 4 | 0 | 6 |
| hablar_con_tecnico | 0 | 0 | 0 | 10 | 0 |
| otro | 0 | 0 | 2 | 0 | 66 |

Threshold sweep (out-of-fold, 80% split):

| threshold | auto precision | auto share | macro-F1 (routed) |
|---|---|---|---|
| 0.30 | 0.918 | 0.370 | 0.877 |
| 0.35 | 0.917 | 0.341 | 0.836 |
| 0.40 | 0.930 | 0.311 | 0.799 |
| 0.45 | 0.961 | 0.278 | 0.776 |
| 0.50 | 0.991 | 0.241 | 0.737 |
| 0.55 | 0.990 | 0.206 | 0.680 |
| 0.60 | 0.988 | 0.178 | 0.626 |
| 0.65 | 0.986 | 0.157 | 0.582 |
| 0.70 | 0.983 | 0.130 | 0.522 |
| 0.75 | 1.000 | 0.089 | 0.436 |
| 0.80 | 1.000 | 0.061 | 0.360 |
| 0.85 | 1.000 | 0.033 | 0.275 |
| 0.90 | 1.000 | 0.017 | 0.220 |

Probe messages (not in the data):

| message | predicted | conf | routed |
|---|---|---|---|
| q precio tiene el cafe | precio | 0.80 | precio |
| cuanto pagan x kilo | precio | 0.88 | precio |
| mi cafe tiene manchas amarillas | reporte | 0.84 | reporte |
| kiero hablar con el ingeniero | hablar_con_tecnico | 0.87 | hablar_con_tecnico |
| como funciona | ayuda | 0.85 | ayuda |
| hola buenas tardes | otro | 0.64 | otro |
| pon musica | otro | 0.57 | otro |
| a como esta el pergamino en la cooperativa | precio | 0.33 | otro |
| las hojas tienen polvo amarillo | reporte | 0.83 | reporte |
| que venga el ingeniero a mi parcela | hablar_con_tecnico | 0.73 | hablar_con_tecnico |
| mis matas tienen polvo naranja | reporte | 0.60 | reporte |
| cuanto estan pagando el kilo de cafe | precio | 0.92 | precio |
| asdf qwerty | otro | 0.41 | otro |
| quiero hablar con el ingeniero | hablar_con_tecnico | 0.92 | hablar_con_tecnico |
| hola buenos dias | otro | 0.61 | otro |

Test errors before threshold (9):

- "que significa CAF1" — true ayuda, predicted otro (0.38)
- "como es posible" — true otro, predicted ayuda (0.47)
- "bit'il ayat" — true otro, predicted ayuda (0.33)
- "info" — true ayuda, predicted otro (0.28)
- "cuanto esta la bolsa de nueva york" — true precio, predicted otro (0.44)
- "pasame tu numero" — true otro, predicted ayuda (0.38)
- "que tal como estas" — true otro, predicted ayuda (0.54)
- "hola que puedo hacer aqui" — true ayuda, predicted otro (0.38)
- "menu" — true ayuda, predicted otro (0.34)

## Limits

- Small, team-written data: the test split comes from the same writers, so real member SMS will score lower. Collect real (consented) messages and relabel.
- The Tseltal examples are unverified AI drafts and too few to measure; Tseltal free text will mostly fall below the threshold and go to the officer (safe, not smart).
- MASSIVE is Spain Spanish about smart-speaker commands; it only teaches what is off-topic.
- PRECIO, AYUDA and TECNICO (and in English PRICE, HELP, OFFICER) are also matched as exact keywords before the classifier runs.
