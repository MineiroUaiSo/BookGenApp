"""Probabilidade calibrada (isotônica) e zonas de decisão por patologia para os escores do TorchXRayVision.

Curvas ajustadas em bench/calibrate_rx.py (IU dev, validação cruzada por paciente) e versionadas em
bench/tuning/rx_calibration.json. Arquivo ausente/inválido -> todas as funções devolvem None (comportamento anterior:
escore cru + limiar por patologia). Aviso: IU está no treino do TorchXRayVision (resultados otimistas) e os negativos
do dev são só estudos normais; a probabilidade vale para essa amostra, não para a prevalência de um serviço real.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

ZONE_NOT_SUGGESTED = "nao_sugerido"
ZONE_INDETERMINATE = "indeterminado"
ZONE_SUGGESTIVE = "sugestivo"

_PATH = Path(os.environ.get("MEDLENS_RX_CALIBRATION",
                            Path(__file__).resolve().parents[2] / "bench" / "tuning" / "rx_calibration.json"))
_CALIB: Optional[dict] = None
# Pathologies whose dev evidence is too thin to ever assert a result (3 IU positives): never 'não sugerido'.
INSUFFICIENT_EVIDENCE = {"Pneumothorax"}


def _load() -> dict:
    global _CALIB
    if _CALIB is None:
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            _CALIB = data.get("pathologies", {}) if isinstance(data, dict) else {}
        except Exception:
            _CALIB = {}
    return _CALIB


def _entry(pathology: str) -> Optional[dict]:
    e = _load().get(pathology)
    if not isinstance(e, dict) or len(e.get("x", [])) < 2 or len(e["x"]) != len(e.get("y", [])):
        return None
    return e


def calibrated_probability(pathology: str, score: float) -> Optional[float]:
    """Calibrated probability (monotone, clipped to the fitted range) or None when no curve exists."""
    e = _entry(pathology)
    if e is None:
        return None
    return float(np.interp(float(score), e["x"], e["y"]))


def zone(pathology: str, score: float) -> Optional[str]:
    """'nao_sugerido' (below raw_low/p_low, sens ~95% on dev) | 'indeterminado' | 'sugestivo' (>= raw_high/p_high, spec 90% on dev).

    None when there is no calibration for the pathology."""
    e = _entry(pathology)
    if e is None or "raw_low" not in e or "raw_high" not in e:
        return None
    # The calibration map is monotone, so cutting the calibrated probability at p_low/p_high is the same as cutting the
    # raw score at raw_low/raw_high; the raw cut avoids ambiguity on the flat steps of the isotonic curve.
    if score >= e["raw_high"]:
        return ZONE_SUGGESTIVE
    if score >= e["raw_low"]:
        return ZONE_INDETERMINATE
    return ZONE_NOT_SUGGESTED


def calibrate_scores(scores: dict[str, float]) -> tuple[dict[str, float], dict[str, str]]:
    """({pathology: calibrated probability}, {pathology: zone}) for the pathologies that have a curve."""
    probs: dict[str, float] = {}
    zones: dict[str, str] = {}
    for k, v in scores.items():
        p = calibrated_probability(k, v)
        z = zone(k, v)
        if p is not None and z is not None:
            probs[k] = round(p, 3)
            zones[k] = z
    return probs, zones
