"""Rhythm regularity, atrial activity series and AV conduction analysis."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


def rr_irregularity(peaks_ms):
    """Irregularity descriptors for short (10 s) strips. Returns dict(cv, rmssd, tpr, dfrac):
    cv = SD/mean RR; rmssd = RMSSD/mean RR; tpr = turning-point ratio (random series ~0.67, smooth
    respiratory sinus arrhythmia ~0.3-0.5); dfrac = fraction of successive |dRR| > 10% of mean RR.
    AF = irregularly irregular RR (Goldberger 10th ed.; AHA/ACC/HRS AF guideline 2023)."""
    rr = np.diff(np.asarray(peaks_ms, float))
    if len(rr) < 3:
        return dict(cv=0.0, rmssd=0.0, tpr=0.0, dfrac=0.0)
    m = rr.mean()
    d = np.diff(rr)
    tp = [(rr[i] - rr[i - 1]) * (rr[i] - rr[i + 1]) > 0 for i in range(1, len(rr) - 1)]
    return dict(cv=float(rr.std() / m), rmssd=float(np.sqrt(np.mean(d ** 2)) / m),
                tpr=float(np.mean(tp)) if tp else 0.0, dfrac=float(np.mean(np.abs(d) > 0.10 * m)))


def ectopy_pattern(peaks_ms, cv_max=0.07):
    """True when the irregularity is explained by isolated premature beats on an otherwise regular
    rhythm (premature beat + pause, bigeminy/trigeminy): the RR intervals not adjacent to a premature
    beat are regular, or the odd/even RR series are each regular. AF has no such underlying regularity."""
    rr = np.diff(np.asarray(peaks_ms, float))
    if len(rr) < 5:
        return False
    med = float(np.median(rr))
    short = [i for i in range(len(rr)) if rr[i] < 0.85 * med]
    if short and len(short) <= max(3, len(rr) // 3):
        drop = set(short) | {i + 1 for i in short if i + 1 < len(rr)}
        rest = np.array([x for i, x in enumerate(rr) if i not in drop])
        if len(rest) >= 3 and rest.std() / rest.mean() < cv_max:
            return True
    ev, od = rr[::2], rr[1::2]
    if len(ev) >= 3 and len(od) >= 3 and ev.std() / ev.mean() < cv_max and od.std() / od.mean() < cv_max and \
            abs(ev.mean() - od.mean()) > 0.1 * rr.mean():
        return True
    return False


def p_consistency(p_ms, beats_ms, lo=80.0, hi=300.0):
    """Atrial activity locked to the QRS: for each QRS onset the nearest P-like peak between `lo` and `hi` ms
    before it. Returns dict(p_frac = beats with such a peak, pr_sd = SD of the peak-to-QRS interval (ms),
    pr_med). Sinus rhythm (even arrhythmic) has a fixed PR, AF has no consistent P (Goldberger 10th ed.)."""
    p = np.asarray(p_ms, float)
    q = np.asarray(beats_ms, float)
    ivs = []
    for qt in q:
        c = p[(p >= qt - hi) & (p <= qt - lo)] if len(p) else p
        ivs.append(float(qt - c[-1]) if len(c) else np.nan)
    ivs = np.array(ivs)
    ok = ivs[~np.isnan(ivs)]
    return dict(p_frac=float(len(ok) / max(1, len(q))), pr_sd=float(ok.std()) if len(ok) >= 3 else float("inf"),
                pr_med=float(np.median(ok)) if len(ok) else None)


def rr_stats(peaks_ms):
    rr = np.diff(np.asarray(peaks_ms, float))
    if len(rr) == 0:
        return rr, 0.0, 0.0, 0.0
    cv = float(rr.std() / rr.mean())
    rmssd = float(np.sqrt(np.mean(np.diff(rr) ** 2)) / rr.mean()) if len(rr) > 1 else 0.0
    return rr, cv, rmssd, float(rr.mean())


def detect_p_series(x, fs, beats, noise):
    """Find P-like positive bumps outside QRS-T of each beat. x: 1-D 40 Hz lead (II preferred).
    Returns peak times in ms (absolute)."""
    n = len(x)
    mask = np.ones(n, bool)
    for b in beats:
        lo = max(0, b["qrs_on"] - int(0.02 * fs))
        t_end = b.get("t_off") or (b["qrs_off"] + int(0.3 * fs))
        mask[lo:min(n, t_end + int(0.03 * fs))] = False
    if mask.sum() < 0.1 * n:
        return []
    xs = uniform_filter1d(x, max(1, int(0.012 * fs)))
    base = np.median(xs[mask])
    y = xs - base
    prom = max(0.02, 4 * noise)
    out = []
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and mask[j + 1]:
            j += 1
        if j - i > int(0.1 * fs):
            seg = y[i:j + 1]
            pk, pr = find_peaks(seg, prominence=prom, width=(int(0.02 * fs), int(0.16 * fs)), rel_height=0.5)
            for k in pk:
                out.append((i + k) * 1000.0 / fs)
        i = j + 1
    return sorted(out)


def atrial_residual(x, fs, beats):
    """Lead trace with the QRS-T complex cancelled: each beat window (QRS onset - 20 ms ... T end + 30 ms, cut at the
    next QRS) is replaced by its difference to the least-squares scaled median QRS-T template, QRS samples are
    interpolated. P waves that fall inside a T wave (fast rates) or are not conducted stay in the residual.
    Returns the residual array or None when fewer than 4 usable beats."""
    x = np.asarray(x, float)
    n = len(x)
    pre = int(0.02 * fs)
    wins = []
    for i, b in enumerate(beats):
        s = max(0, b["qrs_on"] - pre)
        t_end = b.get("t_off") or (b["qrs_off"] + int(0.3 * fs))
        e = min(n - 1, t_end + int(0.03 * fs))
        if i + 1 < len(beats):
            e = min(e, beats[i + 1]["qrs_on"] - pre - 1)
        if e - s > int(0.1 * fs):
            wins.append((s, e, b))
    if len(wins) < 4:
        return None
    full = [(s, e) for s, e, _ in wins]
    ln = int(np.median([e - s for s, e in full]))
    stack = [x[s:s + ln] for s, e in full if e - s >= ln and s + ln <= n]
    if len(stack) < 3:
        return None
    tpl = np.median(np.array(stack), axis=0)
    inside = np.zeros(n, bool)
    for s, e, _ in wins:
        inside[s:e + 1] = True
    base = float(np.median(x[~inside])) if (~inside).sum() > 0.05 * n else float(np.median(x))
    y = x - base
    for s, e, b in wins:
        m = min(e - s + 1, ln)
        t = tpl[:m] - tpl[:m].mean()
        seg = y[s:s + m]
        den = float(t @ t)
        a = float(np.clip((t @ (seg - seg.mean())) / den, 0.0, 3.0)) if den > 0 else 0.0
        y[s:s + m] = seg - seg.mean() - a * t
        if e + 1 > s + m:
            y[s + m:e + 1] -= float(np.mean(y[s + m:e + 1]))
    for b in beats:
        lo, hi = max(0, b["qrs_on"] - int(0.01 * fs)), min(n - 1, b["qrs_off"] + int(0.02 * fs))
        if hi > lo:
            y[lo:hi + 1] = np.linspace(y[lo], y[hi], hi - lo + 1)
    return y - uniform_filter1d(y, max(3, int(0.6 * fs)))


def detect_p_series_resid(x, fs, beats, noise):
    """P-like bumps in the QRS-T-cancelled trace (see atrial_residual), including blocked P and P inside the T
    wave. Returns peak times in ms."""
    y = atrial_residual(x, fs, beats)
    if y is None:
        return []
    ys = uniform_filter1d(y, max(1, int(0.012 * fs)))
    pk, _ = find_peaks(ys, prominence=max(0.02, 4 * noise), width=(int(0.02 * fs), int(0.16 * fs)), rel_height=0.5)
    return [k * 1000.0 / fs for k in pk]


def av_analysis(p_ms, beats_ms, fs, p_alt=None, p_grid=None, grid_info=None):
    """AV analysis on the P series; when that finds no conduction pattern, retried on the QRS-T-cancelled series
    p_alt (blocked P / P inside the T wave). The P->QRS consistency always comes from the primary series."""
    res = _av_core(p_ms, beats_ms, fs)
    if p_alt is not None and res.get("type") is None:
        r2 = _av_core(p_alt, beats_ms, fs)
        if r2.get("type") == "av3":   # the noisier residual series is trusted for dissociation only, not for drop patterns
            r2.update({k: res[k] for k in ("p_frac", "pr_sd", "pr_med")})
            r2["alt"] = True
            return r2
    if p_grid is not None and res.get("type") is None:
        r3 = _av3_from_grid(p_grid, beats_ms, grid_info or {})
        if r3 is not None:   # E5: multi-lead atrial grid, dissociation only
            r3.update({k: res[k] for k in ("p_frac", "pr_sd", "pr_med")})
            r3["grid"] = grid_info
            return r3
    if grid_info:
        res["grid"] = grid_info
    return res


def _av_core(p_ms, beats_ms, fs):
    """p_ms: P peak times; beats_ms: list of qrs_on times (ms). Returns dict or None."""
    p = np.asarray(p_ms, float)
    q = np.asarray(beats_ms, float)
    cons = p_consistency(p, q)
    if len(p) < 4 or len(q) < 4:
        return dict(type=None, **cons)
    pp = np.diff(p)
    base = float(np.median(np.sort(pp)[:max(2, len(pp) // 2)]))
    if base < 250:
        return dict(type=None, **cons)
    near = np.abs(pp / base - np.round(pp / base)) < 0.2
    p_reg = float(np.mean(near))
    # assign each QRS to latest P at least 50 ms before and within 900 ms
    assigned = []
    for qt in q:
        idx = np.where(p <= qt - 50)[0]
        if len(idx) and qt - p[idx[-1]] <= 900:
            assigned.append(int(idx[-1]))
        else:
            assigned.append(-1)
    prs = np.array([q[k] - p[a] if a >= 0 else np.nan for k, a in enumerate(assigned)])
    rr = np.diff(q)
    cv_q = float(rr.std() / rr.mean())
    vent_rate = 60000.0 / rr.mean()
    atr_rate = 60000.0 / base
    res = dict(p_regular=p_reg, atrial_rate=atr_rate, vent_rate=vent_rate, type=None, prs=prs, base=base,
               n_p=len(p), n_q=len(q), **cons)
    # a spurious P-like bump (T/U wave, noise) easily fakes one blocked P in a 10 s strip: require regular atrial
    # activity at a physiological rate (<=160/min; faster P series are noise or flutter) and >=3 blocked P (or a 2:1 pattern); two spurious P bumps in 10 s are common on real tracings.
    if p_reg < 0.85 or atr_rate > 160 or atr_rate < 35:
        return res
    valid = prs[~np.isnan(prs)]
    res.update(cv_q=cv_q, pr_range=float(valid.max() - valid.min()) if len(valid) else 0.0)
    # complete block: ventricular rate clearly below atrial, regular QRS, PR varying
    if vent_rate < 0.7 * atr_rate and len(valid) >= 4 and (valid.max() - valid.min()) > 120 and cv_q < 0.2:
        res["type"] = "av3"
        return res
    # drops: consecutive assigned indices jumping >= 2
    jumps = [k for k in range(1, len(assigned)) if assigned[k] >= 0 and assigned[k - 1] >= 0
             and assigned[k] - assigned[k - 1] >= 2]
    if len(jumps) >= 3 or (jumps and len(q) >= 5 and len(jumps) >= 0.6 * (len(q) - 1)):
        res["n_drops"] = len(jumps)
        if len(jumps) >= 0.6 * (len(q) - 1):
            res["type"] = "av2_21"
            return res
        mob1 = 0
        for k in jumps:
            if k >= 2 and prs[k - 1] > prs[k] + 20 and prs[k - 1] > prs[k - 2] + 10:
                mob1 += 1
        if mob1 >= max(1, len(jumps) // 2 + (len(jumps) % 2)):
            res["type"] = "av2_m1"
        else:
            conducted = prs[~np.isnan(prs)]
            if conducted.max() - conducted.min() <= 40:
                res["type"] = "av2_m2"
            else:
                res["type"] = "av2_m1" if mob1 else "av2_unspec"
    return res


def flutter_features(x, fs, beats):
    """Atrial flutter descriptors from one lead (II preferred): QRS blanked by interpolation, baseline removed,
    then the spectrum of the remaining atrial/ST-T activity is searched for a narrow peak at 3.5-6.7 Hz
    (210-400/min; typical flutter ~300/min, AHA/ACC/ESC SVT guideline 2015). Returns dict(freq_hz, peak_ratio,
    harmonic): peak_ratio = peak power over total 1-15 Hz power, `harmonic` True when the peak sits at an
    integer multiple (2-3x) of the ventricular rate (2:1 / 3:1 conduction) within 10%."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 3 * fs or len(beats) < 4:
        return dict(freq_hz=None, peak_ratio=0.0, harmonic=False)
    y = x.copy()
    for b in beats:
        lo, hi = max(0, b["qrs_on"] - int(0.01 * fs)), min(n - 1, b["qrs_off"] + int(0.02 * fs))
        if hi > lo:
            y[lo:hi + 1] = np.linspace(y[lo], y[hi], hi - lo + 1)
    y = y - uniform_filter1d(y, int(0.5 * fs))
    y = y * np.hanning(n)
    nfft = int(2 ** np.ceil(np.log2(n * 4)))
    sp = np.abs(np.fft.rfft(y, nfft)) ** 2
    fr = np.fft.rfftfreq(nfft, 1.0 / fs)
    tot = sp[(fr >= 1.0) & (fr <= 15.0)].sum()
    band = (fr >= 3.5) & (fr <= 6.7)
    if tot <= 0 or not band.any():
        return dict(freq_hz=None, peak_ratio=0.0, harmonic=False)
    k = np.argmax(np.where(band, sp, 0))
    # power within +-0.5 Hz of the peak
    near = (fr >= fr[k] - 0.5) & (fr <= fr[k] + 0.5)
    q = [b["qrs_on"] for b in beats]
    hr_hz = 1000.0 / (np.mean(np.diff(q)) * 1000.0 / fs) if len(q) > 1 else 0.0
    harm = bool(hr_hz > 0 and any(abs(fr[k] / hr_hz - m) < 0.1 * m for m in (2, 3, 4)))
    return dict(freq_hz=float(fr[k]), peak_ratio=float(sp[near].sum() / tot), harmonic=harm)


ATRIAL_LEADS = ("II", "V1", "aVF")
GRID_ATRIAL_BPM = (40.0, 150.0)   # physiological atrial rate for a dissociated P series
GRID_VENT_CV = 0.12               # regular (escape) ventricular rhythm
GRID_VENT_RATIO = 0.85            # ventricular rate must be clearly below the atrial rate
GRID_INT_TOL = 0.12               # atrial/ventricular rate ratio this close to an integer = harmonic lock, not dissociation
GRID_PHASE_R = 0.45               # QRS phase vs the P grid: resultant length below this = no fixed PR (dissociation)
GRID_MIN_AC = 0.30      # autocorrelation of the combined atrial residual at the atrial period
GRID_MIN_Z = 1.8        # mean combined residual on the P grid, in robust SDs of the residual


def atrial_grid(dlt_by_lead, fs, beats):
    """E5: multi-lead atrial series. The QRS-T-cancelled residuals (atrial_residual) of II, V1 and aVF are
    z-scored, polarity-aligned and summed; the atrial period comes from the autocorrelation (35-200 /min) and the
    phase from the best-fitting periodic comb. Returns (grid_ms, info) with the regular P times (ms) or (None, info).
    Used only to detect AV dissociation (the P-R phase test is in _av_core: PR not constant, ventricular rate < atrial)."""
    ys = []
    for ln in ATRIAL_LEADS:
        x = dlt_by_lead.get(ln)
        if x is None:
            continue
        y = atrial_residual(x, fs, beats)
        if y is None:
            continue
        y = uniform_filter1d(y, max(1, int(0.016 * fs)))
        sd = 1.4826 * float(np.median(np.abs(y - np.median(y))))
        if sd <= 0:
            continue
        ys.append(y / sd)
    if not ys:
        return None, {}
    ref = ys[0]
    comb = ref.copy()
    for y in ys[1:]:
        comb += y if float(np.corrcoef(ref, y)[0, 1]) >= 0 else -y
    comb = comb / len(ys)
    n = len(comb)
    c0 = comb - comb.mean()
    nf = int(2 ** np.ceil(np.log2(2 * n)))
    f = np.fft.rfft(c0, nf)
    ac = np.fft.irfft(f * np.conj(f), nf)[:n]
    ac = ac / ac[0] if ac[0] > 0 else ac
    lo, hi = int(0.30 * fs), min(n // 3, int(1.7 * fs))
    if hi <= lo:
        return None, {}
    seg = ac[lo:hi]
    kbest = int(np.argmax(seg))
    # prefer the shortest lag whose autocorrelation is within 90% of the best (avoids subharmonics)
    cand = [k for k, v in enumerate(seg) if v >= 0.9 * seg[kbest] and 0 < k < len(seg) - 1 and v >= seg[k - 1] and v >= seg[k + 1]]
    k0 = cand[0] if cand else kbest
    T = lo + k0
    info = dict(ac=float(seg[k0]), period_ms=T * 1000.0 / fs)
    if seg[k0] < GRID_MIN_AC:
        return None, info
    best, bphi = -1e9, 0
    step = max(1, int(0.004 * fs))
    for phi in range(0, T, step):
        idx = np.arange(phi, n, T)
        s = float(comb[idx].mean())
        if s > best:
            best, bphi = s, phi
    info["z"] = best
    if best < GRID_MIN_Z:
        return None, info
    return [k * 1000.0 / fs for k in range(bphi, n, T)], info


def _av3_from_grid(grid_ms, beats_ms, info):
    """Complete AV block from the multi-lead atrial grid: regular slow ventricular rhythm, atrial rate clearly above
    it and not an integer multiple (harmonic), and no fixed phase between the QRS and the P grid (PR not constant:
    circular resultant length of the QRS phase within the atrial cycle). Returns an av dict or None."""
    q = np.asarray(beats_ms, float)
    g = np.asarray(grid_ms, float)
    if len(q) < 6 or len(g) < 6:
        return None
    rr = np.diff(q)
    vent = 60000.0 / rr.mean()
    cv = float(rr.std() / rr.mean())
    T = float(np.median(np.diff(g)))
    atr = 60000.0 / T
    ratio = atr / vent
    phase = np.exp(2j * np.pi * (((q - g[0]) % T) / T))
    r = float(abs(phase.mean()))
    info.update(atrial_rate=atr, vent_rate=vent, cv_q=cv, ratio=ratio, phase_r=r)
    if not (GRID_ATRIAL_BPM[0] <= atr <= GRID_ATRIAL_BPM[1]) or cv >= GRID_VENT_CV or vent >= GRID_VENT_RATIO * atr:
        return None
    if abs(ratio - round(ratio)) < GRID_INT_TOL or r >= GRID_PHASE_R:
        return None
    prs = np.array([k - g[g <= k - 50][-1] if (g <= k - 50).any() else np.nan for k in q])
    return dict(type="av3", atrial_rate=atr, vent_rate=vent, prs=prs, n_p=len(g), n_q=len(q), p_regular=1.0)
