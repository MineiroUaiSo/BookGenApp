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


def av_analysis(p_ms, beats_ms, fs):
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
    if p_reg < 0.7:
        return res
    valid = prs[~np.isnan(prs)]
    # complete block: ventricular rate clearly below atrial, regular QRS, PR varying
    if vent_rate < 0.85 * atr_rate and len(valid) >= 4 and (valid.max() - valid.min()) > 120 and cv_q < 0.2:
        res["type"] = "av3"
        return res
    # drops: consecutive assigned indices jumping >= 2
    jumps = [k for k in range(1, len(assigned)) if assigned[k] >= 0 and assigned[k - 1] >= 0
             and assigned[k] - assigned[k - 1] >= 2]
    if jumps:
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
