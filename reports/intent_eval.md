# Intent classifier evaluation (free-text SMS)

Date: 2026-10-03. Produced by `hub/train_intent.py`; raw numbers in `reports/intent_eval.json`.

## Data

- `data/intent/examples.csv`: 545 messages. Per intent: precio 54, reporte 52, ayuda 49, hablar_con_tecnico 48, otro 342.
- Sources: MASSIVE 300, ai-draft-unverified 16, team 229. `team` = written by the team (Mexican rural SMS style, typos, no accents); `ai-draft-unverified` = Tseltal drafts nobody has checked; `MASSIVE` = Amazon MASSIVE 1.1 es-ES utterances (CC BY 4.0) used only as 'otro' (off-topic) examples, after removing intents/words that overlap ours.
- Split: stratified 80/20, random_state=42 -> 436 train / 109 test.

## Model

- TF-IDF char_wb (2, 4), sublinear_tf, l2 + LogisticRegression multinomial, class_weight=balanced, C=10.0 (5-fold CV macro-F1 by C: {'1.0': 0.854, '3.0': 0.854, '10.0': 0.8565, '30.0': 0.8523}). 4399 n-gram features.
- Confidence threshold **0.65** (lowest t with >= 95% precision on auto-answered messages, out-of-fold predictions on the 80% split). Below it the hub replies `sms_pasar_tecnico` and forwards the message to the officer.
- Exported to `hub/intent_model.json`; `hub/intent.py` runs it in pure Python (a test checks it matches scikit-learn on the test split).

## Results on the held-out 20% split

| | n | accuracy | macro-F1 |
|---|---|---|---|
| argmax (no threshold) | 109 | 0.917 | 0.897 |
| with threshold (as deployed) | 109 | 0.917 | 0.874 |
| with threshold, Spanish only | 105 | 0.924 | 0.880 |
| with threshold, excluding MASSIVE | 51 | 0.824 | 0.820 |

Auto-answered share: 31.2% of test messages; precision of those answers: 97.1%. On-topic test messages (true intent is not 'otro') answered with the right card automatically: 80.5%; the rest go to the officer.

Confusion matrix (with threshold; rows = true, columns = predicted):

| true \ pred | precio | reporte | ayuda | hablar_con_tecnico | otro |
|---|---|---|---|---|---|
| precio | 9 | 0 | 0 | 0 | 2 |
| reporte | 0 | 10 | 0 | 0 | 0 |
| ayuda | 0 | 0 | 4 | 0 | 6 |
| hablar_con_tecnico | 0 | 0 | 0 | 10 | 0 |
| otro | 0 | 0 | 1 | 0 | 67 |

Threshold sweep (out-of-fold, 80% split):

| threshold | auto precision | auto share | macro-F1 (routed) |
|---|---|---|---|
| 0.30 | 0.890 | 0.335 | 0.857 |
| 0.35 | 0.890 | 0.335 | 0.857 |
| 0.40 | 0.894 | 0.326 | 0.848 |
| 0.45 | 0.899 | 0.317 | 0.838 |
| 0.50 | 0.937 | 0.291 | 0.832 |
| 0.55 | 0.950 | 0.273 | 0.814 |
| 0.60 | 0.947 | 0.262 | 0.792 |
| 0.65 | 0.963 | 0.245 | 0.779 |
| 0.70 | 0.980 | 0.234 | 0.774 |
| 0.75 | 0.979 | 0.223 | 0.754 |
| 0.80 | 0.989 | 0.202 | 0.721 |
| 0.85 | 0.988 | 0.183 | 0.685 |
| 0.90 | 1.000 | 0.149 | 0.618 |

Probe messages (not in the data):

| message | predicted | conf | routed |
|---|---|---|---|
| q precio tiene el cafe | precio | 0.96 | precio |
| cuanto pagan x kilo | precio | 0.99 | precio |
| mi cafe tiene manchas amarillas | reporte | 0.98 | reporte |
| kiero hablar con el ingeniero | hablar_con_tecnico | 0.99 | hablar_con_tecnico |
| como funciona | ayuda | 0.97 | ayuda |
| hola buenas tardes | otro | 0.95 | otro |
| pon musica | otro | 0.91 | otro |
| a como esta el pergamino en la cooperativa | precio | 0.48 | otro |
| las hojas tienen polvo amarillo | reporte | 0.96 | reporte |
| que venga el ingeniero a mi parcela | hablar_con_tecnico | 0.96 | hablar_con_tecnico |

Test errors before threshold (9):

- "que tal como estas" — true otro, predicted ayuda (0.74)
- "que significa CAF1" — true ayuda, predicted otro (0.73)
- "menu" — true ayuda, predicted otro (0.44)
- "bit'il ayat" — true otro, predicted ayuda (0.43)
- "pasame tu numero" — true otro, predicted ayuda (0.44)
- "hola que puedo hacer aqui" — true ayuda, predicted otro (0.63)
- "cuanto esta la bolsa de nueva york" — true precio, predicted otro (0.66)
- "info" — true ayuda, predicted otro (0.34)
- "como es posible" — true otro, predicted ayuda (0.51)

## Limits

- Small, team-written data: the test split comes from the same writers, so real member SMS will score lower. Collect real (consented) messages and relabel.
- The Tseltal examples are unverified AI drafts and too few to measure; Tseltal free text will mostly fall below the threshold and go to the officer (safe, not smart).
- MASSIVE is Spain Spanish about smart-speaker commands; it only teaches what is off-topic.
- PRECIO, AYUDA and TECNICO are also matched as exact keywords before the classifier runs.
