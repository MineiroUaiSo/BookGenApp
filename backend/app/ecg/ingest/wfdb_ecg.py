"""WFDB (PhysioNet) reader — wfdb is an optional dependency."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.schemas import SourceKind

from .leads import build_signal, normalize_lead, to_mv


def load_wfdb(path: Path):
    try:
        import wfdb
    except ImportError as e:  # pragma: no cover
        raise ImportError("WFDB support needs the 'wfdb' package (pip install wfdb)") from e
    p = Path(path)
    base = str(p.with_suffix("")) if p.suffix.lower() in (".hea", ".dat", ".atr", ".xyz") else str(p)
    rec = wfdb.rdrecord(base)
    sig = rec.p_signal
    if sig is None:
        sig = rec.d_signal.astype(float)
    leads = {}
    units = rec.units or [None] * sig.shape[1]
    for j, name in enumerate(rec.sig_name):
        n = normalize_lead(name)
        if n and n not in leads:
            leads[n] = to_mv(np.asarray(sig[:, j], float), units[j] or "mV")
    if not leads:
        raise ValueError(f"no recognisable ECG leads in WFDB record ({rec.sig_name})")
    return build_signal(leads, float(rec.fs), SourceKind.WFDB)
