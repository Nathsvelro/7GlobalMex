# Intent classifier evaluation (free-text SMS)

Date: 2026-10-04. Produced by `hub/train_intent.py`; raw numbers in `reports/intent_eval.json`.

## Data

- `data/intent/examples.csv`: 872 messages. Per intent: price 101, report 108, help 99, talk_to_officer 99, other 465. Per language: en 427, kik 17, sw 428.
- Sources: MASSIVE 400, ai-draft-unverified 17, team 455. `team` = written by the build team (which includes AI agents) in Kenyan SMS style: English and Kiswahili with sheng, typos, no diacritics; none of it was checked by a native Kiswahili speaker or taken from real members. `ai-draft-unverified` = a few Gikuyu drafts nobody has checked; `MASSIVE` = Amazon MASSIVE 1.1 en-US and sw-KE utterances (CC BY 4.0) used only as 'other' (off-topic) examples, after removing intents/words that overlap ours.
- Split: stratified 80/20, random_state=42 -> 697 train / 175 test.

## Model

- TF-IDF char_wb (2, 4), sublinear_tf, l2 + LogisticRegression multinomial, class_weight=balanced, C=30.0 (5-fold CV macro-F1 by C: {'1.0': 0.8825, '3.0': 0.8909, '10.0': 0.8935, '30.0': 0.8964}). 6490 n-gram features.
- Confidence threshold **0.55** (lowest t with >= 95% precision on auto-answered messages, out-of-fold predictions on the 80% split). Below it the hub replies `sms_pasar_tecnico` and forwards the message to the officer.
- Exported to `hub/intent_model.json`; `hub/intent.py` runs it in pure Python (a test checks it matches scikit-learn on the test split).

## Results on the held-out 20% split

| | n | accuracy | macro-F1 |
|---|---|---|---|
| argmax (no threshold) | 175 | 0.971 | 0.970 |
| with threshold (as deployed) | 175 | 0.954 | 0.950 |
| with threshold, English only | 82 | 1.000 | 1.000 |
| with threshold, Kiswahili only | 89 | 0.921 | 0.917 |
| with threshold, Gikuyu only (too few to mean anything) | 4 | 0.750 | 0.778 |
| with threshold, excluding MASSIVE | 98 | 0.918 | 0.918 |

Auto-answered share: 42.3% of test messages; precision of those answers: 100.0%. On-topic test messages (true intent is not 'other') answered with the right card automatically: 90.2%; the rest go to the officer.

Confusion matrix (with threshold; rows = true, columns = predicted):

| true \ pred | price | report | help | talk_to_officer | other |
|---|---|---|---|---|---|
| price | 19 | 0 | 0 | 0 | 1 |
| report | 0 | 21 | 0 | 0 | 1 |
| help | 0 | 0 | 17 | 0 | 3 |
| talk_to_officer | 0 | 0 | 0 | 17 | 3 |
| other | 0 | 0 | 0 | 0 | 93 |

Threshold sweep (out-of-fold, 80% split):

| threshold | auto precision | auto share | macro-F1 (routed) |
|---|---|---|---|
| 0.30 | 0.919 | 0.441 | 0.896 |
| 0.35 | 0.919 | 0.441 | 0.896 |
| 0.40 | 0.921 | 0.438 | 0.896 |
| 0.45 | 0.927 | 0.433 | 0.897 |
| 0.50 | 0.939 | 0.423 | 0.897 |
| 0.55 | 0.957 | 0.400 | 0.888 |
| 0.60 | 0.963 | 0.385 | 0.876 |
| 0.65 | 0.973 | 0.369 | 0.864 |
| 0.70 | 0.976 | 0.360 | 0.856 |
| 0.75 | 0.975 | 0.342 | 0.832 |
| 0.80 | 0.986 | 0.313 | 0.801 |
| 0.85 | 0.990 | 0.287 | 0.764 |
| 0.90 | 0.989 | 0.253 | 0.704 |

Probe messages (not in the data):

| message | predicted | conf | routed |
|---|---|---|---|
| how much are you paying for a kilo of cherry | price | 0.99 | price |
| bei ya kahawa ni ngapi | price | 1.00 | price |
| my coffee leaves have orange powder | report | 1.00 | report |
| majani ya kahawa yana unga wa rangi ya machungwa | report | 1.00 | report |
| I want to talk to the extension officer | talk_to_officer | 1.00 | talk_to_officer |
| asdf qwerty | other | 0.87 | other |
| wat r u paying for maize | price | 0.78 | price |
| kahawa yangu ina madoa ya kahawia | report | 0.99 | report |
| nataka kuongea na afisa ugani | talk_to_officer | 1.00 | talk_to_officer |
| how do i send my report code | help | 0.79 | help |
| msaada tafadhali nifanye aje | help | 0.99 | help |
| good afternoon | other | 0.90 | other |
| habari za asubuhi | other | 0.96 | other |
| play some music | other | 0.96 | other |
| weka muziki | other | 0.96 | other |

Test errors before threshold (5):

- "show johns office number" — true other, predicted help (0.34)
- "kahua yakwa niirwaru" — true report, predicted other (0.47)
- "nabadilisha lugha aje" — true help, predicted other (0.92)
- "tafadhali tuma mtaalamu wa kilimo" — true talk_to_officer, predicted other (0.66)
- "orodha ya huduma" — true help, predicted other (0.64)

## Limits

- Small, team-written data: the test split comes from the same writers, so real member SMS will score lower. Collect real (consented) messages and relabel.
- The Kiswahili and sheng examples were not checked by a native speaker; real messages will use words and spellings we did not think of.
- The Gikuyu examples are unverified AI drafts and too few to measure; Gikuyu free text will mostly fall below the threshold and go to the officer (safe, not smart).
- MASSIVE is US English and Kenyan Kiswahili smart-speaker commands; it only teaches what is off-topic.
- PRICE/PRICES, HELP and OFFICER (English) and BEI, MSAADA and AFISA (Kiswahili) are also matched as exact keywords before the classifier runs.
