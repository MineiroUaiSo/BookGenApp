"""Regressão: 'preenche' dos índices ECG vinha como numpy.bool (500 na serialização de um ECG real)."""
import json

import numpy as np

from app.ecg.analysis import indices as ix


def test_idx_converte_numpy_bool_para_bool_nativo():
    d = ix._idx(1.234, "mm", 1.0, np.bool_(True), {"a": np.bool_(False)})
    assert type(d["preenche"]) is bool and d["preenche"] is True
    json.dumps(d)  # não pode levantar


def test_idx_preserva_string_e_none():
    assert ix._idx(None, "mm", None, "indeterminado", {})["preenche"] == "indeterminado"
    assert ix._idx(None, "mm", None, None, {})["preenche"] is None
