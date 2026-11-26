"""E1 passo B: PR exibido > 200 ms sem criterio completo de BAV1 -> achado borderline "conferir no tracado".
Nao muda ecg.av_block_1 nem os limiares AV1_*."""
from __future__ import annotations

from synth_ecg import synth_signal
from test_ecg_analysis import codes, run

CODE = "ecg.pr_gt200_unconfirmed"
LABEL = ("PR medido acima de 200 ms sem critério completo de BAV de 1º grau: conferir no traçado")


def _run(pr_ms):
    return run(synth_signal(hr=70, pr_ms=pr_ms, noise_mv=0.005, seed=3)[0])


def test_pr_borderline_pr_exibido_acima_de_200_sem_bav1_emite_achado():
    a = _run(205)
    assert a.global_measurements.pr_ms > 200
    c = codes(a)
    assert "ecg.av_block_1" not in c
    f = next(f for f in a.findings if f.code == CODE)
    assert f.severity == "borderline" and f.label == LABEL


def test_pr_borderline_nao_tira_do_neutro():
    assert "ecg.within_normal_limits" in codes(_run(205))


def test_pr_borderline_bav1_completo_nao_duplica_achado():
    a = _run(230)
    c = codes(a)
    assert "ecg.av_block_1" in c and CODE not in c


def test_pr_borderline_pr_normal_nao_emite():
    a = _run(160)
    assert a.global_measurements.pr_ms <= 200
    assert CODE not in codes(a)
