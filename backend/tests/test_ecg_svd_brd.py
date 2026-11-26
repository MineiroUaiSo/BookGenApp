"""E1 passo A: SVD (ecg.rvh) so com QRS de decisao < 120 ms (salvo eixo > 110 graus); QRS >= 120 ms com R
dominante em V1 e sem padrao de BRE vira "Bloqueio de ramo direito provavel"."""
from __future__ import annotations

import pytest

from synth_ecg import synth_signal
from test_ecg_analysis import codes, run
from test_ecg_analysis_gen import PREC, sinus

R_DOM_V1 = [(0, 10, 1.0), (25, 8, -0.2)]   # R dominante em V1; ultima deflexao e uma "s" pequena (rb_v1 falha)


def _sinus_v1(v1, qrs_scale, axis_deg):
    prec = dict(PREC)
    prec["V1"] = v1
    L, _ = sinus(75, qrs_scale=qrs_scale, prec=prec, axis_deg=axis_deg, noise=0.005)
    return run(L)


def _finding(a, code):
    return next(f for f in a.findings if f.code == code)


# Regra do passo A NAO aplicada: aceite reprovado no PTB-XL dev (docs/benchmarks/trilha_r5_e1_log.md).
# strict=True: quando a regra for adotada, o XPASS forca remover esta marca.
@pytest.mark.xfail(strict=True, reason="E1 passo A reprovado no bench (sens BRD 71,9% < 75%; VPP SVD 21,8% < 40%)")
def test_svd_qrs_largo_r_dominante_v1_vira_brd_provavel_sem_svd():
    a = _sinus_v1(R_DOM_V1, 1.5, 30)
    assert a.global_measurements.qrs_ms >= 130
    c = codes(a)
    assert "ecg.rvh" not in c
    assert "ecg.rbbb" in c
    assert _finding(a, "ecg.rbbb").label == "Bloqueio de ramo direito provável"
    assert "ecg.ivcd" not in c


def test_svd_qrs_estreito_r_dominante_v1_continua_svd_sem_brd():
    a = _sinus_v1(R_DOM_V1, 1.0, 30)
    assert a.global_measurements.qrs_ms < 120
    c = codes(a)
    assert "ecg.rvh" in c
    assert not {"ecg.rbbb", "ecg.irbbb"} & c


def test_svd_qrs_largo_com_eixo_acima_de_110_mantem_svd():
    a = _sinus_v1(R_DOM_V1, 1.5, 120)
    c = codes(a)
    assert "ecg.rvh" in c
    assert "ecg.right_axis_deviation" in c


def test_brd_provavel_nao_dispara_com_padrao_de_bre():
    prec = dict(PREC)
    prec["V1"] = [(10, 14, -1.2)]
    prec["V2"] = [(10, 14, -1.6)]
    prec["V5"] = [(0, 14, 1.4), (30, 14, 0.9)]
    prec["V6"] = [(0, 14, 1.2), (30, 14, 0.8)]
    L, _ = sinus(70, qrs_scale=1.35, prec=prec, axis_deg=10, noise=0.005)
    a = run(L)
    c = codes(a)
    assert "ecg.lbbb" in c
    assert "ecg.rbbb" not in c and "ecg.rvh" not in c


def test_brd_completo_tipico_mantem_rotulo_sem_provavel():
    prec = dict(PREC)
    prec["V1"] = [(-30, 8, 0.25), (0, 10, -0.9), (35, 11, 1.0)]
    prec["V6"] = [(-20, 8, -0.1), (0, 10, 1.0), (40, 13, -0.5)]
    L, _ = sinus(75, qrs_scale=1.5, prec=prec, axis_deg=30, noise=0.005)
    a = run(L)
    assert _finding(a, "ecg.rbbb").label == "Bloqueio completo de ramo direito (BRD)"


def test_ritmo_normal_sem_rvh_nem_brd():
    a = run(synth_signal(hr=70, qrs_ms=90, noise_mv=0.005, seed=3)[0])
    assert not {"ecg.rvh", "ecg.rbbb"} & codes(a)
