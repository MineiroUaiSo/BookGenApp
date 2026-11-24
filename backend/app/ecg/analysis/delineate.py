"""Beat delineation: global (multi-lead) QRS borders + per-lead Q/R/S/R', P, T, U.

All indices are sample indices relative to the segment passed in. Amplitudes in mV relative to the
PR-segment isoelectric baseline of each lead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


TANGENT_T = True
P50_K = 2.5
G_THR = 0.02
LEAD_THR = 0.05
T_SIG = 0.15
T_Q = 1.0


@dataclass
class WaveSeg:
    kind: str
    onset: int
    peak: int
    offset: int
    amp: float
    morph: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class LeadDel:
    lead: str
    base: float
    qrs_on: int
    qrs_off: int
    waves: list
    morph: Optional[str]
    r_max: float          # max positive deflection in QRS window (>=0)
    s_min: float          # most negative deflection in QRS window (<=0)
    main_peak: Optional[int]
    p: Optional[WaveSeg] = None
    t: Optional[WaveSeg] = None
    u: Optional[WaveSeg] = None
    noise: float = 0.0


@dataclass
class BeatDel:
    a: int
    qrs_on: int
    qrs_off: int
    leads: dict
    p_on: Optional[int] = None
    p_off: Optional[int] = None
    t_off: Optional[int] = None
    early_slope_ratio: Optional[float] = None
    vmax: float = 0.0


def _scan(v, im, thr, gap, lo, hi):
    """Borders of the contiguous 'active' region around im (velocity > thr, gaps shorter than `gap` bridged)."""
    i, q, qs = im, 0, im
    on = lo
    while i > lo:
        i -= 1
        if v[i] < thr:
            if q == 0:
                qs = i
            q += 1
            if q >= gap:
                on = qs + 1
                break
        else:
            q = 0
    i, q = im, 0
    off = hi
    while i < hi:
        i += 1
        if v[i] < thr:
            if q == 0:
                qs = i
            q += 1
            if q >= gap:
                off = qs - 1
                break
        else:
            q = 0
    return on, off


def global_qrs(seg, fs, a):
    n = seg.shape[1]
    d = np.gradient(seg, axis=1) * fs
    v = np.sqrt((d ** 2).sum(0))
    v = uniform_filter1d(v, max(1, int(0.004 * fs)))
    w0, w1 = max(1, a - int(0.05 * fs)), min(n - 2, a + int(0.05 * fs))
    im = w0 + int(np.argmax(v[w0:w1 + 1]))
    vmax = float(v[im])
    thr = max(G_THR * vmax, 1.6 * float(np.percentile(v, 30)), P50_K * float(np.percentile(v, 50)))
    gap = max(3, int(0.012 * fs))
    lo, hi = max(1, a - int(0.2 * fs)), min(n - 2, a + int(0.22 * fs))
    on, off = _scan(v, im, thr, gap, lo, hi)
    return on, off, v, vmax


def _runs(y, dead):
    s = np.zeros(len(y), int)
    s[y > dead] = 1
    s[y < -dead] = -1
    runs, i, n = [], 0, len(y)
    while i < n:
        if s[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and s[j + 1] == s[i]:
            j += 1
        runs.append([i, j, int(s[i])])
        i = j + 1
    return runs


def qrs_components(y, on, off, fs):
    """Split QRS (y relative to baseline, index 0 == `on`) into Q/R/S/R' components. Returns (waves, morph)."""
    ma = float(np.max(np.abs(y))) if len(y) else 0.0
    thr = max(0.025, 0.04 * ma)
    runs = _runs(y, 0.5 * thr)
    kept = []
    dropped_between = False
    for i, j, sg in runs:
        k = i + int(np.argmax(sg * y[i:j + 1]))
        if abs(y[k]) < thr:
            if kept and kept[-1][2] != sg:
                dropped_between = True
            continue
        if kept and kept[-1][2] == sg and dropped_between:
            if abs(y[k]) > abs(y[kept[-1][3]]):
                kept[-1][3] = k
            kept[-1][1] = j
        else:
            kept.append([i, j, sg, k])
        dropped_between = False
    if not kept:
        return [], None
    waves, seen_r, seen_s_after = [], False, 0
    names = []
    for idx, (i, j, sg, k) in enumerate(kept):
        if sg > 0:
            name = "R" if not seen_r else "R'"
            seen_r = True
        else:
            name = "Q" if not seen_r else "S"
        names.append(name)
    # morphology string (case by relative amplitude)
    letters = []
    s_count = 0
    for name, (i, j, sg, k) in zip(names, kept):
        up = abs(y[k]) >= 0.5 * ma
        base = name[0]
        if name == "S":
            s_count += 1
        txt = base.upper() if up else base.lower()
        if name == "R'":
            txt += "'"
        elif name == "S" and s_count > 1:
            txt += "'"
        letters.append(txt)
    morph = "".join(letters)
    if names == ["Q"]:
        morph = "QS"
    # boundaries
    bounds = []
    for idx, (i, j, sg, k) in enumerate(kept):
        o = 0 if idx == 0 else (kept[idx - 1][1] + i) // 2
        e = len(y) - 1 if idx == len(kept) - 1 else (j + kept[idx + 1][0]) // 2
        bounds.append((o, e))
    for name, (i, j, sg, k), (o, e) in zip(names, kept, bounds):
        waves.append(WaveSeg(name, on + o, on + k, on + e, float(y[k])))
    return waves, morph


def _extent(y, pk, lo, hi, frac, noise, rise_tol, frac_off=None):
    """Walk from peak pk outwards until |y| < max(frac*|peak|, 2*noise), sign change or re-rise."""
    sg = 1.0 if y[pk] >= 0 else -1.0
    pv = abs(y[pk])
    ys = sg * y
    res = []
    for step, lim in ((-1, lo), (1, hi)):
        thr = max((frac if step < 0 or frac_off is None else frac_off) * pv, 2.0 * noise)
        i, rmin, rmi = pk, ys[pk], pk
        while i != lim:
            i += step
            v = ys[i]
            if v <= thr:
                break
            if v < rmin:
                rmin, rmi = v, i
            elif v - rmin > rise_tol:
                i = rmi
                break
        res.append(i)
    return res[0], res[1]


def _smooth(x, fs, ms=10):
    return uniform_filter1d(x, max(1, int(ms * fs / 1000)))


def _tangent_end(ys, pk, lim, fs, sg, ref=0.0):
    """Tangent method: steepest descending slope after peak pk (sign-normalised), extrapolated to the baseline.

    Returns the intersection index (float) or None. `lim` bounds the search to the right."""
    z = sg * (ys - ref)
    hi = min(lim, len(z) - 2)
    if hi - pk < 3:
        return None
    d = np.gradient(z)
    k = pk + 1 + int(np.argmin(d[pk + 1:hi + 1]))
    sl = d[k]
    if sl >= -1e-6:
        return None
    return k + (0.0 - z[k]) / sl


def detect_t(y, fs, j, hi, noise, a):
    """y: baseline-subtracted 40 Hz signal. Returns WaveSeg or None."""
    lo = j + int(0.02 * fs)
    hi = min(hi, len(y) - 2)
    if hi - lo < int(0.08 * fs):
        return None
    ys = _smooth(y, fs, 12)
    seg = ys[lo:hi + 1]
    prom = max(0.025, 4 * noise)
    pk_p, pr_p = find_peaks(seg, prominence=prom)
    pk_n, pr_n = find_peaks(-seg, prominence=prom)
    cands = [(pr_p["prominences"][i], lo + pk_p[i], 1) for i in range(len(pk_p))] + \
            [(pr_n["prominences"][i], lo + pk_n[i], -1) for i in range(len(pk_n))]
    if not cands:
        return None
    cands.sort(reverse=True)
    prom0, pk, sg = cands[0]
    # prefer tallest among comparable-prominence candidates (dome on ST plateau)
    for pr_, k, s_ in cands[1:]:
        if s_ == sg and pr_ > 0.6 * prom0 and abs(ys[k]) > abs(ys[pk]) * 1.1:
            pk = k
    amp = float(ys[pk])
    on, off = _extent(ys, pk, lo, hi, 0.05, noise, 0.15 * abs(amp) + 0.01, 0.10)
    off_thr = off
    if TANGENT_T:
        te = _tangent_end(ys, pk, off + int(0.04 * fs), fs, 1 if amp > 0 else -1)
        if te is not None:
            off = int(round(min(max(te, pk + 0.03 * fs), off)))
    morph = "positiva" if amp > 0 else "invertida"
    # biphasic: significant opposite peak adjacent
    opp = [(p_, k) for p_, k, s_ in cands[1:] if s_ != sg and p_ >= 0.4 * prom0 and on - int(0.08 * fs) <= k <= off + int(0.12 * fs)]
    if opp:
        p_, k = max(opp)
        o2, f2 = _extent(ys, k, lo, hi, 0.04, noise, 0.15 * abs(ys[k]) + 0.01)
        if TANGENT_T and k > pk:
            te = _tangent_end(ys, k, f2 + int(0.04 * fs), fs, 1 if ys[k] > 0 else -1)
            if te is not None:
                f2 = int(round(min(max(te, k + 0.03 * fs), f2)))
        on, off = min(on, o2), max(off, f2)
        morph = "bifásica (+/-)" if k > pk else "bifásica (-/+)"
    elif abs(amp) < 0.05:
        morph = "achatada"
    return WaveSeg("T", on, pk, off, amp, morph, {"off_thr": max(off, off_thr)})


def detect_u(y, fs, t: WaveSeg, hi, noise):
    lo = t.offset + int(0.01 * fs)
    hi = min(hi, len(y) - 2, t.offset + int(0.25 * fs))
    if hi - lo < int(0.05 * fs):
        return None
    ys = _smooth(y, fs, 12)
    sg = 1 if t.amp > 0 else -1
    pk, pr = find_peaks(sg * ys[lo:hi + 1], prominence=max(0.025, 4 * noise))
    if len(pk) == 0:
        return None
    k = lo + pk[int(np.argmax(pr["prominences"]))]
    amp = float(ys[k])
    if not (0.05 * abs(t.amp) <= abs(amp) <= 0.5 * abs(t.amp)):
        return None
    on, off = _extent(ys, k, lo, hi, 0.1, noise, 0.1 * abs(amp) + 0.01)
    return WaveSeg("U", on, k, off, amp, "U")


def detect_p(y, fs, lo, hi, noise):
    """Most prominent P-like deflection in [lo, hi]. y baseline-subtracted 40 Hz signal."""
    lo = max(lo, 1)
    hi = min(hi, len(y) - 2)
    if hi - lo < int(0.06 * fs):
        return None
    ys = _smooth(y, fs, 12)
    seg = ys[lo:hi + 1]
    # linear detrend over window borders removes residual T-tail slope
    seg = seg - np.linspace(seg[:3].mean(), seg[-3:].mean(), len(seg)) * 0.0
    prom = max(0.02, 4 * noise)
    pk_p, pr_p = find_peaks(seg, prominence=prom)
    pk_n, pr_n = find_peaks(-seg, prominence=prom)
    cands = [(pr_p["prominences"][i], lo + pk_p[i]) for i in range(len(pk_p))] + \
            [(pr_n["prominences"][i], lo + pk_n[i]) for i in range(len(pk_n))]
    if not cands:
        return None
    # candidates must be a "bump" of plausible width; prefer largest prominence, nearest QRS on ties
    cands.sort(key=lambda c: (-round(c[0], 3), -c[1]))
    for pr_, pk in cands:
        amp = float(ys[pk])
        # local reference (flat part of the window) so that residual offsets do not stretch the borders
        # robust isoelectric reference: median of the window away from the candidate bump
        # (a low percentile is biased by noise/pixel quantisation in digitised tracings)
        w = int(0.06 * fs)
        mask = np.ones(hi - lo + 1, dtype=bool)
        mask[max(0, pk - lo - w):pk - lo + w + 1] = False
        ref0 = float(np.median(ys[lo:hi + 1][mask])) if mask.sum() >= int(0.02 * fs) else \
            float(np.percentile(ys[lo:hi + 1], 10 if amp > 0 else 90))
        amp = amp - ref0
        if abs(amp) < prom:
            continue
        yl = ys - ref0
        on, off = _extent(yl, pk, lo, hi, 0.04, noise, 0.6 * abs(amp))
        # biphasic continuation (terminal opposite deflection, e.g. V1)
        sg = 1 if amp > 0 else -1
        tail_end = min(hi, off + int(0.08 * fs))
        extra = {}
        if off < hi and tail_end > off:
            tail = ys[off:tail_end + 1]
            kk = off + int(np.argmin(sg * tail))
            if -sg * ys[kk] >= max(0.03, 0.15 * abs(amp)):
                o2, f2 = _extent(ys, kk, off, hi, 0.1, noise, 0.5 * abs(ys[kk]))
                extra = {"neg_depth": float(abs(ys[kk])), "neg_dur_ms": (f2 - o2) * 1000 / fs,
                         "neg_first": False}
                off = max(off, f2)
        dur = (off - on) * 1000 / fs
        if dur < 25 or dur > 220:
            continue
        # bifid check
        sub = ys[on:off + 1] * sg
        bp, bpr = find_peaks(sub, prominence=0.12 * abs(amp))
        morph = "positiva" if amp > 0 else "negativa"
        if len(bp) >= 2:
            kk = np.argsort(bpr["prominences"])[-2:]
            ip = abs(int(bp[kk[0]]) - int(bp[kk[1]])) * 1000 / fs
            if ip >= 20:
                morph = "bífida"
                extra["interpeak_ms"] = float(ip)
        if extra.get("neg_depth") is not None and morph != "bífida":
            morph = "bifásica (+/-)" if sg > 0 else "bifásica (-/+)"
        return WaveSeg("P", on, pk, off, amp, morph, extra)
    return None


def delineate_beat(seg_amp, seg_del, fs, a, leads, noise, rr_next_ms, rr_prev_ms, detect_p_waves=True):
    n = seg_amp.shape[1]
    on, off, v, vmax = global_qrs(seg_amp, fs, a)
    rr_loc = rr_next_ms or rr_prev_ms or 1000.0
    bd = BeatDel(a=a, qrs_on=on, qrs_off=off, leads={}, vmax=vmax)
    e = min(off, on + int(0.03 * fs))
    bd.early_slope_ratio = float(v[on:e + 1].max() / vmax) if vmax > 0 else None
    b0, b1 = max(0, on - int(0.024 * fs)), max(1, on - int(0.004 * fs))
    gap = max(3, int(0.012 * fs))
    t_hi = on + int(min(0.72 * rr_loc, 620) * fs / 1000)
    for li, lead in enumerate(leads):
        x = seg_amp[li]
        base = float(np.median(x[b0:b1])) if b1 > b0 else float(x[max(0, on - 2)])
        y = x[on:off + 1] - base
        ma = float(np.max(np.abs(y))) if len(y) else 0.0
        d = np.gradient(x) * fs
        d = uniform_filter1d(np.abs(d), max(1, int(0.004 * fs)))
        lon, loff = on, off
        if ma >= 0.04:
            w = d[on:off + 1]
            im = on + int(np.argmax(w))
            lon, loff = _scan(d, im, LEAD_THR * d[im], gap, on, off)
        waves, morph = qrs_components(y, on, off, fs) if ma >= 0.03 else ([], None)
        if waves:
            waves[0].onset = max(on, lon) if waves[0].onset <= lon + 2 else waves[0].onset
            waves[-1].offset = min(off, loff) if waves[-1].offset >= loff - 2 else waves[-1].offset
        mp = None
        if waves:
            mp = max(waves, key=lambda w_: abs(w_.amp)).peak
        ld = LeadDel(lead, base, lon, loff, waves, morph,
                     float(max(0.0, y.max())) if len(y) else 0.0,
                     float(min(0.0, y.min())) if len(y) else 0.0, mp, noise=float(noise[li]))
        yd = seg_del[li] - base
        ld.t = detect_t(yd, fs, off, t_hi, noise[li], a)
        bd.leads[lead] = ld
    # global T end (from leads with substantial T)
    tl = [(l, d_.t) for l, d_ in bd.leads.items() if d_.t is not None]
    if tl:
        mx = max(abs(t.amp) for _, t in tl)
        sig = [t for _, t in tl if abs(t.amp) >= T_SIG * mx]
        offs = sorted(t.offset for t in sig)
        bd.t_off = int(round(float(np.quantile(offs, T_Q)))) if T_Q < 1 else offs[-1]
    t_ref = max(t.extra.get("off_thr", t.offset) for t in sig) if tl else None
    t_ref = t_ref if t_ref is not None else off + int(0.3 * rr_loc * fs / 1000)
    for li, lead in enumerate(leads):
        ld = bd.leads[lead]
        yd = seg_del[li] - ld.base
        if ld.t is not None:
            ld.u = detect_u(yd, fs, ld.t, a + int(max(rr_loc - 300, 0) * fs / 1000), ld.noise)
        if detect_p_waves:
            prev_t = t_ref - int(rr_prev_ms * fs / 1000) if rr_prev_ms else 0
            plo = max(0, prev_t + int(0.02 * fs), on - int(0.5 * fs))
            ld.p = detect_p(yd, fs, plo, on - int(0.01 * fs), ld.noise)
    pl = [(l, d_.p) for l, d_ in bd.leads.items() if d_.p is not None]
    if pl:
        mx = max(abs(p.amp) for _, p in pl)
        sig = [p for _, p in pl if abs(p.amp) >= 0.6 * mx and abs(p.amp) >= 0.03]
        if sig:
            bd.p_on = min(p.onset for p in sig)
            bd.p_off = max(p.offset for p in sig)
    return bd
