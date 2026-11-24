# ECG benchmark results

_Generated 2026-11-24 12:39 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Delineation: QRS on/off within CSE tol | 39% / 59% | LUDB, 200 records |
| Delineation: P onset / T offset within CSE tol | 50% / 82% | LUDB, 200 records |
| Detection sensitivity QRS / P / T | 99% / 84% / 94% | LUDB, 21843 beats |
| Diagnosis AF: sens / spec / PPV | 85% / 96% / 74% | PTB-XL, 3000 recs (314 pos) |
| Diagnosis AV1: sens / spec / PPV | 32% / 97% / 47% | PTB-XL, 3000 recs (210 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 65% / 98% / 66% | PTB-XL, 3000 recs (178 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 66% / 96% / 37% | PTB-XL, 3000 recs (113 pos) |
| Diagnosis LVH: sens / spec / PPV | 72% / 83% / 26% | PTB-XL, 3000 recs (228 pos) |
| Diagnosis MI_any: sens / spec / PPV | 33% / 91% / 58% | PTB-XL, 3000 recs (840 pos) |
| Diagnosis STACH: sens / spec / PPV | 66% / 98% / 66% | PTB-XL, 3000 recs (183 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 59% / 99% / 74% | PTB-XL, 3000 recs (118 pos) |
| NORM -> within normal limits; abnormal flagged | 68.0% (350/515); 85.1% (2115/2485) | PTB-XL, 3000 records |
| Image pipeline usable (litfl) | 67% (exceptions 23) | N=486 |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

**Sources with no results in this run** (manifest missing/empty or dataset not downloadable): wikimedia_ecg, ecglibrary, ecg_image_db.

## LUDB: wave delineation vs cardiologist annotations

200 records analysed (0 failed), 2396 record-leads; annotated beats 21843, P waves 16780, T waves 19538.  Timing: median 0.17 s, p95 0.30 s, max 1.6 s per record (N=200).

### Fiducial-point error vs cardiologist annotation (per lead, per matched beat)

| Fiducial | N matched | error ours-gold, mean ± SD (ms) | median \|err\| (ms) | CSE 2SD tol | within tol | within 2x tol |
|---|---|---|---|---|---|---|
| P onset | 14078 | -0.7 ± 28.3 | 10.0 | ±10.2 | 50.0% (7040/14078) | 75.0% (10558/14078) |
| P offset | 14078 | -1.5 ± 22.8 | 10.0 | ±12.7 | 62.8% (8843/14078) | 82.7% (11643/14078) |
| QRS onset | 21647 | +3.2 ± 16.3 | 10.0 | ±6.5 | 39.2% (8491/21647) | 63.5% (13739/21647) |
| QRS offset | 21647 | +0.6 ± 22.1 | 8.0 | ±11.6 | 59.2% (12809/21647) | 84.0% (18187/21647) |
| T offset | 18290 | -4.2 ± 36.4 | 14.0 | ±30.6 | 82.2% (15037/18290) | 92.7% (16949/18290) |

Tolerances: CSE 2-SD values (P on 10.2, P off 12.7, QRS on 6.5, QRS off 11.6, T off 30.6 ms) — Willems et al., _Methods Inf Med_ 1990;29:263; Martinez et al., _IEEE TBME_ 2004;51:570. Note: LUDB annotators place the QRS 'N' on the dominant deflection; error sign = ours - gold.

### Wave detection

| Wave | Sensitivity (detected / annotated) | PPV (correct / ours, matched beats) |
|---|---|---|
| QRS (beat match R ±75 ms) | 99.2% (21659/21843) | 99.0% (21659/21880) |
| P wave | 83.9% (14078/16780) | 78.6% (14078/17917) |
| T wave | 93.6% (18290/19538) | 88.1% (18290/20762) |

P/T counted detected when our peak lies within the annotated wave ±30 ms (P) / ±50 ms (T). PPV counts our waves in beats matched to an annotated beat.

### Global intervals (our median beat vs annotation: earliest onset / latest offset across leads, median over beats)

| Global interval | N records | error ours-gold mean ± SD | median \|err\| | within tolerance | Pearson r |
|---|---|---|---|---|---|
| PR | 170 | +0.2 ± 34.4 | 11.5 | 66.5% (113/170) (\|err\|<=20) | 0.68 |
| QRS | 200 | -5.9 ± 30.8 | 22.0 | 46.5% (93/200) (\|err\|<=20) | 0.59 |
| QT | 200 | -14.6 ± 31.3 | 22.0 | 66.5% (133/200) (\|err\|<=30) | 0.82 |
| HR (bpm) | 200 | +0.1 ± 2.6 | 0.4 | 94.5% (189/200) (\|err\|<=5) | 0.98 |

### Per-lead mean ± SD error (ms)

| Lead | P on | P off | QRS on | QRS off | T off |
|---|---|---|---|---|---|
| I | -1.9 ± 24.8 | -5.0 ± 17.3 | -1.6 ± 16.0 | +5.5 ± 26.4 | -6.8 ± 32.7 |
| II | +2.0 ± 21.2 | -6.2 ± 16.3 | +0.9 ± 15.9 | +3.7 ± 21.8 | -4.9 ± 31.9 |
| III | +2.7 ± 30.3 | +1.3 ± 26.5 | -2.3 ± 18.2 | +1.0 ± 26.4 | +0.6 ± 47.0 |
| aVR | +0.2 ± 20.7 | -5.4 ± 16.2 | -2.8 ± 18.6 | +6.1 ± 24.1 | -2.0 ± 34.7 |
| aVL | +0.6 ± 30.2 | -3.1 ± 25.2 | -3.3 ± 17.6 | +5.4 ± 26.7 | -1.6 ± 42.0 |
| aVF | +0.2 ± 23.7 | -3.0 ± 20.2 | -1.1 ± 16.5 | +2.3 ± 24.3 | -0.5 ± 38.9 |
| V1 | +6.4 ± 36.0 | +13.3 ± 32.1 | +5.2 ± 15.7 | +2.7 ± 18.3 | -1.6 ± 45.1 |
| V2 | -7.9 ± 36.6 | +2.5 ± 29.7 | +9.3 ± 13.6 | -0.9 ± 16.7 | -4.0 ± 34.4 |
| V3 | -6.0 ± 31.1 | -1.0 ± 23.7 | +10.1 ± 11.5 | -4.1 ± 14.3 | -6.8 ± 33.5 |
| V4 | -2.4 ± 26.6 | -3.3 ± 18.7 | +11.2 ± 11.8 | -6.0 ± 17.6 | -9.0 ± 29.8 |
| V5 | -3.3 ± 29.3 | -3.1 ± 19.0 | +8.3 ± 13.7 | -5.8 ± 19.6 | -7.8 ± 29.1 |
| V6 | -3.2 ± 26.4 | -3.0 ± 17.4 | +4.6 ± 13.8 | -3.3 ± 19.6 | -5.8 ± 32.8 |

### Worst examples

| Criterion | Worst record ids (mean \|err\|) |
|---|---|
| QRS onset | ludb-93 (61 ms), ludb-111 (49 ms), ludb-45 (38 ms), ludb-34 (37 ms), ludb-8 (36 ms) |
| QRS offset | ludb-74 (134 ms), ludb-45 (104 ms), ludb-34 (79 ms), ludb-95 (38 ms), ludb-104 (33 ms) |
| P onset | ludb-31 (72 ms), ludb-5 (46 ms), ludb-60 (40 ms), ludb-130 (37 ms), ludb-26 (36 ms) |
| T offset | ludb-57 (59 ms), ludb-130 (57 ms), ludb-15 (55 ms), ludb-180 (55 ms), ludb-124 (53 ms) |
| lowest QRS detection | ludb-116, ludb-111, ludb-74, ludb-83, ludb-45 |

### Diagnosis agreement with LUDB header statements (small N, indicative only)

LUDB header statements are free-text from the cardiologist (e.g. 'left ventricular hypertrophy' is attached to >50% of records, mostly without voltage criteria; median Sokolow-Lyon here is ~1.3 mV), so low sensitivity for LVH/LAFB mostly reflects label definition, not necessarily detector error.

| Class | N pos | Sens % [CI] | Spec % [CI] | PPV % [CI] | Missed ids |
|---|---|---|---|---|---|
| LVH | 108 | 0 [0-3] | 100 [96-100] | - | ludb-1, ludb-3, ludb-2, ludb-4 |
| STTC | 37 | 41 [26-57] | 95 [91-97] | 65 [45-81] | ludb-3, ludb-4, ludb-8, ludb-13 |
| RBBB_any | 33 | 21 [11-38] | 100 [98-100] | 100 [65-100] | ludb-4, ludb-25, ludb-31, ludb-32 |
| SBRAD | 25 | 20 [9-39] | 100 [98-100] | 100 [57-100] | ludb-6, ludb-12, ludb-24, ludb-27 |
| LAFB | 16 | 0 [0-19] | 100 [98-100] | - | ludb-21, ludb-26, ludb-46, ludb-51 |
| AF | 15 | 80 [55-93] | 98 [95-99] | 75 [51-90] | ludb-8, ludb-93, ludb-95 |
| AV1 | 10 | 10 [2-40] | 98 [95-99] | 25 [5-70] | ludb-13, ludb-15, ludb-20, ludb-61 |
| LBBB_any | 10 | 40 [17-69] | 79 [73-85] | 9 [4-22] | ludb-19, ludb-54, ludb-83, ludb-112 |
| AV3 | 5 | 0 [0-43] | 100 [98-100] | - | ludb-34, ludb-74, ludb-90, ludb-104 |
| STACH | 4 | 0 [0-49] | 100 [98-100] | - | ludb-70, ludb-114, ludb-117, ludb-188 |
| RVH | 3 | 0 [0-56] | 99 [96-100] | 0 [0-66] | ludb-17, ludb-35, ludb-51 |

## PTB-XL: diagnostic statements

3000 records analysed (0 failed). Timing: median 0.13 s, p95 0.23 s, max 1.7 s per record (N=3000). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens % [95% CI] | Spec % [95% CI] | PPV % [95% CI] (this sample) | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 314 | 267 | 96 | 85 [81-89] | 96 [96-97] | 74 [69-78] | 64 (prev 6.9%) | 0.79 |
| AV1 | 1st-degree AV block (1AVB) | 210 | 67 | 76 | 32 [26-38] | 97 [97-98] | 47 [39-55] | 31 (prev 3.6%) | 0.38 |
| AV2 | 2nd-degree AV block (2AVB) | 14 | 0 | 9 | 0 [0-22] | 100 [99-100] | 0 [0-30] | 0 (prev 0.1%) | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 16 | 0 | 0 | 0 [0-19] | 100 [100-100] | - | - | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 178 | 116 | 59 | 65 [58-72] | 98 [97-98] | 66 [59-73] | 44 (prev 2.5%) | 0.66 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 229 | 38 | 20 | 17 [12-22] | 99 [99-100] | 66 [53-76] | 55 (prev 5.1%) | 0.26 |
| RBBB_any | RBBB any | 406 | 210 | 23 | 52 [47-57] | 99 [99-99] | 90 [86-93] | 83 (prev 7.6%) | 0.66 |
| LBBB_complete | complete LBBB (CLBBB) | 113 | 75 | 127 | 66 [57-74] | 96 [95-96] | 37 [31-44] | 28 (prev 2.5%) | 0.48 |
| LBBB_any | LBBB any | 189 | 123 | 93 | 65 [58-72] | 97 [96-97] | 57 [50-63] | 36 (prev 2.8%) | 0.61 |
| LAFB | left anterior fascicular block | 252 | 86 | 66 | 34 [29-40] | 98 [97-98] | 57 [49-64] | 53 (prev 7.4%) | 0.43 |
| LPFB | left posterior fascicular block | 115 | 53 | 71 | 46 [37-55] | 98 [97-98] | 43 [34-52] | 13 (prev 0.8%) | 0.44 |
| WPW | WPW | 79 | 32 | 13 | 41 [30-52] | 100 [99-100] | 71 [57-82] | 25 (prev 0.4%) | 0.52 |
| LVH | left ventricular hypertrophy | 228 | 165 | 459 | 72 [66-78] | 83 [82-85] | 26 [23-30] | 28 (prev 8.0%) | 0.39 |
| RVH | right ventricular hypertrophy | 90 | 37 | 105 | 41 [32-51] | 96 [96-97] | 26 [20-34] | 6 (prev 0.5%) | 0.32 |
| LAE | left atrial enlargement | 123 | 5 | 71 | 4 [2-9] | 98 [97-98] | 7 [3-14] | 3 (prev 1.9%) | 0.05 |
| RAE | right atrial enlargement | 98 | 50 | 44 | 51 [41-61] | 98 [98-99] | 53 [43-63] | 13 (prev 0.4%) | 0.52 |
| LQT | long QT (LNGQT) | 100 | 69 | 362 | 69 [59-77] | 88 [86-89] | 16 [13-20] | 3 (prev 0.5%) | 0.26 |
| SBRAD | sinus bradycardia | 118 | 70 | 25 | 59 [50-68] | 99 [99-99] | 74 [64-81] | 67 (prev 2.9%) | 0.66 |
| STACH | sinus tachycardia | 183 | 121 | 61 | 66 [59-73] | 98 [97-98] | 66 [59-73] | 55 (prev 3.8%) | 0.66 |
| SR | sinus rhythm | 1909 | 1584 | 195 | 83 [81-85] | 82 [80-84] | 89 [88-90] | 94 (prev 76.8%) | 0.86 |
| MI_any | any MI (Q waves or ST elevation) | 840 | 280 | 203 | 33 [30-37] | 91 [89-92] | 58 [54-62] | 45 (prev 19.0%) | 0.42 |
| MI_inferior | inferior MI (IMI etc.) | 413 | 96 | 115 | 23 [19-28] | 96 [95-96] | 45 [39-52] | 37 (prev 10.3%) | 0.31 |
| MI_anterior | anterior/anteroseptal MI | 510 | 160 | 130 | 31 [27-36] | 95 [94-96] | 55 [49-61] | 44 (prev 11.7%) | 0.40 |
| MI_lateral | lateral MI | 294 | 75 | 79 | 26 [21-31] | 97 [96-98] | 49 [41-57] | 26 (prev 3.9%) | 0.33 |
| STTC | ST/T change (any) | 1077 | 600 | 488 | 56 [53-59] | 75 [73-77] | 55 [52-58] | 42 (prev 24.5%) | 0.55 |
| STE | ST elevation (STE_) | 28 | 2 | 222 | 7 [2-23] | 93 [92-93] | 1 [0-3] | 0 (prev 0.1%) | 0.02 |
| STD | ST depression (STD_) | 260 | 171 | 660 | 66 [60-71] | 76 [74-77] | 21 [18-23] | 12 (prev 4.6%) | 0.31 |
| LOWV | low voltage (LVOLT) | 100 | 12 | 91 | 12 [7-20] | 97 [96-97] | 12 [7-19] | 3 (prev 0.8%) | 0.12 |
| NORM | NORM | 515 | 350 | 370 | 68 [64-72] | 85 [84-86] | 49 [45-52] | 78 (prev 43.3%) | 0.57 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 370 | 312 | 121 | 84 [80-88] | 95 [95-96] | 72 [68-76] | 59 (prev 7.2%) | 0.78 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 68.0% [63.8-71.8] (n=515) |
| gold NORM -> we raise >=1 abnormal/critical finding | 32.0% [28.2-36.2] (n=515) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 47.2% [42.9-51.5] (n=515) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 85.1% [83.7-86.5] (n=2485) |
| gold non-NORM -> we say within normal limits (missed) | 14.9% [13.5-16.3] (n=2485) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 1909 | 74 (59-92) | 85.1% (1624/1909) in 60-100 bpm |
| STACH | 183 | 109 (102-124) | 96.7% (177/183) in 100-+ bpm |
| SBRAD | 118 | 49 (42-57) | 95.8% (113/118) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 801 | 416 | 379 | 6 |
| normal | 754 | 4 | 710 | 40 |
| right | 137 | 20 | 12 | 105 |

Axis category agreement: 72.8% [70.6-74.8] (n=1692) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> SR:34, PVC:28, SARRH:15, PAC:15 | FN our findings -> irregular_rhythm:18, left_axis_deviation:13, st_depression_lateral:13, st_depression_inferior:12 |
| AV1 | FP gold labels -> SR:46, LPR:24, PACE:17, ASMI:13 | FN our findings -> sinus_rhythm:59, left_axis_deviation:42, st_depression_lateral:37, long_qt:37 |
| AV2 | FP gold labels -> SR:5, IRBBB:3, NORM:2, CLBBB:2 | FN our findings -> st_depression_lateral:4, right_axis_deviation:3, st_depression_inferior:3, atrial_flutter:3 |
| AV3 | FP gold labels -> - | FN our findings -> long_qt:6, lvh:6, sinus_bradycardia:6, st_depression_lateral:5 |
| RBBB_complete | FP gold labels -> IRBBB:45, SR:39, RVH:23, LAFB:12 | FN our findings -> rvh:48, ivcd:43, sinus_rhythm:29, right_axis_deviation:29 |
| RBBB_incomplete | FP gold labels -> CRBBB:11, SR:8, IMI:6, ABQRS:6 | FN our findings -> sinus_rhythm:122, right_axis_deviation:53, rbbb:46, left_axis_deviation:43 |
| RBBB_any | FP gold labels -> SR:15, ASMI:7, WPW:7, IMI:6 | FN our findings -> sinus_rhythm:120, ivcd:71, right_axis_deviation:60, left_axis_deviation:48 |
| LBBB_complete | FP gold labels -> SR:83, ILBBB:39, ABQRS:25, IVCD:24 | FN our findings -> lvh:30, ivcd:30, st_depression_lateral:24, st_elevation_anterior:23 |
| LBBB_any | FP gold labels -> SR:57, IVCD:25, ABQRS:20, WPW:17 | FN our findings -> ivcd:40, lvh:39, st_depression_lateral:36, t_inversion_lateral:30 |
| LAFB | FP gold labels -> SR:31, ABQRS:25, ASMI:20, AFIB:17 | FN our findings -> left_axis_deviation:153, sinus_rhythm:102, ivcd:64, secondary_repolarization:53 |
| LPFB | FP gold labels -> SR:34, IRBBB:19, ABQRS:19, ASMI:14 | FN our findings -> right_axis_deviation:46, rvh:36, sinus_rhythm:35, rbbb:32 |
| WPW | FP gold labels -> SR:8, ASMI:4, LVH:3, QWAVE:3 | FN our findings -> sinus_rhythm:32, secondary_repolarization:21, lbbb:16, lvh:16 |
| LVH | FP gold labels -> SR:229, CLBBB:83, ASMI:83, AFIB:78 | FN our findings -> st_depression_lateral:29, sinus_rhythm:27, t_inversion_lateral:18, lvh_voltage:16 |
| RVH | FP gold labels -> CRBBB:71, SR:50, LPFB:33, ASMI:21 | FN our findings -> sinus_rhythm:41, rbbb:36, secondary_repolarization:31, left_axis_deviation:29 |
| LAE | FP gold labels -> SR:43, LAFB:11, PACE:10, NORM:9 | FN our findings -> sinus_rhythm:77, lvh:37, secondary_repolarization:29, st_depression_lateral:26 |
| RAE | FP gold labels -> SR:24, STACH:10, ABQRS:10, LVH:7 | FN our findings -> sinus_rhythm:31, within_normal_limits:14, left_axis_deviation:14, long_qt:12 |
| LQT | FP gold labels -> SR:251, ABQRS:71, ASMI:68, STD_:54 | FN our findings -> sinus_rhythm:19, within_normal_limits:14, left_axis_deviation:7, left_axis_mild:5 |
| SBRAD | FP gold labels -> 3AVB:5, LVH:4, ISC_:4, ASMI:4 | FN our findings -> sinus_rhythm:31, within_normal_limits:15, ivcd:12, irregular_rhythm:11 |
| STACH | FP gold labels -> SR:26, ABQRS:12, LVH:12, ASMI:10 | FN our findings -> irregular_rhythm:30, left_axis_deviation:20, lvh:17, st_depression_lateral:16 |
| SR | FP gold labels -> PACE:47, NORM:47, SARRH:41, SBRAD:31 | FN our findings -> irregular_rhythm:200, left_axis_deviation:77, lvh:71, long_qt:68 |
| MI_any | FP gold labels -> SR:77, PACE:73, ABQRS:37, WPW:29 | FN our findings -> sinus_rhythm:306, left_axis_deviation:134, lvh:112, st_depression_lateral:110 |
| MI_inferior | FP gold labels -> PACE:49, SR:37, ABQRS:26, WPW:25 | FN our findings -> sinus_rhythm:179, left_axis_deviation:105, long_qt:77, st_depression_lateral:54 |
| MI_anterior | FP gold labels -> PACE:49, SR:43, CLBBB:24, ABQRS:15 | FN our findings -> sinus_rhythm:186, left_axis_deviation:101, lvh:90, st_depression_lateral:78 |
| MI_lateral | FP gold labels -> PACE:42, SR:27, ABQRS:12, CRBBB:8 | FN our findings -> sinus_rhythm:135, left_axis_deviation:73, pathologic_q_anterior:45, ivcd:45 |
| STTC | FP gold labels -> SR:218, ABQRS:130, ASMI:105, PACE:73 | FN our findings -> sinus_rhythm:288, within_normal_limits:175, long_qt:87, lvh:84 |
| STE | FP gold labels -> SR:85, PACE:64, ASMI:55, ABQRS:37 | FN our findings -> sinus_rhythm:21, within_normal_limits:15, atrial_fibrillation:3, lvh_voltage:3 |
| STD | FP gold labels -> SR:302, ABQRS:159, AFIB:137, ASMI:97 | FN our findings -> sinus_rhythm:50, within_normal_limits:25, lvh:21, long_qt:18 |
| LOWV | FP gold labels -> SR:45, ABQRS:29, ASMI:27, AFIB:23 | FN our findings -> sinus_rhythm:62, within_normal_limits:49, left_axis_deviation:12, long_qt:9 |
| NORM | FP gold labels -> SR:328, ABQRS:75, NDT:57, IRBBB:35 | FN our findings -> sinus_rhythm:93, ivcd:52, sinus_bradycardia:24, av_block_1:15 |
| AF_AFL | FP gold labels -> SR:49, PVC:28, 1AVB:21, NORM:18 | FN our findings -> irregular_rhythm:20, left_axis_deviation:17, st_depression_lateral:16, sinus_rhythm:13 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-00018, ptbxl-00076, ptbxl-00266, ptbxl-00382, ptbxl-00423 | ptbxl-00017, ptbxl-00699, ptbxl-00923, ptbxl-02425, ptbxl-02453 |
| AV1 | ptbxl-00144, ptbxl-00190, ptbxl-00320, ptbxl-00526, ptbxl-00699 | ptbxl-00347, ptbxl-00522, ptbxl-00524, ptbxl-00535, ptbxl-00800 |
| AV2 | ptbxl-02560, ptbxl-10296, ptbxl-10487, ptbxl-10965, ptbxl-11331 | ptbxl-01222, ptbxl-03505, ptbxl-08048, ptbxl-09136, ptbxl-10300 |
| AV3 | - | ptbxl-00959, ptbxl-02047, ptbxl-04838, ptbxl-04827, ptbxl-07688 |
| RBBB_complete | ptbxl-00287, ptbxl-00569, ptbxl-00600, ptbxl-00635, ptbxl-00959 | ptbxl-00428, ptbxl-01157, ptbxl-01635, ptbxl-01733, ptbxl-02311 |
| RBBB_incomplete | ptbxl-01157, ptbxl-01635, ptbxl-04044, ptbxl-04251, ptbxl-05025 | ptbxl-00045, ptbxl-00222, ptbxl-00478, ptbxl-00528, ptbxl-00569 |
| RBBB_any | ptbxl-00287, ptbxl-00600, ptbxl-00635, ptbxl-01134, ptbxl-04044 | ptbxl-00045, ptbxl-00222, ptbxl-00428, ptbxl-00478, ptbxl-00528 |
| LBBB_complete | ptbxl-00223, ptbxl-00282, ptbxl-00685, ptbxl-00688, ptbxl-00883 | ptbxl-00180, ptbxl-00287, ptbxl-00635, ptbxl-01056, ptbxl-02135 |
| LBBB_any | ptbxl-00223, ptbxl-00688, ptbxl-01445, ptbxl-01542, ptbxl-01670 | ptbxl-00180, ptbxl-00287, ptbxl-00423, ptbxl-00635, ptbxl-01056 |
| LAFB | ptbxl-00184, ptbxl-00189, ptbxl-00528, ptbxl-00840, ptbxl-01081 | ptbxl-00172, ptbxl-00260, ptbxl-00348, ptbxl-00428, ptbxl-00508 |
| LPFB | ptbxl-00152, ptbxl-00222, ptbxl-00478, ptbxl-00498, ptbxl-00626 | ptbxl-00428, ptbxl-00635, ptbxl-00788, ptbxl-01733, ptbxl-02227 |
| WPW | ptbxl-00858, ptbxl-04750, ptbxl-06019, ptbxl-09816, ptbxl-09952 | ptbxl-04279, ptbxl-07046, ptbxl-07095, ptbxl-07291, ptbxl-07407 |
| LVH | ptbxl-00180, ptbxl-00190, ptbxl-00266, ptbxl-00281, ptbxl-00449 | ptbxl-00271, ptbxl-00347, ptbxl-00423, ptbxl-00425, ptbxl-00820 |
| RVH | ptbxl-00287, ptbxl-00428, ptbxl-00498, ptbxl-00512, ptbxl-00600 | ptbxl-00222, ptbxl-00667, ptbxl-02409, ptbxl-02748, ptbxl-03050 |
| LAE | ptbxl-00189, ptbxl-00334, ptbxl-00385, ptbxl-00442, ptbxl-00553 | ptbxl-00274, ptbxl-00299, ptbxl-00347, ptbxl-00524, ptbxl-00573 |
| RAE | ptbxl-00260, ptbxl-00554, ptbxl-00738, ptbxl-01157, ptbxl-01426 | ptbxl-00199, ptbxl-00626, ptbxl-00857, ptbxl-00970, ptbxl-01228 |
| LQT | ptbxl-00026, ptbxl-00028, ptbxl-00234, ptbxl-00266, ptbxl-00274 | ptbxl-00260, ptbxl-02381, ptbxl-04132, ptbxl-05586, ptbxl-06479 |
| SBRAD | ptbxl-00186, ptbxl-00383, ptbxl-00508, ptbxl-01433, ptbxl-02062 | ptbxl-00823, ptbxl-01232, ptbxl-01717, ptbxl-02158, ptbxl-02317 |
| STACH | ptbxl-00222, ptbxl-00524, ptbxl-00544, ptbxl-00554, ptbxl-00858 | ptbxl-01158, ptbxl-01670, ptbxl-01894, ptbxl-01902, ptbxl-02160 |
| SR | ptbxl-00128, ptbxl-00144, ptbxl-00190, ptbxl-00228, ptbxl-00281 | ptbxl-00222, ptbxl-00223, ptbxl-00266, ptbxl-00271, ptbxl-00352 |
| MI_any | ptbxl-00144, ptbxl-00146, ptbxl-00180, ptbxl-00190, ptbxl-00222 | ptbxl-00152, ptbxl-00223, ptbxl-00240, ptbxl-00274, ptbxl-00282 |
| MI_inferior | ptbxl-00144, ptbxl-00146, ptbxl-00180, ptbxl-00190, ptbxl-00234 | ptbxl-00184, ptbxl-00240, ptbxl-00266, ptbxl-00281, ptbxl-00423 |
| MI_anterior | ptbxl-00144, ptbxl-00180, ptbxl-00385, ptbxl-00425, ptbxl-00516 | ptbxl-00223, ptbxl-00274, ptbxl-00282, ptbxl-00287, ptbxl-00512 |
| MI_lateral | ptbxl-00144, ptbxl-00146, ptbxl-00222, ptbxl-00498, ptbxl-00516 | ptbxl-00152, ptbxl-00184, ptbxl-00189, ptbxl-00266, ptbxl-00281 |
| STTC | ptbxl-00144, ptbxl-00172, ptbxl-00180, ptbxl-00190, ptbxl-00189 | ptbxl-00026, ptbxl-00028, ptbxl-00039, ptbxl-00116, ptbxl-00128 |
| STE | ptbxl-00144, ptbxl-00180, ptbxl-00190, ptbxl-00189, ptbxl-00234 | ptbxl-01596, ptbxl-01600, ptbxl-01725, ptbxl-02639, ptbxl-02868 |
| STD | ptbxl-00144, ptbxl-00146, ptbxl-00152, ptbxl-00171, ptbxl-00172 | ptbxl-00318, ptbxl-00756, ptbxl-00861, ptbxl-00941, ptbxl-00939 |
| LOWV | ptbxl-00152, ptbxl-00535, ptbxl-00600, ptbxl-00612, ptbxl-00800 | ptbxl-00001, ptbxl-00348, ptbxl-00407, ptbxl-01164, ptbxl-01389 |
| NORM | ptbxl-00116, ptbxl-00128, ptbxl-00155, ptbxl-00160, ptbxl-00199 | ptbxl-00069, ptbxl-00079, ptbxl-00076, ptbxl-00100, ptbxl-00334 |
| AF_AFL | ptbxl-00076, ptbxl-00266, ptbxl-00382, ptbxl-00423, ptbxl-00746 | ptbxl-00017, ptbxl-00347, ptbxl-00699, ptbxl-00858, ptbxl-00923 |

## Images: digitisation + analysis

Failure flags are heuristic proxies (the true failure rate needs a ground-truth comparison, available only for paired sources).

| Source | N | Exceptions | Grid conf < 0.3 | < 2 beats found | Usable (no failure flag) | Median leads | HR plausible (30-250) | Timing |
|---|---|---|---|---|---|---|---|---|
| litfl | 486 | 4.7% (23/486) | 13.4% (62/463) | 24.2% (112/463) | 67.1% (326/486) | 12 | 74.9% (347/463) | median 0.83 s, p95 1.66 s, max 2.9 s per record (N=486) |

### litfl

**Agreement with caption** (311 images whose caption/labels assert >=1 class we can detect; weak evidence: captions are incomplete and non-exhaustive, so 'extra' findings are not necessarily errors). Any asserted class recovered: 29.3% [24.5-34.5] (n=311).

| Caption class | N captions | Recovered by our findings | Our findings of this class on captions that don't mention it |
|---|---|---|---|
| STTC | 127 | 46.5% (59/127) | 67 |
| MI_any | 53 | 34.0% (18/53) | 77 |
| RBBB_any | 51 | 0.0% (0/51) | 7 |
| LBBB_any | 36 | 0.0% (0/36) | 10 |
| AF | 27 | 66.7% (18/27) | 139 |
| WPW | 25 | 0.0% (0/25) | 9 |
| AV3 | 23 | 0.0% (0/23) | 0 |
| LQT | 23 | 21.7% (5/23) | 31 |
| AV2 | 21 | 0.0% (0/21) | 0 |
| STACH | 16 | 25.0% (4/16) | 5 |
| LAFB | 14 | 0.0% (0/14) | 15 |
| RVH | 14 | 21.4% (3/14) | 12 |
| LVH | 13 | 15.4% (2/13) | 14 |
| AV1 | 11 | 0.0% (0/11) | 5 |
| LPFB | 10 | 0.0% (0/10) | 12 |
| SBRAD | 4 | 0.0% (0/4) | 2 |
| NORM | 1 | 0.0% (0/1) | 1 |

138 of 463 captions mention conditions our rules cannot detect (flutter, Brugada, hyperkalaemia, paced rhythm, VT...).

Failure examples: exceptions ['jervell-and-lange-nielsen-syndrome-00-9f859e', 'qt-interval-ecg-library-14-3f0bf9', 'left-atrial-enlargement-ecg-library-02-09ca88', 'hypercalcaemia-ecg-library-00-f1dc08', 'pacemaker-rhythms-normal-patterns-00-be0a40', 'pacemaker-rhythms-normal-patterns-01-094625', 'polymorphic-vt-and-torsades-de-pointes-tdp-01-3f0bf9', 'quetiapine-toxicity-ecg-library-00-3f0bf9']; low grid confidence (<0.3) ['aslanger-pattern-01-13b4f7', 'masquerading-bundle-branch-block-mbbb-00-bdc510', 'wolff-parkinson-white-syndrome-00-46f5b5', 'wolff-parkinson-white-syndrome-05-40bf83', 'wolff-parkinson-white-syndrome-07-7f4916', 'intra-aortic-balloon-pump-00-e2c46c', 'intra-aortic-balloon-pump-trouble-shooting-04-0bcb82', 'ecg-axis-interpretation-01-1190c6']; <2 beats detected ['aslanger-pattern-01-13b4f7', 'masquerading-bundle-branch-block-mbbb-00-bdc510', 'av-block-2nd-degree-mobitz-ii-hay-block-00-d0bfe2', 'second-degree-atrioventricular-block-01-0f21bd', 'second-degree-atrioventricular-block-05-4991b7', 'wolff-parkinson-white-syndrome-07-7f4916', 'intra-aortic-balloon-pump-00-e2c46c', 'ecg-axis-interpretation-01-1190c6']. Top errors: `ValueError: could not detect the ECG grid (px/mm)` x11; `ValueError: no ECG trace found` x6; `ValueError: no trace rows found` x6
