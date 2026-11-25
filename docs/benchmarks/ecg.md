# ECG benchmark results

_Generated 2026-11-25 20:39 UTC by `bench`._


## Summary

| Capability / metric | Result | Dataset, N |
|---|---|---|
| Delineation [dev]: QRS on/off within CSE tol | 56% / 71% | LUDB dev, 160 records |
| Delineation [dev]: P onset / T offset within CSE tol | 48% / 81% | LUDB dev, 160 records |
| Detection sensitivity [dev] QRS / P / T | 99% / 90% / 93% | LUDB dev, 160 records, 17355 beats |
| Delineation [test]: QRS on/off within CSE tol | 65% / 70% | LUDB test, 40 records |
| Delineation [test]: P onset / T offset within CSE tol | 50% / 88% | LUDB test, 40 records |
| Detection sensitivity [test] QRS / P / T | 100% / 96% / 97% | LUDB test, 40 records, 4488 beats |
| Diagnosis AF: sens / spec / PPV | 84% / 98% / 85% | PTB-XL, 9183 recs (1014 pos) |
| Diagnosis AV1: sens / spec / PPV | 40% / 98% / 54% | PTB-XL, 9183 recs (616 pos) |
| Diagnosis RBBB_complete: sens / spec / PPV | 58% / 99% / 69% | PTB-XL, 9183 recs (431 pos) |
| Diagnosis LBBB_complete: sens / spec / PPV | 79% / 96% / 49% | PTB-XL, 9183 recs (428 pos) |
| Diagnosis LVH: sens / spec / PPV | 75% / 86% / 44% | PTB-XL, 9183 recs (1156 pos) |
| Diagnosis MI_any: sens / spec / PPV | 39% / 96% / 70% | PTB-XL, 9183 recs (1942 pos) |
| Diagnosis STACH: sens / spec / PPV | 88% / 99% / 85% | PTB-XL, 9183 recs (637 pos) |
| Diagnosis SBRAD: sens / spec / PPV | 66% / 100% / 93% | PTB-XL, 9183 recs (509 pos) |
| NORM -> within normal limits; abnormal flagged | 74.6% (2101/2815); 81.8% (5212/6368) | PTB-XL, 9183 records |

**Caveats.** Not a medical-device validation. LUDB = 200 healthy-to-pathological 10 s records from one centre; PTB-XL labels are machine+human SCP statements with noise; absent statement != confirmed negative; image-caption agreement is weak evidence. Results are for the current rules/thresholds; re-run `python -m bench.ecg_bench` after changes.

**Sources with no results in this run** (manifest missing/empty or dataset not downloadable): litfl, wikimedia_ecg, ecglibrary, ecg_image_db.

## LUDB dev, records 1-160: wave delineation vs cardiologist annotations

160 records analysed (0 failed), 1916 record-leads; annotated beats 17355, P waves 12873, T waves 15494.  Timing: median 0.21 s, p95 0.59 s, max 1.2 s per record (N=160).

### Fiducial-point error vs cardiologist annotation (per lead, per matched beat)

| Fiducial | N matched | error ours-gold, mean ± SD (ms) | median \|err\| (ms) | CSE 2SD tol | within tol | within 2x tol |
|---|---|---|---|---|---|---|
| P onset | 11613 | -2.0 ± 31.8 | 12.0 | ±10.2 | 47.9% (5566/11613) | 72.0% (8365/11613) |
| P offset | 11613 | -2.6 ± 25.3 | 10.0 | ±12.7 | 58.7% (6819/11613) | 79.0% (9179/11613) |
| QRS onset | 17169 | -1.6 ± 14.5 | 6.0 | ±6.5 | 55.6% (9538/17169) | 78.5% (13482/17169) |
| QRS offset | 17169 | +3.3 ± 12.4 | 6.0 | ±11.6 | 70.9% (12178/17169) | 93.5% (16057/17169) |
| T offset | 14367 | -4.0 ± 37.6 | 16.0 | ±30.6 | 80.5% (11566/14367) | 92.0% (13217/14367) |

Tolerances: CSE 2-SD values (P on 10.2, P off 12.7, QRS on 6.5, QRS off 11.6, T off 30.6 ms) — Willems et al., _Methods Inf Med_ 1990;29:263; Martinez et al., _IEEE TBME_ 2004;51:570. Note: LUDB annotators place the QRS 'N' on the dominant deflection; error sign = ours - gold.

### Wave detection

| Wave | Sensitivity (detected / annotated) | PPV (correct / ours, matched beats) |
|---|---|---|
| QRS (beat match R ±75 ms) | 99.1% (17192/17355) | 98.9% (17192/17392) |
| P wave | 90.2% (11613/12873) | 75.9% (11613/15293) |
| T wave | 92.7% (14367/15494) | 87.8% (14367/16357) |

P/T counted detected when our peak lies within the annotated wave ±30 ms (P) / ±50 ms (T). PPV counts our waves in beats matched to an annotated beat.

### Global intervals (our median beat vs annotation: earliest onset / latest offset across leads, median over beats)

| Global interval | N records | error ours-gold mean ± SD | median \|err\| | within tolerance | Pearson r |
|---|---|---|---|---|---|
| PR | 131 | -6.5 ± 25.0 | 12.0 | 67.9% (89/131) (\|err\|<=20) | 0.71 |
| QRS | 160 | +0.9 ± 24.6 | 11.0 | 74.4% (119/160) (\|err\|<=20) | 0.72 |
| QT | 160 | -3.7 ± 33.1 | 18.0 | 78.8% (126/160) (\|err\|<=30) | 0.79 |
| HR (bpm) | 160 | +0.1 ± 2.8 | 0.4 | 93.1% (149/160) (\|err\|<=5) | 0.98 |

### Per-lead mean ± SD error (ms)

| Lead | P on | P off | QRS on | QRS off | T off |
|---|---|---|---|---|---|
| I | -4.6 ± 27.5 | -6.4 ± 20.4 | -3.0 ± 14.4 | +4.1 ± 13.0 | -6.5 ± 35.9 |
| II | +0.5 ± 23.8 | -6.8 ± 17.8 | -2.3 ± 14.4 | +3.1 ± 13.8 | -4.2 ± 33.1 |
| III | +2.2 ± 32.4 | +1.5 ± 28.8 | -6.2 ± 15.8 | +0.7 ± 14.3 | +1.2 ± 48.0 |
| aVR | -1.9 ± 24.3 | -6.9 ± 18.9 | -4.7 ± 17.8 | +3.9 ± 14.9 | -1.8 ± 36.9 |
| aVL | -2.4 ± 32.9 | -3.6 ± 27.8 | -5.6 ± 16.3 | +4.8 ± 13.2 | -2.8 ± 41.4 |
| aVF | -0.6 ± 24.4 | -3.8 ± 21.0 | -5.2 ± 14.2 | +2.9 ± 13.5 | -0.4 ± 40.6 |
| V1 | +2.7 ± 40.6 | +12.2 ± 32.3 | -0.7 ± 15.0 | +5.1 ± 12.1 | -2.2 ± 45.2 |
| V2 | -6.8 ± 42.2 | +2.1 ± 33.4 | +2.4 ± 13.4 | +3.8 ± 9.9 | -3.2 ± 36.3 |
| V3 | -3.7 ± 34.2 | -2.6 ± 26.9 | +3.5 ± 11.8 | +1.7 ± 9.8 | -6.2 ± 35.2 |
| V4 | -2.7 ± 29.5 | -5.4 ± 21.3 | +2.5 ± 11.7 | +1.9 ± 10.1 | -8.1 ± 30.9 |
| V5 | -2.7 ± 32.7 | -5.5 ± 21.8 | +0.9 ± 11.0 | +3.5 ± 10.0 | -7.4 ± 29.5 |
| V6 | -4.3 ± 31.6 | -5.9 ± 21.7 | -1.1 ± 11.6 | +3.7 ± 11.5 | -5.6 ± 34.1 |

### Worst examples

| Criterion | Worst record ids (mean \|err\|) |
|---|---|
| QRS onset | ludb-93 (79 ms), ludb-111 (54 ms), ludb-45 (45 ms), ludb-34 (39 ms), ludb-90 (34 ms) |
| QRS offset | ludb-74 (34 ms), ludb-10 (22 ms), ludb-93 (21 ms), ludb-103 (20 ms), ludb-35 (20 ms) |
| P onset | ludb-31 (72 ms), ludb-130 (58 ms), ludb-5 (50 ms), ludb-57 (42 ms), ludb-127 (42 ms) |
| T offset | ludb-57 (59 ms), ludb-130 (57 ms), ludb-15 (55 ms), ludb-124 (53 ms), ludb-61 (50 ms) |
| lowest QRS detection | ludb-116, ludb-111, ludb-83, ludb-45, ludb-34 |

### Diagnosis agreement with LUDB header statements (small N, indicative only)

LUDB header statements are free-text from the cardiologist (e.g. 'left ventricular hypertrophy' is attached to >50% of records, mostly without voltage criteria; median Sokolow-Lyon here is ~1.3 mV), so low sensitivity for LVH/LAFB mostly reflects label definition, not necessarily detector error.

| Class | N pos | Sens % [CI] | Spec % [CI] | PPV % [CI] | Missed ids |
|---|---|---|---|---|---|
| LVH | 93 | 0,0% [0,0–0,0] | 98,5% [95,5–100,0] | 0,0% [0,0–0,0] | ludb-2, ludb-3, ludb-7, ludb-6 |
| STTC | 36 | 50,0% [33,3–66,7] | 95,2% [91,1–98,4] | 75,0% [58,3–91,7] | ludb-3, ludb-8, ludb-4, ludb-13 |
| RBBB_any | 31 | 19,4% [6,5–35,5] | 99,2% [97,7–100,0] | 85,7% [57,1–100,0] | ludb-4, ludb-25, ludb-31, ludb-32 |
| SBRAD | 21 | 23,8% [9,5–42,9] | 100,0% [100,0–100,0] | 100,0% [100,0–100,0] | ludb-6, ludb-12, ludb-24, ludb-27 |
| LAFB | 15 | 0,0% [0,0–0,0] | 100,0% [100,0–100,0] | - | ludb-21, ludb-26, ludb-46, ludb-51 |
| AF | 14 | 78,6% [57,1–100,0] | 97,9% [95,2–100,0] | 78,6% [57,1–100,0] | ludb-8, ludb-93, ludb-95 |
| AV1 | 10 | 10,0% [0,0–30,0] | 98,0% [95,3–100,0] | 25,0% [0,0–75,0] | ludb-13, ludb-15, ludb-20, ludb-61 |
| LBBB_any | 10 | 40,0% [10,0–70,0] | 96,0% [92,7–98,7] | 40,0% [10,0–70,0] | ludb-19, ludb-54, ludb-83, ludb-112 |
| AV3 | 5 | 40,0% [0,0–80,0] | 98,1% [95,5–100,0] | 40,0% [0,0–80,0] | ludb-34, ludb-90, ludb-104 |
| RVH | 3 | 0,0% [0,0–0,0] | 98,7% [96,8–100,0] | 0,0% [0,0–0,0] | ludb-17, ludb-35, ludb-51 |
| STACH | 3 | 0,0% [0,0–0,0] | 100,0% [100,0–100,0] | - | ludb-70, ludb-114, ludb-117 |

## LUDB TEST, records 161-200: wave delineation vs cardiologist annotations

40 records analysed (0 failed), 480 record-leads; annotated beats 4488, P waves 3907, T waves 4044.  Timing: median 0.17 s, p95 0.22 s, max 0.2 s per record (N=40).

### Fiducial-point error vs cardiologist annotation (per lead, per matched beat)

| Fiducial | N matched | error ours-gold, mean ± SD (ms) | median \|err\| (ms) | CSE 2SD tol | within tol | within 2x tol |
|---|---|---|---|---|---|---|
| P onset | 3755 | +3.1 ± 24.9 | 12.0 | ±10.2 | 49.6% (1861/3755) | 76.4% (2868/3755) |
| P offset | 3755 | -0.3 ± 21.2 | 8.0 | ±12.7 | 65.9% (2475/3755) | 85.3% (3202/3755) |
| QRS onset | 4488 | +0.8 ± 8.3 | 4.0 | ±6.5 | 65.5% (2938/4488) | 88.2% (3960/4488) |
| QRS offset | 4488 | +2.7 ± 11.6 | 6.0 | ±11.6 | 69.6% (3123/4488) | 94.5% (4239/4488) |
| T offset | 3935 | -5.2 ± 31.7 | 12.0 | ±30.6 | 88.4% (3480/3935) | 95.1% (3742/3935) |

Tolerances: CSE 2-SD values (P on 10.2, P off 12.7, QRS on 6.5, QRS off 11.6, T off 30.6 ms) — Willems et al., _Methods Inf Med_ 1990;29:263; Martinez et al., _IEEE TBME_ 2004;51:570. Note: LUDB annotators place the QRS 'N' on the dominant deflection; error sign = ours - gold.

### Wave detection

| Wave | Sensitivity (detected / annotated) | PPV (correct / ours, matched beats) |
|---|---|---|
| QRS (beat match R ±75 ms) | 100.0% (4488/4488) | 100.0% (4488/4488) |
| P wave | 96.1% (3755/3907) | 86.8% (3755/4326) |
| T wave | 97.3% (3935/4044) | 89.2% (3935/4409) |

P/T counted detected when our peak lies within the annotated wave ±30 ms (P) / ±50 ms (T). PPV counts our waves in beats matched to an annotated beat.

### Global intervals (our median beat vs annotation: earliest onset / latest offset across leads, median over beats)

| Global interval | N records | error ours-gold mean ± SD | median \|err\| | within tolerance | Pearson r |
|---|---|---|---|---|---|
| PR | 39 | -8.9 ± 15.0 | 10.0 | 84.6% (33/39) (\|err\|<=20) | 0.82 |
| QRS | 40 | -7.4 ± 9.8 | 8.0 | 95.0% (38/40) (\|err\|<=20) | 0.65 |
| QT | 40 | -4.8 ± 20.9 | 15.0 | 77.5% (31/40) (\|err\|<=30) | 0.75 |
| HR (bpm) | 40 | +0.0 ± 1.4 | 0.4 | 100.0% (40/40) (\|err\|<=5) | 0.99 |

### Per-lead mean ± SD error (ms)

| Lead | P on | P off | QRS on | QRS off | T off |
|---|---|---|---|---|---|
| I | +3.6 ± 19.6 | -3.9 ± 13.4 | -1.2 ± 7.1 | +6.5 ± 10.0 | -7.5 ± 16.8 |
| II | +5.1 ± 16.8 | -5.7 ± 15.1 | +0.5 ± 7.5 | +2.8 ± 12.2 | -7.2 ± 27.2 |
| III | +7.0 ± 26.3 | +1.3 ± 19.1 | -3.2 ± 10.5 | +4.9 ± 18.6 | -1.6 ± 43.0 |
| aVR | +3.8 ± 14.8 | -3.9 ± 14.0 | -1.4 ± 10.1 | +4.9 ± 13.8 | -2.9 ± 25.1 |
| aVL | +7.9 ± 23.5 | -6.0 ± 20.5 | -3.8 ± 8.3 | +6.8 ± 12.2 | +2.9 ± 43.5 |
| aVF | +2.9 ± 21.9 | -1.4 ± 19.2 | -1.4 ± 8.2 | +2.7 ± 13.0 | -1.0 ± 32.4 |
| V1 | +11.9 ± 32.0 | +14.7 ± 34.9 | +4.5 ± 7.4 | +0.9 ± 8.7 | +0.5 ± 44.8 |
| V2 | +0.5 ± 33.1 | +4.3 ± 30.8 | +6.3 ± 7.7 | -0.8 ± 8.7 | -7.0 ± 26.3 |
| V3 | -3.1 ± 30.1 | +1.7 ± 19.4 | +4.4 ± 6.8 | -0.8 ± 8.6 | -8.9 ± 26.6 |
| V4 | +0.7 ± 22.4 | -1.7 ± 16.1 | +2.9 ± 6.1 | +0.5 ± 7.5 | -12.5 ± 25.3 |
| V5 | -0.7 ± 23.6 | -1.7 ± 16.1 | +2.0 ± 5.5 | +2.2 ± 8.4 | -9.5 ± 27.8 |
| V6 | -3.2 ± 25.2 | +0.1 ± 16.4 | +0.5 ± 5.5 | +1.8 ± 9.5 | -6.6 ± 27.9 |

### Worst examples

| Criterion | Worst record ids (mean \|err\|) |
|---|---|
| QRS onset | ludb-179 (12 ms), ludb-178 (11 ms), ludb-168 (8 ms), ludb-173 (8 ms), ludb-196 (8 ms) |
| QRS offset | ludb-170 (16 ms), ludb-169 (14 ms), ludb-178 (13 ms), ludb-176 (13 ms), ludb-185 (12 ms) |
| P onset | ludb-183 (29 ms), ludb-185 (28 ms), ludb-180 (25 ms), ludb-187 (24 ms), ludb-198 (22 ms) |
| T offset | ludb-180 (55 ms), ludb-179 (37 ms), ludb-163 (33 ms), ludb-183 (32 ms), ludb-190 (26 ms) |
| lowest QRS detection | ludb-161, ludb-162, ludb-163, ludb-164, ludb-165 |

### Diagnosis agreement with LUDB header statements (small N, indicative only)

LUDB header statements are free-text from the cardiologist (e.g. 'left ventricular hypertrophy' is attached to >50% of records, mostly without voltage criteria; median Sokolow-Lyon here is ~1.3 mV), so low sensitivity for LVH/LAFB mostly reflects label definition, not necessarily detector error.

| Class | N pos | Sens % [CI] | Spec % [CI] | PPV % [CI] | Missed ids |
|---|---|---|---|---|---|
| LVH | 15 | 0,0% [0,0–0,0] | 100,0% [100,0–100,0] | - | ludb-163, ludb-164, ludb-165, ludb-170 |
| SBRAD | 4 | 0,0% [0,0–0,0] | 100,0% [100,0–100,0] | - | ludb-170, ludb-169, ludb-172, ludb-189 |
| RBBB_any | 2 | 0,0% [0,0–0,0] | 100,0% [100,0–100,0] | - | ludb-176, ludb-185 |

## PTB-XL: diagnostic statements

9183 records analysed (0 failed). Timing: median 0.22 s, p95 0.40 s, max 3.2 s per record (N=9183). Ground truth = SCP statements in PTB-XL (a code counts as positive when likelihood >= 50 or 0 for non-diagnostic statements; all other records are negatives, so **specificity/PPV are lower bounds because absent statements are not proof of absence** and labels are known to be noisy). **STE_ is annotated inconsistently in PTB-XL, so STE is scored against two golds: STE_ (statement, kept) and STE_acute = any MI statement with infarction_stadium1 in {'Stadium I', 'Stadium I-II'} (same prediction).** The collector's PTB-XL subset is **class-enriched** (not the natural prevalence), so sample PPV is not prevalence-valid: the extra column re-computes PPV from sensitivity/specificity at the natural prevalence in the full ptbxl_database.csv (an approximation). Rare classes have wide CIs.

### Per-class performance

| Class | Meaning | N pos | TP | FP | Sens [IC95% bootstrap] | Spec [IC95%] | PPV [IC95%] (this sample) | Acc [IC95%] | PPV % at full-PTB-XL prevalence | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| AF | atrial fibrillation (AFIB) | 1014 | 849 | 153 | 83,7% [81,4–86,0] | 98,1% [97,8–98,4] | 84,7% [82,5–86,9] | 96,5% [96,2–96,9] | 77 (prev 6.9%) | 0.84 |
| AV1 | 1st-degree AV block (1AVB) | 616 | 247 | 208 | 40,1% [36,1–43,8] | 97,6% [97,2–97,9] | 54,3% [49,7–59,0] | 93,7% [93,2–94,2] | 38 (prev 3.6%) | 0.46 |
| AV2 | 2nd-degree AV block (2AVB) | 12 | 0 | 26 | 0,0% [0,0–0,0] | 99,7% [99,6–99,8] | 0,0% [0,0–0,0] | 99,6% [99,4–99,7] | 0 (prev 0.1%) | 0.00 |
| AV3 | 3rd-degree AV block (3AVB) | 12 | 4 | 18 | 33,3% [8,3–62,5] | 99,8% [99,7–99,9] | 18,2% [4,0–36,4] | 99,7% [99,6–99,8] | 11 (prev 0.1%) | 0.24 |
| RBBB_complete | complete RBBB (CRBBB) | 431 | 250 | 111 | 58,0% [53,4–62,8] | 98,7% [98,5–99,0] | 69,3% [64,6–73,9] | 96,8% [96,4–97,2] | 54 (prev 2.5%) | 0.63 |
| RBBB_incomplete | incomplete RBBB (IRBBB) | 731 | 138 | 96 | 18,9% [16,0–21,8] | 98,9% [98,6–99,1] | 59,0% [52,7–65,3] | 92,5% [92,0–93,0] | 47 (prev 5.1%) | 0.29 |
| RBBB_any | RBBB any | 1162 | 548 | 47 | 47,2% [44,3–49,9] | 99,4% [99,2–99,6] | 92,1% [89,8–94,2] | 92,8% [92,3–93,3] | 87 (prev 7.6%) | 0.62 |
| LBBB_complete | complete LBBB (CLBBB) | 428 | 336 | 350 | 78,5% [74,6–82,5] | 96,0% [95,6–96,4] | 49,0% [45,3–52,9] | 95,2% [94,8–95,7] | 33 (prev 2.5%) | 0.60 |
| LBBB_any | LBBB any | 489 | 386 | 432 | 78,9% [75,2–82,4] | 95,0% [94,6–95,5] | 47,2% [43,7–50,6] | 94,2% [93,7–94,7] | 31 (prev 2.8%) | 0.59 |
| LAFB | left anterior fascicular block | 977 | 118 | 43 | 12,1% [10,2–14,2] | 99,5% [99,3–99,6] | 73,3% [66,2–80,1] | 90,2% [89,6–90,8] | 65 (prev 7.4%) | 0.21 |
| LPFB | left posterior fascicular block | 141 | 19 | 60 | 13,5% [8,0–19,2] | 99,3% [99,2–99,5] | 24,1% [15,0–33,0] | 98,0% [97,7–98,3] | 14 (prev 0.8%) | 0.17 |
| WPW | WPW | 64 | 34 | 60 | 53,1% [40,9–65,7] | 99,3% [99,2–99,5] | 36,2% [26,2–46,0] | 99,0% [98,8–99,2] | 23 (prev 0.4%) | 0.43 |
| LVH | left ventricular hypertrophy | 1156 | 864 | 1094 | 74,7% [72,2–77,3] | 86,4% [85,6–87,1] | 44,1% [42,0–46,3] | 84,9% [84,2–85,6] | 32 (prev 8.0%) | 0.55 |
| RVH | right ventricular hypertrophy | 92 | 44 | 203 | 47,8% [37,6–58,4] | 97,8% [97,5–98,1] | 17,8% [12,9–22,9] | 97,3% [96,9–97,6] | 10 (prev 0.5%) | 0.26 |
| LAE | left atrial enlargement | 238 | 35 | 486 | 14,7% [10,3–19,3] | 94,6% [94,1–95,0] | 6,7% [4,6–9,0] | 92,5% [92,0–93,0] | 5 (prev 1.9%) | 0.09 |
| RAE | right atrial enlargement | 50 | 23 | 125 | 46,0% [32,7–59,6] | 98,6% [98,4–98,9] | 15,5% [10,0–21,6] | 98,3% [98,1–98,6] | 13 (prev 0.4%) | 0.23 |
| LQT | long QT (LNGQT) | 94 | 56 | 659 | 59,6% [49,5–69,8] | 92,7% [92,2–93,3] | 7,8% [5,9–10,0] | 92,4% [91,8–92,9] | 4 (prev 0.5%) | 0.14 |
| SBRAD | sinus bradycardia | 509 | 336 | 25 | 66,0% [62,1–70,2] | 99,7% [99,6–99,8] | 93,1% [90,3–95,7] | 97,8% [97,5–98,1] | 87 (prev 2.9%) | 0.77 |
| STACH | sinus tachycardia | 637 | 562 | 99 | 88,2% [85,7–90,7] | 98,8% [98,6–99,1] | 85,0% [82,1–87,6] | 98,1% [97,8–98,4] | 75 (prev 3.8%) | 0.87 |
| SR | sinus rhythm | 6081 | 5422 | 496 | 89,2% [88,3–89,9] | 84,0% [82,7–85,3] | 91,6% [90,9–92,3] | 87,4% [86,7–88,1] | 95 (prev 76.8%) | 0.90 |
| MI_any | any MI (Q waves or ST elevation) | 1942 | 749 | 315 | 38,6% [36,4–40,8] | 95,6% [95,2–96,1] | 70,4% [67,6–73,2] | 83,6% [82,8–84,3] | 67 (prev 19.0%) | 0.50 |
| MI_inferior | inferior MI (IMI etc.) | 979 | 275 | 128 | 28,1% [25,1–30,9] | 98,4% [98,2–98,7] | 68,2% [63,8–72,6] | 90,9% [90,3–91,5] | 67 (prev 10.3%) | 0.40 |
| MI_anterior | anterior/anteroseptal MI | 1280 | 445 | 191 | 34,8% [32,1–37,3] | 97,6% [97,2–97,9] | 70,0% [66,3–73,7] | 88,8% [88,2–89,4] | 66 (prev 11.7%) | 0.46 |
| MI_lateral | lateral MI | 371 | 125 | 124 | 33,7% [29,1–38,8] | 98,6% [98,3–98,8] | 50,2% [44,1–56,6] | 96,0% [95,6–96,4] | 49 (prev 3.9%) | 0.40 |
| STTC | ST/T change (any) | 3051 | 1459 | 930 | 47,8% [46,2–49,6] | 84,8% [83,9–85,7] | 61,1% [59,1–63,0] | 72,5% [71,7–73,5] | 51 (prev 24.5%) | 0.54 |
| STE | ST elevation (STE_) | 22 | 0 | 373 | 0,0% [0,0–0,0] | 95,9% [95,5–96,3] | 0,0% [0,0–0,0] | 95,7% [95,3–96,1] | 0 (prev 0.1%) | 0.00 |
| STD | ST depression (STD_) | 732 | 414 | 1480 | 56,6% [53,1–60,2] | 82,5% [81,7–83,3] | 21,9% [20,0–23,8] | 80,4% [79,6–81,2] | 14 (prev 4.6%) | 0.32 |
| STD_desc | ST depression, descriptive (st_depression_* OR strain) vs STD_ | 732 | 419 | 1624 | 57,2% [53,7–60,8] | 80,8% [79,9–81,7] | 20,5% [18,8–22,4] | 78,9% [78,1–79,7] | 13 (prev 4.6%) | 0.30 |
| STD_isch | ST depression, ischemic (st_depression_* only) vs ISC*/MI/STD_ | 3112 | 1313 | 581 | 42,2% [40,6–43,9] | 90,4% [89,7–91,1] | 69,3% [67,3–71,4] | 74,1% [73,2–75,0] | 64 (prev 28.3%) | 0.52 |
| LOWV | low voltage (LVOLT) | 145 | 22 | 174 | 15,2% [9,6–21,3] | 98,1% [97,8–98,4] | 11,2% [7,0–15,9] | 96,8% [96,4–97,1] | 6 (prev 0.8%) | 0.13 |
| NORM | NORM | 2815 | 2101 | 1156 | 74,6% [73,0–76,2] | 81,8% [80,9–82,8] | 64,5% [62,9–66,2] | 79,6% [78,8–80,5] | 76 (prev 43.3%) | 0.69 |
| PACE | pacemaker rhythm (PACE) | 237 | 105 | 5 | 44,3% [37,7–50,8] | 99,9% [99,9–100,0] | 95,5% [91,3–99,0] | 98,5% [98,2–98,7] | 92 (prev 1.3%) | 0.61 |
| AF_AFL | AF or flutter (AFIB+AFLT) | 1060 | 888 | 246 | 83,8% [81,6–85,9] | 97,0% [96,6–97,4] | 78,3% [76,0–80,7] | 95,4% [95,0–95,9] | 68 (prev 7.2%) | 0.81 |
| STE_acute | ST elevation vs acute-MI gold (MI + stadium I/I-II) | 123 | 63 | 310 | 51,2% [42,3–60,3] | 96,6% [96,2–97,0] | 16,9% [13,0–20,9] | 96,0% [95,6–96,4] | 9 (prev 0.7%) | 0.25 |

### STD split (descriptive vs ischemic)

Cases counted as STD only through secondary_repolarization_lvh (lost by the ischemic definition): 149; with ischemic gold label (ISC*/MI/STD_): 37; with STD_ label: 5.

### Normal-vs-abnormal screening

| Normal vs abnormal screening | Rate |
|---|---|
| gold NORM -> we say within normal limits | 74,6% [73,0–76,2] (n=2815) |
| gold NORM -> we raise >=1 abnormal/critical finding | 25,4% [23,8–27,0] (n=2815) |
| gold NORM -> we raise any non-normal finding (incl. borderline) | 63,5% [61,7–65,3] (n=2815) |
| gold non-NORM -> we raise >=1 abnormal/critical finding | 81,8% [80,9–82,8] (n=6368) |
| gold non-NORM -> we say within normal limits (missed) | 18,2% [17,2–19,1] (n=6368) |

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
| AF | FP gold labels -> PACE:40, SR:37, SARRH:25, PVC:25 | FN our findings -> st_not_assessable:88, irregular_rhythm:85, st_depression_lateral:57, lvh:49 |
| AV1 | FP gold labels -> SR:133, LVH:47, LAFB:40, ABQRS:40 | FN our findings -> st_not_assessable:228, sinus_rhythm:188, left_axis_deviation:122, lvh:101 |
| AV2 | FP gold labels -> SR:17, NORM:8, ABQRS:5, SBRAD:4 | FN our findings -> st_depression_lateral:6, sinus_tachycardia:5, short_pr:4, right_axis_deviation:3 |
| AV3 | FP gold labels -> SR:8, IRBBB:5, IMI:3, CRBBB:3 | FN our findings -> st_not_assessable:4, lvh:3, st_depression_lateral:3, irregular_rhythm:3 |
| RBBB_complete | FP gold labels -> IRBBB:89, SR:78, ABQRS:23, LAFB:22 | FN our findings -> rvh:119, st_not_assessable:104, sinus_rhythm:96, left_axis_deviation:88 |
| RBBB_incomplete | FP gold labels -> CRBBB:71, SR:55, AFIB:22, ABQRS:21 | FN our findings -> sinus_rhythm:419, st_not_assessable:305, within_normal_limits:224, left_axis_deviation:116 |
| RBBB_any | FP gold labels -> SR:17, ASMI:16, LAFB:12, AFIB:11 | FN our findings -> sinus_rhythm:413, st_not_assessable:409, within_normal_limits:226, left_axis_deviation:143 |
| LBBB_complete | FP gold labels -> SR:199, LVH:108, ISC_:106, LAFB:106 | FN our findings -> st_not_assessable:89, st_elevation_anterior:76, lvh:68, ivcd:59 |
| LBBB_any | FP gold labels -> SR:249, LVH:139, ISC_:136, ABQRS:126 | FN our findings -> st_not_assessable:99, st_elevation_anterior:79, lvh:72, ivcd:60 |
| LAFB | FP gold labels -> SR:18, IMI:16, ABQRS:16, AFIB:11 | FN our findings -> left_axis_deviation:815, st_not_assessable:605, sinus_rhythm:584, lvh:214 |
| LPFB | FP gold labels -> SR:27, NORM:18, AFIB:14, IRBBB:12 | FN our findings -> right_axis_deviation:100, secondary_repolarization:65, sinus_rhythm:65, rvh:62 |
| WPW | FP gold labels -> SR:39, ABQRS:25, IMI:13, STACH:12 | FN our findings -> st_not_assessable:23, sinus_rhythm:18, lbbb:11, secondary_repolarization:11 |
| LVH | FP gold labels -> SR:646, CLBBB:340, AFIB:186, LAFB:173 | FN our findings -> sinus_rhythm:181, st_not_assessable:150, st_depression_lateral:123, t_inversion_lateral:66 |
| RVH | FP gold labels -> CRBBB:152, SR:113, LPFB:49, AFIB:48 | FN our findings -> sinus_rhythm:39, rbbb:31, secondary_repolarization:30, left_axis_deviation:24 |
| LAE | FP gold labels -> SR:346, LVH:214, ISC_:157, ABQRS:73 | FN our findings -> sinus_rhythm:132, st_not_assessable:128, lvh:84, left_axis_deviation:71 |
| RAE | FP gold labels -> STACH:48, SR:46, NORM:26, ABQRS:25 | FN our findings -> sinus_rhythm:16, left_axis_deviation:12, sinus_tachycardia:7, secondary_repolarization:6 |
| LQT | FP gold labels -> SR:459, LVH:154, ABQRS:134, ISC_:132 | FN our findings -> sinus_rhythm:28, within_normal_limits:21, st_not_assessable:11, left_axis_deviation:7 |
| SBRAD | FP gold labels -> NORM:7, LAFB:4, LVH:3, 1AVB:3 | FN our findings -> sinus_rhythm:129, within_normal_limits:102, st_not_assessable:81, irregular_rhythm:32 |
| STACH | FP gold labels -> SR:39, NST_:23, ABQRS:17, ISC_:16 | FN our findings -> atrial_flutter:41, st_not_assessable:21, left_axis_deviation:20, st_depression_lateral:16 |
| SR | FP gold labels -> NORM:199, SBRAD:129, SARRH:107, LVH:52 | FN our findings -> irregular_rhythm:443, st_not_assessable:328, lvh:193, left_axis_deviation:185 |
| MI_any | FP gold labels -> SR:182, CLBBB:83, ABQRS:59, LVH:50 | FN our findings -> sinus_rhythm:676, st_not_assessable:613, left_axis_deviation:380, lvh:297 |
| MI_inferior | FP gold labels -> SR:64, ABQRS:50, WPW:28, ASMI:21 | FN our findings -> sinus_rhythm:406, st_not_assessable:352, left_axis_deviation:250, lvh:146 |
| MI_anterior | FP gold labels -> SR:114, CLBBB:76, LVH:43, ISC_:33 | FN our findings -> sinus_rhythm:457, st_not_assessable:452, left_axis_deviation:315, lvh:239 |
| MI_lateral | FP gold labels -> SR:70, LAFB:28, ABQRS:27, PACE:25 | FN our findings -> st_not_assessable:144, sinus_rhythm:134, left_axis_deviation:108, pathologic_q_anterior:63 |
| STTC | FP gold labels -> SR:503, ABQRS:307, ASMI:296, LAFB:166 | FN our findings -> sinus_rhythm:979, st_not_assessable:731, within_normal_limits:669, lvh:332 |
| STE | FP gold labels -> SR:220, ASMI:135, ABQRS:96, LAFB:78 | FN our findings -> sinus_rhythm:19, within_normal_limits:17, st_not_assessable:7, lvh_voltage:3 |
| STD | FP gold labels -> SR:762, LVH:496, ISC_:423, AFIB:374 | FN our findings -> sinus_rhythm:204, st_not_assessable:132, lvh:112, within_normal_limits:95 |
| STD_desc | FP gold labels -> SR:850, LVH:527, ISC_:449, AFIB:405 | FN our findings -> sinus_rhythm:201, st_not_assessable:127, lvh:107, within_normal_limits:95 |
| STD_isch | FP gold labels -> SR:284, NST_:172, AFIB:142, NDT:86 | FN our findings -> sinus_rhythm:1095, st_not_assessable:997, left_axis_deviation:624, lvh:440 |
| LOWV | FP gold labels -> SR:83, ABQRS:57, ASMI:53, AFIB:40 | FN our findings -> sinus_rhythm:96, within_normal_limits:77, st_not_assessable:61, left_axis_deviation:14 |
| NORM | FP gold labels -> SR:1018, NDT:418, ABQRS:210, IRBBB:156 | FN our findings -> st_not_assessable:275, sinus_rhythm:266, sinus_bradycardia:189, sinus_tachycardia:155 |
| PACE | FP gold labels -> LAFB:2, IMI:2, ABQRS:2, SR:2 | FN our findings -> lvh:58, st_not_assessable:50, left_axis_deviation:48, sinus_rhythm:48 |
| AF_AFL | FP gold labels -> SR:77, STACH:50, NORM:47, 1AVB:46 | FN our findings -> st_not_assessable:89, irregular_rhythm:87, st_depression_lateral:59, lvh:50 |
| STE_acute | FP gold labels -> SR:177, ASMI:88, CLBBB:77, LAFB:62 | FN our findings -> st_not_assessable:35, sinus_rhythm:31, lvh:23, left_axis_deviation:22 |

### Example ids for debugging

| Class | False-positive ids (first 5) | False-negative ids (first 5) |
|---|---|---|
| AF | ptbxl-00423, ptbxl-00517, ptbxl-00602, ptbxl-00757, ptbxl-00882 | ptbxl-00547, ptbxl-00699, ptbxl-00759, ptbxl-00923, ptbxl-00942 |
| AV1 | ptbxl-00269, ptbxl-00385, ptbxl-00507, ptbxl-00621, ptbxl-00676 | ptbxl-00182, ptbxl-00346, ptbxl-00522, ptbxl-00555, ptbxl-00556 |
| AV2 | ptbxl-00273, ptbxl-03254, ptbxl-05670, ptbxl-06553, ptbxl-06629 | ptbxl-03505, ptbxl-08048, ptbxl-09136, ptbxl-10300, ptbxl-11209 |
| AV3 | ptbxl-00477, ptbxl-01006, ptbxl-02145, ptbxl-04735, ptbxl-06466 | ptbxl-02047, ptbxl-07688, ptbxl-09322, ptbxl-10505, ptbxl-15368 |
| RBBB_complete | ptbxl-00482, ptbxl-00932, ptbxl-01063, ptbxl-01444, ptbxl-01466 | ptbxl-00428, ptbxl-00957, ptbxl-01570, ptbxl-01575, ptbxl-01688 |
| RBBB_incomplete | ptbxl-00957, ptbxl-01126, ptbxl-01575, ptbxl-02017, ptbxl-02201 | ptbxl-00052, ptbxl-00087, ptbxl-00222, ptbxl-00255, ptbxl-00236 |
| RBBB_any | ptbxl-01063, ptbxl-01126, ptbxl-02201, ptbxl-02815, ptbxl-03006 | ptbxl-00052, ptbxl-00087, ptbxl-00222, ptbxl-00255, ptbxl-00236 |
| LBBB_complete | ptbxl-00282, ptbxl-00325, ptbxl-00413, ptbxl-00423, ptbxl-00507 | ptbxl-00635, ptbxl-00730, ptbxl-00822, ptbxl-01694, ptbxl-01710 |
| LBBB_any | ptbxl-00325, ptbxl-00349, ptbxl-00413, ptbxl-00507, ptbxl-00551 | ptbxl-00635, ptbxl-00730, ptbxl-00822, ptbxl-01694, ptbxl-01710 |
| LAFB | ptbxl-00840, ptbxl-06926, ptbxl-07097, ptbxl-07159, ptbxl-07412 | ptbxl-00182, ptbxl-00220, ptbxl-00235, ptbxl-00260, ptbxl-00305 |
| LPFB | ptbxl-00222, ptbxl-00367, ptbxl-00626, ptbxl-00689, ptbxl-01273 | ptbxl-00428, ptbxl-00547, ptbxl-00635, ptbxl-00788, ptbxl-01066 |
| WPW | ptbxl-00550, ptbxl-00738, ptbxl-00858, ptbxl-01547, ptbxl-03514 | ptbxl-02145, ptbxl-07046, ptbxl-07291, ptbxl-07399, ptbxl-07407 |
| LVH | ptbxl-00085, ptbxl-00256, ptbxl-00257, ptbxl-00279, ptbxl-00286 | ptbxl-00211, ptbxl-00423, ptbxl-00502, ptbxl-00513, ptbxl-00540 |
| RVH | ptbxl-00428, ptbxl-00635, ptbxl-00903, ptbxl-01044, ptbxl-01049 | ptbxl-00222, ptbxl-00667, ptbxl-03050, ptbxl-03244, ptbxl-03504 |
| LAE | ptbxl-00002, ptbxl-00269, ptbxl-00286, ptbxl-00289, ptbxl-00296 | ptbxl-00489, ptbxl-00616, ptbxl-00652, ptbxl-00711, ptbxl-00713 |
| RAE | ptbxl-00108, ptbxl-00260, ptbxl-00550, ptbxl-00738, ptbxl-00860 | ptbxl-00626, ptbxl-00857, ptbxl-00970, ptbxl-01670, ptbxl-05334 |
| LQT | ptbxl-00316, ptbxl-00349, ptbxl-00413, ptbxl-00429, ptbxl-00447 | ptbxl-00260, ptbxl-04132, ptbxl-05046, ptbxl-05301, ptbxl-05586 |
| SBRAD | ptbxl-00191, ptbxl-00507, ptbxl-01075, ptbxl-01126, ptbxl-01277 | ptbxl-00225, ptbxl-00235, ptbxl-00284, ptbxl-01168, ptbxl-01232 |
| STACH | ptbxl-00222, ptbxl-00550, ptbxl-00858, ptbxl-00942, ptbxl-01033 | ptbxl-00698, ptbxl-00855, ptbxl-01074, ptbxl-01214, ptbxl-01670 |
| SR | ptbxl-00037, ptbxl-00225, ptbxl-00235, ptbxl-00350, ptbxl-00362 | ptbxl-00182, ptbxl-00222, ptbxl-00255, ptbxl-00256, ptbxl-00269 |
| MI_any | ptbxl-00222, ptbxl-00410, ptbxl-00621, ptbxl-00730, ptbxl-00822 | ptbxl-00106, ptbxl-00257, ptbxl-00263, ptbxl-00282, ptbxl-00290 |
| MI_inferior | ptbxl-00310, ptbxl-00455, ptbxl-00547, ptbxl-00730, ptbxl-00822 | ptbxl-00257, ptbxl-00270, ptbxl-00290, ptbxl-00325, ptbxl-00380 |
| MI_anterior | ptbxl-00621, ptbxl-00730, ptbxl-00822, ptbxl-00826, ptbxl-01319 | ptbxl-00106, ptbxl-00257, ptbxl-00263, ptbxl-00282, ptbxl-00482 |
| MI_lateral | ptbxl-00222, ptbxl-00310, ptbxl-00410, ptbxl-00855, ptbxl-01128 | ptbxl-00528, ptbxl-00547, ptbxl-00833, ptbxl-00924, ptbxl-00914 |
| STTC | ptbxl-00191, ptbxl-00211, ptbxl-00222, ptbxl-00310, ptbxl-00380 | ptbxl-00054, ptbxl-00087, ptbxl-00133, ptbxl-00209, ptbxl-00257 |
| STE | ptbxl-00410, ptbxl-00455, ptbxl-00532, ptbxl-00528, ptbxl-00608 | ptbxl-01596, ptbxl-01600, ptbxl-01725, ptbxl-02639, ptbxl-02868 |
| STD | ptbxl-00191, ptbxl-00211, ptbxl-00259, ptbxl-00263, ptbxl-00310 | ptbxl-00257, ptbxl-00313, ptbxl-00325, ptbxl-00337, ptbxl-00333 |
| STD_desc | ptbxl-00191, ptbxl-00211, ptbxl-00259, ptbxl-00263, ptbxl-00282 | ptbxl-00257, ptbxl-00313, ptbxl-00325, ptbxl-00337, ptbxl-00333 |
| STD_isch | ptbxl-00191, ptbxl-00211, ptbxl-00428, ptbxl-00522, ptbxl-00575 | ptbxl-00106, ptbxl-00257, ptbxl-00270, ptbxl-00269, ptbxl-00282 |
| LOWV | ptbxl-00255, ptbxl-00321, ptbxl-00532, ptbxl-00547, ptbxl-00604 | ptbxl-00001, ptbxl-00348, ptbxl-00407, ptbxl-00934, ptbxl-00971 |
| NORM | ptbxl-00054, ptbxl-00052, ptbxl-00106, ptbxl-00133, ptbxl-00192 | ptbxl-00002, ptbxl-00019, ptbxl-00012, ptbxl-00078, ptbxl-00085 |
| PACE | ptbxl-04377, ptbxl-10455, ptbxl-16970, ptbxl-19202, ptbxl-21243 | ptbxl-01461, ptbxl-01596, ptbxl-01641, ptbxl-02486, ptbxl-02885 |
| AF_AFL | ptbxl-00338, ptbxl-00423, ptbxl-00517, ptbxl-00602, ptbxl-00698 | ptbxl-00547, ptbxl-00699, ptbxl-00759, ptbxl-00858, ptbxl-00923 |
| STE_acute | ptbxl-00410, ptbxl-00455, ptbxl-00528, ptbxl-00608, ptbxl-00730 | ptbxl-02425, ptbxl-02525, ptbxl-03076, ptbxl-03956, ptbxl-04830 |

---
## Estado desta geracao (ECG)
- Data: 2026-11-25. Codigo base 2be7b23 (nenhum arquivo de backend/app/ecg mudou desde 592005b; 2be7b23 so acrescenta RX/laudo/UI). Gerado em worktree proprio (wt/ecg-final).
- Rodada completa e fresca, sem cache reaproveitado: LUDB (200: 160 dev + 40 teste) e PTB-XL dev large N=9183 (folds 1-8; folds 9-10 intocados), `--source all --split dev --set large --workers 8`. Reproduz exatamente os numeros do R4 (docs/benchmarks/r4_ptbxl_large.md): NORM -> normal 74,6% (2101/2815), AF 83,7%/84,7%, STD 56,6% / espec 82,5%, STE_acute sens 51,2% (FP 310/9060), LVH 74,7%/44,1%.
- Diferenca para a geracao anterior (c9a5a49): strain so anota (STD sens volta de 52,9% para 56,6%), Sokolow-Lyon `>=`, BRE/marca-passo declaram ST nao interpretavel (nunca saem como normal).
- Secao "Images" ausente: manifestos litfl/wikimedia/ecglibrary/ecg_image_db nao existem em data/datasets.
- QRS largo sem bloqueio (analise sobre o cache R3T8L, 9183 registros): a largura global (primeiro onset a ultimo offset) tem vies de +25 ms vs 12SL (ver r4_ptbxl_large.md), 4876/9183 registros tem QRS global >= 120 ms e 2970 deles sem BRD/BRE/IVCD/marca-passo, dos quais 1010 sao NORM no gold (34%). Por isso o aviso de ST por QRS largo continua "borderline" e a regra de IVCD usa a largura mista mediana-por-derivacao (E4); promover a "anormal" derrubaria NORM -> normal. Pergunta ao medico em RETOMADA.md.
- Teste externo CODE-test NAO rodado nesta geracao (uma unica vez, no fim; ver RETOMADA.md).
