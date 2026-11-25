# R2 — STD descritivo vs isquêmico

Dev PTB-XL large (N=9183, folds 1-8), tag `STDsplit`, workers 4, código atual (rules.py inalterado).
Comando: `cd backend && PYTHONPATH=. MEDLENS_DATASETS=../data/datasets MEDLENS_BENCH=../data/bench .venv/bin/python -m bench.ecg_bench --source ptbxl --split dev --set large --tag STDsplit --workers 4`

Definições (bench/ecg_bench.py):
- STD isquêmico (`STD_isch`): só `ecg.st_depression_*` (= métrica `STD` antiga).
- STD descritivo (`STD_desc`): `st_depression_*` OU `ecg.secondary_repolarization_lvh` (strain).
- Ouro "STD_": rótulo STD_. Ouro "isquêmico": ISC_/ISCAL/ISCIN/ISCIL/ISCAS/ISCLA/ISCAN + MI (IMI, ASMI, ...) + STD_.

## Sens/espec (IC95% Wilson; bootstrap no ecg.md fica equivalente)

| Ouro | Predição | N+ | Sens | Espec |
|---|---|---|---|---|
| STD_ | isquêmico | 732 | 47,8% [44,2–51,4] | 85,1% [84,4–85,9] |
| STD_ | descritivo | 732 | 52,6% [49,0–56,2] | 82,2% [81,4–83,0] |
| isquêmico (ISC*+MI+STD_) | isquêmico | 3112 | 34,0% [32,4–35,7] | 91,0% [90,3–91,7] |
| isquêmico (ISC*+MI+STD_) | descritivo | 3112 | 39,4% [37,7–41,2] | 89,1% [88,3–89,9] |
| só ISC* | isquêmico | 1344 | 47,8% [45,1–50,4] | 87,7% [87,0–88,4] |
| só ISC* | descritivo | 1344 | 58,7% [56,1–61,3] | 86,0% [85,2–86,7] |
| só MI | isquêmico | 1942 | 25,7% [23,9–27,7] | 84,7% [83,9–85,5] |
| só MI | descritivo | 1942 | 29,6% [27,6–31,7] | 81,9% [80,9–82,7] |

## Casos que deixaram de contar STD (só strain, sem st_depression_*): 284

- Com rótulo STD_: 35 (12%) -> explica 4,8 pts de sens (35/732).
- Com rótulo isquêmico (ISC*/MI/STD_): 168 (59%): ISC_ 131, MI 75 (sobrepostos), ISCAL 14, ISCIL 3, ISCAS 2, ISCIN 2.
- Sem rótulo isquêmico: 116 (41%).

## Conclusão

Contra rótulos, o custo da supressão é > 2 pts: -4,8 pts de sens (ouro STD_), -5,4 pts (ouro isquêmico), -10,9 pts (só ISC*), com ganho de espec de ~2-3 pts. Ressalvas: (1) ISC_ é rótulo inespecífico e comumente acompanha HVE/strain no PTB-XL; (2) MI sem STD aparente não é "depressão" do ST; (3) 59% dos casos perdidos têm rótulo isquêmico contra prevalência de 34%, enriquecimento real mas modesto. Isquemia real mascarada por strain não é mensurável com estes rótulos. Decisão (restringir supressão ou aceitar o custo) segue médica.
