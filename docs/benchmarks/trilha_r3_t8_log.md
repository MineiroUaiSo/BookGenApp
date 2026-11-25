# Trilha R3-T8 (E3 FA/flutter + E4 NORM)

Bench: `cd backend && PYTHONPATH=. MEDLENS_DATASETS=/Users/macbook/medlens/data/datasets MEDLENS_BENCH=/Users/macbook/medlens/data/bench python -m bench.ecg_bench --source ptbxl --split dev [--set large] --tag <TAG> --workers 4`. Antes = HEAD ffaa222 (tags R3T8_0 / R3T8L_0); depois = tags R3T8_2 / R3T8L_1.

## Mudancas (limiares NORM intocados)
- rhythm.rr_alternation (lag-2 AC>=0,5 e lag-1<=-0,3, >=8 RR): alternancia/bigeminismo exclui FA (vai para ritmo sinusal irregular).
- rhythm.flutter_multilead (II/III/aVF/V1, banda 4,0-5,67 Hz = 240-340/min) + teste de flutter ANTES de FA (razao>=0,75, sem P ligada, sem ectopia/alternancia).
- Sokolow-Lyon isolado em <40 anos vira limitrofe (lvh_voltage) salvo strain lateral; QTc limitrofe >450 homem / >460 mulher (>470 alterado, >500 critico mantidos); T invertida so em V1-V3 de mulher <40 = limitrofe.

## Resultados (dev PTB-XL, sens/PPV %)
| | default N=1183 antes -> depois | large N=9183 antes -> depois |
|---|---|---|
| AF | 84,2/79,6 (FP 34) -> 82,9/82,4 (FP 28) | 84,4/84,0 (FP 163) -> 83,7/84,7 (FP 153) |
| AF+flutter | 81,9/78,8 -> 80,9/80,1 | 84,4/77,9 -> 83,8/78,3 |
| NORM->normal | 76,5 -> 76,5 | 74,6 -> 74,6 |
| non-NORM >=1 achado | 86,9 -> 86,9 | 81,9 -> 81,8 |
| LVH sens/espec | 76,1/83,6 -> igual | 74,8/86,3 -> 74,7/86,4 |
| LQT sens/espec | 62,3/87,5 -> igual | 61,7/91,4 -> 59,6/92,7 (sens -2,1) |
Demais (STD, STE_acute, MI_any, STTC) identicos.

Varredura do limiar de flutter (default): razao 0,45 -> AF sens 77,8 (pior); 0,6 -> 81,0; 0,75 -> 82,9 (= so alternancia). Flutter-primeiro quase nao recupera AFLT (ganho ~0).

## Metas nao atingidas
PPV FA 0,85 (84,7 large; sens 83,7 < 0,83? ok >=0,83). NORM>=80% NAO atingido (74,6): os bloqueios de NORM nao eram so estes tres criterios. LQT sens caiu 2,1 pts (IC sobrepoe) pelo corte feminino 460.
Suite completa: tudo passa (comando: pytest -q --disable-warnings em backend).
