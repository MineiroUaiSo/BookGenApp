# bench/tuning

Versioned tuning artefacts (thresholds, rule parameters, calibration tables) live here as `*.json`.

Rules:
- Fit/choose values on **dev** records only (see `../splits.json`).
- Never write a test-split record id (e.g. `ludb-170`, PTB-XL strat_fold 9-10, `qtdb-*`) in these files,
  not even as a comment/provenance field. `tests/test_no_test_leak.py` fails the build if one appears.
- Record dev ids that justify a value if useful; keep datasets/caches out of git.
