# ECG benchmark results

_Generated 2026-11-24 11:20 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Delineation: QRS on/off within CSE tol | 32% / 57% | LUDB, 200 records |
| Delineation: P onset / T offset within CSE tol | 51% / 55% | LUDB, 200 records |
| Detection sensitivity QRS / P / T | 99% / 66% / 91% | LUDB, 21843 beats |
| Diagnosis AF: sens / spec / PPV | 38% / 99% / 88% | PTB-XL, 1844 recs (182 pos) |
| Diagnosis AV1: sens / spec / PPV | 40% / 74% / 14% | PTB-XL, 1844 recs (182 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 70% / 72% / 21% | PTB-XL, 1844 recs (172 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 0% / 100% / 0% | PTB-XL, 1844 recs (107 pos) |
| Diagnosis LVH: sens / spec / PPV | 88% / 66% / 18% | PTB-XL, 1844 recs (146 pos) |
| Diagnosis MI_any: sens / spec / PPV | 35% / 86% / 57% | PTB-XL, 1844 recs (650 pos) |
| Diagnosis STACH: sens / spec / PPV | 54% / 98% / 71% | PTB-XL, 1844 recs (134 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 79% / 93% / 39% | PTB-XL, 1844 recs (102 pos) |
| NORM -> within normal limits; abnormal flagged | 10.0% (16/160); 98.0% (1651/1684) | PTB-XL, 1844 records |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

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

1844 records analysed (0 failed). Timing: median 0.33 s, p95 0.72 s, max 6.9 s per record (N=1844). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens % [95% CI] | Spec % [95% CI] | PPV % [95% CI] (this sample) | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 182 | 69 | 9 | 38 [31-45] | 99 [99-100] | 88 [80-94] | 84 (prev 6.9%) | 0.53 |
| AV1 | 1st-degree AV block (1AVB) | 182 | 72 | 436 | 40 [33-47] | 74 [72-76] | 14 [11-17] | 5 (prev 3.6%) | 0.21 |
| AV2 | 2nd-degree AV block (2AVB) | 3 | 0 | 190 | 0 [0-56] | 90 [88-91] | 0 [0-2] | 0 (prev 0.1%) | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 4 | 0 | 11 | 0 [0-49] | 99 [99-100] | 0 [0-26] | 0 (prev 0.1%) | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 172 | 121 | 466 | 70 [63-77] | 72 [70-74] | 21 [18-24] | 6 (prev 2.5%) | 0.32 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 194 | 47 | 161 | 24 [19-31] | 90 [89-92] | 23 [17-29] | 12 (prev 5.1%) | 0.23 |
| RBBB_any | RBBB any | 365 | 251 | 544 | 69 [64-73] | 63 [61-66] | 32 [28-35] | 13 (prev 7.6%) | 0.43 |
| LBBB_complete | complete LBBB (CLBBB) | 107 | 0 | 2 | 0 [0-3] | 100 [100-100] | 0 [0-66] | 0 (prev 2.5%) | 0.00 |
| LBBB_any | LBBB any | 183 | 1 | 14 | 1 [0-3] | 99 [99-99] | 7 [1-30] | 2 (prev 2.8%) | 0.01 |
| LAFB | left anterior fascicular block | 199 | 31 | 9 | 16 [11-21] | 99 [99-100] | 78 [62-88] | 70 (prev 7.4%) | 0.26 |
| LPFB | left posterior fascicular block | 113 | 24 | 8 | 21 [15-30] | 100 [99-100] | 75 [58-87] | 27 (prev 0.8%) | 0.33 |
| WPW | WPW | 79 | 8 | 8 | 10 [5-19] | 100 [99-100] | 50 [28-72] | 8 (prev 0.4%) | 0.17 |
| LVH | left ventricular hypertrophy | 146 | 128 | 569 | 88 [81-92] | 66 [64-69] | 18 [16-21] | 19 (prev 8.0%) | 0.30 |
| RVH | right ventricular hypertrophy | 90 | 17 | 77 | 19 [12-28] | 96 [95-96] | 18 [12-27] | 2 (prev 0.5%) | 0.18 |
| LAE | left atrial enlargement | 111 | 50 | 517 | 45 [36-54] | 70 [68-72] | 9 [7-11] | 3 (prev 1.9%) | 0.15 |
| RAE | right atrial enlargement | 98 | 51 | 29 | 52 [42-62] | 98 [98-99] | 64 [53-73] | 12 (prev 0.4%) | 0.57 |
| LQT | long QT (LNGQT) | 100 | 93 | 1039 | 93 [86-97] | 40 [38-43] | 8 [7-10] | 1 (prev 0.5%) | 0.15 |
| SBRAD | sinus bradycardia | 102 | 81 | 128 | 79 [71-86] | 93 [91-94] | 39 [32-46] | 25 (prev 2.9%) | 0.52 |
| STACH | sinus tachycardia | 134 | 72 | 30 | 54 [45-62] | 98 [98-99] | 71 [61-79] | 55 (prev 3.8%) | 0.61 |
| SR | sinus rhythm | 1193 | 710 | 59 | 60 [57-62] | 91 [88-93] | 92 [90-94] | 96 (prev 76.8%) | 0.72 |
| MI_any | any MI (Q waves or ST elevation) | 650 | 228 | 171 | 35 [32-39] | 86 [84-88] | 57 [52-62] | 36 (prev 19.0%) | 0.43 |
| MI_inferior | inferior MI (IMI etc.) | 314 | 63 | 77 | 20 [16-25] | 95 [94-96] | 45 [37-53] | 31 (prev 10.3%) | 0.28 |
| MI_anterior | anterior/anteroseptal MI | 393 | 141 | 150 | 36 [31-41] | 90 [88-91] | 48 [43-54] | 32 (prev 11.7%) | 0.41 |
| MI_lateral | lateral MI | 285 | 59 | 26 | 21 [16-26] | 98 [98-99] | 69 [59-78] | 33 (prev 3.9%) | 0.32 |
| STTC | ST/T change (any) | 542 | 356 | 544 | 66 [62-70] | 58 [56-61] | 40 [36-43] | 34 (prev 24.5%) | 0.49 |
| STE | ST elevation (STE_) | 1 | 0 | 265 | 0 [0-79] | 86 [84-87] | 0 [0-1] | 0 (prev 0.1%) | 0.00 |
| STD | ST depression (STD_) | 112 | 78 | 603 | 70 [61-77] | 65 [63-67] | 11 [9-14] | 9 (prev 4.6%) | 0.20 |
| LOWV | low voltage (LVOLT) | 12 | 4 | 68 | 33 [14-61] | 96 [95-97] | 6 [2-13] | 7 (prev 0.8%) | 0.10 |
| NORM | NORM | 160 | 16 | 13 | 10 [6-16] | 99 [99-100] | 55 [38-72] | 91 (prev 43.3%) | 0.17 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 238 | 71 | 7 | 30 [24-36] | 100 [99-100] | 91 [83-96] | 84 (prev 7.2%) | 0.45 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 10.0% [6.2-15.6] (n=160) |
| gold NORM -> we raise >=1 abnormal/critical finding | 83.8% [77.3-88.7] (n=160) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 90.0% [84.4-93.8] (n=160) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 98.0% [97.3-98.6] (n=1684) |
| gold non-NORM -> we say within normal limits (missed) | 0.8% [0.5-1.3] (n=1684) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 1193 | 74 (59-93) | 86.2% (1028/1193) in 60-100 bpm |
| STACH | 134 | 110 (102-124) | 98.5% (132/134) in 100-+ bpm |
| SBRAD | 102 | 49 (43-56) | 96.1% (98/102) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 584 | 305 | 276 | 3 |
| normal | 461 | 4 | 424 | 33 |
| right | 116 | 17 | 5 | 94 |

Axis category agreement: 70.9% [68.2-73.4] (n=1161) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> BIGU:4, CRBBB:3, ASMI:2, PVC:2 | FN our findings -> non_sinus_p:74, lvh:52, long_qt:46, left_axis_deviation:43 |
| AV1 | FP gold labels -> SR:314, ABQRS:76, SBRAD:56, ASMI:53 | FN our findings -> long_qt:77, non_sinus_p:48, lvh:44, left_axis_deviation:30 |
| AV2 | FP gold labels -> SR:149, ABQRS:50, 1AVB:27, IRBBB:26 | FN our findings -> non_sinus_p:2, st_depression_inferior:2, long_qt:2, st_depression_anterolateral:1 |
| AV3 | FP gold labels -> SR:5, ASMI:3, ALMI:2, IRBBB:2 | FN our findings -> non_sinus_p:4, lvh:3, rbbb:2, st_depression_lateral:2 |
| RBBB_complete | FP gold labels -> SR:323, CLBBB:102, ABQRS:99, ASMI:81 | FN our findings -> ivcd:48, rvh:47, long_qt:35, left_axis_deviation:31 |
| RBBB_incomplete | FP gold labels -> SR:105, ABQRS:30, SBRAD:20, ISCAL:20 | FN our findings -> long_qt:96, rbbb:81, sinus_rhythm:69, right_axis_deviation:51 |
| RBBB_any | FP gold labels -> SR:374, ABQRS:115, CLBBB:102, ASMI:82 | FN our findings -> long_qt:71, ivcd:54, rvh:52, sinus_rhythm:45 |
| LBBB_complete | FP gold labels -> IVCD:1, SR:1, ASMI:1, ILBBB:1 | FN our findings -> rbbb:102, lvh:92, long_qt:83, st_elevation_anterior:82 |
| LBBB_any | FP gold labels -> SR:9, NORM:4, ABQRS:4, AMI:2 | FN our findings -> rbbb:154, lvh:138, long_qt:122, st_depression_lateral:118 |
| LAFB | FP gold labels -> SR:6, ALMI:4, ABQRS:4, ASMI:3 | FN our findings -> left_axis_deviation:159, long_qt:113, lvh:87, rbbb:85 |
| LPFB | FP gold labels -> RAO/RAE:3, STACH:3, SR:3, IRBBB:2 | FN our findings -> right_axis_deviation:72, long_qt:55, rbbb:45, sinus_rhythm:31 |
| WPW | FP gold labels -> SR:4, IRBBB:3, CLBBB:1, ISCAL:1 | FN our findings -> long_qt:55, lvh:43, rbbb:42, sinus_rhythm:28 |
| LVH | FP gold labels -> SR:355, ABQRS:120, ASMI:116, LAFB:102 | FN our findings -> st_depression_lateral:8, sinus_rhythm:7, lae:7, av_block_1:6 |
| RVH | FP gold labels -> SR:45, CRBBB:42, LPFB:27, ABQRS:25 | FN our findings -> rbbb:66, long_qt:56, sinus_rhythm:42, right_axis_deviation:29 |
| LAE | FP gold labels -> SR:382, ABQRS:107, 1AVB:69, ASMI:66 | FN our findings -> long_qt:40, lvh:28, sinus_rhythm:27, rbbb:20 |
| RAE | FP gold labels -> SR:15, ABQRS:8, STACH:8, LPFB:5 | FN our findings -> long_qt:25, sinus_rhythm:23, lvh:17, left_axis_deviation:13 |
| LQT | FP gold labels -> SR:746, ABQRS:229, ASMI:163, CRBBB:132 | FN our findings -> st_depression_lateral:5, lvh:4, left_axis_deviation:2, av_block_2:2 |
| SBRAD | FP gold labels -> SR:115, ABQRS:26, IRBBB:17, LVH:15 | FN our findings -> irregular_rhythm:7, lvh:7, rbbb:6, non_sinus_p:6 |
| STACH | FP gold labels -> SR:13, AFLT:9, LVH:5, ABQRS:5 | FN our findings -> long_qt:34, non_sinus_p:28, lvh:27, st_depression_lateral:23 |
| SR | FP gold labels -> SARRH:20, IRBBB:13, ASMI:10, LAFB:10 | FN our findings -> long_qt:343, lvh:197, rbbb:179, lae:158 |
| MI_any | FP gold labels -> SR:110, CLBBB:86, ABQRS:24, 1AVB:22 | FN our findings -> long_qt:267, sinus_rhythm:158, lvh:138, lae:129 |
| MI_inferior | FP gold labels -> SR:49, ABQRS:21, CLBBB:20, WPW:17 | FN our findings -> long_qt:159, sinus_rhythm:94, left_axis_deviation:84, lvh:81 |
| MI_anterior | FP gold labels -> SR:98, CLBBB:87, 1AVB:23, LVH:20 | FN our findings -> long_qt:162, sinus_rhythm:95, lvh:95, av_block_1:80 |
| MI_lateral | FP gold labels -> SR:21, CRBBB:11, ABQRS:11, LAFB:7 | FN our findings -> long_qt:145, lvh:91, sinus_rhythm:87, left_axis_deviation:69 |
| STTC | FP gold labels -> SR:314, ABQRS:148, ASMI:118, CLBBB:97 | FN our findings -> long_qt:127, sinus_rhythm:89, lae:69, av_block_1:57 |
| STE | FP gold labels -> SR:166, CLBBB:87, ASMI:74, ABQRS:48 | FN our findings -> av_block_1:1, sinus_bradycardia:1, rbbb:1 |
| STD | FP gold labels -> SR:337, ABQRS:143, AFIB:102, ASMI:90 | FN our findings -> long_qt:21, sinus_rhythm:16, lvh:12, lae:11 |
| LOWV | FP gold labels -> SR:37, ABQRS:24, ASMI:22, AFIB:18 | FN our findings -> long_qt:4, av_block_1:3, lae:3, left_axis_deviation:3 |
| NORM | FP gold labels -> SR:13, ABQRS:4, NDT:3, AMI:1 | FN our findings -> long_qt:81, sinus_rhythm:65, av_block_1:48, sinus_bradycardia:44 |
| AF_AFL | FP gold labels -> BIGU:4, CRBBB:3, ASMI:2, PVC:2 | FN our findings -> non_sinus_p:103, lvh:78, left_axis_deviation:65, st_depression_lateral:54 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-3784, ptbxl-9926, ptbxl-10360, ptbxl-11418, ptbxl-4990 | ptbxl-598, ptbxl-569, ptbxl-3041, ptbxl-3835, ptbxl-3947 |
| AV1 | ptbxl-172, ptbxl-57, ptbxl-553, ptbxl-545, ptbxl-598 | ptbxl-234, ptbxl-524, ptbxl-685, ptbxl-800, ptbxl-1014 |
| AV2 | ptbxl-440, ptbxl-441, ptbxl-685, ptbxl-1713, ptbxl-1876 | ptbxl-3505, ptbxl-16401, ptbxl-19164 |
| AV3 | ptbxl-3568, ptbxl-8066, ptbxl-14493, ptbxl-21819, ptbxl-706 | ptbxl-8620, ptbxl-11500, ptbxl-4838, ptbxl-8210 |
| RBBB_complete | ptbxl-287, ptbxl-347, ptbxl-180, ptbxl-618, ptbxl-545 | ptbxl-172, ptbxl-1157, ptbxl-3582, ptbxl-3784, ptbxl-4068 |
| RBBB_incomplete | ptbxl-79, ptbxl-524, ptbxl-2476, ptbxl-3308, ptbxl-3891 | ptbxl-478, ptbxl-823, ptbxl-856, ptbxl-1261, ptbxl-1612 |
| RBBB_any | ptbxl-79, ptbxl-287, ptbxl-347, ptbxl-180, ptbxl-524 | ptbxl-172, ptbxl-478, ptbxl-856, ptbxl-1157, ptbxl-1261 |
| LBBB_complete | ptbxl-11180, ptbxl-20077 | ptbxl-287, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598 |
| LBBB_any | ptbxl-758, ptbxl-18398, ptbxl-2417, ptbxl-2598, ptbxl-3875 | ptbxl-287, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598 |
| LAFB | ptbxl-14671, ptbxl-840, ptbxl-4995, ptbxl-12665, ptbxl-16340 | ptbxl-172, ptbxl-4068, ptbxl-4214, ptbxl-4586, ptbxl-5338 |
| LPFB | ptbxl-478, ptbxl-626, ptbxl-947, ptbxl-10769, ptbxl-11343 | ptbxl-1157, ptbxl-2623, ptbxl-3641, ptbxl-3947, ptbxl-4105 |
| WPW | ptbxl-7296, ptbxl-13248, ptbxl-858, ptbxl-11506, ptbxl-12391 | ptbxl-4279, ptbxl-4658, ptbxl-4825, ptbxl-5028, ptbxl-5303 |
| LVH | ptbxl-234, ptbxl-180, ptbxl-512, ptbxl-478, ptbxl-618 | ptbxl-2705, ptbxl-5062, ptbxl-17351, ptbxl-423, ptbxl-425 |
| RVH | ptbxl-172, ptbxl-1157, ptbxl-3582, ptbxl-4068, ptbxl-4586 | ptbxl-2748, ptbxl-3242, ptbxl-5338, ptbxl-5951, ptbxl-7882 |
| LAE | ptbxl-57, ptbxl-287, ptbxl-180, ptbxl-440, ptbxl-553 | ptbxl-524, ptbxl-796, ptbxl-4571, ptbxl-7518, ptbxl-7598 |
| RAE | ptbxl-1157, ptbxl-3582, ptbxl-5961, ptbxl-8348, ptbxl-14729 | ptbxl-4546, ptbxl-199, ptbxl-626, ptbxl-857, ptbxl-970 |
| LQT | ptbxl-9, ptbxl-165, ptbxl-172, ptbxl-287, ptbxl-180 | ptbxl-320, ptbxl-6647, ptbxl-7727, ptbxl-12410, ptbxl-13838 |
| SBRAD | ptbxl-79, ptbxl-758, ptbxl-1200, ptbxl-2135, ptbxl-2746 | ptbxl-823, ptbxl-2359, ptbxl-3484, ptbxl-8251, ptbxl-8815 |
| STACH | ptbxl-5062, ptbxl-5966, ptbxl-7296, ptbxl-9144, ptbxl-9813 | ptbxl-1876, ptbxl-4893, ptbxl-6517, ptbxl-7055, ptbxl-8161 |
| SR | ptbxl-478, ptbxl-2368, ptbxl-2626, ptbxl-3855, ptbxl-5338 | ptbxl-79, ptbxl-234, ptbxl-441, ptbxl-618, ptbxl-685 |
| MI_any | ptbxl-180, ptbxl-618, ptbxl-598, ptbxl-798, ptbxl-1093 | ptbxl-287, ptbxl-512, ptbxl-800, ptbxl-1014, ptbxl-1157 |
| MI_inferior | ptbxl-234, ptbxl-180, ptbxl-798, ptbxl-1093, ptbxl-1367 | ptbxl-545, ptbxl-1157, ptbxl-1492, ptbxl-1907, ptbxl-1998 |
| MI_anterior | ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598, ptbxl-798 | ptbxl-287, ptbxl-512, ptbxl-800, ptbxl-1014, ptbxl-1261 |
| MI_lateral | ptbxl-4586, ptbxl-5951, ptbxl-8348, ptbxl-10982, ptbxl-13100 | ptbxl-800, ptbxl-2311, ptbxl-5154, ptbxl-5574, ptbxl-6702 |
| STTC | ptbxl-172, ptbxl-234, ptbxl-180, ptbxl-512, ptbxl-618 | ptbxl-524, ptbxl-1612, ptbxl-1713, ptbxl-1998, ptbxl-4756 |
| STE | ptbxl-234, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-798 | ptbxl-4059 |
| STD | ptbxl-172, ptbxl-234, ptbxl-347, ptbxl-180, ptbxl-512 | ptbxl-4112, ptbxl-5062, ptbxl-8178, ptbxl-13913, ptbxl-13974 |
| LOWV | ptbxl-800, ptbxl-3582, ptbxl-6075, ptbxl-6803, ptbxl-8220 | ptbxl-8627, ptbxl-6251, ptbxl-14033, ptbxl-14382, ptbxl-15775 |
| NORM | ptbxl-1541, ptbxl-2590, ptbxl-3265, ptbxl-6233, ptbxl-6536 | ptbxl-9, ptbxl-79, ptbxl-165, ptbxl-57, ptbxl-440 |
| AF_AFL | ptbxl-3784, ptbxl-9926, ptbxl-10360, ptbxl-11418, ptbxl-4990 | ptbxl-347, ptbxl-598, ptbxl-569, ptbxl-2795, ptbxl-3041 |
