# Demo sample images

Upload them in the app to show each result. Everything here is **held out**: never used to train the shipped model (`app/model/labels.json`). Generated from `samples.json` by `model/demo_samples.py --readme`; every answer below is checked in the real app logic (Chromium, `app/infer.js`: blur check, threshold, `otro` -> fail-safe) by `node model/check_demo_samples.mjs`, which reads the SMS codes from `app/sms.js` at run time (result: `reports/model_demo_samples_check.json`). "What the app should say" = the observation SMS code + the English card the farmer sees (`content/cards.json`); UNSR / OTHR are the fail-safe.

## Lab crops (in the repo)

Kenyan JMuBEN close-up crops (about 128x128 px) from the model's held-out TEST split, like the training data. JMuBEN was photographed in the Mutira coffee plantation, Kirinyaga County - the county of our users - but these are lab-like close-ups from one plantation and one camera, **not** photos taken with the app on a farm. For 'not coffee' (expected: the fail-safe, code OTHR) photograph an object (a cup, a bucket), **not** another plant's leaf: the shipped model answers some apple, cherry and tomato leaves as a disease (`reports/model_eval.md`, section (a)).

| file | true label | what the app should say | source (dataset path) | licence |
|---|---|---|---|---|
| sano_1.jpg | sano | HLTH - Healthy | JMuBEN arabica_coffee_leaf_disease_classification/Healthy/10(6717).jpg | CC BY 4.0 |
| sano_2.jpg | sano | HLTH - Healthy | JMuBEN arabica_coffee_leaf_disease_classification/Healthy/2(610).jpg | CC BY 4.0 |
| roya_1.jpg | roya | RUST - Leaf rust | JMuBEN arabica_coffee_leaf_disease_classification/Leaf_rust/2(7).jpg | CC BY 4.0 |
| blurred_roya.jpg | roya (Gaussian blur radius 4 of roya_1.jpg) | UNSR - I'm not sure — show the leaf to the extension officer. | JMuBEN arabica_coffee_leaf_disease_classification/Leaf_rust/2(7).jpg | CC BY 4.0 |
| roya_2.jpg | roya | RUST - Leaf rust | JMuBEN arabica_coffee_leaf_disease_classification/Leaf_rust/2(912).jpg | CC BY 4.0 |
| minador_1.jpg | minador | MINR - Leaf miner | JMuBEN arabica_coffee_leaf_disease_classification/Miner/1(4768).jpg | CC BY 4.0 |
| minador_2.jpg | minador | MINR - Leaf miner | JMuBEN arabica_coffee_leaf_disease_classification/Miner/1(4639).jpg | CC BY 4.0 |
| phoma_1.jpg | phoma | PHOM - Phoma leaf spot | JMuBEN arabica_coffee_leaf_disease_classification/Phoma/6(2546).jpg | CC BY 4.0 |
| phoma_2.jpg | phoma | PHOM - Phoma leaf spot | JMuBEN arabica_coffee_leaf_disease_classification/Phoma/6(931).jpg | CC BY 4.0 |
| cercospora_1.jpg | cercospora | CERC - Brown eye spot | JMuBEN arabica_coffee_leaf_disease_classification/Cerscospora/8(808).jpg | CC BY 4.0 |
| cercospora_2.jpg | cercospora | CERC - Brown eye spot | JMuBEN arabica_coffee_leaf_disease_classification/Cerscospora/7(277).jpg | CC BY 4.0 |

Attribution: JMuBEN/JMuBEN2, Jepkoech et al. 2021, *Data in Brief* 36:107142 (CC BY 4.0). `blurred_roya.jpg` is a Gaussian-blurred copy (radius 4) of `roya_1.jpg`.

## Field photos (iNaturalist, held-out field test)

Real photos from the held-out field test (`reports/field_inat_attribution.csv`, split `field_test`: the observers were never used for training), all from Latin America: our iNaturalist set has no rust photo from East Africa (0 of 219; `reports/field_eval.md`, "East Africa and Kenya"), so there is no Kenyan field demo photo yet. Labels are the iNaturalist community identification, not an agronomist's diagnosis. Only CC BY photos may be kept in this repository; the CC BY-NC ones are downloaded on the demo machine with:

```bash
python3 model/demo_samples.py --field   # plain python3, no venv; needs internet once
```

| file | in repo? | true label | what the app should say | licence | attribution | link | why this photo |
|---|---|---|---|---|---|---|---|
| field_whole_tree.jpg | yes | roya (iNaturalist identification: Hemileia vastatrix) | OTHR - I'm not sure — show the leaf to the extension officer. | CC BY (iNaturalist licence code CC-BY) | (c) Carl Ramirez (carl_ramirez), CC BY, via iNaturalist | https://www.inaturalist.org/photos/516559609 | the only CC BY / CC0 rust photos in the held-out field test are 4 whole-tree shots by one observer (screened 'no': symptom not visible); v2 at 0.90 answers none of them. This one shows the honest limit: a real field photo of a sick tree, taken from too far, gets the fail-safe 'I'm not sure - show the leaf to the extension officer'. Unchanged file. |
| field/roya_field_1.jpg | no - downloaded by `--field` (gitignored) | roya (iNaturalist identification: Hemileia vastatrix) | RUST - Leaf rust | CC BY-NC (iNaturalist licence code CC-BY-NC) | (c) jpgalvan, CC BY-NC, via iNaturalist | https://www.inaturalist.org/photos/31642233 | held-out field test (observer never used for training), research grade, Latin America, symptom visible, v2 at 0.90 -> roya (p_roya 0.996 in the app in Chromium; 0.996 in the field-evaluation pipeline). Non-commercial licence: downloaded for the demo, not redistributed in this repository. |
| field/roya_field_2.jpg | no - downloaded by `--field` (gitignored) | roya (iNaturalist identification: Hemileia vastatrix) | RUST - Leaf rust | CC BY-NC (iNaturalist licence code CC-BY-NC) | (c) Flavio Genis (flavio_genis_), CC BY-NC, via iNaturalist | https://www.inaturalist.org/photos/474590285 | held-out field test (observer never used for training), research grade, Latin America, symptom visible, v2 at 0.90 -> roya (p_roya 0.986 in the app in Chromium; 0.984 in the field-evaluation pipeline). Non-commercial licence: downloaded for the demo, not redistributed in this repository. |

Location (rounded to 0.1 degree), date and quality grade of each field photo are in `samples.json`. The two rust photos were picked because the app answers them correctly: they show what it can do on a clear field photo, they are not a measure of accuracy (that is `reports/field_eval.md`).
