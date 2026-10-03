# Demo sample images

Held-out TEST images (never trained on), written by `model/demo_samples.py`. Upload them in the app to show each result. They are Kenyan close-up crops (128x128) like the training data - **not** Chiapas field photos. For 'not coffee' (expected: DUDA) photograph any object or another plant.

| file | true label | what the app should say | source (dataset path) |
|---|---|---|---|
| sano_1.jpg | sano | sano | arabica/arabica_coffee_leaf_disease_classification/Healthy/10(6717).jpg |
| sano_2.jpg | sano | sano | arabica/arabica_coffee_leaf_disease_classification/Healthy/2(610).jpg |
| roya_1.jpg | roya | roya | arabica/arabica_coffee_leaf_disease_classification/Leaf_rust/2(7).jpg |
| blurred_roya.jpg | roya (blurred r=4) | DUDA | arabica/arabica_coffee_leaf_disease_classification/Leaf_rust/2(7).jpg |
| roya_2.jpg | roya | roya | arabica/arabica_coffee_leaf_disease_classification/Leaf_rust/2(912).jpg |
| minador_1.jpg | minador | minador | arabica/arabica_coffee_leaf_disease_classification/Miner/1(4768).jpg |
| minador_2.jpg | minador | minador | arabica/arabica_coffee_leaf_disease_classification/Miner/1(4639).jpg |
| phoma_1.jpg | phoma | phoma | arabica/arabica_coffee_leaf_disease_classification/Phoma/6(2546).jpg |
| phoma_2.jpg | phoma | phoma | arabica/arabica_coffee_leaf_disease_classification/Phoma/6(931).jpg |
| cercospora_1.jpg | cercospora | cercospora | arabica/arabica_coffee_leaf_disease_classification/Cerscospora/8(808).jpg |
| cercospora_2.jpg | cercospora | cercospora | arabica/arabica_coffee_leaf_disease_classification/Cerscospora/7(277).jpg |

Attribution: coffee images from JMuBEN/JMuBEN2, Jepkoech et al. 2021, *Data in Brief* 36:107142 (CC BY 4.0). `blurred_roya.jpg` is a Gaussian-blurred copy (radius 4) of `roya_1.jpg`.
