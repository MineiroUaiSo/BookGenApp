# ECG benchmark results

_Generated 2026-11-24 11:15 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Delineation: QRS on/off within CSE tol | 32% / 57% | LUDB, 200 records |
| Delineation: P onset / T offset within CSE tol | 51% / 55% | LUDB, 200 records |
| Detection sensitivity QRS / P / T | 99% / 66% / 91% | LUDB, 21843 beats |
| Diagnosis AF: sens / spec / PPV | 30% / 99% / 75% | PTB-XL, 511 recs (40 pos) |
| Diagnosis AV1: sens / spec / PPV | 43% / 68% / 28% | PTB-XL, 511 recs (115 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 69% / 59% / 29% | PTB-XL, 511 recs (100 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 0% / 100% / -% | PTB-XL, 511 recs (100 pos) |
| Diagnosis LVH: sens / spec / PPV | 91% / 66% / 16% | PTB-XL, 511 recs (34 pos) |
| Diagnosis MI_any: sens / spec / PPV | 42% / 73% / 31% | PTB-XL, 511 recs (116 pos) |
| Diagnosis STACH: sens / spec / PPV | 39% / 98% / 60% | PTB-XL, 511 recs (31 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 65% / 93% / 24% | PTB-XL, 511 recs (17 pos) |
| NORM -> within normal limits; abnormal flagged | 12.7% (15/118); 99.5% (391/393) | PTB-XL, 511 records |
| Image pipeline usable (litfl) | 80% (exceptions 0) | N=5 |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

## LUDB: wave delineation vs cardiologist annotations

200 records analysed (0 failed), 2396 record-leads; annotated beats 21843, P waves 16780, T waves 19538.  Timing: median 0.50 s, p95 1.19 s, max 6.0 s per record (N=200).

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

## PTB-XL: diagnostic statements

511 records analysed (0 failed). Timing: median 0.52 s, p95 0.84 s, max 6.9 s per record (N=511). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens % [95% CI] | Spec % [95% CI] | PPV % [95% CI] (this sample) | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 40 | 12 | 4 | 30 [18-45] | 99 [98-100] | 75 [51-90] | 73 (prev 6.9%) | 0.43 |
| AV1 | 1st-degree AV block (1AVB) | 115 | 50 | 127 | 43 [35-53] | 68 [63-72] | 28 [22-35] | 5 (prev 3.6%) | 0.34 |
| AV2 | 2nd-degree AV block (2AVB) | 0 | 0 | 63 | - | 88 [85-90] | 0 [0-6] | - | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 2 | 0 | 4 | 0 [0-66] | 99 [98-100] | 0 [0-49] | 0 (prev 0.1%) | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 100 | 69 | 169 | 69 [59-77] | 59 [54-64] | 29 [24-35] | 4 (prev 2.5%) | 0.41 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 100 | 28 | 16 | 28 [20-37] | 96 [94-98] | 64 [49-76] | 28 (prev 5.1%) | 0.39 |
| RBBB_any | RBBB any | 199 | 126 | 156 | 63 [56-70] | 50 [44-56] | 45 [39-51] | 9 (prev 7.6%) | 0.52 |
| LBBB_complete | complete LBBB (CLBBB) | 100 | 0 | 0 | 0 [0-4] | 100 [99-100] | - | - | 0.00 |
| LBBB_any | LBBB any | 142 | 0 | 2 | 0 [0-3] | 99 [98-100] | 0 [0-66] | 0 (prev 2.8%) | 0.00 |
| LAFB | left anterior fascicular block | 53 | 4 | 1 | 8 [3-18] | 100 [99-100] | 80 [38-96] | 74 (prev 7.4%) | 0.14 |
| LPFB | left posterior fascicular block | 18 | 3 | 1 | 17 [6-39] | 100 [99-100] | 75 [30-95] | 40 (prev 0.8%) | 0.27 |
| WPW | WPW | 0 | 0 | 2 | - | 100 [99-100] | 0 [0-66] | - | 0.00 |
| LVH | left ventricular hypertrophy | 34 | 31 | 163 | 91 [77-97] | 66 [61-70] | 16 [11-22] | 19 (prev 8.0%) | 0.27 |
| RVH | right ventricular hypertrophy | 10 | 2 | 27 | 20 [6-51] | 95 [92-96] | 7 [2-22] | 2 (prev 0.5%) | 0.10 |
| LAE | left atrial enlargement | 33 | 18 | 167 | 55 [38-70] | 65 [61-69] | 10 [6-15] | 3 (prev 1.9%) | 0.17 |
| RAE | right atrial enlargement | 2 | 1 | 6 | 50 [9-91] | 99 [97-99] | 14 [3-51] | 16 (prev 0.4%) | 0.22 |
| LQT | long QT (LNGQT) | 1 | 1 | 327 | 100 [21-100] | 36 [32-40] | 0 [0-2] | 1 (prev 0.5%) | 0.01 |
| SBRAD | sinus bradycardia | 17 | 11 | 34 | 65 [41-83] | 93 [91-95] | 24 [14-39] | 22 (prev 2.9%) | 0.35 |
| STACH | sinus tachycardia | 31 | 12 | 8 | 39 [24-56] | 98 [97-99] | 60 [39-78] | 48 (prev 3.8%) | 0.47 |
| SR | sinus rhythm | 355 | 207 | 21 | 58 [53-63] | 87 [80-91] | 91 [86-94] | 93 (prev 76.8%) | 0.71 |
| MI_any | any MI (Q waves or ST elevation) | 116 | 49 | 108 | 42 [34-51] | 73 [68-77] | 31 [24-39] | 27 (prev 19.0%) | 0.36 |
| MI_inferior | inferior MI (IMI etc.) | 55 | 15 | 30 | 27 [17-40] | 93 [91-95] | 33 [21-48] | 32 (prev 10.3%) | 0.30 |
| MI_anterior | anterior/anteroseptal MI | 81 | 30 | 103 | 37 [27-48] | 76 [72-80] | 23 [16-30] | 17 (prev 11.7%) | 0.28 |
| MI_lateral | lateral MI | 28 | 10 | 9 | 36 [21-54] | 98 [96-99] | 53 [32-73] | 44 (prev 3.9%) | 0.43 |
| STTC | ST/T change (any) | 78 | 58 | 193 | 74 [64-83] | 55 [51-60] | 23 [18-29] | 35 (prev 24.5%) | 0.35 |
| STE | ST elevation (STE_) | 0 | 0 | 134 | - | 74 [70-77] | 0 [0-3] | - | 0.00 |
| STD | ST depression (STD_) | 15 | 8 | 193 | 53 [30-75] | 61 [57-65] | 4 [2-8] | 6 (prev 4.6%) | 0.07 |
| LOWV | low voltage (LVOLT) | 1 | 0 | 17 | 0 [0-79] | 97 [95-98] | 0 [0-18] | 0 (prev 0.8%) | 0.00 |
| NORM | NORM | 118 | 15 | 0 | 13 [8-20] | 100 [99-100] | 100 [80-100] | 100 (prev 43.3%) | 0.23 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 43 | 12 | 4 | 28 [17-43] | 99 [98-100] | 75 [51-90] | 72 (prev 7.2%) | 0.41 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 12.7% [7.9-19.9] (n=118) |
| gold NORM -> we raise >=1 abnormal/critical finding | 79.7% [71.5-85.9] (n=118) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 87.3% [80.1-92.1] (n=118) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 99.5% [98.2-99.9] (n=393) |
| gold non-NORM -> we say within normal limits (missed) | 0.0% [0.0-1.0] (n=393) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 355 | 73 (60-91) | 88.5% (314/355) in 60-100 bpm |
| STACH | 31 | 107 (101-120) | 96.8% (30/31) in 100-+ bpm |
| SBRAD | 17 | 50 (44-57) | 94.1% (16/17) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 158 | 86 | 72 | 0 |
| normal | 129 | 0 | 118 | 11 |
| right | 26 | 6 | 1 | 19 |

Axis category agreement: 71.2% [66.0-76.0] (n=313) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> CRBBB:3, PVC:2, BIGU:2, ASMI:1 | FN our findings -> non_sinus_p:19, rbbb:16, long_qt:16, lvh:15 |
| AV1 | FP gold labels -> SR:101, CLBBB:37, CRBBB:32, NORM:29 | FN our findings -> long_qt:45, non_sinus_p:31, lvh:27, lae:21 |
| AV2 | FP gold labels -> SR:48, 1AVB:20, IRBBB:17, NORM:12 | FN our findings -> - |
| AV3 | FP gold labels -> SR:4, IRBBB:2, ASMI:1, ALMI:1 | FN our findings -> rbbb:2, non_sinus_p:2, lvh:2, st_depression_inferior:1 |
| RBBB_complete | FP gold labels -> SR:111, CLBBB:95, 1AVB:33, ILBBB:28 | FN our findings -> ivcd:30, rvh:27, long_qt:23, left_axis_deviation:20 |
| RBBB_incomplete | FP gold labels -> SR:8, NORM:7, 1AVB:7, IMI:2 | FN our findings -> long_qt:42, sinus_rhythm:33, rbbb:29, lae:18 |
| RBBB_any | FP gold labels -> SR:101, CLBBB:95, 1AVB:38, ILBBB:29 | FN our findings -> long_qt:46, ivcd:32, sinus_rhythm:31, rvh:28 |
| LBBB_complete | FP gold labels -> - | FN our findings -> rbbb:95, lvh:86, st_elevation_anterior:79, long_qt:78 |
| LBBB_any | FP gold labels -> NORM:2, SR:2, 1AVB:1 | FN our findings -> rbbb:123, lvh:114, st_depression_lateral:99, long_qt:97 |
| LAFB | FP gold labels -> IRBBB:1, NST_:1, AFIB:1 | FN our findings -> left_axis_deviation:47, long_qt:39, rbbb:24, ivcd:21 |
| LPFB | FP gold labels -> NORM:1, IRBBB:1, SARRH:1 | FN our findings -> right_axis_deviation:12, ivcd:8, rvh:7, st_depression_inferior:7 |
| WPW | FP gold labels -> CLBBB:1, IRBBB:1, ISCAL:1, SR:1 | FN our findings -> - |
| LVH | FP gold labels -> SR:107, CLBBB:82, 1AVB:43, ASMI:27 | FN our findings -> st_depression_lateral:2, sinus_rhythm:1, rbbb:1, t_inversion_anterolateral:1 |
| RVH | FP gold labels -> CRBBB:25, LAFB:15, SR:11, ABQRS:10 | FN our findings -> rbbb:8, long_qt:6, left_axis_deviation:4, sinus_rhythm:3 |
| LAE | FP gold labels -> SR:126, 1AVB:48, CRBBB:37, CLBBB:36 | FN our findings -> long_qt:12, lvh:9, rbbb:9, st_depression_lateral:6 |
| RAE | FP gold labels -> SR:5, CRBBB:3, IMI:3, ASMI:2 | FN our findings -> sinus_rhythm:1, left_axis_deviation:1 |
| LQT | FP gold labels -> SR:244, CRBBB:79, CLBBB:78, 1AVB:69 | FN our findings -> - |
| SBRAD | FP gold labels -> SR:30, NORM:13, IRBBB:10, CRBBB:6 | FN our findings -> rbbb:3, irregular_rhythm:2, non_sinus_p:2, av_block_1:2 |
| STACH | FP gold labels -> SR:4, 1AVB:3, CLBBB:3, ASMI:3 | FN our findings -> long_qt:12, lvh:10, st_depression_lateral:9, rbbb:9 |
| SR | FP gold labels -> SARRH:10, IRBBB:8, NORM:7, 1AVB:5 | FN our findings -> long_qt:108, rbbb:69, lvh:59, lae:53 |
| MI_any | FP gold labels -> CLBBB:82, SR:70, 1AVB:18, PVC:15 | FN our findings -> long_qt:48, rbbb:28, lae:26, left_axis_deviation:22 |
| MI_inferior | FP gold labels -> SR:20, CLBBB:19, LAFB:9, 1AVB:8 | FN our findings -> long_qt:31, rbbb:20, lae:14, left_axis_deviation:14 |
| MI_anterior | FP gold labels -> CLBBB:83, SR:67, 1AVB:18, PVC:15 | FN our findings -> long_qt:37, rbbb:20, left_axis_deviation:20, sinus_rhythm:18 |
| MI_lateral | FP gold labels -> CRBBB:8, SR:7, LAFB:5, ABQRS:3 | FN our findings -> long_qt:13, rbbb:7, sinus_rhythm:7, left_axis_deviation:7 |
| STTC | FP gold labels -> SR:111, CLBBB:90, CRBBB:59, 1AVB:48 | FN our findings -> long_qt:13, sinus_rhythm:9, lae:9, lvh:7 |
| STE | FP gold labels -> SR:85, CLBBB:82, 1AVB:30, ASMI:23 | FN our findings -> - |
| STD | FP gold labels -> SR:114, CLBBB:79, CRBBB:57, 1AVB:47 | FN our findings -> long_qt:4, lae:3, sinus_rhythm:3, irbbb:2 |
| LOWV | FP gold labels -> SR:10, ASMI:8, 1AVB:6, CRBBB:6 | FN our findings -> lae:1, av_block_1:1, long_qt:1, sinus_bradycardia:1 |
| NORM | FP gold labels -> - | FN our findings -> long_qt:66, sinus_rhythm:62, av_block_1:31, lae:31 |
| AF_AFL | FP gold labels -> CRBBB:3, PVC:2, BIGU:2, ASMI:1 | FN our findings -> non_sinus_p:20, rbbb:18, lvh:18, long_qt:16 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-3784, ptbxl-9926, ptbxl-10360, ptbxl-11418 | ptbxl-598, ptbxl-569, ptbxl-3041, ptbxl-3835, ptbxl-3947 |
| AV1 | ptbxl-172, ptbxl-57, ptbxl-553, ptbxl-545, ptbxl-598 | ptbxl-234, ptbxl-524, ptbxl-685, ptbxl-800, ptbxl-1014 |
| AV2 | ptbxl-440, ptbxl-441, ptbxl-685, ptbxl-1713, ptbxl-1876 | - |
| AV3 | ptbxl-3568, ptbxl-8066, ptbxl-14493, ptbxl-21819 | ptbxl-8620, ptbxl-11500 |
| RBBB_complete | ptbxl-287, ptbxl-347, ptbxl-180, ptbxl-618, ptbxl-545 | ptbxl-172, ptbxl-1157, ptbxl-3582, ptbxl-3784, ptbxl-4068 |
| RBBB_incomplete | ptbxl-79, ptbxl-524, ptbxl-2476, ptbxl-3308, ptbxl-3891 | ptbxl-478, ptbxl-823, ptbxl-856, ptbxl-1261, ptbxl-1612 |
| RBBB_any | ptbxl-79, ptbxl-287, ptbxl-347, ptbxl-180, ptbxl-524 | ptbxl-172, ptbxl-478, ptbxl-856, ptbxl-1157, ptbxl-1261 |
| LBBB_complete | - | ptbxl-287, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598 |
| LBBB_any | ptbxl-758, ptbxl-18398 | ptbxl-287, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598 |
| LAFB | ptbxl-14671 | ptbxl-172, ptbxl-4068, ptbxl-4214, ptbxl-4586, ptbxl-5338 |
| LPFB | ptbxl-478 | ptbxl-1157, ptbxl-2623, ptbxl-3641, ptbxl-3947, ptbxl-4105 |
| WPW | ptbxl-7296, ptbxl-13248 | - |
| LVH | ptbxl-234, ptbxl-180, ptbxl-512, ptbxl-478, ptbxl-618 | ptbxl-2705, ptbxl-5062, ptbxl-17351 |
| RVH | ptbxl-172, ptbxl-1157, ptbxl-3582, ptbxl-4068, ptbxl-4586 | ptbxl-2748, ptbxl-3242, ptbxl-5338, ptbxl-5951, ptbxl-7882 |
| LAE | ptbxl-57, ptbxl-287, ptbxl-180, ptbxl-440, ptbxl-553 | ptbxl-524, ptbxl-796, ptbxl-4571, ptbxl-7518, ptbxl-7598 |
| RAE | ptbxl-1157, ptbxl-3582, ptbxl-5961, ptbxl-8348, ptbxl-14729 | ptbxl-4546 |
| LQT | ptbxl-9, ptbxl-165, ptbxl-172, ptbxl-287, ptbxl-180 | - |
| SBRAD | ptbxl-79, ptbxl-758, ptbxl-1200, ptbxl-2135, ptbxl-2746 | ptbxl-823, ptbxl-2359, ptbxl-3484, ptbxl-8251, ptbxl-8815 |
| STACH | ptbxl-5062, ptbxl-5966, ptbxl-7296, ptbxl-9144, ptbxl-9813 | ptbxl-1876, ptbxl-4893, ptbxl-6517, ptbxl-7055, ptbxl-8161 |
| SR | ptbxl-478, ptbxl-2368, ptbxl-2626, ptbxl-3855, ptbxl-5338 | ptbxl-79, ptbxl-234, ptbxl-441, ptbxl-618, ptbxl-685 |
| MI_any | ptbxl-180, ptbxl-618, ptbxl-598, ptbxl-798, ptbxl-1093 | ptbxl-287, ptbxl-512, ptbxl-800, ptbxl-1014, ptbxl-1157 |
| MI_inferior | ptbxl-234, ptbxl-180, ptbxl-798, ptbxl-1093, ptbxl-1367 | ptbxl-545, ptbxl-1157, ptbxl-1492, ptbxl-1907, ptbxl-1998 |
| MI_anterior | ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-598, ptbxl-798 | ptbxl-287, ptbxl-512, ptbxl-800, ptbxl-1014, ptbxl-1261 |
| MI_lateral | ptbxl-4586, ptbxl-5951, ptbxl-8348, ptbxl-10982, ptbxl-13100 | ptbxl-800, ptbxl-2311, ptbxl-5154, ptbxl-5574, ptbxl-6702 |
| STTC | ptbxl-172, ptbxl-234, ptbxl-180, ptbxl-512, ptbxl-618 | ptbxl-524, ptbxl-1612, ptbxl-1713, ptbxl-1998, ptbxl-4756 |
| STE | ptbxl-234, ptbxl-180, ptbxl-618, ptbxl-545, ptbxl-798 | - |
| STD | ptbxl-172, ptbxl-234, ptbxl-347, ptbxl-180, ptbxl-512 | ptbxl-4112, ptbxl-5062, ptbxl-8178, ptbxl-13913, ptbxl-13974 |
| LOWV | ptbxl-800, ptbxl-3582, ptbxl-6075, ptbxl-6803, ptbxl-8220 | ptbxl-8627 |
| NORM | - | ptbxl-9, ptbxl-79, ptbxl-165, ptbxl-57, ptbxl-440 |
| AF_AFL | ptbxl-3784, ptbxl-9926, ptbxl-10360, ptbxl-11418 | ptbxl-347, ptbxl-598, ptbxl-569, ptbxl-2795, ptbxl-3041 |

## Images: digitisation + analysis

Failure flags are heuristic proxies (the true failure rate needs a ground-truth comparison, available only for paired sources).

| Source | N | Exceptions | Grid conf < 0.3 | < 2 beats found | Usable (no failure flag) | Median leads | HR plausible (30-250) | Timing |
|---|---|---|---|---|---|---|---|---|
| litfl | 5 | 0.0% (0/5) | 20.0% (1/5) | 20.0% (1/5) | 80.0% (4/5) | 12 | 80.0% (4/5) | median 1.39 s, p95 3.11 s, max 3.2 s per record (N=5) |

### litfl

**Agreement with caption** (5 images whose caption/labels assert >=1 class we can detect; weak evidence: captions are incomplete and non-exhaustive, so 'extra' findings are not necessarily errors). Any asserted class recovered: 60.0% [23.1-88.2] (n=5).

| Caption class | N captions | Recovered by our findings | Our findings of this class on captions that don't mention it |
|---|---|---|---|
| AF | 5 | 60.0% (3/5) | 0 |

Failure examples: exceptions -; low grid confidence (<0.3) ['13b4f726efa24930']; <2 beats detected ['13b4f726efa24930'].
