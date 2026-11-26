# Trilha R5-M3: BRE completo em QRS largo (PTB-XL 180) e falsos achados de HVE/HCM

Base 03abab1, branch `wt/r5-m3`. Sem push/deploy. Medido só no PTB-XL DEV (folds 1-8, `--set large`, N = 9183). O CODE-test não foi tocado.

## Reprodução (registro 180, rótulo: CLBBB 100 + ritmo sinusal, 81 anos)

Largura do QRS: global 250 ms, mediana das derivações 216 ms (208-224 por derivação), largura mista dos critérios de condução 224 ms.
Isso explica 216 vs 250: cada achado citava uma fonte diferente.

Achados ANTES: ritmo sinusal, `ecg.implausible_measurement` (QRS 216 ms > 200 sem bloqueio), `ecg.lae`, `ecg.lvh` (Sokolow 45, Cornell 60, Romhilt-Estes 5),
`ecg.hcm_pattern` (alterado), `ecg.st_elevation_inferior/anterior` (limítrofes), `ecg.t_inversion_lateral`, `ecg.st_not_assessable` (QRS 250 ms). Sem `ecg.lbbb`.

## Causas-raiz

1. `_classify_bbb` devolvia `None` só por `rb_inc_lbbb_excl`: V1 com ondas [Q -2,8 mV, R 0,77 mV] (a subida terminal é o ST elevado absorvido pelo delineador) tinha R terminal 27% do S e vetava o BRE como "rSr'".
   rSr' exige um r inicial (AHA/ACCF/HRS 2009 Parte III, rsr'/rsR'/rSR' em V1), e esse V1 começa por Q. O veto agora exige onda inicial R/R'.
2. Ordem das regras: a nota "medida de PR/QRS implausível" nasce na seção de PR, antes de `c["bbb"]` existir. Mesmo com BRE classificado depois, a nota saía.
   O teto de 200 ms vale só para QRS SEM morfologia de bloqueio/marca-passo (cartão `misc.medida_implausivel`); agora a seção de PR usa a classificação provisória.
   O limiar de 200 ms foi mantido (única base do repositório); nenhum limiar novo.
3. HVE por voltagem e padrão HCM não tinham supressão com BRE (o HCM já excluía BRE/BRD, a HVE não). Com BRE completo, `ecg.lvh`, `ecg.lvh_voltage`, strain/`secondary_repolarization_lvh` e `ecg.hcm_pattern`
   não são emitidos; vira `ecg.lvh_not_assessable_lbbb` (borderline, "HVE por voltagem não avaliável na presença de BRE") com as medidas. Índices continuam calculados. O ST segue a nota Sgarbossa/Smith existente.
4. Largura única: `_conduction_width` (mediana por derivação + 0,25 x (global - mediana)) alimenta os critérios de condução e o texto da nota `ecg.st_not_assessable` (o limiar >= 120 ms continua na largura global, decisão anterior do médico).
   A medida em si (`features.py`, viés de +25 ms da global) NÃO foi alterada.
5. QTc: já existe ajuste ao QRS na regra de QT longo (QT - (QRS - 100) quando QRS >= 120). Os QTc exibidos (global, Bazett etc.) não são ajustados; o parágrafo único agora diz
   "O QTc acima não tem ajuste ao QRS largo, o que tende a superestimá-lo." quando QRS >= 120 ms. Nenhuma regra nova de QT.

## Registro 180 DEPOIS

`ecg.lbbb` (QRS 224 ms; V1 predominantemente negativo -28 mm, R sem q em D1/V5/V6), `ecg.lvh_not_assessable_lbbb`, `ecg.secondary_repolarization` (esperada com BRE), `ecg.st_not_assessable` (BRE, Sgarbossa/Smith manual),
`ecg.lae`, `ecg.left_axis_mild`, `ecg.pr_gt200_unconfirmed` (PR 218 ms, nota existente que antes era escondida pela nota implausível), ritmo sinusal.
Sumiram: implausível, `ecg.lvh`, `ecg.hcm_pattern`, supra de ST limítrofe, inversão de T lateral.

## Aceite (PTB-XL dev, folds 1-8, mesmo comando do bench: `--source ptbxl --set large --split dev --workers 3 --tag R5M3`, antes = código base, depois = código desta branch)

IC95% por bootstrap multinomial (`bench.report.bootstrap_binary_ci`). Posit. = N gold+ (regra do bench: probabilidade >= 50 ou 0).

| achado vs gold | N gold+ | TP | FP | sens % (IC95%) | espec % (IC95%) | VPP % (IC95%) |
|---|---|---|---|---|---|---|
| ANTES BRE completo (`ecg.lbbb`) vs CLBBB | 428 | 336 | 350 | 78,5 [74,6-82,5] | 96,0 [95,6-96,4] | 49,0 [45,3-52,9] |
| DEPOIS BRE completo | 428 | 368 | 353 | 86,0 [82,6-89,2] | 96,0 [95,6-96,4] | 51,0 [47,5-54,8] |
| ANTES BRE qualquer vs CLBBB+ILBBB | 489 | 386 | 432 | 78,9 [75,2-82,4] | 95,0 [94,6-95,5] | 47,2 [43,7-50,6] |
| DEPOIS BRE qualquer | 489 | 418 | 435 | 85,5 [82,3-88,5] | 95,0 [94,5-95,4] | 49,0 [45,6-52,4] |
| ANTES HVE (`ecg.lvh`) vs LVH | 1156 | 864 | 1094 | 74,7 [72,2-77,3] | 86,4 [85,6-87,1] | 44,1 [42,0-46,3] |
| DEPOIS HVE | 1156 | 751 | 719 | 65,0 [62,2-67,7] | 91,0 [90,4-91,7] | 51,1 [48,7-53,9] |

BRE completo: +7,5 pp de sensibilidade (336 -> 368 dos 428), especificidade inalterada (FP 350 -> 353), IC não se sobrepõem na sensibilidade. ACEITE: passa.

HVE: a VPP sobe (44,1 -> 51,1) e a especificidade sobe (86,4 -> 91,0), mas a SENSIBILIDADE cai 9,7 pp: dos 488 `ecg.lvh` retirados, 113 eram verdadeiros (registros com LVH + BRE no gold) e 375 falsos.
Esse é o custo da supressão pedida; está disponível a nota `ecg.lvh_not_assessable_lbbb` nesses registros. Decisão clínica do dono se prefere rebaixar em vez de suprimir.

Outras classes (sens/espec/VPP) com IC: BRD completo e BRD qualquer, WPW, AV1, LAE, QT longo, NORM idênticos; MI_any sens 38,6 -> 38,4, espec 95,6 -> 96,1; STTC sens 47,8 -> 47,8, espec 84,8 -> 85,4; STE FP 373 -> 341 (efeito do ST já tratado como secundário ao BRE recém-reconhecido).

### Quem mudou

537 de 9183 registros tiveram algum achado diferente. Todos têm BRE depois (ou BRD completo com QRS > 200 ms nos 5 casos onde a nota implausível saiu), nenhum com QRS < 120 ms sem bloqueio: 0 alterações fora de BRE/QRS largo.
Mudanças por código (registros): `ecg.lbbb` +35 (32 TP), `ecg.lvh_not_assessable_lbbb` +510, `ecg.lvh` -488, `ecg.lvh_voltage` -38, `ecg.secondary_repolarization_lvh` -149, `ecg.hcm_pattern` -11 (133 -> 122),
`ecg.implausible_measurement` -35 (54 -> 19; 30 com BRE, 5 com BRD completo de 214-274 ms), `ecg.ivcd` -13 (viraram BRE), ST/T/Q espúrios com BRE -145 no total (`st_elevation_anterior` -32, `st_depression_lateral` -19, `t_inversion_lateral` -15, etc.),
`ecg.secondary_repolarization` +34, `ecg.pr_gt200_unconfirmed` +7, `ecg.short_pr` +1, `ecg.within_normal_limits` -1.

Limites: o QRS de 200-260 ms deste tipo de traçado (ST elevado absorvido na duração) provavelmente é superestimado; a largura global tem viés de +25 ms vs 12SL (pendência anterior), não corrigido aqui.
Os 3 FP novos de BRE e os 11 `hcm_pattern` removidos não foram revisados caso a caso. Testes: `backend/tests/test_ecg_lbbb_r5m3.py` (11 testes; RED provado antes das mudanças).
