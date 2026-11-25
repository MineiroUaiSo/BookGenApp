"""Fast regression set: ~10 synthetic ECGs -> emitted finding codes compared with a versioned snapshot.

Regenerate deliberately with: MEDLENS_UPDATE_SNAPSHOT=1 pytest tests/test_ecg_regression_snapshot.py
(review the diff of tests/data/ecg_regression_snapshot.json before committing).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.ecg.analysis import analyze_signal
from app.schemas import ECGSignal, SourceKind
from synth_ecg import synth_signal

SNAP = Path(__file__).parent / "data" / "ecg_regression_snapshot.json"

CASES = {
    "normal_70": dict(hr=70, seed=1),
    "sinus_tachy_130": dict(hr=130, qt_ms=330, pr_ms=140, seed=1),
    "sinus_brady_45": dict(hr=45, seed=2),
    "av1_pr_280": dict(hr=70, pr_ms=280, seed=3),
    "wide_qrs_140": dict(hr=70, qrs_ms=140, seed=4),
    "long_qt_520": dict(hr=60, qt_ms=520, seed=5),
    "irregular_rr": dict(hr=80, rr_jitter=0.35, seed=6),
    "st_elev_v2_v4": dict(hr=70, st_by_lead={"V2": 0.3, "V3": 0.35, "V4": 0.3}, seed=7),
    "st_dep_v4_v6": dict(hr=70, st_by_lead={"V4": -0.2, "V5": -0.25, "V6": -0.2}, seed=8),
    "noisy_normal": dict(hr=70, noise_mv=0.12, wander_mv=0.3, seed=9),
}


def _codes(kwargs: dict) -> list[str]:
    leads, _ = synth_signal(seconds=10.0, **kwargs)
    sig = ECGSignal(fs=500, leads={k: [float(x) for x in v] for k, v in leads.items()}, duration_s=10.0,
                    source=SourceKind.CSV)
    return sorted({f.code for f in analyze_signal(sig, "snap").findings})


def test_regression_snapshot_codes_match_versioned_file():
    got = {name: _codes(kw) for name, kw in CASES.items()}
    if os.environ.get("MEDLENS_UPDATE_SNAPSHOT") == "1":
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(got, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    want = json.loads(SNAP.read_text())
    assert got == want


def test_regression_snapshot_covers_at_least_ten_cases():
    assert len(CASES) >= 10
