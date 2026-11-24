# ECG benchmark results

_Generated 2026-11-24 11:42 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Delineation: QRS on/off within CSE tol | 32% / 57% | LUDB, 200 records |
| Delineation: P onset / T offset within CSE tol | 51% / 55% | LUDB, 200 records |
| Detection sensitivity QRS / P / T | 99% / 66% / 91% | LUDB, 21843 beats |
| Diagnosis AF: sens / spec / PPV | 41% / 99% / 77% | PTB-XL, 3000 recs (314 pos) |
| Diagnosis AV1: sens / spec / PPV | 39% / 74% / 10% | PTB-XL, 3000 recs (210 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 70% / 83% / 21% | PTB-XL, 3000 recs (178 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 0% / 100% / 0% | PTB-XL, 3000 recs (113 pos) |
| Diagnosis LVH: sens / spec / PPV | 82% / 68% / 17% | PTB-XL, 3000 recs (228 pos) |
| Diagnosis MI_any: sens / spec / PPV | 32% / 88% / 51% | PTB-XL, 3000 recs (840 pos) |
| Diagnosis STACH: sens / spec / PPV | 50% / 98% / 67% | PTB-XL, 3000 recs (183 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 78% / 92% / 29% | PTB-XL, 3000 recs (118 pos) |
| NORM -> within normal limits; abnormal flagged | 19.0% (98/515); 96.3% (2393/2485) | PTB-XL, 3000 records |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

**Sources with no results in this run** (manifest missing/empty or dataset not downloadable): litfl, wikimedia_ecg, ecglibrary, ecg_image_db.

## LUDB: wave delineation vs cardiologist annotations

200 records analysed (0 failed), 2396 record-leads; annotated beats 21843, P waves 16780, T waves 19538.  Timing: median 0.44 s, p95 0.86 s, max 3.9 s per record (N=200).

### Fiducial-point error vs cardiologist annotation (per lead, per matched beat)

| Fiducial | N matched | error ours-gold, mean ± SD (ms) | median \|err\| (ms) | CSE 2SD tol | within tol | within 2x tol |
|---|---|---|---|---|---|---|
| P onset | 11082 | -0.3 ± 27.1 | 10.0 | ±10.2 | 50.7% (5624/11082) | 77.5% (8585/11082) |
| P offset | 11082 | -3.2 ± 22.0 | 8.0 | ±12.7 | 64.6% (7160/11082) | 84.4% (9353/11082) |
| QRS onset | 21647 | +7.2 ± 16.5 | 12.0 | ±6.5 | 32.1% (6951/21647) | 55.0% (11908/21647) |
| QRS offset | 21647 | -5.3 ± 23.9 | 10.0 | ±11.6 | 56.7% (12268/21647) | 83.1% (17981/21647) |
| T offset | 17742 | +44.0 ± 82.3 | 24.0 | ±30.6 | 55.5% (9838/17742) | 68.1% (12082/17742) |

Tolerances: CSE 2-SD values (P on 10.2, P off 12.7, QRS on 6.5, QRS off 11.6, T off 30.6 ms) — Willems et al., _Methods Inf Med_ 1990;29:263; Martinez et al., _IEEE TBME_ 2004;51:570. Note: LUDB annotators place the QRS 'N' on the dominant deflection; error sign = ours - gold.

### Wave detection

| Wave | Sensitivity (detected / annotated) | PPV (correct / ours, matched beats) |
|---|---|---|
| QRS (beat match R ±75 ms) | 99.2% (21659/21843) | 99.0% (21659/21880) |
| P wave | 66.0% (11082/16780) | 76.7% (11082/14455) |
| T wave | 90.8% (17742/19538) | 88.2% (17742/20122) |

P/T counted detected when our peak lies within the annotated wave ±30 ms (P) / ±50 ms (T). PPV counts our waves in beats matched to an annotated beat.

### Global intervals (our median beat vs annotation: earliest onset / latest offset across leads, median over beats)

| Global interval | N records | error ours-gold mean ± SD | median \|err\| | within tolerance | Pearson r |
|---|---|---|---|---|---|
| PR | 155 | +1.7 ± 35.4 | 12.0 | 68.4% (106/155) (\|err\|<=20) | 0.60 |
| QRS | 200 | +33.2 ± 77.4 | 20.5 | 50.0% (100/200) (\|err\|<=20) | 0.38 |
| QT | 197 | +83.6 ± 87.3 | 106.0 | 23.9% (47/197) (\|err\|<=30) | 0.35 |
| HR (bpm) | 200 | +0.1 ± 2.6 | 0.4 | 94.5% (189/200) (\|err\|<=5) | 0.98 |

### Per-lead mean ± SD error (ms)

| Lead | P on | P off | QRS on | QRS off | T off |
|---|---|---|---|---|---|
| I | -0.8 ± 24.7 | -6.2 ± 17.4 | +1.4 ± 16.1 | +0.3 ± 28.9 | +32.4 ± 73.2 |
| II | +2.6 ± 21.6 | -7.5 ± 17.6 | +4.9 ± 16.3 | -2.4 ± 22.8 | +61.0 ± 89.6 |
| III | +1.3 ± 29.6 | -1.7 ± 26.7 | +1.7 ± 19.5 | -4.0 ± 27.9 | +36.2 ± 80.4 |
| aVR | +0.9 ± 20.9 | -6.5 ± 16.6 | +1.7 ± 18.6 | -0.6 ± 26.4 | +58.5 ± 87.9 |
| aVL | +0.9 ± 29.7 | -4.1 ± 24.3 | -0.4 ± 18.3 | +1.2 ± 29.8 | +21.0 ± 64.5 |
| aVF | +0.0 ± 23.1 | -5.0 ± 21.5 | +3.0 ± 16.6 | -3.2 ± 26.1 | +55.8 ± 85.6 |
| V1 | +5.4 ± 35.5 | +10.9 ± 30.5 | +8.0 ± 14.5 | -1.9 ± 17.6 | +32.8 ± 86.8 |
| V2 | -8.8 ± 32.5 | -0.2 ± 25.7 | +12.3 ± 12.5 | -5.4 ± 16.2 | +45.9 ± 81.3 |
| V3 | -3.6 ± 27.8 | -2.0 ± 21.7 | +14.4 ± 12.0 | -7.7 ± 14.8 | +46.5 ± 82.8 |
| V4 | -1.5 ± 24.9 | -3.9 ± 16.8 | +15.8 ± 12.0 | -13.1 ± 20.5 | +43.3 ± 79.8 |
| V5 | -3.3 ± 27.8 | -4.4 ± 18.2 | +13.7 ± 13.0 | -14.1 ± 21.5 | +47.0 ± 82.2 |
| V6 | -3.4 ± 25.7 | -4.0 ± 17.4 | +10.3 ± 13.1 | -12.5 ± 21.3 | +45.3 ± 81.3 |

### Worst examples

| Criterion | Worst record ids (mean \|err\|) |
|---|---|
| QRS onset | ludb-93 (56 ms), ludb-111 (47 ms), ludb-90 (32 ms), ludb-8 (32 ms), ludb-74 (31 ms) |
| QRS offset | ludb-74 (136 ms), ludb-45 (121 ms), ludb-34 (97 ms), ludb-104 (77 ms), ludb-72 (49 ms) |
| P onset | ludb-42 (123 ms), ludb-130 (54 ms), ludb-5 (51 ms), ludb-31 (48 ms), ludb-48 (44 ms) |
| T offset | ludb-153 (145 ms), ludb-176 (142 ms), ludb-15 (140 ms), ludb-63 (139 ms), ludb-174 (136 ms) |
| lowest QRS detection | ludb-116, ludb-111, ludb-74, ludb-83, ludb-45 |

### Diagnosis agreement with LUDB header statements (small N, indicative only)

LUDB header statements are free-text from the cardiologist (e.g. 'left ventricular hypertrophy' is attached to >50% of records, mostly without voltage criteria; median Sokolow-Lyon here is ~1.3 mV), so low sensitivity for LVH/LAFB mostly reflects label definition, not necessarily detector error.

| Class | N pos | Sens % [CI] | Spec % [CI] | PPV % [CI] | Missed ids |
|---|---|---|---|---|---|
| LVH | 108 | 0 [0-3] | 100 [96-100] | - | ludb-1, ludb-2, ludb-4, ludb-6 |
| STTC | 37 | 54 [38-69] | 87 [80-91] | 48 [33-62] | ludb-4, ludb-6, ludb-3, ludb-13 |
| RBBB_any | 33 | 82 [66-91] | 48 [40-55] | 24 [17-32] | ludb-78, ludb-77, ludb-99, ludb-117 |
| SBRAD | 25 | 56 [37-73] | 93 [88-96] | 52 [34-69] | ludb-6, ludb-24, ludb-41, ludb-39 |
| LAFB | 16 | 0 [0-19] | 100 [98-100] | - | ludb-21, ludb-26, ludb-46, ludb-51 |
| AF | 15 | 40 [20-64] | 98 [95-99] | 60 [31-83] | ludb-8, ludb-38, ludb-83, ludb-88 |
| AV1 | 10 | 50 [24-76] | 90 [85-94] | 21 [9-40] | ludb-15, ludb-20, ludb-61, ludb-120 |
| LBBB_any | 10 | 10 [2-40] | 100 [98-100] | 100 [21-100] | ludb-13, ludb-24, ludb-44, ludb-51 |
| AV3 | 5 | 0 [0-43] | 99 [97-100] | 0 [0-79] | ludb-34, ludb-74, ludb-90, ludb-104 |
| STACH | 4 | 0 [0-49] | 100 [98-100] | - | ludb-70, ludb-114, ludb-117, ludb-188 |
| RVH | 3 | 0 [0-56] | 100 [98-100] | - | ludb-17, ludb-35, ludb-51 |

## PTB-XL: diagnostic statements

3000 records analysed (0 failed). Timing: median 0.57 s, p95 1.10 s, max 8.0 s per record (N=3000). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens % [95% CI] | Spec % [95% CI] | PPV % [95% CI] (this sample) | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 314 | 129 | 39 | 41 [36-47] | 99 [98-99] | 77 [70-83] | 68 (prev 6.9%) | 0.54 |
| AV1 | 1st-degree AV block (1AVB) | 210 | 82 | 713 | 39 [33-46] | 74 [73-76] | 10 [8-13] | 5 (prev 3.6%) | 0.16 |
| AV2 | 2nd-degree AV block (2AVB) | 14 | 1 | 281 | 7 [1-31] | 91 [89-92] | 0 [0-2] | 0 (prev 0.1%) | 0.01 |
| AV3 | 3rd-degree AV block (3AVB) | 16 | 0 | 10 | 0 [0-19] | 100 [99-100] | 0 [0-28] | 0 (prev 0.1%) | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 178 | 125 | 477 | 70 [63-76] | 83 [82-84] | 21 [18-24] | 10 (prev 2.5%) | 0.32 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 229 | 49 | 216 | 21 [17-27] | 92 [91-93] | 18 [14-24] | 13 (prev 5.1%) | 0.20 |
| RBBB_any | RBBB any | 406 | 246 | 621 | 61 [56-65] | 76 [74-78] | 28 [25-31] | 17 (prev 7.6%) | 0.39 |
| LBBB_complete | complete LBBB (CLBBB) | 113 | 0 | 2 | 0 [0-3] | 100 [100-100] | 0 [0-66] | 0 (prev 2.5%) | 0.00 |
| LBBB_any | LBBB any | 189 | 1 | 16 | 1 [0-3] | 99 [99-100] | 6 [1-27] | 3 (prev 2.8%) | 0.01 |
| LAFB | left anterior fascicular block | 252 | 52 | 17 | 21 [16-26] | 99 [99-100] | 75 [64-84] | 73 (prev 7.4%) | 0.32 |
| LPFB | left posterior fascicular block | 115 | 29 | 24 | 25 [18-34] | 99 [99-99] | 55 [41-67] | 20 (prev 0.8%) | 0.35 |
| WPW | WPW | 79 | 7 | 7 | 9 [4-17] | 100 [100-100] | 50 [27-73] | 12 (prev 0.4%) | 0.15 |
| LVH | left ventricular hypertrophy | 228 | 187 | 894 | 82 [77-86] | 68 [66-69] | 17 [15-20] | 18 (prev 8.0%) | 0.29 |
| RVH | right ventricular hypertrophy | 90 | 18 | 95 | 20 [13-29] | 97 [96-97] | 16 [10-24] | 3 (prev 0.5%) | 0.18 |
| LAE | left atrial enlargement | 123 | 52 | 871 | 42 [34-51] | 70 [68-71] | 6 [4-7] | 3 (prev 1.9%) | 0.10 |
| RAE | right atrial enlargement | 98 | 61 | 50 | 62 [52-71] | 98 [98-99] | 55 [46-64] | 14 (prev 0.4%) | 0.58 |
| LQT | long QT (LNGQT) | 100 | 92 | 1405 | 92 [85-96] | 52 [50-53] | 6 [5-7] | 1 (prev 0.5%) | 0.12 |
| SBRAD | sinus bradycardia | 118 | 92 | 224 | 78 [70-84] | 92 [91-93] | 29 [24-34] | 23 (prev 2.9%) | 0.42 |
| STACH | sinus tachycardia | 183 | 92 | 45 | 50 [43-57] | 98 [98-99] | 67 [59-74] | 55 (prev 3.8%) | 0.57 |
| SR | sinus rhythm | 1909 | 1119 | 109 | 59 [56-61] | 90 [88-92] | 91 [89-93] | 95 (prev 76.8%) | 0.71 |
| MI_any | any MI (Q waves or ST elevation) | 840 | 271 | 262 | 32 [29-35] | 88 [86-89] | 51 [47-55] | 38 (prev 19.0%) | 0.39 |
| MI_inferior | inferior MI (IMI etc.) | 413 | 77 | 125 | 19 [15-23] | 95 [94-96] | 38 [32-45] | 31 (prev 10.3%) | 0.25 |
| MI_anterior | anterior/anteroseptal MI | 510 | 167 | 217 | 33 [29-37] | 91 [90-92] | 43 [39-48] | 33 (prev 11.7%) | 0.37 |
| MI_lateral | lateral MI | 294 | 61 | 64 | 21 [17-26] | 98 [97-98] | 49 [40-57] | 26 (prev 3.9%) | 0.29 |
| STTC | ST/T change (any) | 1077 | 682 | 692 | 63 [60-66] | 64 [62-66] | 50 [47-52] | 36 (prev 24.5%) | 0.56 |
| STE | ST elevation (STE_) | 28 | 2 | 343 | 7 [2-23] | 88 [87-90] | 1 [0-2] | 0 (prev 0.1%) | 0.01 |
| STD | ST depression (STD_) | 260 | 185 | 898 | 71 [65-76] | 67 [65-69] | 17 [15-19] | 10 (prev 4.6%) | 0.28 |
| LOWV | low voltage (LVOLT) | 100 | 13 | 90 | 13 [8-21] | 97 [96-97] | 13 [8-20] | 3 (prev 0.8%) | 0.13 |
| NORM | NORM | 515 | 98 | 35 | 19 [16-23] | 99 [98-99] | 74 [66-80] | 91 (prev 43.3%) | 0.30 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 370 | 132 | 36 | 36 [31-41] | 99 [98-99] | 79 [72-84] | 67 (prev 7.2%) | 0.49 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 19.0% [15.9-22.6] (n=515) |
| gold NORM -> we raise >=1 abnormal/critical finding | 68.2% [64.0-72.0] (n=515) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 81.0% [77.4-84.1] (n=515) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 96.3% [95.5-97.0] (n=2485) |
| gold non-NORM -> we say within normal limits (missed) | 1.4% [1.0-2.0] (n=2485) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 1909 | 74 (59-92) | 85.1% (1624/1909) in 60-100 bpm |
| STACH | 183 | 109 (102-124) | 96.7% (177/183) in 100-+ bpm |
| SBRAD | 118 | 49 (42-57) | 95.8% (113/118) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 801 | 408 | 387 | 6 |
| normal | 754 | 5 | 711 | 38 |
| right | 137 | 20 | 13 | 104 |

Axis category agreement: 72.3% [70.1-74.4] (n=1692) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> BIGU:19, PVC:14, SR:9, ISC_:5 | FN our findings -> non_sinus_p:124, lvh:89, long_qt:79, st_depression_lateral:77 |
| AV1 | FP gold labels -> SR:525, NORM:144, ABQRS:107, ASMI:70 | FN our findings -> long_qt:83, non_sinus_p:62, lvh:49, st_depression_lateral:33 |
| AV2 | FP gold labels -> SR:224, ABQRS:57, NORM:53, ASMI:34 | FN our findings -> long_qt:5, non_sinus_p:5, lvh:4, st_depression_inferior:4 |
| AV3 | FP gold labels -> SR:4, IRBBB:2, WPW:2, ASMI:2 | FN our findings -> long_qt:13, non_sinus_p:7, lvh:6, rbbb:6 |
| RBBB_complete | FP gold labels -> SR:277, CLBBB:105, ABQRS:90, PACE:72 | FN our findings -> rvh:49, long_qt:36, ivcd:35, left_axis_deviation:27 |
| RBBB_incomplete | FP gold labels -> SR:150, NORM:40, ABQRS:39, STD_:28 | FN our findings -> long_qt:99, sinus_rhythm:75, rbbb:71, lae:59 |
| RBBB_any | FP gold labels -> SR:381, ABQRS:117, CLBBB:105, PACE:72 | FN our findings -> long_qt:83, sinus_rhythm:57, rvh:57, lae:53 |
| LBBB_complete | FP gold labels -> IVCD:1, SR:1, ASMI:1, ILBBB:1 | FN our findings -> rbbb:105, lvh:98, st_depression_lateral:84, long_qt:82 |
| LBBB_any | FP gold labels -> SR:8, NDT:4, NORM:3, LOWT:3 | FN our findings -> rbbb:146, lvh:144, st_depression_lateral:126, long_qt:124 |
| LAFB | FP gold labels -> SR:9, ABQRS:6, ALMI:4, STACH:4 | FN our findings -> left_axis_deviation:188, long_qt:127, lvh:100, sinus_rhythm:86 |
| LPFB | FP gold labels -> SR:11, NORM:5, ABQRS:4, AFIB:4 | FN our findings -> right_axis_deviation:70, long_qt:49, rbbb:43, sinus_rhythm:29 |
| WPW | FP gold labels -> SR:4, IRBBB:3, ISCAL:1, ISCIN:1 | FN our findings -> long_qt:56, lvh:44, rbbb:42, sinus_rhythm:30 |
| LVH | FP gold labels -> SR:513, ABQRS:157, ASMI:144, LAFB:125 | FN our findings -> st_depression_lateral:21, long_qt:20, t_inversion_lateral:11, av_block_1:11 |
| RVH | FP gold labels -> SR:49, CRBBB:46, LPFB:27, ABQRS:24 | FN our findings -> rbbb:63, long_qt:55, sinus_rhythm:40, left_axis_deviation:29 |
| LAE | FP gold labels -> SR:677, NORM:158, ABQRS:141, LAFB:97 | FN our findings -> long_qt:41, lvh:32, sinus_rhythm:30, st_depression_lateral:23 |
| RAE | FP gold labels -> SR:26, ABQRS:11, STACH:11, ASMI:8 | FN our findings -> long_qt:23, sinus_rhythm:20, lvh:14, left_axis_deviation:11 |
| LQT | FP gold labels -> SR:923, ABQRS:273, ASMI:204, LAFB:146 | FN our findings -> st_depression_lateral:5, lvh:3, rae:2, st_depression_inferior:2 |
| SBRAD | FP gold labels -> SR:198, NORM:62, ABQRS:36, IRBBB:20 | FN our findings -> irregular_rhythm:10, lvh:9, av_block_1:9, long_qt:8 |
| STACH | FP gold labels -> SR:18, AFLT:12, ABQRS:8, NST_:7 | FN our findings -> long_qt:45, non_sinus_p:39, st_depression_lateral:35, lvh:34 |
| SR | FP gold labels -> SARRH:41, NORM:25, PACE:15, ASMI:14 | FN our findings -> long_qt:427, lvh:283, lae:267, sinus_bradycardia:198 |
| MI_any | FP gold labels -> SR:114, CLBBB:87, PACE:74, ABQRS:26 | FN our findings -> long_qt:325, sinus_rhythm:220, lvh:192, lae:178 |
| MI_inferior | FP gold labels -> PACE:50, SR:43, ABQRS:23, WPW:17 | FN our findings -> long_qt:202, sinus_rhythm:130, left_axis_deviation:111, lvh:104 |
| MI_anterior | FP gold labels -> SR:101, CLBBB:85, PACE:56, LVH:24 | FN our findings -> long_qt:197, lvh:137, sinus_rhythm:131, lae:105 |
| MI_lateral | FP gold labels -> PACE:38, SR:17, ABQRS:11, CRBBB:7 | FN our findings -> long_qt:141, sinus_rhythm:99, lvh:93, left_axis_deviation:75 |
| STTC | FP gold labels -> SR:340, ABQRS:163, ASMI:131, CLBBB:102 | FN our findings -> long_qt:219, sinus_rhythm:187, lae:143, lvh:110 |
| STE | FP gold labels -> SR:166, CLBBB:85, ASMI:74, PACE:65 | FN our findings -> sinus_rhythm:13, lvh:8, lae:8, long_qt:6 |
| STD | FP gold labels -> SR:432, ABQRS:192, AFIB:163, ASMI:121 | FN our findings -> long_qt:41, lae:32, sinus_rhythm:32, lvh:27 |
| LOWV | FP gold labels -> SR:44, ABQRS:29, ASMI:26, AFIB:23 | FN our findings -> sinus_rhythm:47, long_qt:38, lae:33, av_block_1:32 |
| NORM | FP gold labels -> SR:32, ABQRS:8, IMI:5, NDT:4 | FN our findings -> sinus_rhythm:176, lae:158, av_block_1:148, sinus_bradycardia:97 |
| AF_AFL | FP gold labels -> BIGU:19, PVC:14, SR:9, ISC_:5 | FN our findings -> non_sinus_p:150, lvh:114, st_depression_lateral:98, long_qt:83 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-10360, ptbxl-11418, ptbxl-16757, ptbxl-19210, ptbxl-01184 | ptbxl-13069, ptbxl-13698, ptbxl-13849, ptbxl-14671, ptbxl-15447 |
| AV1 | ptbxl-10130, ptbxl-10131, ptbxl-10203, ptbxl-10283, ptbxl-10336 | ptbxl-10982, ptbxl-11397, ptbxl-12221, ptbxl-12223, ptbxl-13246 |
| AV2 | ptbxl-10297, ptbxl-10296, ptbxl-10518, ptbxl-11474, ptbxl-11802 | ptbxl-16401, ptbxl-19164, ptbxl-01222, ptbxl-03505, ptbxl-09136 |
| AV3 | ptbxl-14493, ptbxl-21819, ptbxl-13415, ptbxl-21201, ptbxl-00706 | ptbxl-11500, ptbxl-00959, ptbxl-02047, ptbxl-04827, ptbxl-04838 |
| RBBB_complete | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10301, ptbxl-10395 | ptbxl-10982, ptbxl-11045, ptbxl-11963, ptbxl-13112, ptbxl-13698 |
| RBBB_incomplete | ptbxl-15892, ptbxl-17961, ptbxl-10045, ptbxl-10309, ptbxl-10388 | ptbxl-10203, ptbxl-10489, ptbxl-10518, ptbxl-10965, ptbxl-11020 |
| RBBB_any | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10301, ptbxl-10395 | ptbxl-10203, ptbxl-10489, ptbxl-10982, ptbxl-11020, ptbxl-11045 |
| LBBB_complete | ptbxl-11180, ptbxl-20077 | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10395, ptbxl-11418 |
| LBBB_any | ptbxl-18398, ptbxl-10076, ptbxl-11180, ptbxl-13696, ptbxl-15603 | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10301, ptbxl-10395 |
| LAFB | ptbxl-14671, ptbxl-12665, ptbxl-16340, ptbxl-17976, ptbxl-19545 | ptbxl-10888, ptbxl-10982, ptbxl-11397, ptbxl-11500, ptbxl-11527 |
| LPFB | ptbxl-10769, ptbxl-11343, ptbxl-16938, ptbxl-21023, ptbxl-21792 | ptbxl-11045, ptbxl-13069, ptbxl-13112, ptbxl-13962, ptbxl-14678 |
| WPW | ptbxl-13248, ptbxl-11506, ptbxl-12391, ptbxl-12761, ptbxl-14311 | ptbxl-10053, ptbxl-10246, ptbxl-10266, ptbxl-10822, ptbxl-10869 |
| LVH | ptbxl-10003, ptbxl-10130, ptbxl-10283, ptbxl-10297, ptbxl-10296 | ptbxl-17351, ptbxl-10115, ptbxl-10753, ptbxl-11132, ptbxl-11235 |
| RVH | ptbxl-10982, ptbxl-11045, ptbxl-11963, ptbxl-12138, ptbxl-13112 | ptbxl-10518, ptbxl-18417, ptbxl-10218, ptbxl-10279, ptbxl-10136 |
| LAE | ptbxl-10131, ptbxl-10297, ptbxl-10296, ptbxl-10395, ptbxl-10359 | ptbxl-11020, ptbxl-11397, ptbxl-11441, ptbxl-13908, ptbxl-14116 |
| RAE | ptbxl-14729, ptbxl-17937, ptbxl-10943, ptbxl-11916, ptbxl-12410 | ptbxl-10236, ptbxl-11025, ptbxl-11123, ptbxl-11869, ptbxl-12342 |
| LQT | ptbxl-10130, ptbxl-10131, ptbxl-10283, ptbxl-10292, ptbxl-10336 | ptbxl-12410, ptbxl-13838, ptbxl-15617, ptbxl-18520, ptbxl-00260 |
| SBRAD | ptbxl-10003, ptbxl-10359, ptbxl-10695, ptbxl-11797, ptbxl-11834 | ptbxl-18108, ptbxl-10266, ptbxl-11331, ptbxl-11959, ptbxl-12216 |
| STACH | ptbxl-13094, ptbxl-13853, ptbxl-18916, ptbxl-10752, ptbxl-12692 | ptbxl-10301, ptbxl-10826, ptbxl-11418, ptbxl-11397, ptbxl-13246 |
| SR | ptbxl-11527, ptbxl-13404, ptbxl-14937, ptbxl-16861, ptbxl-17472 | ptbxl-10003, ptbxl-10131, ptbxl-10297, ptbxl-10395, ptbxl-10359 |
| MI_any | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10395, ptbxl-10694 | ptbxl-10826, ptbxl-11170, ptbxl-11527, ptbxl-11963, ptbxl-12221 |
| MI_inferior | ptbxl-10395, ptbxl-11397, ptbxl-11474, ptbxl-11804, ptbxl-12178 | ptbxl-10301, ptbxl-10888, ptbxl-11170, ptbxl-11963, ptbxl-13698 |
| MI_anterior | ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10395, ptbxl-10694 | ptbxl-10826, ptbxl-11527, ptbxl-12936, ptbxl-13218, ptbxl-13246 |
| MI_lateral | ptbxl-10982, ptbxl-13100, ptbxl-13820, ptbxl-13962, ptbxl-13953 | ptbxl-10888, ptbxl-11527, ptbxl-12138, ptbxl-12221, ptbxl-13698 |
| STTC | ptbxl-10003, ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10301 | ptbxl-10336, ptbxl-10661, ptbxl-12138, ptbxl-14166, ptbxl-15989 |
| STE | ptbxl-10283, ptbxl-10296, ptbxl-10301, ptbxl-10395, ptbxl-10694 | ptbxl-01596, ptbxl-01600, ptbxl-01725, ptbxl-02639, ptbxl-02886 |
| STD | ptbxl-10003, ptbxl-10130, ptbxl-10283, ptbxl-10296, ptbxl-10301 | ptbxl-13913, ptbxl-13974, ptbxl-17960, ptbxl-18121, ptbxl-10045 |
| LOWV | ptbxl-13069, ptbxl-13112, ptbxl-13222, ptbxl-14192, ptbxl-15838 | ptbxl-14033, ptbxl-14382, ptbxl-15775, ptbxl-15877, ptbxl-16175 |
| NORM | ptbxl-10828, ptbxl-11839, ptbxl-14297, ptbxl-15207, ptbxl-16281 | ptbxl-10203, ptbxl-10292, ptbxl-10297, ptbxl-10489, ptbxl-10694 |
| AF_AFL | ptbxl-10360, ptbxl-11418, ptbxl-19210, ptbxl-01184, ptbxl-02204 | ptbxl-13069, ptbxl-13094, ptbxl-13698, ptbxl-13849, ptbxl-14671 |
