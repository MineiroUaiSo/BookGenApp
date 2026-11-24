"""ECG analysis without AI: preprocessing, R peaks, delineation, measurements, rhythm, rules.

Conventions (contract with the frontend):
  * Wave times are absolute milliseconds from the start of the signal; beat_index is 0-based and
    indexes `r_peaks_ms` (beats too close to the signal borders have no waves).
  * median_beats[lead] is sampled at signal.fs and starts exactly 300 ms BEFORE the R peak
    (R-peak sample index inside the array = round(0.3*fs) = `median_beat_r_index`); it ends
    ~0.75*RR (max 700 ms, min 450 ms) after the R peak. `median_waves` are the fiducials of the median
    beat in ms relative to the first sample of the median beat array (beat_index = -1).
  * ConductionPhase times are relative to the P-wave onset (global) of the representative (median)
    beat; the SA phase therefore starts slightly negative. Without P wave (AF) they are relative to
    R - 200 ms.
  * Amplitudes (mV) are relative to the PR-segment isoelectric level of each lead; Q and S
    amplitudes are negative.
Optional dependency neurokit2 is not required (own implementation).
"""
from __future__ import annotations

import numpy as np

from ...schemas import (ECGAnalysis, ECGSignal, GlobalMeasurements, Wave, WaveKind)
from ..conduction import conduction_timeline
from .delineate import delineate_beat
from .leads import ALL_LEADS, derive_missing, normalize
from .measure import MEDIAN_PRE_MS, build_median, measure_median
from .preprocess import noise_sigma, preprocess
from .rhythm import av_analysis, detect_p_series, rr_stats
from .rpeaks import detect_r_peaks
from .rules import build_findings, classify_rhythm

_KIND = {"P": WaveKind.P, "Q": WaveKind.Q, "R": WaveKind.R, "S": WaveKind.S, "R'": WaveKind.R_PRIME,
         "T": WaveKind.T, "U": WaveKind.U}


def _waves(bd, leads, fs, offset, beat_index, t0=0.0):
    """Convert BeatDel to Wave list; time(ms) = (idx + offset)*1000/fs - t0."""
    ms = 1000.0 / fs
    T = lambda i: round((i + offset) * ms - t0, 2)
    out = []
    for lead in leads:
        ld = bd.leads[lead]
        if ld.waves:
            main = max(ld.waves, key=lambda w: abs(w.amp))
            out.append(Wave(kind=WaveKind.QRS, lead=lead, beat_index=beat_index, onset_ms=T(ld.qrs_on),
                            peak_ms=T(main.peak), offset_ms=T(ld.qrs_off), amplitude_mv=round(ld.r_max - ld.s_min, 4),
                            duration_ms=round((ld.qrs_off - ld.qrs_on) * ms, 2), morphology=ld.morph))
        for w in ld.waves:
            m = ld.morph if False else None
            out.append(Wave(kind=_KIND[w.kind], lead=lead, beat_index=beat_index, onset_ms=T(w.onset),
                            peak_ms=T(w.peak), offset_ms=T(w.offset), amplitude_mv=round(w.amp, 4),
                            duration_ms=round((w.offset - w.onset) * ms, 2), morphology=m))
        for w in (ld.p, ld.t, ld.u):
            if w is not None:
                out.append(Wave(kind=_KIND[w.kind], lead=lead, beat_index=beat_index, onset_ms=T(w.onset),
                                peak_ms=T(w.peak), offset_ms=T(w.offset), amplitude_mv=round(w.amp, 4),
                                duration_ms=round((w.offset - w.onset) * ms, 2), morphology=w.morph))
    return out


def _minimal(signal, study_id, warnings):
    return ECGAnalysis(study_id=study_id, signal=signal, global_measurements=GlobalMeasurements(),
                       warnings=warnings)


def analyze_signal(signal: ECGSignal, study_id: str) -> ECGAnalysis:
    warnings: list[str] = []
    fs = float(signal.fs)
    d = normalize(signal.leads)
    derived = derive_missing(d)
    if derived:
        warnings.append("Derivações calculadas a partir de D1 e D2: " + ", ".join(derived))
    leads = [l for l in ALL_LEADS if l in d]
    if not leads:
        return _minimal(signal, study_id, ["Nenhuma derivação reconhecida no sinal."])
    n = min(len(d[l]) for l in leads)
    X = np.stack([d[l][:n] for l in leads])
    if fs < 250:
        warnings.append(f"Frequência de amostragem baixa ({fs:.0f} Hz): durações e amplitudes menos precisas.")
    if n / fs < 3:
        warnings.append("Registro muito curto (<3 s): medidas e ritmo pouco confiáveis.")
    for l, q in (signal.quality or {}).items():
        if q < 0.5:
            warnings.append(f"Qualidade do sinal baixa na derivação {l} ({q:.2f}).")
    amp, dlt, info = preprocess(X, fs)
    if info["mains"]:
        warnings.append(f"Interferência de rede {info['mains']:.0f} Hz detectada e filtrada.")
    noise = noise_sigma(amp)
    peaks, ref = detect_r_peaks(amp, fs)
    if len(peaks) < 2:
        return _minimal(signal, study_id, warnings + ["Menos de 2 complexos QRS detectados; análise não realizada."])
    if len(peaks) < 4:
        warnings.append("Poucos batimentos detectados (<4): análise de ritmo limitada.")
    pk_ms = peaks * 1000.0 / fs
    rr, cv, rmssd, rr_mean = rr_stats(pk_ms)
    rr_sd = float(rr.std())
    rr_med = float(np.median(rr))
    sn = float(np.median(amp[ref, peaks])) / max(float(np.median(noise)), 1e-6)
    if np.median(noise) > 0.05 or sn < 8:
        warnings.append(f"Ruído elevado (sigma {np.median(noise)*1000:.0f} µV): delimitação das ondas pode ser imprecisa.")

    # ---- per-beat delineation
    bds, beat_info, all_waves = {}, [], []
    for i, p in enumerate(peaks):
        rp = rr[i - 1] if i > 0 else None
        rn = rr[i] if i < len(rr) else None
        loc = rp or rn or 1000.0
        pre = int(min(max(0.6 * loc, 400), 650) * fs / 1000)
        post = int(max(min(0.75 * (rn or loc), 700), 450) * fs / 1000)
        if p - pre < 0 or p + post >= n:
            beat_info.append({"qrs_on": max(0, p - int(0.04 * fs)), "qrs_off": p + int(0.04 * fs), "t_off": None})
            continue
        try:
            bd = delineate_beat(amp[:, p - pre:p + post + 1], dlt[:, p - pre:p + post + 1], fs, pre, leads, noise,
                                rn, rp)
        except Exception as e:  # pragma: no cover - defensive
            warnings.append(f"Falha ao delinear batimento {i}: {e}")
            beat_info.append({"qrs_on": p, "qrs_off": p, "t_off": None})
            continue
        bds[i] = (bd, p - pre)
        beat_info.append({"qrs_on": p - pre + bd.qrs_on, "qrs_off": p - pre + bd.qrs_off,
                          "t_off": (p - pre + bd.t_off) if bd.t_off is not None else None,
                          "p_on": (p - pre + bd.p_on) if bd.p_on is not None else None})
        all_waves += _waves(bd, leads, fs, p - pre, i)

    # ---- median beat
    med = build_median(amp, dlt, peaks, fs, rr_med)
    if med is None:
        return _minimal(signal, study_id, warnings + ["Não foi possível construir o batimento mediano."])
    med_amp, med_dlt, a_idx, n_used = med
    mbd = delineate_beat(med_amp, med_dlt, fs, a_idx, leads, noise, rr_med, rr_med)
    lms, gm, extras = measure_median(mbd, med_amp, med_dlt, fs, leads, rr_mean, rr_sd)
    start = a_idx - int(round(MEDIAN_PRE_MS * fs / 1000))
    median_beats = {l: [round(float(v), 5) for v in med_amp[i, start:]] for i, l in enumerate(leads)}
    median_waves = _waves(mbd, leads, fs, -start, -1)

    # ---- rhythm context
    L = {m.lead: m for m in lms}
    pl_ = "II" if "II" in L else ("I" if "I" in L else leads[0])
    p_amp = L[pl_].p_amplitude_mv
    avr = L.get("aVR").p_amplitude_mv if "aVR" in L else None
    p_present = mbd.p_on is not None
    sinus_p = bool(p_present and p_amp is not None and p_amp > 0.03 and (avr is None or avr < 0.02))
    frac_p = float(np.mean([1.0 if b[0].p_on is not None else 0.0 for b in bds.values()])) if bds else 0.0
    li2 = leads.index(pl_)
    p_series = detect_p_series(dlt[li2], fs, beat_info, noise[li2])
    av = av_analysis(p_series, [b["qrs_on"] * 1000.0 / fs for b in beat_info], fs)
    ctx = dict(gm=gm, lm=L, bd=mbd, fs=fs, hr=gm.heart_rate_bpm, cv=cv, rmssd=rmssd, p_present=p_present,
               sinus_p=sinus_p, frac_p=frac_p, av=av)
    gm.rhythm, ctx["rhythm_kind"] = classify_rhythm(ctx)
    if ctx["rhythm_kind"] == "af":
        gm.p_duration_ms = gm.pr_ms = gm.p_axis_deg = None
    findings = build_findings(ctx)
    conduction = conduction_timeline(gm, median_waves, findings)
    return ECGAnalysis(study_id=study_id, signal=signal, r_peaks_ms=[round(float(x), 2) for x in pk_ms],
                       waves=all_waves, median_beats=median_beats, lead_measurements=lms, global_measurements=gm,
                       conduction=conduction, findings=findings, warnings=warnings,
                       median_waves=median_waves, median_beat_r_index=int(round(MEDIAN_PRE_MS * fs / 1000)))
