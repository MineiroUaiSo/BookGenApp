# ECG image digitiser: experiment log

Scope: `backend/app/ecg/digitize/`. Data: LITFL images (486, CC BY-NC-SA). Split: deterministic by LITFL page
(`md5(extra.page_title or url) % 100 < 70` = dev, else test): 321 dev / 165 test images.
Run: `cd backend && python -m bench.ecg_bench --source litfl --litfl-split dev|test --workers 2 --force`
(prints the image report; `docs/benchmarks/ecg.md` is untouched). All tuning on dev; test run once at the end
(plus a before-run of the unmodified HEAD pipeline on test).

## What the images really look like
~15-20 % of the "ECG" images are not ECGs (anatomy/lead-placement drawings, QT nomograms, text pages, retina photos,
teaching diagrams with a drawn ECG). Those cannot be digitised meaningfully and are the floor of every proxy metric.
Real ECGs: full 3x4(+1 rhythm) pages in grey/pink/blue grids with the calibration pulse at the left *or right*;
3x4 pages without rhythm strip; 2-column x 3-row pages (V1-V3 | V4-V6); single or double rhythm strips; one-lead
crops with arrows/circles/text; low resolution (2-5 px/mm), faint grey traces, dark printed 5 mm grid lines.
No tesseract/OCR is installed, so lead labels are not read.

## Findings and changes (in order)
| # | Finding | Change | Effect on dev (usable / <2 beats / HR plausible) |
|---|---|---|---|
| 0 | baseline (HEAD) | - | 65.1 % / 25.6 % / 73.4 % |
| 1 | 1-2 row images and cropped pages were forced into the 3x4 template with 0.6 s columns; "trace length differs from 10 s" snapped to 2.5 s | new layout decision: 1-2 rows -> `strips` (first row named II); 3-5 rows -> 3x4(+1); column count kept at the nominal 2.5 s/column and dropped when the page is narrower; boundaries on the measured span when 7.5-12.5 s wide | 84.4 % / 1.0 % / 94.9 % |
| 2 | data origin assumed 9 mm after the left ink when no pulse found (lost the first beat); pulse only searched on the left | origin = first ink column when no pulse; pulse searched on the right edge too (data end = pulse) | (included above) |
| 3 | grid pitch: y profile polluted by trace rows (e.g. 24 px/mm vs 3.8 in x); 1 mm vs 5 mm harmonic confusions | square-grid consistency (disagreeing axis replaced by the more confident one); scale sanity from beat period (tall-QRS column spacing, autocorrelation fallback): wrong harmonic rescaled x5/x0.2/x2/x0.5 when HR would be outside 26-214 bpm; no grid at all -> scale from beat period (75 bpm) or 250 mm page width, confidence 0.1 | HR plausible 96.8 % |
| 4 | QRS strokes are thin and anti-aliased (V 0.5-0.72) and fall below the global ink threshold: only baseline/T survived, QRS lost | `grid.flatten`: divide out the separable grid (masked per-column x per-row medians) before thresholding; vertical closing (5 px) + 1-px fringe of fainter pixels touching ink | RBBB example (rbbb-06) now reports RBBB with QRS 128 ms |
| 5 | dark printed vertical grid lines became full-height spikes | `trace.remove_grid_lines` (>=3 thin streaks with >50 % column coverage) | test in `test_digitize_real.py` |
| 6 | all 2.5 s leads of a 3x4 page without rhythm strip have equal length, so the analysis treated them as simultaneous (HR doubled, false tachycardia/AF) | `analysis._align_segments` now also checks `offset_s.*` (one-line change outside digitize/) | removes false tachycardia on 3-row pages |
| 7 | cropped 2-column chest pages mislabelled I-III/aVR-aVF | `trace.classify_triplet/assign_triplets`: Einthoven/Goldberger residual ratios identify limb groups from physics; only used on narrow pages and only on strong evidence (on noisy scans the ratios are unreliable: median 0.9 on wide pages, so wide pages keep the standard order) | n/a (no truth) |
| 8 | tried: tick-mark detection for column borders | no gain (nominal borders already agreed with ticks in the example) and moved peaks around; removed | - |

## Dev before/after (321 images)
| | Exceptions | Grid conf < 0.3 | < 2 beats | Usable | HR plausible | median time |
|---|---|---|---|---|---|---|
| before | 5.0 % | 15.7 % | 25.6 % | 65.1 % | 73.4 % | 0.81 s |
| after | 1.9 % | 13.0 % | 2.2 % | 84.1 % | 96.5 % | 1.87 s (machine under load) |

Caption agreement (dev, recovered / n): any class 28.0 % -> 27.9 %; STTC 45.9 -> 32.9 %; MI 35.0 -> 35.0 %;
RBBB 0/39 -> 4/38; LBBB 0/24 -> 0/23; WPW 0/19 -> 0/19; AF 58.8 -> 76.5 %; AV2/AV3 0; LVH 18 -> 30 %; LQT 18 -> 28 %.

## Test before/after (165 images, evaluated once)
| | Exceptions | Grid conf < 0.3 | < 2 beats | Usable | HR plausible |
|---|---|---|---|---|---|
| before (HEAD) | 3.0 % | 12.5 % | 1.2 % | 83.6 % | 98.1 % |
| after | 4.8 % | 11.5 % | 0.0 % | 84.2 % | 100 % |

Caption agreement (test): any class 35.8 % -> 32.6 % (n=95); RBBB 2/12 -> 2/12; STTC 50 -> 49 %; MI 45 -> 36 %;
AF 90 -> 80 %; LPFB 2/6 -> 0/6; AV2/AV3/AV1/LBBB/WPW 0.

## Honest reading
* Dev usable 65 -> 84 % is mostly layout fixes (strips, cropped pages, no pulse): the old pipeline produced
  garbage for ~1/4 of the images (<2 beats). On the test split the old pipeline was already at 84 % by the same proxy
  (different mix of images), so the proxy gain does not replicate there; the caption-agreement numbers are flat to
  slightly worse within the (wide) confidence intervals (n = 95-219 captions).
* Morphology is better on clean 12-lead pages (QRS spikes preserved, grid lines gone) but the diagnostic classes the
  task targets (RBBB, LBBB, AV block, WPW) stay near 0 on images: most captioned images are single-lead V1/V6 crops,
  2-row teaching figures or pages where the lead identity is unknown without reading the label (we default to II),
  and AV-block/WPW need rules that are not driven by digitiser quality.
* False AF stays high (~120 extra on dev): the analysis builds R peaks from staggered 2.5 s segments with +-70 ms
  jitter versus the per-lead peaks (checked on a clean page: per-lead RR 0.76-0.79 s, analysis RR 0.64-0.90 s). That
  is an analysis-side issue (rhythm from segmented pages), not the digitiser.
* Not done: lead-label OCR (no OCR engine installed; would fix V1/V6 crops and V-lead pages), learned
  trace/grid segmentation (the classical flatten + hysteresis fix removed the main failure without a model),
  overlapping-row separation (rows whose traces cross).
