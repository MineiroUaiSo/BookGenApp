"""R5 / E2: dupla contagem de QRS (onda T alta contada como R) nao pode virar taquicardia/FA falsa.

Guarda em rpeaks.detect_r_peaks: com FC detectada > 150 bpm e picos que alternam forca (R forte, T fraca) com
intervalo R->T estavel, as ondas T sao descartadas; o que continuar ambiguo sai com `unreliable=True`
(rpeaks.detect_r_peaks_ex). Taquicardia real (picos simetricos, mesma forca) nao pode mudar.

O teste metamorfico usa PTB-XL (NORM, dev) e e pulado quando o dataset nao esta disponivel."""
from __future__ import annotations

import random

import numpy as np
import pytest
from synth_ecg import LEAD_ORDER, _g, synth_signal
from test_ecg_analysis import codes, run

from app.ecg.analysis import rpeaks

FS = 500


def _tspike(hr, ratio=0.8, off=0.30, sd=0.012, seed=1, noise=0.01, rr_jitter=0.0, alt=None):
    """Sinal sintetico com uma 'onda T' estreita (pico) `off` s depois de cada R, de amplitude `ratio` x R
    (modo de falha real: o detector de energia de inclinacao conta a T como um segundo QRS)."""
    leads, fid = synth_signal(hr=hr, noise_mv=noise, seed=seed, rr_jitter=rr_jitter)
    t = np.arange(len(leads["II"])) / FS
    out = {}
    for k, v in leads.items():
        amp = max(float(v.max()), -float(v.min()))
        w = np.zeros_like(v)
        for i, rt in enumerate(fid["r_peaks_s"]):
            a = ratio * amp * (alt if alt and i % 2 else 1.0)
            w += a * np.sign(v[int(rt * FS)]) * _g(t, rt + off, sd)
        out[k] = v + w
    return out, fid


def _hr(a):
    return a.global_measurements.heart_rate_bpm


# ------------------------------------------------------------------ sintetico: T alta
@pytest.mark.parametrize("ratio", [0.5, 0.8])
def test_t_alta_75bpm_nao_dobra_a_fc_nem_vira_fa(ratio):
    leads, _ = _tspike(75, ratio=ratio)
    a = run(leads)
    assert abs(_hr(a) - 75) <= 3, _hr(a)
    assert "ecg.atrial_fibrillation" not in codes(a)
    assert "ecg.irregular_rhythm" not in codes(a)


def test_t_alta_com_jitter_de_rr_nao_vira_fa():
    leads, _ = _tspike(75, ratio=0.8, rr_jitter=0.08, seed=5)
    a = run(leads)
    assert abs(_hr(a) - 75) <= 6, _hr(a)
    assert "ecg.atrial_fibrillation" not in codes(a)


def test_t_alta_110bpm_nao_vira_taquicardia_de_220():
    leads, _ = _tspike(110, ratio=0.8, off=0.25)
    a = run(leads)
    assert abs(_hr(a) - 110) <= 4, _hr(a)


# ------------------------------------------------------------------ sintetico: taquicardia real continua
@pytest.mark.parametrize("hr", [160, 180])
def test_taquicardia_real_continua(hr):
    leads, _ = synth_signal(hr=hr, noise_mv=0.01, seed=1)
    assert abs(_hr(run(leads)) - hr) <= 5


def test_taquicardia_real_com_alternancia_eletrica_continua():
    """QRS alternando 100%/85% de amplitude (alternancia eletrica de TSV) com RR constante != R-T."""
    leads, fid = synth_signal(hr=160, noise_mv=0.01, seed=2)
    n = len(leads["II"])
    gain = np.ones(n)
    t = np.arange(n) / FS
    for i, rt in enumerate(fid["r_peaks_s"]):
        if i % 2:
            gain *= 1.0
            gain[(t > rt - 0.06) & (t < rt + 0.08)] = 0.85
    alt = {k: v * gain for k, v in leads.items()}
    assert abs(_hr(run(alt)) - 160) <= 5


# ------------------------------------------------------------------ guarda: unidade
def _amp_ref(leads):
    return np.stack([np.asarray(leads[k], float) for k in LEAD_ORDER])


def test_guarda_remove_t_e_nao_marca_ambiguo():
    leads, fid = _tspike(75, ratio=0.8)
    peaks, ref, unreliable = rpeaks.detect_r_peaks_ex(_amp_ref(leads), FS)
    hr = 60.0 * FS / np.median(np.diff(peaks))
    assert abs(hr - 75) <= 3 and not unreliable
    # compatibilidade: detect_r_peaks continua devolvendo (peaks, ref)
    p2, r2 = rpeaks.detect_r_peaks(_amp_ref(leads), FS)
    assert np.array_equal(p2, peaks) and r2 == ref


def test_guarda_ainda_rapido_apos_remover_t_marca_unreliable():
    """Candidatos R(forte)/T(fraca) a 120 ms: a T e removida, mas o que sobra segue a 162 bpm -> ambiguo."""
    n, fs = 5000, 500.0
    keep = np.array([int((0.3 + 0.37 * k + (0.12 if j else 0.0)) * fs) for k in range(12) for j in (0, 1)])
    mwi = np.zeros(n)
    mwi[keep[0::2]], mwi[keep[1::2]] = 1.0, 0.4
    new, unreliable = rpeaks._t_wave_guard(keep, mwi, fs)
    assert len(new) == 12 and unreliable


def test_guarda_alternancia_simetrica_nao_remove_picos():
    """Picos simetricos (T a meio ciclo) nunca sao descartados: a FC nao e dividida, mas o sinal avisa."""
    leads, _ = _tspike(75, ratio=0.5, off=0.40)
    peaks, _, unreliable = rpeaks.detect_r_peaks_ex(_amp_ref(leads), FS)
    assert 60.0 * FS / np.median(np.diff(peaks)) >= 145 and unreliable


def test_guarda_nao_dispara_em_taquicardia_real():
    leads, _ = synth_signal(hr=170, noise_mv=0.01, seed=3)
    peaks, _, unreliable = rpeaks.detect_r_peaks_ex(_amp_ref(leads), FS)
    assert abs(60.0 * FS / np.median(np.diff(peaks)) - 170) <= 5 and not unreliable


def test_guarda_nao_dispara_em_fc_normal():
    leads, _ = _tspike(75, ratio=0.8)
    # FC normal e sem T alta: nada muda e nada e marcado
    plain, _ = synth_signal(hr=75, noise_mv=0.01, seed=1)
    peaks, _, unreliable = rpeaks.detect_r_peaks_ex(_amp_ref(plain), FS)
    assert abs(60.0 * FS / np.median(np.diff(peaks)) - 75) <= 2 and not unreliable


# ------------------------------------------------------------------ metamorfico PTB-XL
def _norm_dev_records(n=200, seed=0):
    eb = pytest.importorskip("bench.ecg_bench")
    from bench import ptbxl_large
    try:
        recs = ptbxl_large.large_dev_records(eb.DATA_ROOT)   # PTB-XL strat_fold 1-8 (dev); nunca os folds 9-10
    except Exception:
        pytest.skip("PTB-XL (dev) indisponivel em MEDLENS_DATASETS")
    keep = [r for r in recs if r.get("kind", "signal") != "image" and eb.parse_scp(r).get("NORM", 0) >= 80
            and eb.resolve("ptbxl", r["path"]).exists()]
    if len(keep) < n:
        pytest.skip("PTB-XL (NORM, dev) indisponivel em MEDLENS_DATASETS")
    keep.sort(key=lambda r: r["id"])
    return eb, random.Random(seed).sample(keep, n)


def _taper_t(x, peaks, fs, gain=2.0):
    """Multiplica por `gain` a janela da onda T (R+80 ms .. R+min(450 ms, 0.7 RR)) com borda suave (sem degrau)."""
    out = np.array(x, float)
    n = out.shape[1]
    rr = np.diff(peaks)
    for i, p in enumerate(peaks):
        r_next = rr[i] if i < len(rr) else rr[-1]
        a, b = int(p + 0.08 * fs), int(p + min(0.45 * fs, 0.7 * r_next))
        if b - a < 10 or a >= n:
            continue
        b = min(b, n)
        w = np.hanning(b - a)
        out[:, a:b] *= 1.0 + (gain - 1.0) * w
    return out


def test_metamorfico_ptbxl_norm_t_x2_nao_muda_a_fc():
    eb, recs = _norm_dev_records()
    from app.ecg.analysis.preprocess import preprocess
    from app.ecg.ingest import load_ecg
    ok = 0
    for r in recs:
        sig = load_ecg(eb.resolve("ptbxl", r["path"]))
        X = np.stack([np.asarray(sig.leads[k], float) for k in LEAD_ORDER if k in sig.leads])
        amp0, _, _ = preprocess(X, sig.fs)
        p0, _ = rpeaks.detect_r_peaks(amp0, sig.fs)
        amp1, _, _ = preprocess(_taper_t(X, p0, sig.fs), sig.fs)
        p1, _ = rpeaks.detect_r_peaks(amp1, sig.fs)
        if len(p0) < 2 or len(p1) < 2:
            continue
        hr0 = 60.0 * sig.fs / np.median(np.diff(p0))
        hr1 = 60.0 * sig.fs / np.median(np.diff(p1))
        ok += abs(hr1 - hr0) <= 5
    assert ok / len(recs) >= 0.98, f"{ok}/{len(recs)}"
