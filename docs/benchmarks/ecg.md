# ECG benchmark results

_Generated 2026-11-24 12:18 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Diagnosis AF: sens / spec / PPV | 85% / 97% / 70% | PTB-XL, 1817 recs (156 pos) |
| Diagnosis AV1: sens / spec / PPV | 33% / 97% / 49% | PTB-XL, 1817 recs (135 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 63% / 99% / 73% | PTB-XL, 1817 recs (103 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 74% / 97% / 57% | PTB-XL, 1817 recs (102 pos) |
| Diagnosis LVH: sens / spec / PPV | 74% / 83% / 27% | PTB-XL, 1817 recs (140 pos) |
| Diagnosis MI_any: sens / spec / PPV | 33% / 93% / 62% | PTB-XL, 1817 recs (483 pos) |
| Diagnosis STACH: sens / spec / PPV | 67% / 98% / 65% | PTB-XL, 1817 recs (87 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 60% / 99% / 77% | PTB-XL, 1817 recs (93 pos) |
| NORM -> within normal limits; abnormal flagged | 67.9% (315/464); 82.7% (1119/1353) | PTB-XL, 1817 records |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

**Sources with no results in this run** (manifest missing/empty or dataset not downloadable): ludb, litfl, wikimedia_ecg, ecglibrary, ecg_image_db.

## PTB-XL: diagnostic statements

1817 records analysed (0 failed). Timing: median 0.32 s, p95 0.57 s, max 4.1 s per record (N=1817). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens % [95% CI] | Spec % [95% CI] | PPV % [95% CI] (this sample) | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 156 | 132 | 56 | 85 [78-89] | 97 [96-97] | 70 [63-76] | 65 (prev 6.9%) | 0.77 |
| AV1 | 1st-degree AV block (1AVB) | 135 | 44 | 45 | 33 [25-41] | 97 [96-98] | 49 [39-60] | 31 (prev 3.6%) | 0.39 |
| AV2 | 2nd-degree AV block (2AVB) | 2 | 0 | 6 | 0 [0-66] | 100 [99-100] | 0 [0-39] | 0 (prev 0.1%) | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 4 | 0 | 0 | 0 [0-49] | 100 [100-100] | - | - | 0.00 |
| RBBB_complete | complete RBBB (CRBBB) | 103 | 65 | 24 | 63 [53-72] | 99 [98-99] | 73 [63-81] | 53 (prev 2.5%) | 0.68 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 136 | 14 | 10 | 10 [6-17] | 99 [99-100] | 58 [39-76] | 48 (prev 5.1%) | 0.17 |
| RBBB_any | RBBB any | 238 | 107 | 6 | 45 [39-51] | 100 [99-100] | 95 [89-98] | 91 (prev 7.6%) | 0.61 |
| LBBB_complete | complete LBBB (CLBBB) | 102 | 75 | 57 | 74 [64-81] | 97 [96-97] | 57 [48-65] | 36 (prev 2.5%) | 0.64 |
| LBBB_any | LBBB any | 117 | 87 | 51 | 74 [66-81] | 97 [96-98] | 63 [55-71] | 42 (prev 2.8%) | 0.68 |
| LAFB | left anterior fascicular block | 151 | 53 | 36 | 35 [28-43] | 98 [97-98] | 60 [49-69] | 57 (prev 7.4%) | 0.44 |
| LPFB | left posterior fascicular block | 36 | 20 | 36 | 56 [40-70] | 98 [97-99] | 36 [24-49] | 18 (prev 0.8%) | 0.43 |
| WPW | WPW | 15 | 5 | 6 | 33 [15-58] | 100 [99-100] | 45 [21-72] | 27 (prev 0.4%) | 0.38 |
| LVH | left ventricular hypertrophy | 140 | 103 | 282 | 74 [66-80] | 83 [81-85] | 27 [23-31] | 28 (prev 8.0%) | 0.39 |
| RVH | right ventricular hypertrophy | 20 | 8 | 59 | 40 [22-61] | 97 [96-97] | 12 [6-22] | 6 (prev 0.5%) | 0.18 |
| LAE | left atrial enlargement | 81 | 3 | 42 | 4 [1-10] | 98 [97-98] | 7 [2-18] | 3 (prev 1.9%) | 0.05 |
| RAE | right atrial enlargement | 19 | 11 | 23 | 58 [36-77] | 99 [98-99] | 32 [19-49] | 17 (prev 0.4%) | 0.42 |
| LQT | long QT (LNGQT) | 23 | 18 | 214 | 78 [58-90] | 88 [86-89] | 8 [5-12] | 3 (prev 0.5%) | 0.14 |
| SBRAD | sinus bradycardia | 93 | 56 | 17 | 60 [50-70] | 99 [98-99] | 77 [66-85] | 65 (prev 2.9%) | 0.67 |
| STACH | sinus tachycardia | 87 | 58 | 31 | 67 [56-76] | 98 [97-99] | 65 [55-74] | 59 (prev 3.8%) | 0.66 |
| SR | sinus rhythm | 1223 | 1042 | 132 | 85 [83-87] | 78 [74-81] | 89 [87-90] | 93 (prev 76.8%) | 0.87 |
| MI_any | any MI (Q waves or ST elevation) | 483 | 159 | 96 | 33 [29-37] | 93 [91-94] | 62 [56-68] | 52 (prev 19.0%) | 0.43 |
| MI_inferior | inferior MI (IMI etc.) | 249 | 55 | 46 | 22 [17-28] | 97 [96-98] | 54 [45-64] | 46 (prev 10.3%) | 0.31 |
| MI_anterior | anterior/anteroseptal MI | 302 | 98 | 73 | 32 [27-38] | 95 [94-96] | 57 [50-64] | 47 (prev 11.7%) | 0.41 |
| MI_lateral | lateral MI | 157 | 40 | 44 | 25 [19-33] | 97 [96-98] | 48 [37-58] | 28 (prev 3.9%) | 0.33 |
| STTC | ST/T change (any) | 548 | 301 | 249 | 55 [51-59] | 80 [78-82] | 55 [51-59] | 48 (prev 24.5%) | 0.55 |
| STE | ST elevation (STE_) | 6 | 0 | 128 | 0 [0-39] | 93 [92-94] | 0 [0-3] | 0 (prev 0.1%) | 0.00 |
| STD | ST depression (STD_) | 131 | 82 | 333 | 63 [54-70] | 80 [78-82] | 20 [16-24] | 13 (prev 4.6%) | 0.30 |
| LOWV | low voltage (LVOLT) | 37 | 4 | 56 | 11 [4-25] | 97 [96-98] | 7 [3-16] | 3 (prev 0.8%) | 0.08 |
| NORM | NORM | 464 | 315 | 234 | 68 [64-72] | 83 [81-85] | 57 [53-61] | 75 (prev 43.3%) | 0.62 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 166 | 143 | 70 | 86 [80-91] | 96 [95-97] | 67 [61-73] | 61 (prev 7.2%) | 0.75 |

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 67.9% [63.5-72.0] (n=464) |
| gold NORM -> we raise >=1 abnormal/critical finding | 32.1% [28.0-36.5] (n=464) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 44.6% [40.2-49.2] (n=464) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 82.7% [80.6-84.6] (n=1353) |
| gold non-NORM -> we say within normal limits (missed) | 17.3% [15.4-19.4] (n=1353) |

### Heart rate vs rhythm statements

| SCP rhythm | N | our HR median (P10-P90) | HR consistent with label |
|---|---|---|---|
| SR | 1223 | 73 (59-91) | 84.8% (1037/1223) in 60-100 bpm |
| STACH | 87 | 109 (101-121) | 96.6% (84/87) in 100-+ bpm |
| SBRAD | 93 | 49 (44-57) | 95.7% (89/93) in 0-60 bpm |

### QRS axis vs metadata

| metadata axis (rows) | N | ours: left (<-30) | ours: normal | ours: right (>90) |
|---|---|---|---|---|
| left | 476 | 229 | 246 | 1 |
| normal | 465 | 2 | 441 | 22 |
| right | 58 | 10 | 6 | 42 |

Axis category agreement: 71.3% [68.4-74.0] (n=999) (metadata `heart_axis`: LAD/ALAD/AXL = left, RAD/ARAD/AXR = right, MID = normal; SAG excluded).

### Confusion highlights

| Class | What the FPs really are (gold SCP codes) | What we reported for FNs |
|---|---|---|
| AF | FP gold labels -> SR:22, PVC:18, NORM:13, SARRH:11 | FN our findings -> irregular_rhythm:10, secondary_repolarization:7, left_axis_deviation:6, sinus_rhythm:6 |
| AV1 | FP gold labels -> SR:28, LPR:16, NORM:11, PACE:9 | FN our findings -> sinus_rhythm:40, left_axis_deviation:27, long_qt:25, lvh:24 |
| AV2 | FP gold labels -> SR:4, NORM:2, CLBBB:2, SARRH:1 | FN our findings -> atrial_fibrillation:2, st_depression_inferior:1, long_qt:1 |
| AV3 | FP gold labels -> - | FN our findings -> secondary_repolarization:3, lvh:3, left_axis_deviation:2, long_qt:2 |
| RBBB_complete | FP gold labels -> IRBBB:22, SR:16, RVH:9, LAFB:7 | FN our findings -> rvh:29, ivcd:29, sinus_rhythm:20, left_axis_deviation:18 |
| RBBB_incomplete | FP gold labels -> CRBBB:6, SR:6, IMI:5, ABQRS:4 | FN our findings -> sinus_rhythm:80, left_axis_deviation:31, within_normal_limits:31, rbbb:23 |
| RBBB_any | FP gold labels -> SR:5, ASMI:4, IMI:3, ABQRS:2 | FN our findings -> sinus_rhythm:84, ivcd:45, left_axis_deviation:32, right_axis_deviation:31 |
| LBBB_complete | FP gold labels -> SR:36, IVCD:19, PACE:8, IMI:8 | FN our findings -> lvh:21, ivcd:20, st_depression_lateral:19, st_elevation_anterior:15 |
| LBBB_any | FP gold labels -> SR:31, IVCD:19, PACE:8, ASMI:6 | FN our findings -> ivcd:21, lvh:20, st_depression_lateral:19, t_inversion_lateral:16 |
| LAFB | FP gold labels -> SR:18, ABQRS:17, ASMI:13, ILMI:12 | FN our findings -> left_axis_deviation:92, sinus_rhythm:63, ivcd:41, secondary_repolarization:30 |
| LPFB | FP gold labels -> SR:19, IRBBB:11, ABQRS:9, AFIB:8 | FN our findings -> right_axis_deviation:14, rvh:10, sinus_rhythm:9, st_depression_inferior:8 |
| WPW | FP gold labels -> SR:4, NORM:3, LPFB:2, ASMI:2 | FN our findings -> sinus_rhythm:6, within_normal_limits:4, lbbb:3, secondary_repolarization:3 |
| LVH | FP gold labels -> SR:148, CLBBB:75, ASMI:51, AFIB:45 | FN our findings -> sinus_rhythm:18, st_depression_lateral:13, t_inversion_lateral:11, long_qt:9 |
| RVH | FP gold labels -> CRBBB:46, SR:28, AFIB:13, ABQRS:13 | FN our findings -> sinus_rhythm:10, rbbb:10, secondary_repolarization:9, left_axis_deviation:8 |
| LAE | FP gold labels -> SR:26, NORM:9, ASMI:6, CRBBB:6 | FN our findings -> sinus_rhythm:51, lvh:27, secondary_repolarization:19, long_qt:18 |
| RAE | FP gold labels -> SR:16, NORM:5, ASMI:4, ISCIL:4 | FN our findings -> sinus_rhythm:5, within_normal_limits:4, left_axis_deviation:2, atrial_flutter:2 |
| LQT | FP gold labels -> SR:152, ASMI:47, ABQRS:42, 1AVB:34 | FN our findings -> low_voltage:2, sinus_rhythm:2, left_axis_deviation:2, lvh:2 |
| SBRAD | FP gold labels -> LVH:4, ISC_:3, ASMI:3, ISCAS:2 | FN our findings -> sinus_rhythm:25, within_normal_limits:14, irregular_rhythm:8, lvh:8 |
| STACH | FP gold labels -> SR:17, LVH:7, ABQRS:6, ISC_:5 | FN our findings -> irregular_rhythm:12, lvh:9, left_axis_deviation:8, non_sinus_p:7 |
| SR | FP gold labels -> NORM:42, SARRH:35, PACE:27, SBRAD:25 | FN our findings -> irregular_rhythm:108, left_axis_deviation:43, lvh:41, within_normal_limits:37 |
| MI_any | FP gold labels -> PACE:40, SR:30, CLBBB:19, LVH:10 | FN our findings -> sinus_rhythm:191, left_axis_deviation:85, lvh:69, long_qt:67 |
| MI_inferior | FP gold labels -> PACE:24, SR:12, CRBBB:10, LAFB:9 | FN our findings -> sinus_rhythm:112, left_axis_deviation:70, long_qt:49, lvh:35 |
| MI_anterior | FP gold labels -> PACE:27, SR:24, CLBBB:16, LVH:10 | FN our findings -> sinus_rhythm:123, left_axis_deviation:57, lvh:55, st_depression_lateral:47 |
| MI_lateral | FP gold labels -> PACE:25, SR:12, LVH:6, ABQRS:4 | FN our findings -> sinus_rhythm:74, left_axis_deviation:49, ivcd:27, long_qt:26 |
| STTC | FP gold labels -> SR:113, ASMI:68, ABQRS:60, CRBBB:46 | FN our findings -> sinus_rhythm:154, within_normal_limits:90, long_qt:48, lvh:44 |
| STE | FP gold labels -> SR:55, ASMI:40, PACE:32, LAFB:19 | FN our findings -> sinus_rhythm:4, within_normal_limits:3, st_depression_anterolateral:1, atrial_fibrillation:1 |
| STD | FP gold labels -> SR:159, AFIB:71, ABQRS:70, ASMI:66 | FN our findings -> sinus_rhythm:26, within_normal_limits:14, lvh:8, t_inversion_lateral:8 |
| LOWV | FP gold labels -> SR:32, ASMI:17, ABQRS:17, AFIB:13 | FN our findings -> sinus_rhythm:21, within_normal_limits:17, left_axis_deviation:5, atrial_fibrillation:4 |
| NORM | FP gold labels -> SR:209, ABQRS:53, NDT:46, IRBBB:23 | FN our findings -> sinus_rhythm:83, ivcd:48, sinus_bradycardia:24, atrial_fibrillation:13 |
| AF_AFL | FP gold labels -> SR:29, PVC:18, NORM:16, 1AVB:15 | FN our findings -> irregular_rhythm:10, sinus_rhythm:7, st_depression_lateral:6, lvh:6 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-00076, ptbxl-00018, ptbxl-00266, ptbxl-00382, ptbxl-00756 | ptbxl-00017, ptbxl-02549, ptbxl-03166, ptbxl-05777, ptbxl-06221 |
| AV1 | ptbxl-00144, ptbxl-00190, ptbxl-00526, ptbxl-01166, ptbxl-01645 | ptbxl-00347, ptbxl-00524, ptbxl-00800, ptbxl-01014, ptbxl-01713 |
| AV2 | ptbxl-02560, ptbxl-10296, ptbxl-10965, ptbxl-11331, ptbxl-14219 | ptbxl-01222, ptbxl-19164 |
| AV3 | - | ptbxl-00959, ptbxl-08210, ptbxl-08620, ptbxl-11500 |
| RBBB_complete | ptbxl-00287, ptbxl-00569, ptbxl-00959, ptbxl-02409, ptbxl-02626 | ptbxl-01157, ptbxl-02311, ptbxl-03582, ptbxl-03784, ptbxl-03947 |
| RBBB_incomplete | ptbxl-01157, ptbxl-04044, ptbxl-14354, ptbxl-15203, ptbxl-15526 | ptbxl-00478, ptbxl-00569, ptbxl-00806, ptbxl-00856, ptbxl-00959 |
| RBBB_any | ptbxl-00287, ptbxl-04044, ptbxl-10950, ptbxl-14354, ptbxl-15647 | ptbxl-00478, ptbxl-00806, ptbxl-00856, ptbxl-01200, ptbxl-01612 |
| LBBB_complete | ptbxl-00223, ptbxl-00685, ptbxl-00688, ptbxl-01542, ptbxl-01717 | ptbxl-00287, ptbxl-01056, ptbxl-02135, ptbxl-03479, ptbxl-03484 |
| LBBB_any | ptbxl-00223, ptbxl-00688, ptbxl-01542, ptbxl-01717, ptbxl-01940 | ptbxl-00287, ptbxl-01056, ptbxl-02135, ptbxl-03479, ptbxl-03484 |
| LAFB | ptbxl-00184, ptbxl-00189, ptbxl-01627, ptbxl-02051, ptbxl-02158 | ptbxl-00172, ptbxl-00569, ptbxl-01906, ptbxl-01940, ptbxl-02033 |
| LPFB | ptbxl-00152, ptbxl-00478, ptbxl-00498, ptbxl-00800, ptbxl-00947 | ptbxl-02623, ptbxl-03947, ptbxl-04105, ptbxl-05951, ptbxl-07769 |
| WPW | ptbxl-09816, ptbxl-09952, ptbxl-10994, ptbxl-12340, ptbxl-13962 | ptbxl-04279, ptbxl-09823, ptbxl-09699, ptbxl-10822, ptbxl-11300 |
| LVH | ptbxl-00180, ptbxl-00190, ptbxl-00266, ptbxl-00281, ptbxl-00449 | ptbxl-00271, ptbxl-00347, ptbxl-00425, ptbxl-01307, ptbxl-01611 |
| RVH | ptbxl-00287, ptbxl-00498, ptbxl-00512, ptbxl-00947, ptbxl-01093 | ptbxl-02409, ptbxl-02748, ptbxl-03242, ptbxl-05338, ptbxl-07882 |
| LAE | ptbxl-00189, ptbxl-00334, ptbxl-00553, ptbxl-01093, ptbxl-01158 | ptbxl-00274, ptbxl-00299, ptbxl-00347, ptbxl-00524, ptbxl-00573 |
| RAE | ptbxl-00554, ptbxl-01157, ptbxl-01490, ptbxl-01426, ptbxl-01950 | ptbxl-01785, ptbxl-02123, ptbxl-04546, ptbxl-04863, ptbxl-04995 |
| LQT | ptbxl-00026, ptbxl-00028, ptbxl-00234, ptbxl-00266, ptbxl-00274 | ptbxl-02381, ptbxl-06515, ptbxl-14093, ptbxl-17298, ptbxl-18520 |
| SBRAD | ptbxl-00186, ptbxl-00383, ptbxl-01433, ptbxl-02062, ptbxl-02598 | ptbxl-00823, ptbxl-01717, ptbxl-02158, ptbxl-02317, ptbxl-02370 |
| STACH | ptbxl-00524, ptbxl-00544, ptbxl-00554, ptbxl-05062, ptbxl-05966 | ptbxl-01158, ptbxl-02160, ptbxl-02692, ptbxl-03337, ptbxl-04025 |
| SR | ptbxl-00128, ptbxl-00144, ptbxl-00190, ptbxl-00228, ptbxl-00281 | ptbxl-00223, ptbxl-00271, ptbxl-00266, ptbxl-00352, ptbxl-00377 |
| MI_any | ptbxl-00144, ptbxl-00190, ptbxl-00299, ptbxl-00498, ptbxl-00516 | ptbxl-00152, ptbxl-00223, ptbxl-00240, ptbxl-00274, ptbxl-00287 |
| MI_inferior | ptbxl-00144, ptbxl-00190, ptbxl-00234, ptbxl-00299, ptbxl-01093 | ptbxl-00184, ptbxl-00240, ptbxl-00266, ptbxl-00281, ptbxl-00425 |
| MI_anterior | ptbxl-00144, ptbxl-00425, ptbxl-00516, ptbxl-00544, ptbxl-01307 | ptbxl-00223, ptbxl-00274, ptbxl-00287, ptbxl-00512, ptbxl-00564 |
| MI_lateral | ptbxl-00144, ptbxl-00498, ptbxl-00516, ptbxl-01307, ptbxl-01399 | ptbxl-00152, ptbxl-00184, ptbxl-00189, ptbxl-00266, ptbxl-00281 |
| STTC | ptbxl-00144, ptbxl-00172, ptbxl-00190, ptbxl-00189, ptbxl-00234 | ptbxl-00026, ptbxl-00028, ptbxl-00039, ptbxl-00128, ptbxl-00116 |
| STE | ptbxl-00144, ptbxl-00190, ptbxl-00189, ptbxl-00234, ptbxl-00299 | ptbxl-02886, ptbxl-04059, ptbxl-04822, ptbxl-10061, ptbxl-12026 |
| STD | ptbxl-00152, ptbxl-00144, ptbxl-00171, ptbxl-00172, ptbxl-00190 | ptbxl-00318, ptbxl-00756, ptbxl-00861, ptbxl-00968, ptbxl-01175 |
| LOWV | ptbxl-00152, ptbxl-00612, ptbxl-00800, ptbxl-00947, ptbxl-02039 | ptbxl-01758, ptbxl-02158, ptbxl-02838, ptbxl-04145, ptbxl-05008 |
| NORM | ptbxl-00128, ptbxl-00116, ptbxl-00155, ptbxl-00160, ptbxl-00723 | ptbxl-00076, ptbxl-00069, ptbxl-00079, ptbxl-00100, ptbxl-00334 |
| AF_AFL | ptbxl-00076, ptbxl-00266, ptbxl-00382, ptbxl-00756, ptbxl-00800 | ptbxl-00017, ptbxl-00347, ptbxl-02549, ptbxl-05777, ptbxl-06221 |
