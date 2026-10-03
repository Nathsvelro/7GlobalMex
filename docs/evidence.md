# Evidence for Cafetal: the figures behind the problem

This file holds the numbers behind Cafetal's problem statement: who Noor is, what threatens her coffee, how far away advice is, what phone and network she has, what language support exists for Tseltal, and what price references exist. Every row gives the value, year, place, source and URL. Each row also says whether the figure is **measured** (census, survey, administrative record, field monitoring, observed market price) or **modelled/estimated** (forecast, model output), and how far we were able to check it.

**How we checked (read this first).** The build machine's network blocks almost every statistics site: INEGI, World Bank, FAO/FAOSTAT, GSMA, USDA FAS, ICO, IFT, SNIIM, HDX, OpenCelliD and Wikipedia all failed, through both the web-fetch tool and curl (tested 2026-10-03). Only GitHub raw files and the Hugging Face Hub (through its connector) could be read directly. So most rows below rest on **web-search result summaries**. We never opened those pages, so a teammate with normal internet should click the URL before quoting a number on stage. Where two sources disagree, we show both.

Verification codes used in the tables:

| Code | Meaning |
|---|---|
| **F** | Fetched: read directly on the primary source or its official metadata during this session |
| **L** | Read locally from a file in this repo |
| **S** | Search snippet only: seen in a search-engine summary; the page itself was not opened. **Unverified.** |
| **D** | Derived by us from cited figures (the arithmetic is shown) |

---

## 1. Phones and mobile internet among women (GSMA)

The GSMA surveys LMICs as a group. Recent reports give few Mexico-only numbers, and **no Chiapas or indigenous-women figure was found.**

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| Women are 7% less likely than men to own a mobile phone, and 13% less likely to own a smartphone | 2025 data (2026 report) | LMICs (aggregate) | GSMA Mobile Gender Gap Report 2026, https://www.gsma.com/gender-gap/ ; press release https://www.gsma.com/newsroom/press-release/810-million-women-still-not-using-mobile-internet-in-low-and-middle-income-countries-compared-to-595-million-men/ | Survey-based estimate (GSMA Consumer Survey, modelled up to LMIC level) | S |
| 64% of women vs 73% of men own a smartphone; women are 12% less likely to use mobile internet; 810 million women offline | 2025 | LMICs | Same as above | Survey-based estimate | S |
| Latin America is one of only two regions where the mobile internet gender gap narrowed | 2025 | Latin America | Same as above | Survey-based estimate | S |
| Gaps of 8% (mobile ownership) and 14% (smartphone ownership); women 14% less likely to use mobile internet; 61% of women own a smartphone | 2024 data (2025 report) | LMICs | GSMA Mobile Gender Gap Report 2025, https://www.gsma.com/gender-gap-2025/ ; press release https://www.gsma.com/newsroom/press-release/progress-closing-the-mobile-internet-gender-gap-stalls-in-lmics-gsma-mobile-gender-gap-report-2025/ | Survey-based estimate | S |
| An entry-level smartphone costs women about 24% of monthly income on average, double the cost for men | 2024 | LMICs | GSMA 2025, same URL | Modelled (affordability calculation) | S |
| **Urban women in Mexico are 2% less likely than urban men to own a phone; rural women are 26% less likely than rural men** | GSMA Consumer Survey 2021 | Mexico, urban vs rural | GSMA Connected Women blog "Rural women have so much to gain from mobile, but are being left behind", https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/programme/connected-women/rural-women-have-so-much-to-gain-from-mobile-but-are-being-left-behind/ | Survey (nationally representative) | S |
| LAC women's mobile ownership 86%, ownership gap 2%, mobile-internet gap -1% | Year not confirmed | Latin America and Caribbean | Search summary of the GSMA 2025 page; **low confidence** (the edition year was unclear) | Survey-based estimate | S |

## 2. Financial accounts by gender (World Bank Global Findex and Mexico's ENIF)

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| 49% of adults (15+) have an account | 2021 | Mexico | Global Findex 2021, as reported by Mexico Business News, https://mexicobusiness.news/finance/news/world-banks-global-findex-shows-2021-results ; microdata https://microdata.worldbank.org/index.php/catalog/5859 | Survey (n≈1,000) | S |
| 43% of women vs 56% of men have an account (13-point gap, double the developing-economy average) | 2021 | Mexico | Search summary attributing this to Findex 2021. The likely carrier is AFI (2024), https://www.afi-global.org/wp-content/uploads/2024/10/Mexico_The-Role-Regulators-Play-in-Closing-the-Financial-Inclusion-Gender-Gap.pdf ; **attribution not confirmed** | Survey | S |
| 29% of people in rural localities have an account, vs 66% of rural people worldwide | Findex 2021 (cited 2024) | Mexico, rural | World Bank / SHCP, *Expandiendo la inclusión financiera de las mujeres en México* (Sept 2024), https://documents1.worldbank.org/curated/en/099101024093034566/pdf/P502307-e38e08ad-8b5a-4741-89c4-43b003610f0a.pdf | Survey | S |
| 70% of adults have an account; women 66% vs men 74% | 2024 (Findex 2025) | Latin America and Caribbean (excluding high-income) | Global Findex 2025, https://www.worldbank.org/en/publication/globalfindex | Survey | S |
| Mexico is one of the 8 economies that together hold over half of the world's ~1.3 billion unbanked adults | 2024 | Mexico | Global Findex 2025, same URL | Survey | S |
| Mexico's Findex 2025 fieldwork ran 1 May to 31 Dec 2024. **We did not find a Mexico headline figure for account ownership by gender** | 2024 | Mexico | Microdata catalogue https://microdata.worldbank.org/index.php/catalog/7945 | Survey | S (metadata only) |
| Mobile money accounts, Mexico | — | Mexico | **Not found.** Mobile money in the African sense is marginal in Mexico; check Findex indicator "mobile money account" in the databank | — | — |
| 72.8% of women vs 80.9% of men have at least one formal financial product; formal savings 58.6% vs 68.0% | 2024 | Mexico (national survey) | INEGI/CNBV ENIF 2024, https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2025/enif/ENIF2024_CP.pdf ; SHCP bulletin https://www.gob.mx/cms/uploads/attachment/file/1034891/Bolet_n_IF_Mujeres_31102025.pdf | Survey | S |

## 3. Coffee production, area and yield in Mexico (FAOSTAT and others)

**FAOSTAT could not be reached** from the build machine (the fao.org web pages and the bulk download were both blocked). The rows below come from USDA, SIAP and secondary sources that quote FAOSTAT. The secondary figures for 2022 disagree (174,341 t vs 181,700 t), so **the official FAOSTAT series still has to be pulled** (see "How to close the gaps").

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| Green coffee production 174,341 t | 2022 | Mexico | HelgiLibrary (cites FAO), https://www.helgilibrary.com/charts/which-country-produces-the-most-coffee/ | Official statistic (FAO) via secondary source | S |
| Green coffee production fell from 440,000 t (1990) to 181,700 t (2022) | 1990, 2022 | Mexico | *Revista Bio Ciencias* (UAN), "Analysis of coffee exports in Mexico from 1981 to 2022", https://revistabiociencias.uan.edu.mx/index.php/BIOCIENCIAS/article/download/1957/2035 | Official statistics via a journal article | S |
| Average yield 368 kg/ha of green coffee (2,000 kg/ha cherry), vs a world average of 691 kg/ha | 2000–2014 average | Mexico vs world | *Rev. Mex. Cienc. Agríc.* (2016), "Productividad y rentabilidad potencial del café en el trópico mexicano", https://www.scielo.org.mx/scielo.php?script=sci_arttext&pid=S2007-09342016000802011 | Official statistics via a journal article | S |
| Production forecast 3.9 million 60-kg bags GBE (3.54 M arabica, 0.363 M robusta); 663,070 ha harvested; national yield 5.89 bags/ha | MY2025/26 | Mexico | USDA FAS GAIN, Mexico Coffee Annual MX2025-0023 (May 2025), https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Coffee+Annual_Mexico+City_Mexico_MX2025-0023.pdf | **Forecast** (USDA attaché estimate) | S |
| 5.89 bags/ha × 60 kg = **≈353 kg/ha green coffee** | MY2025/26 | Mexico | Derived from the row above | Forecast (derived) | D |
| Production forecast 4.135 M bags (3.575 M arabica, 0.56 M robusta), +1%; exports 3.41 M bags | MY2026/27 | Mexico | USDA FAS GAIN, Mexico Coffee Annual (May 2026), https://www.fas.usda.gov/data/gain/2026/05/mexico-coffee-annual | **Forecast** | S |
| 4.1 M bags; 0.69 M ha planted, 0.66 M ha harvested; yield 6.1 bags/ha (≈366 kg/ha) | MY2023/24 | Mexico | USDA FAS GAIN MX2023-0024, https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Coffee+Annual_Mexico+City_Mexico_MX2023-0024.pdf | Forecast (kg figure derived by us) | S / D |
| More than 1 million t of coffee cherry nationally; Chiapas harvested 392,000 t | 2024 | Mexico / Chiapas | SIAP data reported in the press: https://rotativo.com.mx/dia-del-cafe-mexico-produccion-chiapas-veracruz-puebla-2026 and https://www.cuartopoder.mx/chiapas/chiapas-primer-productor-nacional-de-cafe-cereza/488506 | Administrative statistic (SIAP), via press | S |
| Long-term trend: OWID's coffee-yield chart (FAOSTAT 1961–2024) | 1961–2024 | All countries | https://ourworldindata.org/grapher/coffee-yields | Official statistic | not opened |

## 4. Coffee leaf rust, Chiapas and who grows coffee

### 4a. Rust epidemic (2012 onward)

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| Rust epidemics hit Central America and Mexico in 2012–13. Production fell 16% in 2013 vs 2011–12 and a further 10% in 2013–14 vs 2012–13 (Colombia: −31% on average, 2008–11) | 2012–2014 | Central America (and Mexico) | Avelino et al. (2015), *Food Security* 7:303–321, doi:10.1007/s12571-015-0446-9, https://link.springer.com/article/10.1007/s12571-015-0446-9 | Measured production statistics | S (abstract text in snippet) |
| Loss of at least 2.3 M bags in 2012–13, worth ~US$548.2 M; ~374,000 jobs expected to be lost | 2012–13 | Central America | ICO, *Report on the outbreak of coffee leaf rust in Central America* (ED-2157, 2013), https://www.ico.org/documents/cy2012-13/ed-2157e-report-clr.pdf | **Estimate / projection** | S |
| More than 373,000 jobs lost, about 17% of the region's coffee workforce | 2013–14 | Central America | Oxfam Issue Briefing (Aug 2014), https://www-cdn.oxfam.org/s3fs-public/file_attachments/ib-coffee-rust-employment-collapse-central-america-140814-en.pdf | Estimate | S |
| More than 400,000 coffee workers lost their livelihoods (Honduras, El Salvador, Guatemala); yield losses above 50% in some regions | 2012– | Central America | "Epidemics and the future of coffee production", *PNAS* 118(27) e2023212118 (2021), https://www.pnas.org/doi/10.1073/pnas.2023212118 | Review of estimates | S |
| National production fell by more than half, from 4.3 to 2.2 million 60-kg bags | 2012 → 2016 | Mexico | USDA data cited in "La roya y el futuro del café en Chiapas", *Rev. Mex. Sociología* (2019), https://www.scielo.org.mx/scielo.php?script=sci_arttext&pid=S0188-25032019000200389 | Estimates (USDA), via journal | S |
| Production 2.2 M bags in MY2015/16, down from ~4.5 M five years earlier; rust named the main cause | 2015/16 | Mexico | USDA FAS GAIN Mexico Coffee Annual (May 2016), https://apps.fas.usda.gov/newgainapi/api/report/downloadreportbyfilename?filename=Coffee+Annual_Mexico+City_Mexico_5-13-2016.pdf | Estimate | S |
| **About 60% of Chiapas' coffee area affected by rust** (Veracruz about 70%) | c. 2015–16 | Chiapas, Veracruz | USDA FAS GAIN Mexico Coffee Annual (2015/2016 editions; see the 2016 URL above) | Estimate | S |
| Rust has been in Mexico since 1981 and is present in every coffee zone. Jan–Jun 2026: 10,015 ha sampled, average rust presence 9.3% of plants and 2.6% of leaves | 2026 | Mexico (8 states) | SENASICA 2026 campaign, as reported by Alerta Chiapas (2026-07-08), https://alertachiapas.com/2026/07/08/cafe-chiapas-senasica-roya-2026/ ; B15, https://b15.com.mx/noticias/nacional/invierten-32-2-mdp-para-proteger-cafetales-en-ocho-estados-y-fortalecer-produccion-nacional/ | **Measured** (phytosanitary monitoring), via press | S |

### 4b. Chiapas' weight and the producers

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| Chiapas produces 37% of Mexico's coffee; Chiapas, Veracruz, Puebla and Oaxaca together produce 91.4% | MY2025/26 | Chiapas / Mexico | USDA FAS GAIN MX2025-0023 (URL in §3) | Estimate | S |
| Chiapas is about 40–41% of national production | 2025–26 | Chiapas | SADER figures reported in the press: https://alertachiapas.com/2026/05/27/cafe-chiapas-record-exportacion-2025-productor-cadena-valor/ , https://portavozchiapas.com.mx/2026/01/25/importacion-de-robusta-hunde-el-precio-del-cafe-chiapaneco/ | Administrative, via press | S |
| **180,856 coffee producers on 253,764 ha in Chiapas**; 88 coffee municipalities; more than 180,000 families | Padrón Nacional Cafetalero (date not stated) | Chiapas | INCAFECH (Chiapas coffee institute), https://incafech.gob.mx/assets/media/documentos/Datos%20cafe.pdf ; repeated by Alerta Chiapas (2026-04-10), https://alertachiapas.com/2026/04/10/el-cafe-chiapaneco-en-crisis/ | **Administrative registry** | S |
| Average 253,764 ha ÷ 180,856 producers = **1.4 ha per producer** | — | Chiapas | Derived from the row above | Administrative (derived) | D |
| 510,544 producers on 675,258 ha nationally; "almost 90%" have less than 2 ha | PNC (date not stated) | Mexico | Search summary of the Padrón Nacional Cafetalero (carrier pages include https://www.agricultura.gob.mx/sites/default/files/sagarpa/document/2018/11/14/1533/14112018-2003-nal-cafe.pdf) | Administrative registry | S |
| About 545,000 coffee farmers on 712,000 ha; 22% are women; producers come from about 32 indigenous peoples | 2025 study | Mexico | ICO, *Mexico's Coffee Value Chain* (Mar 2025), https://ico.org/global-knowledge-hub/wp-content/uploads/2025/03/Mexico_Coffee-Value-Chain-Study.pdf | Study, compiled from registries | S |
| **66.5% (118,879) of the 178,879 coffee growers supported by Producción para el Bienestar are indigenous**; 37.4% are women; 87,979 of the beneficiaries are in Chiapas | 2020 (as of 30 Sept) | Mexico / Chiapas | SADER press release (2020-10-01), https://www.gob.mx/agricultura/prensa/apoya-produccion-para-el-bienestar-a-mas-de-178-mil-cafetaleros-66-5-son-indigenas?idiom=es | **Administrative record** | S |

## 5. Extension services: how far away is the technician?

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| "The nearest extension officer visits the sub-county twice a year at best"; extension is constrained by staff shortages, manual data and delayed alerts | 2026 | Noor (composite, drawn from World Bank work) | Hackathon concept note, Annex B (`docs/concept-note.pdf`) | Scenario (not a statistic) | L |
| **Only about 3% of agricultural production units received technical assistance** | 2007 census | Mexico | "Asistencia técnica en el sector agropecuario en México: análisis del VIII Censo Agropecuario y Forestal", *Rev. Mex. Cienc. Agríc.* (2012), https://www.scielo.org.mx/scielo.php?script=sci_arttext&pid=S2007-09342012000500008 | **Census** (measured) | S |
| About 5,000 extension workers cover barely 3% of rural production units; operating rules set 30 farmers per agent | 2016–17 | Mexico | "Caracterización de extensionistas rurales en México", *Rev. Mex. Cienc. Agríc.* (INIFAP, 2021), https://cienciasagricolas.inifap.gob.mx/index.php/agricolas/en/article/view/2893 | Evaluation survey (FAO-SADER M&E system) | S |
| 7,114 extension workers hired nationally; in practice an average of 136 farmers per agent in Michoacán | 2016–17 | Mexico / Michoacán | "Puntos críticos de la operación del programa nuevo extensionismo rural en Michoacán", *Terra Latinoamericana* (2022), https://www.scielo.org.mx/scielo.php?script=sci_arttext_plus&pid=S0187-57792022000100131 | Evaluation data | S |
| 30.8% of production units name lack of training and technical assistance as a problem (73.8% name high input costs) | 2019 | Mexico | INEGI, Encuesta Nacional Agropecuaria 2019, press release 481/20, https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2020/ENA/Ena2019.pdf | **Survey** (sample of 69,124 production units) | S |
| SENASICA 2026 coffee-pest campaign: MXN 32.2 M, **77 specialists** across 8 coffee states, target of 24,341 ha | 2026 | Mexico (incl. Chiapas) | Alerta Chiapas (2026-07-08) and B15 (URLs in §4a) | Administrative (budget/plan), via press | S |
| 77 specialists for ~510,544 registered producers is **about 1 specialist per 6,600 producers**; 24,341 ha is **about 3.7%** of the 663,070 ha harvested | 2026 | Mexico | Derived from the rows above and from §3–4. Assumes nearly all producers are in the 8 campaign states | Derived | D |
| Extension agents per farmer, Chiapas only | — | Chiapas | **Not found.** We tried INEGI Censo Agropecuario 2022 (it has a technical-assistance variable, but no headline % surfaced), ENA 2019 Chiapas mini-report (the % was not visible) and FAO evaluations | — | — |

## 6. Language: Tseltal (Bats'il k'op, ISO 639-3 `tzh`)

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| **589,144 Tseltal speakers aged 3+** | 2020 | Mexico | INEGI, Censo de Población y Vivienda 2020, tabulado https://www.inegi.org.mx/app/tabulados/interactivos/?pxq=LenguaIndigena_Lengua_07_f1908b4a-e833-4234-9a0f-3207d7207d15&idrt=132&opc=t | **Census** | S |
| 562,120 of them live in Chiapas, where Tseltal is the most-spoken indigenous language | 2020 | Chiapas | INEGI 2020 (same table), via search summary | Census | S |
| **28.4% of Tseltal speakers do not speak Spanish** (Tsotsil: 32.1%); Tseltal is one of 5 languages with a monolingual rate of 20% or more | 2020 | Mexico | Indigenous Mexico, "Ethnic Identity in the 2020 Mexican Census" (cites INEGI 2020), https://www.indigenousmexico.org/articles/ethnic-identity-in-the-2020-mexican-census | Census, via secondary source | S |
| 11.8% (865,972) of all indigenous-language speakers aged 3+ do not speak Spanish | 2020 | Mexico | INEGI 2020, via INMUJERES indicator card, http://estadistica-sig.inmujeres.gob.mx/formas/tarjetas/Poblacion_indigena.pdf | Census | S |
| 28.2% of Chiapas' population speaks an indigenous language | 2020 | Chiapas | INEGI 2020, via search summary | Census | S |
| Illiteracy among indigenous-language speakers aged 15+: 20.9%. Literacy is 73.7% for women and 84.8% for men; the snippet also showed an inconsistent 35.6% / 17.8% split | 2020 | Mexico | INMUJERES card (URL above), citing INEGI 2020 | Census | S (internally inconsistent; verify) |
| Literacy *in Tseltal* vs literacy in Spanish | — | — | **Not found.** The census measures literacy without naming the language | — | — |

## 7. Connectivity in rural Mexico and Chiapas

| Value | Year | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| Internet users (age 6+): urban 88.9%, **rural 75.2%**; national 86.1% (104.9 M) | 2025 | Mexico | INEGI/IFT ENDUTIH 2025 press release, https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/endutih/ENDUTIH_25.pdf | **Survey** | S |
| **53.9% of households in Chiapas have internet**, the lowest of any state (Oaxaca 64.0%, Veracruz 68.3%; national 78.3%) | 2025 | Chiapas | ENDUTIH 2025, as reported by La Silla Rota (2026-06-16), https://lasillarota.com/negocios/2026/6/16/uno-de-cada-cinco-hogares-en-mexico-aun-no-tiene-internet-falta-de-recursos-principal-causa-604122.html | Survey | S |
| 84.6% of people 6+ used a mobile phone; 97.3% of internet users connect by smartphone | 2025 | Mexico | ENDUTIH 2025 (URL above) | Survey | S |
| Internet users: urban 86.9%, rural 68.5% | 2024 | Mexico | ENDUTIH 2024 press release 57/25, https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2025/endutih/ENDUTIH_24.pdf | Survey | S |
| Chiapas 64.9% (snippets disagree on whether this is internet users or mobile-phone users); 50.7% of Chiapas households have internet | 2024 | Chiapas | ENDUTIH 2024 (URL above) | Survey | S (ambiguous) |
| 86% of the indigenous population has mobile coverage from at least one technology | 2024 | Mexico | IFT press release 73/2024, https://www.ift.org.mx/comunicacion-y-medios/comunicados-ift/es/en-mexico-86-de-la-poblacion-indigena-cuenta-con-cobertura-de-servicio-movil-en-al-menos-una | Operator-declared coverage maps × Census 2020 (**modelled coverage, not measured signal**) | S |
| **Tseltal people: 66% of the population covered at the first level, 58% at the second, 47% at the third; 9% of Tseltal localities have no coverage** | 2024 | Tseltal localities | IFT, *Diagnóstico de cobertura del servicio móvil en los pueblos indígenas 2024*, https://www.ift.org.mx/sites/default/files/contenidogeneral/usuarios-y-audiencias/diagnosticodecoberturamovilenlospueblosindigenas2024.pdf | Modelled coverage (operator maps) | S |
| Chiapas: 47% of the population covered by 2G, 57% by 3G, 58% by 4G; 24 municipalities without 4G; 16 municipalities with no coverage at all (≈208,000 people), including the highland municipalities Larráinzar, Aldama and Santiago del Pinar | Undated (likely c. 2019–20; the report says the state has 118 municipalities) | Chiapas | IFT, *Diagnóstico de banda ancha en el estado de Chiapas*, https://despliegueinfra.ift.org.mx/docs/CHIAPAS.pdf | Modelled coverage | S |
| OpenCelliD towers in the Chiapas highlands | — | Los Altos de Chiapas | **Not queried**: opencellid.org is blocked from the build machine. How to check is in "How to close the gaps" | Crowd-sourced cell locations | — |

## 8. AI language support for Tseltal

This is the best-verified section: we read the Hugging Face Hub, the FLORES GitHub repo and the Common Voice GitHub metadata directly.

| What | Finding | Date checked / source | Verified? |
|---|---|---|---|
| Meta MMS-TTS model `facebook/mms-tts-tzh` | **Does not exist** under that exact name (Hub returns "not found") | Hugging Face Hub, 2026-10-03 | F |
| Meta MMS-TTS for Tseltal | **Exists as two dialect checkpoints**: `facebook/mms-tts-tzh-dialect_tenejapa` (Tenejapa is a highland municipality near San Cristóbal) and `facebook/mms-tts-tzh-dialect_bachajon` (Bachajón, in Chilón). VITS, 36.3 M parameters, `model.safetensors` 145 MB, **licence CC-BY-NC-4.0 (non-commercial)**, Transformers ≥4.33 | https://hf.co/facebook/mms-tts-tzh-dialect_tenejapa , https://hf.co/facebook/mms-tts-tzh-dialect_bachajon | F |
| Meta MMS ASR for Tseltal | `facebook/mms-1b-all` (965 M params, CC-BY-NC-4.0) ships adapters `adapter.tzh-dialect_tenejapa` and `adapter.tzh-dialect_bachajon` (~8.8 MB each) plus vocab files. The Tenejapa vocab is 36 Latin characters, including `'` for the glottal stop | https://hf.co/facebook/mms-1b-all | F |
| MMS training data | "a new dataset based on readings of publicly available religious texts" (New Testament recordings), so the vocabulary is far from coffee and farming | Pratap et al. 2023, arXiv:2305.13516 (read via HF Papers) | F |
| Tsotsil (`tzo`) in MMS | Also present as dialect checkpoints (Chamula, Chenalhó) | HF Hub | F |
| FLORES-200 / NLLB-200 | **Tseltal not included.** The only indigenous American languages in the 204-language list are Central Aymara (`ayr_Latn`), Guarani (`grn_Latn`) and Ayacucho Quechua (`quy_Latn`). NLLB-200 is trained and evaluated on this list | https://raw.githubusercontent.com/facebookresearch/flores/main/flores200/README.md | F |
| FLORES+ (OLDI) | Not in the dataset's language tags as of its 2026-10-01 update | https://hf.co/datasets/openlanguagedata/flores_plus | F (metadata) |
| Mozilla Common Voice | **Tseltal absent** from Scripted Speech v27.0 (2026-09-11, 295 locales) and from Spontaneous Speech v5.0 (2026-09-11, 80 locales). Other languages of Mexico are present, e.g. Copainalá Zoque (`zoc`, Chiapas, 10.1 validated hours), Central Puebla Nahuatl (`ncx`, 10.7 h), Western Highland Purépecha (`pua`, 10.2 h) | Stats JSON at https://raw.githubusercontent.com/common-voice/cv-dataset/main/datasets/scripted-speech/cv-corpus-27.0-2026-09-11.json and `.../spontaneous-speech/sps-corpus-5.0-2026-09-11.json` | F |
| Google MADLAD-400 MT (`google/madlad400-3b-mt`) | Lists **`tzh` and `tzo`** among its languages. Apache-2.0, 2.94 B params (too big for the phone; a candidate for drafting translations at the hub, **output must be marked UNVERIFIED**). We did not measure its quality | https://hf.co/google/madlad400-3b-mt | F (metadata) |
| Community parallel data | `danvazquez20/tseltal`: 16,061 train + 1,785 test Spanish–Tseltal sentence pairs. Provenance and licence are not stated, so do not use without checking | https://hf.co/datasets/danvazquez20/tseltal | F |
| Google Translate | Not confirmed either way (its 2024 expansion added Yucatec Maya, Q'eqchi', Zapotec and Nahuatl; we found no mention of Tseltal) | Search | S |

## 9. Price references (for the non-AI "PRECIO" reply)

| Value | Date | Geography | Source + URL | Type | Verified? |
|---|---|---|---|---|---|
| **ICO composite indicator (I-CIP) averaged 287.29 US¢/lb** (range 279.38–301.97); July 2026: 287.26 | Aug 2026 | International | ICO Coffee Market Report Aug 2026, https://www.ico.org/documents/cy2025-26/cmr-0826-e.pdf ; daily I-CIP table https://icocoffee.org/documents/prices/I-CIP_08.2026.pdf | Market price (observed index) | S |
| Group indicators: Other Milds (the group that includes Mexican washed arabica) 361.31 ¢/lb; Colombian Milds 387.46; Brazilian Naturals 322.24; Robustas 180.63 | Aug 2026 | International | Same ICO report | Market price | S |
| 287.29 ¢/lb × 2.20462 = **≈6.33 USD/kg green**; Other Milds ≈7.97 USD/kg | Aug 2026 | International | Derived | Market price (derived) | D |
| ICE "C" (New York arabica futures, US¢/lb): InfoAserca republishes NY futures ("Café en New York (CSCE)") and daily international spot prices | Daily | International / Mexico | https://info.aserca.gob.mx/futuros/futuro.asp?de=cafe , https://info.aserca.gob.mx/fisicos/fisico.asp?de=cafe | Market price | S (pages exist; values not read) |
| AMECAFE | No current public producer-price series found (only a 2018 presentation) | Mexico | https://amecafe.org.mx/wp-content/uploads/2018/08/PRECIOS-DEL-CAFE.pdf | — | S |
| **Producers paid 45–48 MXN/kg, against ~70 MXN/kg cost of production**. Product form (pergamino or cereza) not stated in the snippet | Jan & Apr 2026 | Chiapas (Soconusco) | Portavoz Chiapas (2026-01-25), https://portavozchiapas.com.mx/2026/01/25/importacion-de-robusta-hunde-el-precio-del-cafe-chiapaneco/ ; Alerta Chiapas (2026-04-10), https://alertachiapas.com/2026/04/10/el-cafe-chiapaneco-en-crisis/ | Reported by press (not an official series) | S |
| Up to 7,000 MXN per quintal (2024); 2023–24 cycle average 2,500 MXN per quintal of pergamino. **Conflicting**; the quintal is given as 57.5 kg in one source and 46 kg in another | 2024 | Chiapas | Cuarto Poder, https://www.cuartopoder.mx/chiapas/precio-del-quintal-de-cafe-por-las-nubes/514714 ; other figures from search summaries | Reported | S (low confidence) |
| Producers who sell to a *coyote* at the farm, outside a co-op, rarely get more than 20% of the exchange value; the producer captures 5–10% of the consumer price | 2026 | Chiapas | Alerta Chiapas (2026-05-27), https://alertachiapas.com/2026/05/27/cafe-chiapas-record-exportacion-2025-productor-cadena-valor/ | Reported / opinion | S |
| SNIIM wholesale: white maize 8.00–10.00 MXN/kg; beans 16.50–46.00 MXN/kg (market not identified in the snippet); black beans, Estado de México, 17.00–46.47 MXN/kg (17 Sept 2026) | 9 and 17 Sept 2026 | Mexico wholesale markets | SNIIM, https://www.economia-sniim.gob.mx/nuevo/Precios_de_Granos.htm , http://www.economia-sniim.gob.mx/PreciosProdSelPorEstado.asp?edo=15 | Market price (observed) | S |
| WFP food prices for Mexico on HDX: the dataset exists, **but covers 2000-01-15 to 2022-06-15 only**. It comes from SNIIM via FAO GIEWS, licence CC BY-IGO, so it is too old for 2026 replies; use SNIIM directly | 2022 | Mexico | https://data.humdata.org/dataset/wfp-food-prices-for-mexico | Market price | S |

## 10. Comparison with the two examples in the concept note

The concept note (Annex B) points to **Wadhwani AI's cotton pest tool** (CottonAce) and to **World Bank-supported digital advisory in Côte d'Ivoire**. With CottonAce, a farmer photographs the pests caught in a pheromone trap; the app counts pink bollworms and gives a threshold-based spray advisory. Reported results are up to 26.5% higher profit margins and 38% lower pesticide spending in an independent review, and up to 22% higher income in 2020–21 in Ranebennur (Karnataka) and Wardha (Maharashtra). There was **no significant benefit in a 2021–22 multistate trial**, because unusually heavy rain kept pest pressure low (search snippets only: https://aiforcause.org/stories/cottonace-pest-management-india , https://www.fastcompany.com/90640843/google-is-helping-deploy-ai-to-prevent-pests-devastating-indian-crops ; dataset paper arXiv:2304.00763).

Cafetal copies that pattern: one photo, on-device vision, one action this week. The difference is that we cannot count insects; we classify leaf symptoms, and we hand uncertain cases to a person. That year with no benefit is also a reminder that advice must be humble when conditions change.

Côte d'Ivoire's **e-Agriculture Project** (P160418, US$70 M, 2018–2023) shows what makes advisory reach farmers in the first place: registries and connectivity. It reports more than 400,000 people with improved market access through its Agristore platform, broadband for more than 221,000 rural people and more than 43,000 new mobile money accounts. It also introduced a Producer Card to register cocoa farmers (snippets: https://www.worldbank.org/en/results/2025/03/04/afw-from-fields-to-markets-the-role-of-digital-platforms-in-west-africa-agricultural-success ; PAD https://documents1.worldbank.org/curated/en/900251527478271533/pdf/COTE-DIVOIRE-PADnew-05082018.pdf).

Cafetal takes the same lesson at co-op scale: the consented member registry and the SMS channel are what let a diagnosis become an extension visit.

**Lab-to-field gap (verified):** a model trained on 54,306 controlled-condition leaf images reached 99.35% on its held-out test set but **31.4%** on images taken in other conditions (Mohanty, Hughes & Salathé 2016, arXiv:1604.03169, read via HF Papers: **F**). This is why Cafetal reports its accuracy on our own field photos separately, and why it falls back to "No estoy seguro" when unsure.

---

## Gaps and caveats

1. **Most figures are snippet-level (S).** The build machine could not open INEGI, World Bank, FAO, GSMA, USDA, ICO, IFT or SNIIM pages. Before the video, a teammate should open the URL behind every number we quote on screen. The fully verified rows (F) are the AI-language facts (§8) and the Mohanty lab-to-field result.
2. **No FAOSTAT pull.** The secondary sources disagree for 2022 (174,341 t vs 181,700 t green coffee). USDA figures are attaché **forecasts/estimates** in marketing years (Oct–Sep), not FAOSTAT calendar years, so do not mix the two series in one chart.
3. **Measured vs modelled.** Census, ENDUTIH, ENIF, ENA, the SENASICA sampling and registry counts are measured. GSMA LMIC aggregates are survey-based models. ILO agricultural employment (WDI says 11.96% of employment in 2023, *modelled ILO estimate*; S) is modelled. IFT coverage is **operator-declared maps crossed with census localities, not measured signal**. USDA and ICO crop and job-loss numbers are estimates or projections.
4. **Geography mismatch.** Almost nothing is specific to the Chiapas highlands (Los Altos). Chiapas-level data hides big differences between the Soconusco lowlands (where most of the press price reports come from) and the highlands.
5. **Gender data is thin.** There is no Mexico or Chiapas figure for women's smartphone ownership in the 2025/2026 GSMA reports. The rural-women phone gap (26%) dates from the 2021 survey.
6. **Prices are not farm-gate in Noor's valley.** Press-reported Chiapas prices conflict, and the product form (pergamino or cereza) and the size of a quintal are often unstated. Cafetal's PRECIO reply must name the unit (MXN/kg pergamino), the source and the date, and say "precio de referencia".
7. **Tseltal is dialect-diverse.** MMS covers only the Tenejapa and Bachajón varieties, trained on Bible readings and released under a non-commercial licence. Its quality on farming vocabulary is unknown. Any machine output stays **UNVERIFIED / SIN VERIFICAR** until a native speaker reviews it.
8. **Things we looked for and did not find:** Findex 2025 headline numbers for Mexico by gender; mobile-money ownership in Mexico; extension agents per farmer in Chiapas; literacy *in* Tseltal; OpenCelliD tower counts for Los Altos.
9. **Weak or contested rows** are marked "low confidence" or "ambiguous" in the tables. Do not quote them in the pitch.

## How to close the gaps (for a teammate with normal internet)

- **FAOSTAT:** open https://www.fao.org/faostat/en/#data/QCL and choose Area "Mexico" (FAO code 138), Item "Coffee, green" (code 656), Elements "Area harvested", "Production" and "Yield", years 2010, 2012, 2015, 2020 and the latest. Or use the bulk file https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip . Record the release date shown on the page.
- **Findex:** in https://databank.worldbank.org (Global Findex), look up Mexico, 2021 and 2024, for "Account (% age 15+)" with the female, male and rural splits, and "Mobile money account".
- **OpenCelliD:** register at https://opencellid.org, get an API token, then download the Mexico country export (MCC **334**) from https://opencellid.org/downloads.php. The API call `cell/getInArea` is limited to 4 km² per request, so work on the country file instead. Filter it to the Los Altos box (roughly lat 16.5–17.2 N, lon −92.9 to −92.2 W; San Cristóbal ≈ 16.74 N, −92.64 W; Tenejapa ≈ 16.81 N, −92.51 W) and count cells by `radio` (GSM / UMTS / LTE). OpenCelliD is crowd-sourced and records **where towers are, not where coverage is**: an empty area may only mean nobody has mapped it. For operator-declared coverage, use the IFT diagnostic (§7) and each operator's coverage map.
- **Prices:** for coffee, use the ICO monthly report and InfoAserca daily pages; for maize and beans, use SNIIM (choose one named market, e.g. Central de Abasto de Tuxtla Gutiérrez, and keep the same market every week).

---

## Problem statement (template from PROJECT_BRIEF.md §3, filled with the strongest figures)

**Current statement** (used in README.md and VIDEO_SCRIPT.md):

> Because of Cafetal, **Noor** will **get a sick-looking coffee leaf onto her extension officer's visit list, with spoken advice in Tseltal while she waits,** by **the same weekend she notices it**, which she would otherwise **do late: whenever the officer next comes by, twice a year at best**; we know because **that is the gap the challenge brief describes for her (concept note, Annex B, 2026).**

**Why it was narrowed:** the first draft below promised that Noor would *know which leaf problem* she has. On field photos the shipped model almost always says "No estoy seguro" (0 of 53 held-out iNaturalist rust photos correct, `reports/field_eval.md`), so the build cannot back that promise. A "not sure" answer still puts the farm on the officer's list. The evidence bullets below still apply; use only the code-L line until the code-S sources are opened.

**First draft (kept for its evidence; do not use the sentence):**

> Because of Cafetal, **Noor** will **know whether leaf rust or another leaf problem is hurting her coffee, and get onto the extension officer's visit list,** by **the same weekend she notices it**, which she would otherwise only discover **at harvest, after the yield is already lost**. We know because:
> - **the extension officer reaches her area twice a year at best** (concept note, Annex B, 2026). In Mexico, only **about 3% of farms receive technical assistance** (INEGI Censo Agropecuario 2007, measured; analysed in *Rev. Mex. Cienc. Agríc.* 2012). In 2026, the federal coffee-pest campaign fields **77 specialists across eight coffee states** (SENASICA, July 2026);
> - **leaf rust cut Mexico's coffee harvest by about half, from 4.3 to 2.2 million bags between 2012 and 2016, and hit about 60% of Chiapas' coffee area** (USDA FAS estimates, cited in *Rev. Mex. Sociología* 2019; USDA GAIN 2016). Rust is still present in every coffee zone (SENASICA, 2026);
> - **Chiapas grows about 37–40% of Mexico's coffee with 180,856 producers averaging 1.4 ha** (USDA GAIN 2025; Padrón Nacional Cafetalero via INCAFECH). Two-thirds of supported coffee growers are indigenous (SADER, 2020), and 28% of Tseltal speakers do not speak Spanish (INEGI Census 2020, via secondary source). Hence voice in Tseltal, and SMS for a basic phone.

*Reserve figures, if the slide needs a connectivity line:* in 2025, 53.9% of Chiapas households had internet, the lowest of any state (ENDUTIH 2025). In 2021, rural Mexican women were 26% less likely than rural men to own a phone (GSMA). We still owe the **FAOSTAT yield trend**: the brief asks for it, but we could not fetch it; until then, use USDA's 5.89 bags/ha (≈353 kg/ha) forecast for 2025/26 and label it as a USDA forecast.
