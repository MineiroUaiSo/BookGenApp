# R2 — linha de base de avaliação (PTB-XL dev ampliado)

_Gerado em 2026-11-24 20:47 UTC · commit 3a3589e · tag `R2base` · N = 9183 registros dev (PTB-XL folds 1-8; folds 9-10 BURNED, fora)._

Linha de base R2: **código atual, nenhuma regra alterada**. Referência para as trilhas E5/E1/E3/E4.

**Reproduzir** (a partir de `backend/`):

```bash
export MEDLENS_DATASETS=/path/to/data/datasets MEDLENS_BENCH=$PWD/../data/bench PYTHONPATH=.   # datasets: ptbxl_full, ptbxl_plus
python -m bench.ecg_bench --source ptbxl --split dev --set large --tag R2base --workers 3
python -m bench.r2_report --tag R2base --out ../docs/benchmarks/r2_base.md
```

| Métrica-chave | Valor |
|---|---|
| NORM → normal | 2102/2815 = 74.7% |
| AF sens / VPP | sens 84.4% / VPP 84.0% (N pos 1014) |
| AV1 sens / VPP | sens 38.3% / VPP 52.8% (N pos 616) |
| AV3 sens / VPP | sens 0.0% / VPP 0.0% (N pos 12) |
| STD sens / espec | 56.6% / 82.5% (N pos 732) |
| STE_acute sens / FP | sens 51.2% (N pos 123) / FP 341 de 9060 negativos (3.76%) |
| STE (gold STE_) sens / VPP | 0.0% / 0.0% (N pos 22) |
| LVH sens / VPP | sens 72.7% / VPP 44.3% (N pos 1156) |
| CRBBB sens / VPP | sens 58.0% / VPP 68.7% (N pos 431) |
| LBBB sens / VPP | sens 78.5% / VPP 49.0% (N pos 428) |
| LQT sens / VPP | sens 61.7% / VPP 6.9% (N pos 94) |
| viés PR vs 12SL (ms) | 11,6 [10,6–12,5] |
| MAE ST-J médio das 12 derivações vs 12SL (µV) | 28.9 |
| MAE QRS vs 12SL (ms) / viés | 27,1 [26,8–27,4] / 25,3 [25,0–25,7] |

## Composição da amostra dev

9183 registros válidos. Amostra dev congelada, enriquecida em classes raras (bench/lists/ptbxl_large_dev.json, semente 20261124); **prevalências abaixo não são as naturais**.

| Classe | Descrição | N positivos (gold) |
|---|---|---|
| NORM | NORM | 2815 |
| AF | atrial fibrillation (AFIB) | 1014 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 1060 |
| AV1 | 1st-degree AV block (1AVB) | 616 |
| AV2 | 2nd-degree AV block (2AVB) | 12 |
| AV3 | 3rd-degree AV block (3AVB) | 12 |
| RBBB_complete | complete RBBB (CRBBB) | 431 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 731 |
| LBBB_complete | complete LBBB (CLBBB) | 428 |
| LBBB_any | LBBB any | 489 |
| LVH | left ventricular hypertrophy | 1156 |
| RVH | right ventricular hypertrophy | 92 |
| STACH | sinus tachycardia | 637 |
| SBRAD | sinus bradycardia | 509 |
| PACE | pacemaker rhythm (PACE) | 237 |
| STD | ST depression (STD_) | 732 |
| STE | ST elevation (STE_) | 22 |
| STE_acute | ST elevation vs acute-MI gold (MI + stadium I/I-II) | 123 |
| LQT | long QT (LNGQT) | 94 |
| WPW | WPW | 64 |
| LAFB | left anterior fascicular block | 977 |
| LPFB | left posterior fascicular block | 141 |
| MI_any | any MI (Q waves or ST elevation) | 1942 |
| STTC | ST/T change (any) | 3051 |
| LOWV | low voltage (LVOLT) | 145 |

## Diagnóstico PTB-XL (dev ampliado, IC95% bootstrap)

9183 records analysed (0 failed). Timing: median 0.68 s, p95 3.92 s, max 40.1 s per record (N=9183). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). **STE_ is annotated inconsistently in PTB-XL, so STE is scored against two golds: STE_ (statement, kept) and STE_acute = any MI statement with infarction_stadium1 in {'Stadium I', 'Stadium I-II'} (same prediction).** The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens [IC95% bootstrap] | Spec [IC95%] | PPV [IC95%] (this sample) | Acc [IC95%] | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 1014 | 856 | 163 | 84,4% [82,2–86,6] | 98,0% [97,7–98,3] | 84,0% [81,8–86,3] | 96,5% [96,1–96,9] | 76 (prev 6.9%) | 0.84 |
| AV1 | 1st-degree AV block (1AVB) | 616 | 236 | 211 | 38,3% [34,3–42,2] | 97,5% [97,2–97,8] | 52,8% [48,2–57,4] | 93,6% [93,1–94,0] | 37 (prev 3.6%) | 0.44 |
| AV2 | 2nd-degree AV block (2AVB) | 12 | 0 | 26 | 0,0% [0,0–0,0] | 99,7% [99,6–99,8] | 0,0% [0,0–0,0] | 99,6% [99,4–99,7] | 0 (prev 0.1%) | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 12 | 0 | 3 | 0,0% [0,0–0,0] | 100,0% [99,9–100,0] | 0,0% [0,0–0,0] | 99,8% [99,7–99,9] | 0 (prev 0.1%) | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 431 | 250 | 114 | 58,0% [53,5–62,7] | 98,7% [98,4–98,9] | 68,7% [63,9–73,4] | 96,8% [96,4–97,1] | 53 (prev 2.5%) | 0.63 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 731 | 138 | 96 | 18,9% [16,0–21,8] | 98,9% [98,6–99,1] | 59,0% [52,7–65,3] | 92,5% [92,0–93,0] | 47 (prev 5.1%) | 0.29 |
| RBBB_any | RBBB any | 1162 | 550 | 48 | 47,3% [44,5–50,1] | 99,4% [99,2–99,6] | 92,0% [89,7–94,1] | 92,8% [92,3–93,3] | 87 (prev 7.6%) | 0.62 |
| LBBB_complete | complete LBBB (CLBBB) | 428 | 336 | 350 | 78,5% [74,6–82,5] | 96,0% [95,6–96,4] | 49,0% [45,3–52,9] | 95,2% [94,8–95,7] | 33 (prev 2.5%) | 0.60 |
| LBBB_any | LBBB any | 489 | 386 | 432 | 78,9% [75,2–82,4] | 95,0% [94,6–95,5] | 47,2% [43,7–50,6] | 94,2% [93,7–94,7] | 31 (prev 2.8%) | 0.59 |
| LAFB | left anterior fascicular block | 977 | 118 | 43 | 12,1% [10,2–14,2] | 99,5% [99,3–99,6] | 73,3% [66,2–80,1] | 90,2% [89,6–90,8] | 65 (prev 7.4%) | 0.21 |
| LPFB | left posterior fascicular block | 141 | 19 | 60 | 13,5% [8,0–19,2] | 99,3% [99,2–99,5] | 24,1% [15,0–33,0] | 98,0% [97,7–98,3] | 14 (prev 0.8%) | 0.17 |
| WPW | WPW | 64 | 33 | 52 | 51,6% [39,1–63,8] | 99,4% [99,3–99,6] | 38,8% [28,6–49,5] | 99,1% [98,9–99,3] | 25 (prev 0.4%) | 0.44 |
| LVH | left ventricular hypertrophy | 1156 | 840 | 1058 | 72,7% [70,0–75,3] | 86,8% [86,1–87,6] | 44,3% [42,1–46,5] | 85,0% [84,3–85,8] | 33 (prev 8.0%) | 0.55 |
| RVH | right ventricular hypertrophy | 92 | 44 | 202 | 47,8% [37,5–58,2] | 97,8% [97,5–98,1] | 17,9% [12,9–22,9] | 97,3% [97,0–97,6] | 10 (prev 0.5%) | 0.26 |
| LAE | left atrial enlargement | 238 | 7 | 203 | 2,9% [0,9–5,1] | 97,7% [97,4–98,0] | 3,3% [1,0–5,9] | 95,3% [94,8–95,7] | 2 (prev 1.9%) | 0.03 |
| RAE | right atrial enlargement | 50 | 23 | 125 | 46,0% [32,7–59,6] | 98,6% [98,4–98,9] | 15,5% [10,0–21,6] | 98,3% [98,1–98,6] | 13 (prev 0.4%) | 0.23 |
| LQT | long QT (LNGQT) | 94 | 58 | 785 | 61,7% [51,9–71,8] | 91,4% [90,7–91,9] | 6,9% [5,2–8,6] | 91,1% [90,4–91,6] | 4 (prev 0.5%) | 0.12 |
| SBRAD | sinus bradycardia | 509 | 336 | 27 | 66,0% [62,1–70,2] | 99,7% [99,6–99,8] | 92,6% [89,7–95,3] | 97,8% [97,5–98,1] | 86 (prev 2.9%) | 0.77 |
| STACH | sinus tachycardia | 637 | 561 | 99 | 88,1% [85,5–90,6] | 98,8% [98,6–99,1] | 85,0% [82,1–87,6] | 98,1% [97,8–98,4] | 75 (prev 3.8%) | 0.87 |
| SR | sinus rhythm | 6081 | 5422 | 496 | 89,2% [88,3–89,9] | 84,0% [82,7–85,3] | 91,6% [90,9–92,3] | 87,4% [86,7–88,1] | 95 (prev 76.8%) | 0.90 |
| MI_any | any MI (Q waves or ST elevation) | 1942 | 750 | 340 | 38,6% [36,4–40,8] | 95,3% [94,8–95,8] | 68,8% [66,0–71,6] | 83,3% [82,6–84,1] | 66 (prev 19.0%) | 0.49 |
| MI_inferior | inferior MI (IMI etc.) | 979 | 276 | 138 | 28,2% [25,2–31,0] | 98,3% [98,0–98,6] | 66,7% [62,2–71,0] | 90,8% [90,2–91,4] | 66 (prev 10.3%) | 0.40 |
| MI_anterior | anterior/anteroseptal MI | 1280 | 446 | 204 | 34,8% [32,2–37,4] | 97,4% [97,1–97,8] | 68,6% [65,0–72,4] | 88,7% [88,0–89,3] | 64 (prev 11.7%) | 0.46 |
| MI_lateral | lateral MI | 371 | 127 | 139 | 34,2% [29,7–39,3] | 98,4% [98,2–98,7] | 47,7% [41,7–53,8] | 95,8% [95,4–96,2] | 47 (prev 3.9%) | 0.40 |
| STTC | ST/T change (any) | 3051 | 1468 | 949 | 48,1% [46,5–49,9] | 84,5% [83,6–85,4] | 60,7% [58,8–62,7] | 72,4% [71,6–73,3] | 50 (prev 24.5%) | 0.54 |
| STE | ST elevation (STE_) | 22 | 0 | 404 | 0,0% [0,0–0,0] | 95,6% [95,2–96,0] | 0,0% [0,0–0,0] | 95,4% [94,9–95,8] | 0 (prev 0.1%) | 0.00 |
| STD | ST depression (STD_) | 732 | 414 | 1480 | 56,6% [53,1–60,2] | 82,5% [81,7–83,3] | 21,9% [20,0–23,8] | 80,4% [79,6–81,2] | 14 (prev 4.6%) | 0.32 |
| LOWV | low voltage (LVOLT) | 145 | 22 | 174 | 15,2% [9,6–21,3] | 98,1% [97,8–98,4] | 11,2% [7,0–15,9] | 96,8% [96,4–97,1] | 6 (prev 0.8%) | 0.13 |
| NORM | NORM | 2815 | 2102 | 1147 | 74,7% [73,1–76,2] | 82,0% [81,0–82,9] | 64,7% [63,0–66,4] | 79,7% [78,9–80,5] | 76 (prev 43.3%) | 0.69 |
| PACE | pacemaker rhythm (PACE) | 237 | 105 | 5 | 44,3% [37,7–50,8] | 99,9% [99,9–100,0] | 95,5% [91,3–99,0] | 98,5% [98,2–98,7] | 92 (prev 1.3%) | 0.61 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 1060 | 895 | 254 | 84,4% [82,3–86,6] | 96,9% [96,5–97,2] | 77,9% [75,5–80,3] | 95,4% [95,0–95,9] | 68 (prev 7.2%) | 0.81 |
| STE_acute | ST elevation vs acute-MI gold (MI + stadium I/I-II) | 123 | 63 | 341 | 51,2% [42,2–60,4] | 96,2% [95,8–96,6] | 15,6% [12,0–19,3] | 95,6% [95,2–96,0] | 9 (prev 0.7%) | 0.24 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 74,7% [73,0–76,2] (n=2815) |
| gold NORM -> we raise >=1 abnormal/critical finding | 25,3% [23,8–27,0] (n=2815) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 45,5% [43,6–47,3] (n=2815) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 82,0% [81,0–82,9] (n=6368) |
| gold non-NORM -> we say within normal limits (missed) | 18,0% [17,1–19,0] (n=6368) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 6081 | 71 (57-90) | 83.5% (5079/6081) in 60-100 bpm |
| STACH | 637 | 108 (102-121) | 98.7% (629/637) in 100-+ bpm |
| SBRAD | 509 | 49 (44-57) | 98.4% (501/509) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 2547 | 1390 | 1144 | 13 |
| normal | 2967 | 10 | 2851 | 106 |
| right | 221 | 36 | 26 | 159 |

Axis category agreement: 76,7% [75,6–77,8] (n=5735) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> SR:42, PACE:42, PVC:28, SARRH:25 | FN our findings -> irregular_rhythm:76, st_depression_lateral:54, lvh:44, t_inversion_lateral:34 |
| AV1 | FP gold labels -> SR:131, LVH:48, ABQRS:40, LAFB:36 | FN our findings -> sinus_rhythm:199, left_axis_deviation:126, lvh:103, secondary_repolarization:88 |
| AV2 | FP gold labels -> SR:17, NORM:8, ABQRS:5, SBRAD:4 | FN our findings -> st_depression_lateral:6, sinus_tachycardia:5, short_pr:4, t_inversion_lateral:4 |
| AV3 | FP gold labels -> SR:2, WPW:1, NORM:1, VCLVH:1 | FN our findings -> sinus_bradycardia:4, lvh:3, st_elevation_inferior:3, st_depression_lateral:3 |
| RBBB_complete | FP gold labels -> IRBBB:91, SR:81, ABQRS:23, LAFB:22 | FN our findings -> rvh:119, sinus_rhythm:96, left_axis_deviation:88, ivcd:81 |
| RBBB_incomplete | FP gold labels -> CRBBB:71, SR:55, AFIB:22, ABQRS:21 | FN our findings -> sinus_rhythm:419, within_normal_limits:224, left_axis_deviation:116, rbbb:91 |
| RBBB_any | FP gold labels -> SR:18, ASMI:16, LAFB:12, AFIB:11 | FN our findings -> sinus_rhythm:411, within_normal_limits:224, left_axis_deviation:143, ivcd:131 |
| LBBB_complete | FP gold labels -> SR:199, LVH:108, ISC_:106, LAFB:106 | FN our findings -> ivcd:85, st_elevation_anterior:76, lvh:67, st_depression_lateral:52 |
| LBBB_any | FP gold labels -> SR:249, LVH:139, ISC_:136, ABQRS:126 | FN our findings -> ivcd:86, st_elevation_anterior:79, lvh:70, sinus_rhythm:58 |
| LAFB | FP gold labels -> SR:18, IMI:16, ABQRS:16, AFIB:11 | FN our findings -> left_axis_deviation:815, sinus_rhythm:584, secondary_repolarization:210, lvh:209 |
| LPFB | FP gold labels -> SR:27, NORM:18, AFIB:14, IRBBB:12 | FN our findings -> right_axis_deviation:100, secondary_repolarization:66, sinus_rhythm:65, rvh:62 |
| WPW | FP gold labels -> SR:32, ABQRS:20, STACH:13, IMI:10 | FN our findings -> sinus_rhythm:19, secondary_repolarization:13, lbbb:11, lvh:10 |
| LVH | FP gold labels -> SR:626, CLBBB:330, AFIB:180, LAFB:169 | FN our findings -> sinus_rhythm:194, st_depression_lateral:139, t_inversion_lateral:81, st_depression_inferior:69 |
| RVH | FP gold labels -> CRBBB:152, SR:113, LPFB:49, AFIB:48 | FN our findings -> sinus_rhythm:39, secondary_repolarization:31, rbbb:31, left_axis_deviation:24 |
| LAE | FP gold labels -> SR:127, LVH:36, PACE:33, ISC_:32 | FN our findings -> sinus_rhythm:155, lvh:112, secondary_repolarization:77, left_axis_deviation:77 |
| RAE | FP gold labels -> STACH:48, SR:46, NORM:26, ABQRS:25 | FN our findings -> sinus_rhythm:16, left_axis_deviation:12, sinus_tachycardia:7, secondary_repolarization:6 |
| LQT | FP gold labels -> SR:558, LVH:176, ABQRS:155, ISC_:151 | FN our findings -> sinus_rhythm:26, within_normal_limits:19, left_axis_deviation:7, left_axis_mild:6 |
| SBRAD | FP gold labels -> NORM:7, LAFB:4, LVH:3, 1AVB:3 | FN our findings -> sinus_rhythm:129, within_normal_limits:101, irregular_rhythm:32, left_axis_deviation:24 |
| STACH | FP gold labels -> SR:39, NST_:23, ABQRS:17, ISC_:16 | FN our findings -> atrial_flutter:41, left_axis_deviation:20, st_depression_lateral:17, irregular_rhythm:15 |
| SR | FP gold labels -> NORM:199, SBRAD:129, SARRH:107, LVH:52 | FN our findings -> irregular_rhythm:438, left_axis_deviation:185, lvh:183, within_normal_limits:142 |
| MI_any | FP gold labels -> SR:190, CLBBB:84, ABQRS:59, PACE:55 | FN our findings -> sinus_rhythm:677, left_axis_deviation:380, lvh:278, st_depression_lateral:247 |
| MI_inferior | FP gold labels -> SR:66, ABQRS:50, WPW:28, ASMI:22 | FN our findings -> sinus_rhythm:406, left_axis_deviation:249, lvh:138, st_depression_lateral:137 |
| MI_anterior | FP gold labels -> SR:121, CLBBB:77, LVH:44, ISC_:32 | FN our findings -> sinus_rhythm:458, left_axis_deviation:315, lvh:219, st_depression_lateral:199 |
| MI_lateral | FP gold labels -> SR:74, PACE:35, LAFB:28, ABQRS:27 | FN our findings -> sinus_rhythm:133, left_axis_deviation:107, pathologic_q_anterior:62, pathologic_q_inferior:50 |
| STTC | FP gold labels -> SR:511, ABQRS:309, ASMI:296, LAFB:167 | FN our findings -> sinus_rhythm:974, within_normal_limits:663, lvh:318, long_qt:248 |
| STE | FP gold labels -> SR:229, ASMI:138, ABQRS:100, LAFB:79 | FN our findings -> sinus_rhythm:19, within_normal_limits:17, lvh_voltage:3, lae:3 |
| STD | FP gold labels -> SR:762, LVH:496, ISC_:423, AFIB:374 | FN our findings -> sinus_rhythm:204, lvh:110, within_normal_limits:95, left_axis_deviation:57 |
| LOWV | FP gold labels -> SR:83, ABQRS:57, ASMI:53, AFIB:40 | FN our findings -> sinus_rhythm:96, within_normal_limits:77, left_axis_deviation:14, long_qt:9 |
| NORM | FP gold labels -> SR:1013, NDT:412, ABQRS:212, IRBBB:156 | FN our findings -> sinus_rhythm:264, sinus_bradycardia:189, sinus_tachycardia:155, lvh:91 |
| PACE | FP gold labels -> LAFB:2, IMI:2, ABQRS:2, SR:2 | FN our findings -> lvh:58, left_axis_deviation:48, sinus_rhythm:48, short_qt:37 |
| AF_AFL | FP gold labels -> SR:82, STACH:51, NORM:47, 1AVB:47 | FN our findings -> irregular_rhythm:78, st_depression_lateral:56, lvh:45, left_axis_deviation:38 |
| STE_acute | FP gold labels -> SR:186, ASMI:91, CLBBB:78, LAFB:63 | FN our findings -> sinus_rhythm:31, lvh:23, left_axis_deviation:22, secondary_repolarization:16 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-00423, ptbxl-00517, ptbxl-00602, ptbxl-00706, ptbxl-00757 | ptbxl-00547, ptbxl-00699, ptbxl-00759, ptbxl-00923, ptbxl-00942 |
| AV1 | ptbxl-00269, ptbxl-00320, ptbxl-00385, ptbxl-00501, ptbxl-00507 | ptbxl-00182, ptbxl-00346, ptbxl-00522, ptbxl-00556, ptbxl-00730 |
| AV2 | ptbxl-00273, ptbxl-03254, ptbxl-05670, ptbxl-06553, ptbxl-06629 | ptbxl-03505, ptbxl-08048, ptbxl-09136, ptbxl-10300, ptbxl-11209 |
| AV3 | ptbxl-02145, ptbxl-06466, ptbxl-16724 | ptbxl-02047, ptbxl-04827, ptbxl-04838, ptbxl-07688, ptbxl-08911 |
| RBBB_complete | ptbxl-00482, ptbxl-00932, ptbxl-01063, ptbxl-01444, ptbxl-01466 | ptbxl-00428, ptbxl-00957, ptbxl-01570, ptbxl-01575, ptbxl-01688 |
| RBBB_incomplete | ptbxl-00957, ptbxl-01126, ptbxl-01575, ptbxl-02017, ptbxl-02201 | ptbxl-00052, ptbxl-00087, ptbxl-00222, ptbxl-00236, ptbxl-00255 |
| RBBB_any | ptbxl-01063, ptbxl-01126, ptbxl-02201, ptbxl-02815, ptbxl-03006 | ptbxl-00052, ptbxl-00087, ptbxl-00222, ptbxl-00236, ptbxl-00255 |
| LBBB_complete | ptbxl-00282, ptbxl-00325, ptbxl-00413, ptbxl-00423, ptbxl-00507 | ptbxl-00635, ptbxl-00730, ptbxl-00822, ptbxl-01694, ptbxl-01710 |
| LBBB_any | ptbxl-00325, ptbxl-00349, ptbxl-00413, ptbxl-00507, ptbxl-00551 | ptbxl-00635, ptbxl-00730, ptbxl-00822, ptbxl-01694, ptbxl-01710 |
| LAFB | ptbxl-00840, ptbxl-06926, ptbxl-07097, ptbxl-07159, ptbxl-07412 | ptbxl-00182, ptbxl-00220, ptbxl-00235, ptbxl-00260, ptbxl-00305 |
| LPFB | ptbxl-00222, ptbxl-00367, ptbxl-00626, ptbxl-00689, ptbxl-01273 | ptbxl-00428, ptbxl-00547, ptbxl-00635, ptbxl-00788, ptbxl-01066 |
| WPW | ptbxl-00550, ptbxl-00738, ptbxl-00858, ptbxl-01547, ptbxl-03514 | ptbxl-02145, ptbxl-07046, ptbxl-07291, ptbxl-07399, ptbxl-07407 |
| LVH | ptbxl-00085, ptbxl-00257, ptbxl-00256, ptbxl-00279, ptbxl-00289 | ptbxl-00211, ptbxl-00423, ptbxl-00502, ptbxl-00513, ptbxl-00540 |
| RVH | ptbxl-00428, ptbxl-00635, ptbxl-00903, ptbxl-01044, ptbxl-01049 | ptbxl-00222, ptbxl-00667, ptbxl-03050, ptbxl-03244, ptbxl-03504 |
| LAE | ptbxl-00269, ptbxl-00286, ptbxl-00385, ptbxl-00442, ptbxl-00575 | ptbxl-00489, ptbxl-00616, ptbxl-00652, ptbxl-00711, ptbxl-00713 |
| RAE | ptbxl-00108, ptbxl-00260, ptbxl-00550, ptbxl-00738, ptbxl-00860 | ptbxl-00626, ptbxl-00857, ptbxl-00970, ptbxl-01670, ptbxl-05334 |
| LQT | ptbxl-00316, ptbxl-00349, ptbxl-00363, ptbxl-00413, ptbxl-00429 | ptbxl-00260, ptbxl-04132, ptbxl-05046, ptbxl-05301, ptbxl-05586 |
| SBRAD | ptbxl-00191, ptbxl-00507, ptbxl-01075, ptbxl-01126, ptbxl-01277 | ptbxl-00225, ptbxl-00235, ptbxl-00284, ptbxl-01168, ptbxl-01232 |
| STACH | ptbxl-00222, ptbxl-00550, ptbxl-00858, ptbxl-00942, ptbxl-01033 | ptbxl-00698, ptbxl-00855, ptbxl-01074, ptbxl-01214, ptbxl-01670 |
| SR | ptbxl-00037, ptbxl-00225, ptbxl-00235, ptbxl-00350, ptbxl-00362 | ptbxl-00182, ptbxl-00222, ptbxl-00255, ptbxl-00256, ptbxl-00269 |
| MI_any | ptbxl-00085, ptbxl-00222, ptbxl-00410, ptbxl-00621, ptbxl-00730 | ptbxl-00106, ptbxl-00257, ptbxl-00263, ptbxl-00282, ptbxl-00290 |
| MI_inferior | ptbxl-00310, ptbxl-00455, ptbxl-00547, ptbxl-00730, ptbxl-00822 | ptbxl-00257, ptbxl-00270, ptbxl-00290, ptbxl-00325, ptbxl-00380 |
| MI_anterior | ptbxl-00085, ptbxl-00621, ptbxl-00730, ptbxl-00822, ptbxl-00826 | ptbxl-00106, ptbxl-00257, ptbxl-00263, ptbxl-00282, ptbxl-00482 |
| MI_lateral | ptbxl-00085, ptbxl-00222, ptbxl-00310, ptbxl-00410, ptbxl-00855 | ptbxl-00528, ptbxl-00547, ptbxl-00833, ptbxl-00914, ptbxl-00924 |
| STTC | ptbxl-00085, ptbxl-00191, ptbxl-00211, ptbxl-00222, ptbxl-00310 | ptbxl-00054, ptbxl-00087, ptbxl-00133, ptbxl-00209, ptbxl-00257 |
| STE | ptbxl-00085, ptbxl-00410, ptbxl-00455, ptbxl-00528, ptbxl-00532 | ptbxl-01600, ptbxl-01596, ptbxl-01725, ptbxl-02639, ptbxl-02868 |
| STD | ptbxl-00191, ptbxl-00211, ptbxl-00259, ptbxl-00263, ptbxl-00310 | ptbxl-00257, ptbxl-00313, ptbxl-00325, ptbxl-00333, ptbxl-00337 |
| LOWV | ptbxl-00255, ptbxl-00321, ptbxl-00532, ptbxl-00547, ptbxl-00604 | ptbxl-00001, ptbxl-00348, ptbxl-00407, ptbxl-00934, ptbxl-00971 |
| NORM | ptbxl-00054, ptbxl-00052, ptbxl-00106, ptbxl-00133, ptbxl-00192 | ptbxl-00002, ptbxl-00012, ptbxl-00019, ptbxl-00078, ptbxl-00085 |
| PACE | ptbxl-04377, ptbxl-10455, ptbxl-16970, ptbxl-19202, ptbxl-21243 | ptbxl-01461, ptbxl-01596, ptbxl-01641, ptbxl-02486, ptbxl-02885 |
| AF_AFL | ptbxl-00338, ptbxl-00423, ptbxl-00517, ptbxl-00602, ptbxl-00698 | ptbxl-00547, ptbxl-00699, ptbxl-00759, ptbxl-00858, ptbxl-00923 |
| STE_acute | ptbxl-00085, ptbxl-00410, ptbxl-00455, ptbxl-00528, ptbxl-00608 | ptbxl-02425, ptbxl-02525, ptbxl-03076, ptbxl-03956, ptbxl-04830 |

## Medidas vs 12SL (PTB-XL+)

Referência: algoritmo GE Marquette 12SL (PTB-XL+ 1.0.1, features/12sl_features.csv); **não é padrão-ouro humano**. Unidades: ms (PR, QRS, QT, QTc Bazett), bpm (FC), µV (ST no ponto J; 12SL STJ e nosso st_j_mv estão em mV e foram ×1000). Viés = média(nosso − 12SL); MAE = média |nosso − 12SL|; IC95% bootstrap por registro (2000 reamostras, semente fixa). Pares apenas onde ambos têm valor (PR ausente em FA/sem onda P). ECGdeli não é usado (medianas muito diferentes de 12SL e do PTB-XL, ex. QRS 160 ms vs 94 ms: critério de bordas distinto).

| Medida | Unid. | N pareado / N dev | média 12SL | viés (nosso − 12SL) [IC95%] | MAE [IC95%] | r de Pearson |
|---|---|---|---|---|---|---|
| PR | ms | 7620 / 9183 | 169.0 | 11,6 [10,6–12,5] | 27,1 [26,4–27,9] | 0.59 |
| QRS | ms | 9183 / 9183 | 101.9 | 25,3 [25,0–25,7] | 27,1 [26,8–27,4] | 0.79 |
| QT | ms | 9180 / 9183 | 396.1 | 29,8 [29,0–30,6] | 33,8 [33,1–34,5] | 0.72 |
| QTc (Bazett) | ms | 9180 / 9183 | 437.9 | 34,6 [33,7–35,5] | 38,9 [38,1–39,7] | 0.59 |
| FC | bpm | 9183 / 9183 | 76.4 | 0,1 [0,0–0,1] | 0,4 [0,4–0,5] | 0.99 |

**ST no ponto J por derivação (µV)**

| Derivação | N pareado | média 12SL (µV) | viés (nosso − 12SL) µV [IC95%] | MAE µV [IC95%] | r |
|---|---|---|---|---|---|
| I | 9183 | -15 | -7 [-8–-6] | 21 [20–22] | 0.52 |
| II | 9183 | -12 | -6 [-8–-4] | 27 [25–29] | 0.30 |
| III | 9183 | 2 | 0 [-2–3] | 34 [31–36] | 0.12 |
| aVR | 9183 | 12 | 9 [8–10] | 18 [17–19] | 0.61 |
| aVL | 9183 | -8 | -4 [-5–-2] | 25 [23–27] | 0.19 |
| aVF | 9183 | -4 | -3 [-6–-1] | 28 [26–30] | 0.15 |
| V1 | 9183 | 25 | 14 [12–16] | 31 [30–33] | 0.60 |
| V2 | 9183 | 35 | 13 [10–15] | 40 [37–43] | 0.59 |
| V3 | 9183 | 12 | 7 [4–10] | 41 [38–44] | 0.54 |
| V4 | 9183 | -23 | -1 [-4–1] | 35 [32–38] | 0.42 |
| V5 | 9183 | -37 | -6 [-8–-5] | 25 [24–27] | 0.61 |
| V6 | 9183 | -26 | -8 [-9–-7] | 22 [21–24] | 0.60 |

## Subgrupos (sexo, idade, aparelho, ruído)

**NORM → normal**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 2815 | 74,7% [73,1–76,2] | 82,0% [81,0–82,9] | 64,7% [63,0–66,4] |
| aparelho | AT-6     6 | 1044 | 311 | 68,5% [63,3–73,6] | 81,0% [78,2–83,8] | 60,5% [55,2–65,4] |
| aparelho | AT-6 C 5.5 | 1686 | 551 | 75,5% [72,0–79,0] | 80,4% [78,1–82,7] | 65,2% [61,5–69,1] |
| aparelho | AT-6 C 5.8 | 378 | 99 | 75,8% [67,3–84,6] | 82,4% [77,8–86,5] | 60,5% [51,7–68,5] |
| aparelho | CS-12 | 1549 | 509 | 71,9% [68,2–75,7] | 78,6% [76,1–81,1] | 62,1% [57,8–66,1] |
| aparelho | CS-12   E | 810 | 585 | 80,7% [77,6–83,8] | 51,1% [44,7–57,8] | 81,1% [78,0–84,3] |
| aparelho | CS100    3 | 3175 | 605 | 74,5% [71,1–78,0] | 86,9% [85,6–88,1] | 57,2% [53,6–60,7] |
| aparelho | other | 541 | 155 | 70,3% [63,2–77,5] | 82,6% [78,7–86,3] | 61,9% [54,6–69,1] |
| idade | 40-65 | 3945 | 1431 | 77,3% [75,1–79,4] | 77,2% [75,5–78,8] | 65,8% [63,6–68,3] |
| idade | <40 | 978 | 692 | 72,7% [69,4–76,2] | 73,4% [68,0–78,5] | 86,9% [84,0–89,7] |
| idade | >65 | 4260 | 692 | 71,2% [68,0–74,7] | 86,1% [84,9–87,2] | 49,8% [46,6–53,0] |
| ruído: baseline_drift | com | 591 | 222 | 82,9% [77,7–87,8] | 79,4% [75,2–83,4] | 70,8% [65,3–76,4] |
| ruído: baseline_drift | sem | 8592 | 2593 | 74,0% [72,3–75,6] | 82,1% [81,2–83,1] | 64,2% [62,4–66,0] |
| ruído: burst_noise | com | 297 | 72 | 76,4% [65,6–86,0] | 87,1% [82,8–91,4] | 65,5% [54,8–75,3] |
| ruído: burst_noise | sem | 8886 | 2743 | 74,6% [73,0–76,1] | 81,8% [80,9–82,7] | 64,7% [63,0–66,4] |
| ruído: electrodes_problems | com | 13 | 2 (!) | 50,0% [0,0–100,0] | 90,9% [70,0–100,0] | 50,0% [0,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 2813 | 74,7% [73,1–76,2] | 82,0% [81,0–82,9] | 64,7% [63,0–66,4] |
| ruído: static_noise | com | 1303 | 359 | 78,0% [73,7–82,0] | 84,0% [81,6–86,4] | 65,0% [60,5–69,5] |
| ruído: static_noise | sem | 7880 | 2456 | 74,2% [72,4–75,8] | 81,6% [80,6–82,6] | 64,7% [62,9–66,5] |
| sexo | F | 4264 | 1523 | 79,0% [76,9–81,0] | 79,5% [77,9–81,0] | 68,1% [65,9–70,3] |
| sexo | M | 4919 | 1292 | 69,6% [67,0–72,1] | 83,9% [82,7–85,1] | 60,6% [58,2–63,2] |

**AF**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 1014 | 84,4% [82,2–86,6] | 98,0% [97,7–98,3] | 84,0% [81,8–86,3] |
| aparelho | AT-6     6 | 1044 | 121 | 81,8% [74,8–88,5] | 97,7% [96,7–98,6] | 82,5% [75,2–88,8] |
| aparelho | AT-6 C 5.5 | 1686 | 175 | 89,1% [84,4–93,8] | 97,9% [97,2–98,7] | 83,4% [77,7–88,7] |
| aparelho | AT-6 C 5.8 | 378 | 44 | 86,4% [75,6–95,7] | 99,1% [97,9–100,0] | 92,7% [83,3–100,0] |
| aparelho | CS-12 | 1549 | 141 | 81,6% [75,4–87,8] | 98,5% [97,8–99,1] | 84,6% [78,2–90,3] |
| aparelho | CS-12   E | 810 | 6 (!) | 50,0% [0,0–100,0] | 98,9% [98,1–99,5] | 25,0% [0,0–53,3] |
| aparelho | CS100    3 | 3175 | 465 | 84,1% [80,6–87,4] | 97,3% [96,7–97,9] | 84,4% [81,2–87,7] |
| aparelho | other | 541 | 62 | 87,1% [78,3–95,0] | 98,7% [97,7–99,6] | 90,0% [81,8–96,7] |
| idade | 40-65 | 3945 | 326 | 85,6% [81,8–89,4] | 98,7% [98,3–99,1] | 85,6% [81,8–89,5] |
| idade | <40 | 978 | 12 | 58,3% [28,6–87,5] | 98,0% [97,1–98,9] | 26,9% [10,3–45,0] |
| idade | >65 | 4260 | 676 | 84,3% [81,6–87,0] | 97,3% [96,7–97,8] | 85,5% [82,6–88,2] |
| ruído: baseline_drift | com | 591 | 60 | 86,7% [77,6–94,9] | 98,7% [97,7–99,6] | 88,1% [79,1–96,0] |
| ruído: baseline_drift | sem | 8592 | 954 | 84,3% [82,1–86,5] | 98,0% [97,6–98,3] | 83,8% [81,4–86,0] |
| ruído: burst_noise | com | 297 | 91 | 85,7% [78,4–92,4] | 97,1% [94,6–99,1] | 92,9% [86,8–97,7] |
| ruído: burst_noise | sem | 8886 | 923 | 84,3% [81,9–86,6] | 98,0% [97,7–98,3] | 83,2% [80,8–85,5] |
| ruído: electrodes_problems | com | 13 | 1 (!) | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 1013 | 84,4% [82,1–86,6] | 98,0% [97,7–98,3] | 84,0% [81,8–86,3] |
| ruído: static_noise | com | 1303 | 164 | 86,0% [80,5–91,1] | 97,4% [96,4–98,3] | 82,5% [76,4–88,0] |
| ruído: static_noise | sem | 7880 | 850 | 84,1% [81,6–86,6] | 98,1% [97,8–98,4] | 84,3% [81,8–86,6] |
| sexo | F | 4264 | 450 | 84,4% [81,0–87,7] | 97,9% [97,4–98,4] | 82,8% [79,3–86,2] |
| sexo | M | 4919 | 564 | 84,4% [81,3–87,4] | 98,1% [97,7–98,5] | 85,0% [82,1–88,0] |

**AV1**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 616 | 38,3% [34,3–42,2] | 97,5% [97,2–97,8] | 52,8% [48,2–57,4] |
| aparelho | AT-6     6 | 1044 | 49 | 28,6% [16,4–42,4] | 97,7% [96,7–98,6] | 37,8% [22,0–53,8] |
| aparelho | AT-6 C 5.5 | 1686 | 66 | 47,0% [34,7–59,7] | 97,2% [96,3–98,0] | 40,3% [29,2–51,8] |
| aparelho | AT-6 C 5.8 | 378 | 19 | 42,1% [20,0–66,7] | 96,7% [94,7–98,3] | 40,0% [17,6–62,5] |
| aparelho | CS-12 | 1549 | 181 | 34,3% [27,3–41,7] | 98,3% [97,6–99,0] | 72,9% [63,5–82,6] |
| aparelho | CS-12   E | 810 | 18 | 55,6% [31,2–80,0] | 99,6% [99,1–100,0] | 76,9% [50,0–100,0] |
| aparelho | CS100    3 | 3175 | 236 | 38,6% [32,7–45,2] | 96,8% [96,1–97,4] | 49,2% [42,4–56,9] |
| aparelho | other | 541 | 47 | 42,6% [28,3–57,1] | 98,0% [96,7–99,2] | 66,7% [48,4–82,8] |
| idade | 40-65 | 3945 | 169 | 37,3% [29,9–44,8] | 98,3% [97,9–98,7] | 49,6% [41,1–58,6] |
| idade | <40 | 978 | 27 | 37,0% [18,5–56,3] | 99,3% [98,6–99,8] | 58,8% [33,3–81,8] |
| idade | >65 | 4260 | 420 | 38,8% [34,0–43,5] | 96,4% [95,8–96,9] | 53,8% [47,9–59,3] |
| ruído: baseline_drift | com | 591 | 41 | 41,5% [26,7–57,2] | 98,0% [96,7–99,1] | 60,7% [41,7–78,3] |
| ruído: baseline_drift | sem | 8592 | 575 | 38,1% [33,9–42,1] | 97,5% [97,2–97,8] | 52,3% [47,4–56,8] |
| ruído: burst_noise | com | 297 | 16 | 25,0% [5,9–50,0] | 96,8% [94,6–98,6] | 30,8% [7,1–57,1] |
| ruído: burst_noise | sem | 8886 | 600 | 38,7% [34,7–42,6] | 97,6% [97,2–97,9] | 53,5% [48,8–58,1] |
| ruído: electrodes_problems | com | 13 | 4 (!) | 50,0% [0,0–100,0] | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 612 | 38,2% [34,2–42,2] | 97,5% [97,2–97,8] | 52,6% [48,0–57,2] |
| ruído: static_noise | com | 1303 | 106 | 43,4% [34,2–52,9] | 98,2% [97,4–98,9] | 67,6% [56,5–78,8] |
| ruído: static_noise | sem | 7880 | 510 | 37,3% [33,0–41,3] | 97,4% [97,1–97,8] | 50,1% [45,0–55,1] |
| sexo | F | 4264 | 227 | 36,1% [29,8–42,7] | 98,0% [97,5–98,4] | 50,0% [42,2–58,1] |
| sexo | M | 4919 | 389 | 39,6% [34,7–44,6] | 97,2% [96,6–97,6] | 54,4% [48,3–60,3] |

**CRBBB**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 431 | 58,0% [53,5–62,7] | 98,7% [98,4–98,9] | 68,7% [63,9–73,4] |
| aparelho | AT-6     6 | 1044 | 63 | 57,1% [44,6–69,4] | 98,7% [98,0–99,4] | 73,5% [60,6–85,4] |
| aparelho | AT-6 C 5.5 | 1686 | 73 | 50,7% [39,0–62,2] | 98,1% [97,5–98,8] | 55,2% [42,9–66,7] |
| aparelho | AT-6 C 5.8 | 378 | 18 | 55,6% [31,2–80,0] | 98,9% [97,8–99,7] | 71,4% [45,5–93,3] |
| aparelho | CS-12 | 1549 | 64 | 45,3% [33,3–58,1] | 98,8% [98,2–99,3] | 61,7% [47,7–75,5] |
| aparelho | CS-12   E | 810 | 5 (!) | 60,0% [0,0–100,0] | 99,4% [98,8–99,9] | 37,5% [0,0–75,0] |
| aparelho | CS100    3 | 3175 | 177 | 65,0% [58,0–71,8] | 98,6% [98,2–99,1] | 73,7% [66,7–80,9] |
| aparelho | other | 541 | 31 | 64,5% [47,2–81,8] | 99,4% [98,6–100,0] | 87,0% [70,8–100,0] |
| idade | 40-65 | 3945 | 127 | 56,7% [47,5–65,4] | 99,2% [98,9–99,4] | 69,2% [60,0–77,8] |
| idade | <40 | 978 | 8 (!) | 37,5% [0,0–75,0] | 99,1% [98,5–99,6] | 25,0% [0,0–53,3] |
| idade | >65 | 4260 | 296 | 59,1% [53,6–64,7] | 98,2% [97,7–98,6] | 70,6% [64,7–76,3] |
| ruído: baseline_drift | com | 591 | 13 | 61,5% [33,3–88,9] | 99,0% [98,1–99,7] | 57,1% [28,6–83,3] |
| ruído: baseline_drift | sem | 8592 | 418 | 57,9% [53,4–62,6] | 98,7% [98,4–98,9] | 69,1% [64,4–73,9] |
| ruído: burst_noise | com | 297 | 11 | 90,9% [71,4–100,0] | 99,0% [97,6–100,0] | 76,9% [50,0–100,0] |
| ruído: burst_noise | sem | 8886 | 420 | 57,1% [52,5–62,0] | 98,7% [98,4–98,9] | 68,4% [63,5–73,2] |
| ruído: electrodes_problems | com | 13 | 2 (!) | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 429 | 57,8% [53,3–62,4] | 98,7% [98,4–98,9] | 68,5% [63,7–73,2] |
| ruído: static_noise | com | 1303 | 71 | 57,7% [45,8–69,0] | 98,7% [98,0–99,3] | 71,9% [60,0–82,7] |
| ruído: static_noise | sem | 7880 | 360 | 58,1% [53,1–63,1] | 98,7% [98,4–98,9] | 68,1% [62,6–73,3] |
| sexo | F | 4264 | 121 | 52,1% [42,7–61,3] | 99,1% [98,8–99,4] | 62,4% [52,9–71,7] |
| sexo | M | 4919 | 310 | 60,3% [55,1–65,8] | 98,4% [98,0–98,7] | 71,1% [65,7–76,5] |

**LBBB**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 428 | 78,5% [74,6–82,5] | 96,0% [95,6–96,4] | 49,0% [45,3–52,9] |
| aparelho | AT-6     6 | 1044 | 32 | 78,1% [63,2–92,6] | 97,2% [96,2–98,2] | 47,2% [33,3–60,4] |
| aparelho | AT-6 C 5.5 | 1686 | 71 | 67,6% [56,4–78,1] | 96,3% [95,4–97,1] | 44,4% [34,9–53,5] |
| aparelho | AT-6 C 5.8 | 378 | 15 | 53,3% [26,7–80,0] | 97,5% [95,8–98,9] | 47,1% [22,2–71,4] |
| aparelho | CS-12 | 1549 | 41 | 73,2% [59,4–86,1] | 96,8% [95,9–97,7] | 38,5% [27,6–50,0] |
| aparelho | CS-12   E | 810 | 4 (!) | 100,0% [100,0–100,0] | 99,5% [99,0–99,9] | 50,0% [12,5–88,9] |
| aparelho | CS100    3 | 3175 | 245 | 84,9% [80,2–89,5] | 93,8% [92,9–94,6] | 53,3% [48,5–58,4] |
| aparelho | other | 541 | 20 | 65,0% [43,5–86,7] | 96,4% [94,7–97,9] | 40,6% [23,3–57,9] |
| idade | 40-65 | 3945 | 194 | 76,8% [70,9–82,8] | 95,6% [94,9–96,2] | 47,3% [41,5–53,0] |
| idade | <40 | 978 | 3 (!) | 100,0% [100,0–100,0] | 99,2% [98,6–99,7] | 27,3% [0,0–60,0] |
| idade | >65 | 4260 | 231 | 79,7% [74,6–84,9] | 95,6% [95,0–96,2] | 51,1% [45,7–56,4] |
| ruído: baseline_drift | com | 591 | 24 | 79,2% [62,5–95,0] | 97,0% [95,6–98,4] | 52,8% [36,0–69,0] |
| ruído: baseline_drift | sem | 8592 | 404 | 78,5% [74,5–82,5] | 95,9% [95,5–96,4] | 48,8% [45,1–52,7] |
| ruído: burst_noise | com | 297 | 9 (!) | 100,0% [100,0–100,0] | 93,1% [90,1–95,9] | 31,0% [14,7–48,6] |
| ruído: burst_noise | sem | 8886 | 419 | 78,0% [73,9–82,1] | 96,1% [95,7–96,5] | 49,8% [46,0–53,7] |
| ruído: electrodes_problems | com | 13 | 1 (!) | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 427 | 78,5% [74,5–82,4] | 96,0% [95,6–96,4] | 48,9% [45,2–52,8] |
| ruído: static_noise | com | 1303 | 47 | 85,1% [73,8–95,0] | 95,2% [94,0–96,3] | 40,0% [30,5–49,1] |
| ruído: static_noise | sem | 7880 | 381 | 77,7% [73,5–82,0] | 96,1% [95,7–96,6] | 50,5% [46,7–54,6] |
| sexo | F | 4264 | 179 | 77,7% [71,6–83,7] | 98,0% [97,6–98,5] | 63,5% [56,9–69,9] |
| sexo | M | 4919 | 249 | 79,1% [74,2–84,0] | 94,2% [93,6–94,9] | 42,2% [37,7–46,8] |

**STD**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 732 | 56,6% [53,1–60,2] | 82,5% [81,7–83,3] | 21,9% [20,0–23,8] |
| aparelho | AT-6     6 | 1044 | 227 | 59,5% [53,1–65,9] | 88,1% [85,8–90,2] | 58,2% [51,5–64,5] |
| aparelho | AT-6 C 5.5 | 1686 | 369 | 55,0% [50,0–59,9] | 89,4% [87,7–91,0] | 59,4% [53,9–64,4] |
| aparelho | AT-6 C 5.8 | 378 | 96 | 58,3% [47,8–68,4] | 86,9% [82,8–90,8] | 60,2% [50,0–69,9] |
| aparelho | CS-12 | 1549 | 22 | 50,0% [29,2–72,0] | 80,2% [78,2–82,1] | 3,5% [1,6–5,6] |
| aparelho | CS-12   E | 810 | 0 | - | 96,5% [95,2–97,8] | 0,0% [0,0–0,0] |
| aparelho | CS100    3 | 3175 | 0 | - | 75,5% [74,0–76,9] | 0,0% [0,0–0,0] |
| aparelho | other | 541 | 18 | 50,0% [26,7–73,3] | 81,1% [77,8–84,4] | 8,3% [3,7–13,8] |
| idade | 40-65 | 3945 | 126 | 46,0% [37,4–54,9] | 85,4% [84,2–86,5] | 9,4% [7,1–11,9] |
| idade | <40 | 978 | 9 (!) | 55,6% [20,0–88,9] | 93,4% [91,8–94,9] | 7,2% [1,5–13,7] |
| idade | >65 | 4260 | 597 | 58,8% [54,9–62,7] | 76,6% [75,2–77,9] | 29,0% [26,6–31,6] |
| ruído: baseline_drift | com | 591 | 43 | 60,5% [45,8–75,0] | 85,8% [83,0–88,6] | 25,0% [16,8–33,3] |
| ruído: baseline_drift | sem | 8592 | 689 | 56,3% [52,7–60,0] | 82,3% [81,4–83,1] | 21,7% [19,9–23,7] |
| ruído: burst_noise | com | 297 | 10 | 70,0% [40,0–100,0] | 80,1% [75,4–84,5] | 10,9% [3,7–19,2] |
| ruído: burst_noise | sem | 8886 | 722 | 56,4% [52,8–60,0] | 82,6% [81,8–83,4] | 22,2% [20,4–24,3] |
| ruído: electrodes_problems | com | 13 | 2 (!) | 50,0% [0,0–100,0] | 81,8% [55,6–100,0] | 33,3% [0,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 730 | 56,6% [53,1–60,2] | 82,5% [81,7–83,3] | 21,8% [20,0–23,8] |
| ruído: static_noise | com | 1303 | 19 | 52,6% [30,0–75,0] | 77,9% [75,7–80,1] | 3,4% [1,5–5,7] |
| ruído: static_noise | sem | 7880 | 713 | 56,7% [53,0–60,3] | 83,3% [82,5–84,2] | 25,2% [23,2–27,5] |
| sexo | F | 4264 | 450 | 57,3% [52,8–62,0] | 81,5% [80,3–82,7] | 26,8% [24,0–29,6] |
| sexo | M | 4919 | 282 | 55,3% [49,5–60,9] | 83,3% [82,1–84,4] | 16,7% [14,3–19,1] |

**STE_acute**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 123 | 51,2% [42,2–60,4] | 96,2% [95,8–96,6] | 15,6% [12,0–19,3] |
| aparelho | AT-6     6 | 1044 | 13 | 46,2% [18,7–75,0] | 96,6% [95,4–97,8] | 14,6% [4,8–27,5] |
| aparelho | AT-6 C 5.5 | 1686 | 8 (!) | 12,5% [0,0–41,7] | 96,2% [95,2–97,1] | 1,5% [0,0–5,2] |
| aparelho | AT-6 C 5.8 | 378 | 3 (!) | 100,0% [100,0–100,0] | 96,0% [93,9–97,9] | 16,7% [0,0–35,7] |
| aparelho | CS-12 | 1549 | 31 | 54,8% [37,5–71,9] | 96,8% [95,9–97,8] | 26,2% [15,7–37,7] |
| aparelho | CS-12   E | 810 | 2 (!) | 50,0% [0,0–100,0] | 98,6% [97,8–99,4] | 8,3% [0,0–28,6] |
| aparelho | CS100    3 | 3175 | 54 | 50,0% [37,0–63,3] | 95,5% [94,8–96,2] | 16,2% [10,9–21,8] |
| aparelho | other | 541 | 12 | 66,7% [37,5–92,3] | 94,7% [92,8–96,6] | 22,2% [8,8–36,8] |
| idade | 40-65 | 3945 | 51 | 45,1% [32,1–58,7] | 96,8% [96,2–97,3] | 15,4% [9,9–21,4] |
| idade | <40 | 978 | 0 | - | 97,2% [96,2–98,2] | 0,0% [0,0–0,0] |
| idade | >65 | 4260 | 72 | 55,6% [43,4–67,1] | 95,5% [94,9–96,1] | 17,5% [12,4–22,6] |
| ruído: baseline_drift | com | 591 | 9 (!) | 33,3% [0,0–66,7] | 97,4% [96,0–98,6] | 16,7% [0,0–36,4] |
| ruído: baseline_drift | sem | 8592 | 114 | 52,6% [43,8–61,9] | 96,2% [95,7–96,6] | 15,5% [12,1–19,4] |
| ruído: burst_noise | com | 297 | 5 (!) | 40,0% [0,0–100,0] | 97,3% [95,2–99,0] | 20,0% [0,0–50,0] |
| ruído: burst_noise | sem | 8886 | 118 | 51,7% [42,9–60,7] | 96,2% [95,8–96,6] | 15,5% [11,9–19,3] |
| ruído: electrodes_problems | com | 13 | 0 | - | 92,3% [76,9–100,0] | 0,0% [0,0–0,0] |
| ruído: electrodes_problems | sem | 9170 | 123 | 51,2% [42,2–60,4] | 96,2% [95,8–96,6] | 15,6% [12,1–19,4] |
| ruído: static_noise | com | 1303 | 25 | 56,0% [36,4–75,0] | 97,0% [96,1–98,0] | 26,9% [15,1–40,0] |
| ruído: static_noise | sem | 7880 | 98 | 50,0% [39,5–59,8] | 96,1% [95,7–96,5] | 13,9% [10,2–17,7] |
| sexo | F | 4264 | 47 | 59,6% [45,3–73,8] | 96,6% [96,1–97,2] | 16,5% [11,2–21,9] |
| sexo | M | 4919 | 76 | 46,1% [34,5–57,3] | 95,9% [95,3–96,4] | 15,0% [10,3–19,8] |

**LVH**

| dimensão | nível | N | N pos | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] |
|---|---|---|---|---|---|---|
| todos | todos | 9183 | 1156 | 72,7% [70,0–75,3] | 86,8% [86,1–87,6] | 44,3% [42,1–46,5] |
| aparelho | AT-6     6 | 1044 | 132 | 66,7% [58,6–75,4] | 85,7% [83,4–88,0] | 40,4% [33,7–47,2] |
| aparelho | AT-6 C 5.5 | 1686 | 271 | 77,5% [72,5–82,4] | 86,1% [84,4–87,9] | 51,7% [47,3–56,7] |
| aparelho | AT-6 C 5.8 | 378 | 51 | 58,8% [45,6–72,1] | 83,2% [79,0–87,1] | 35,3% [25,0–45,3] |
| aparelho | CS-12 | 1549 | 115 | 78,3% [70,5–85,6] | 90,4% [88,9–91,9] | 39,6% [33,2–45,9] |
| aparelho | CS-12   E | 810 | 14 | 64,3% [37,5–90,0] | 96,5% [95,2–97,7] | 24,3% [11,1–39,5] |
| aparelho | CS100    3 | 3175 | 520 | 71,5% [67,8–75,4] | 83,1% [81,6–84,5] | 45,3% [42,0–48,8] |
| aparelho | other | 541 | 53 | 77,4% [64,8–88,1] | 87,1% [84,3–89,8] | 39,4% [30,2–48,6] |
| idade | 40-65 | 3945 | 437 | 70,9% [66,7–75,1] | 89,3% [88,3–90,4] | 45,3% [41,7–49,1] |
| idade | <40 | 978 | 50 | 66,0% [53,1–78,7] | 95,2% [93,7–96,4] | 42,3% [31,6–53,6] |
| idade | >65 | 4260 | 669 | 74,3% [70,9–77,6] | 82,2% [80,9–83,5] | 43,8% [40,8–46,7] |
| ruído: baseline_drift | com | 591 | 45 | 80,0% [67,9–90,9] | 88,3% [85,6–90,9] | 36,0% [26,7–45,5] |
| ruído: baseline_drift | sem | 8592 | 1111 | 72,4% [69,6–75,1] | 86,7% [85,9–87,5] | 44,7% [42,5–47,1] |
| ruído: burst_noise | com | 297 | 37 | 78,4% [64,7–91,2] | 88,5% [84,3–92,3] | 49,2% [36,7–62,3] |
| ruído: burst_noise | sem | 8886 | 1119 | 72,5% [69,7–75,1] | 86,8% [86,0–87,5] | 44,1% [41,9–46,6] |
| ruído: electrodes_problems | com | 13 | 1 (!) | 100,0% [100,0–100,0] | 75,0% [50,0–100,0] | 25,0% [0,0–100,0] |
| ruído: electrodes_problems | sem | 9170 | 1155 | 72,6% [70,0–75,3] | 86,8% [86,1–87,6] | 44,3% [42,2–46,6] |
| ruído: static_noise | com | 1303 | 149 | 65,1% [57,7–73,0] | 88,6% [86,7–90,6] | 42,5% [36,1–49,0] |
| ruído: static_noise | sem | 7880 | 1007 | 73,8% [71,1–76,6] | 86,5% [85,7–87,3] | 44,5% [42,2–46,9] |
| sexo | F | 4264 | 481 | 75,1% [71,0–78,8] | 84,8% [83,7–86,0] | 38,6% [35,6–41,8] |
| sexo | M | 4919 | 675 | 71,0% [67,5–74,4] | 88,6% [87,6–89,5] | 49,7% [46,5–52,9] |

## Regras de gold e limitações

- Gold diagnóstico = códigos SCP do ptbxl_database.csv com verossimilhança >= 50 ou 0 (declarações não diagnósticas); todo o resto é negativo (especificidade/VPP são limites inferiores; rótulos PTB-XL são ruidosos).
- **STE_**: declaração SCP, anotada de forma inconsistente no PTB-XL (mantida como gold 'STE').
- **STE_acute** (novo): qualquer código de infarto (IMI, AMI, ASMI, ILMI, ALMI, INJAS, LMI, INJAL, IPLMI, IPMI, INJIN, INJLA, PMI, INJIL, MI) com infarction_stadium1 em {'Stadium I', 'Stadium I-II'}. A predição é a mesma de STE (qualquer ecg.st_elevation_*).
- Subgrupos: sexo (0=M, 1=F), idade (<40, 40–65, >65; 300 = '>89' entra em >65), aparelho (6 mais frequentes + other), flags de ruído do PTB-XL (texto não vazio em baseline_drift, static_noise, burst_noise, electrodes_problems = 'com').
- Medidas: PTB-XL+ 1.0.1, algoritmo 12SL (não é padrão-ouro humano).
- IC95% = bootstrap percentil por registro (2000 reamostras, semente fixa). Com 0 (ou todos) acertos em n pequeno o intervalo degenera em [0,0–0,0]: nesses casos ler como limite superior ~3/n (regra dos três), não como certeza.
- Tempo: a execução R2base levou 3723 s com --workers 3 numa máquina compartilhada (carga média ~100); mediana 0,68 s/registro por worker.
- RX (IU dev): **os metadados do IU X-Ray só trazem PA/LATERAL (incidência frontal por ordem/legenda, sem DICOM ViewPosition): não há distinção AP vs PA, portanto não há tabela por incidência AP/PA.**
