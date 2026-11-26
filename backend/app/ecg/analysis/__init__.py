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
from .ectopy import beat_correlations, ectopic_beats, rr_irregularity_excl
from .pacing import (RELAXED, STRICT, blank_spikes, classify_pacing, detect_spikes, is_paced_timing,
                     spike_timing)
from .preprocess import noise_sigma, preprocess
from .rhythm import atrial_grid, av_analysis, detect_p_series, detect_p_series_resid, ectopy_pattern, flutter_features, rr_alternation, flutter_multilead, rr_irregularity, rr_stats
from .rpeaks import detect_r_peaks_ex
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


def _align_segments(d, signal, fs, warnings):
    """Digitized pages (3x4, 6x2) give leads of unequal length with start offsets in
    calibration['offset_s.<lead>']. Place them on a common timeline (zeros outside the recorded
    window) and return a per-lead validity mask; None when all leads already share one timeline."""
    lens = {k: len(v) for k, v in d.items()}
    cal = signal.calibration or {}
    # equal-length leads on one timeline -> nothing to align; a 3x4 page without rhythm strip has equal-length
    # 2.5 s leads that start at different offsets and must NOT be treated as simultaneous
    offs = {round(float(cal.get(f"offset_s.{k}", 0.0)), 3) for k in d}
    if len(set(lens.values())) <= 1 and len(offs) <= 1:
        return None
    n = max(int(round(cal.get(f"offset_s.{k}", 0.0) * fs)) + ln for k, ln in lens.items())
    valid = {}
    for k, v in list(d.items()):
        o = int(round(cal.get(f"offset_s.{k}", 0.0) * fs))
        full = np.zeros(n)
        m = np.zeros(n, dtype=bool)
        full[o:o + len(v)] = v
        m[o:o + len(v)] = True
        d[k], valid[k] = full, m
        valid[("seg", k)] = (o, len(v))
    warnings.append("Traçado digitalizado em segmentos (ex.: 3x4): cada derivação foi medida apenas "
                    "nos batimentos registrados no seu trecho; ritmo avaliado pela tira longa.")
    return valid


def _segmented_median(amp, dlt, peaks, fs, rr_med, leads, valid, warnings):
    """Median beat per lead using only beats inside that lead's recorded window."""
    outs = []
    for i, l in enumerate(leads):
        m = valid[l]
        pk = np.array([p for p in peaks if m[max(0, p - int(0.65 * fs)):p + int(0.7 * fs)].all()], dtype=int)
        r = build_median(amp[i:i + 1], dlt[i:i + 1], pk if len(pk) else peaks, fs, rr_med) if len(pk) else None
        if r is None:
            r = build_median(amp[i:i + 1], dlt[i:i + 1], peaks, fs, rr_med)
            warnings.append(f"Derivação {l}: nenhum batimento completo no trecho registrado.")
        if r is None:
            return None
        outs.append(r)
    return (np.vstack([o[0] for o in outs]), np.vstack([o[1] for o in outs]), outs[0][2],
            min(o[3] for o in outs))


def _minimal(signal, study_id, warnings):
    return ECGAnalysis(study_id=study_id, signal=signal, global_measurements=GlobalMeasurements(),
                       warnings=warnings)


def _rhythm_only(signal, study_id, warnings, pk_ms, rr, cv, rmssd, rr_mean):
    """Abstention for photos whose printed grid is irregular after rectification (distorted / low quality):
    amplitudes, intervals and ST cannot be trusted, so only heart rate and a coarse regularity label are given."""
    from app.ecg.analysis.rules import AF_CV, AF_RMSSD
    warnings = warnings + ["Foto com grade irregular ou distorcida: escala de tempo e amplitude não confiáveis. "
                           "Informados apenas frequência cardíaca e regularidade do ritmo; amplitudes, intervalos "
                           "(PR/QRS/QT) e ST não foram medidos. Refaça a foto com a folha plana e de frente."]
    irregular = cv >= AF_CV and rmssd >= AF_RMSSD
    gm = GlobalMeasurements(
        heart_rate_bpm=round(60000.0 / rr_mean, 1) if rr_mean else None, rr_mean_ms=round(float(rr_mean), 1),
        rr_sd_ms=round(float(rr.std()), 1) if len(rr) else None,
        rhythm="Ritmo irregular (avaliar no ECG original)" if irregular else "Ritmo regular (só frequência avaliada)")
    return ECGAnalysis(study_id=study_id, signal=signal, r_peaks_ms=[round(float(x), 2) for x in pk_ms],
                       global_measurements=gm, warnings=warnings)


def analyze_signal(signal: ECGSignal, study_id: str, age: float | None = None,
                   sex: str | None = None) -> ECGAnalysis:
    """age (years) and sex ('M'/'F') are optional; when given, voltage criteria use age/sex-aware limits."""
    warnings: list[str] = []
    fs = float(signal.fs)
    d = normalize(signal.leads)
    valid = _align_segments(d, signal, fs, warnings)
    derived = derive_missing(d) if valid is None else []
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
    spikes = detect_spikes(X, fs, **STRICT) if valid is None else None   # RAW signal, before the 150 Hz low-pass
    amp, dlt, info = preprocess(X, fs)
    if info["mains"]:
        warnings.append(f"Interferência de rede {info['mains']:.0f} Hz detectada e filtrada.")
    noise = noise_sigma(amp)
    peaks, ref, rp_unreliable = detect_r_peaks_ex(amp, fs)
    if len(peaks) < 2:
        return _minimal(signal, study_id, warnings + ["Menos de 2 complexos QRS detectados; análise não realizada."])
    pace_info = None
    if spikes is not None:
        for relaxed in (False, True):
            sp_ = detect_spikes(X, fs, **RELAXED) if relaxed else spikes
            tm = spike_timing(sp_["idx"], peaks, fs)
            if is_paced_timing(tm, frac_min=0.6 if relaxed else 0.4, sd_max=15.0 if relaxed else 20.0):
                pace_info = dict(spikes=sp_["idx"], timing=tm, relaxed=relaxed)
                break
        if pace_info is not None:   # blank the stimuli so the low-pass/delineation do not see a fake QRS onset
            X = blank_spikes(X, pace_info["spikes"], fs)
            amp, dlt, info = preprocess(X, fs)
            noise = noise_sigma(amp)
            peaks, ref, rp_unreliable = detect_r_peaks_ex(amp, fs)
            if len(peaks) < 2:
                return _minimal(signal, study_id, warnings + ["Menos de 2 complexos QRS detectados; análise não realizada."])
    if len(peaks) < 4:
        warnings.append("Poucos batimentos detectados (<4): análise de ritmo limitada.")
    pk_ms = peaks * 1000.0 / fs
    rr, cv, rmssd, rr_mean = rr_stats(pk_ms)
    if (signal.calibration or {}).get("rhythm_only"):
        return _rhythm_only(signal, study_id, warnings, pk_ms, rr, cv, rmssd, rr_mean)
    rr_sd = float(rr.std())
    rr_med = float(np.median(rr))
    sn = float(np.median(amp[ref, peaks])) / max(float(np.median(noise)), 1e-6)
    if np.median(noise) > 0.05 or sn < 8:
        warnings.append(f"Ruído elevado (sigma {np.median(noise)*1000:.0f} µV): delimitação das ondas pode ser imprecisa.")

    # ---- median beat
    med = build_median(amp, dlt, peaks, fs, rr_med) if valid is None else \
        _segmented_median(amp, dlt, peaks, fs, rr_med, leads, valid, warnings)
    if med is None:
        return _minimal(signal, study_id, warnings + ["Não foi possível construir o batimento mediano."])
    med_amp, med_dlt, a_idx, n_used = med
    mbd = delineate_beat(med_amp, med_dlt, fs, a_idx, leads, noise, rr_med, rr_med)
    # P position of the median beat (relative to its QRS onset): weak P waves of single beats are searched there
    _pp = [d_.p.peak - mbd.qrs_on for d_ in mbd.leads.values() if d_.p is not None]
    p_prior = int(np.median(_pp)) if len(_pp) >= 3 else None

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
                                rn, rp, p_prior=p_prior)
        except Exception as e:  # pragma: no cover - defensive
            warnings.append(f"Falha ao delinear batimento {i}: {e}")
            beat_info.append({"qrs_on": p, "qrs_off": p, "t_off": None})
            continue
        bds[i] = (bd, p - pre)
        if valid is not None:  # segmented page (e.g. 3x4): keep only leads recorded during this beat
            ok = [l for l in leads if valid[l][p - pre:p + post + 1].all()]
            bw = _waves(bd, ok, fs, p - pre, i)
            beat_info.append({"qrs_on": p - pre + bd.pre_on, "qrs_off": p - pre + bd.pre_off,
                              "t_off": (p - pre + bd.t_off) if bd.t_off is not None else None,
                              "p_on": (p - pre + bd.p_on) if bd.p_on is not None else None})
            all_waves += bw
            continue
        beat_info.append({"qrs_on": p - pre + bd.pre_on, "qrs_off": p - pre + bd.pre_off,
                          "t_off": (p - pre + bd.t_off) if bd.t_off is not None else None,
                          "p_on": (p - pre + bd.p_on) if bd.p_on is not None else None})
        all_waves += _waves(bd, leads, fs, p - pre, i)

    lms, gm, extras = measure_median(mbd, med_amp, med_dlt, fs, leads, rr_mean, rr_sd)
    if valid is not None:  # segmented pages: the union of per-lead borders is widened by the inter-lead timing jitter
        q_ = [m.qrs_ms for m in lms if m.qrs_ms]
        if len(q_) >= 6 and gm.qrs_ms and gm.qrs_ms > 1.25 * float(np.median(q_)):
            gm.qrs_ms = float(np.median(q_))
            warnings.append("QRS global estimado pela mediana das derivações (bordas combinadas alargadas pela digitalização por segmentos).")
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
    p_alt = detect_p_series_resid(dlt[li2], fs, beat_info, noise[li2])
    p_grid, grid_info = atrial_grid({l: dlt[i] for i, l in enumerate(leads)}, fs, beat_info)
    av = av_analysis(p_series, [b["qrs_on"] * 1000.0 / fs for b in beat_info], fs, p_alt=p_alt,
                     p_grid=p_grid, grid_info=grid_info)
    ectopic = ectopic_beats(pk_ms, beat_correlations(amp, peaks, fs, ref))   # PVC/PAC: excluded from the AF test
    irr = rr_irregularity_excl(pk_ms, ectopic) if ectopic.any() else rr_irregularity(pk_ms)
    # PR of each beat (earliest P onset in any lead -> QRS onset) for the AV-block rule: consistent beats only
    pr_beats = [(b['qrs_on'] - b['p_on']) * 1000.0 / fs for b in beat_info if b.get('p_on') is not None]
    ctx = dict(gm=gm, lm=L, bd=mbd, fs=fs, hr=gm.heart_rate_bpm, cv=cv, rmssd=rmssd, p_present=p_present,
               sinus_p=sinus_p, frac_p=frac_p, av=av, age=age, sex=sex, pr_beats=pr_beats,
               irr=irr, ectopy=ectopy_pattern(pk_ms), n_ectopic=int(ectopic.sum()),
               flutter=flutter_features(dlt[li2], fs, beat_info), paced=None,
               flutter_f=flutter_multilead({l: dlt[i] for i, l in enumerate(leads)}, fs, beat_info),
               rr_alt=rr_alternation(pk_ms), rpeaks_unreliable=bool(rp_unreliable),
               source=getattr(signal.source, "value", signal.source), quality=dict(signal.quality or {}))
    if pace_info is not None:
        ptype = classify_pacing(pace_info["timing"], gm.qrs_ms, pace_info["spikes"], peaks, fs)
        if ptype and (not pace_info["relaxed"] or (gm.qrs_ms or 0) >= 120.0):
            ctx["paced"] = dict(type=ptype, n_spikes=pace_info["timing"]["n_spikes"],
                                delay_ms=float(np.median(pace_info["timing"]["delays_ms"])),
                                relaxed=pace_info["relaxed"])
    gm.rhythm, ctx["rhythm_kind"] = classify_rhythm(ctx)
    if ctx["rhythm_kind"] in ("af", "flutter"):
        gm.p_duration_ms = gm.pr_ms = gm.p_axis_deg = None
    findings = build_findings(ctx)
    if ctx.get("st_q_skipped"):
        warnings.append(f"ST/Q não avaliados em {', '.join(ctx['st_q_skipped'])} (ruído).")
    from .. import plausibility
    findings = plausibility.apply(signal, gm, lms, findings, warnings)  # K2/K3: withhold findings of suspect digitisations
    conduction = conduction_timeline(gm, median_waves, findings)
    if valid is not None:  # return leads on the common timeline so viewers can draw each segment in place
        signal = signal.model_copy(update={
            "leads": {k: [round(float(v), 5) for v in d[k]] for k in leads},
            "duration_s": round(n / fs, 3)})
    return ECGAnalysis(study_id=study_id, signal=signal, r_peaks_ms=[round(float(x), 2) for x in pk_ms],
                       waves=all_waves, median_beats=median_beats, lead_measurements=lms, global_measurements=gm,
                       conduction=conduction, findings=findings, warnings=warnings,
                       median_waves=median_waves, median_beat_r_index=int(round(MEDIAN_PRE_MS * fs / 1000)))
