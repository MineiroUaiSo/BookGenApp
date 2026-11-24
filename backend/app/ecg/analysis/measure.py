"""Median-beat construction and measurements (lead-wise and global)."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from ...schemas import GlobalMeasurements, LeadMeasurements
from .leads import LIMB, LIMB_ANGLE, PRECORDIAL

MEDIAN_PRE_MS = 300.0  # contract: median_beats start 300 ms before the R peak


def build_median(amp, dlt, peaks, fs, rr_med_ms):
    """Median beat on a long internal window. Returns (med_amp, med_dlt, a_idx, n_used) or None."""
    n = amp.shape[1]
    pre = int(min(max(0.6 * rr_med_ms, 400), 650) * fs / 1000)
    post = int(min(0.75 * rr_med_ms, 700) * fs / 1000)
    post = max(post, int(0.45 * fs))
    use = [p for p in peaks if p - pre >= 0 and p + post < n]
    if len(use) < 1:
        return None
    segs = np.stack([amp[:, p - pre:p + post + 1] for p in use])
    if len(use) >= 4:
        core = segs[:, :, pre - int(0.06 * fs):pre + int(0.08 * fs)].reshape(len(use), -1)
        tmpl = np.median(core, axis=0)
        cc = np.array([np.corrcoef(c, tmpl)[0, 1] if c.std() > 0 and tmpl.std() > 0 else 0 for c in core])
        ok = cc > 0.85
        if ok.sum() >= 3:
            use = [u for u, k in zip(use, ok) if k]
            segs = segs[ok]
    dsegs = np.stack([dlt[:, p - pre:p + post + 1] for p in use])
    return np.median(segs, axis=0), np.median(dsegs, axis=0), pre, len(use)


def _net_area(x, base, on, off):
    return float(np.sum(x[on:off + 1] - base))


def axis_from_areas(areas: dict) -> Optional[float]:
    """Least-squares frontal vector from limb-lead net areas (hexaxial); degrees in (-180, 180]."""
    rows, vals = [], []
    for l, v in areas.items():
        if l in LIMB_ANGLE and v is not None:
            th = math.radians(LIMB_ANGLE[l])
            rows.append([math.cos(th), math.sin(th)])
            vals.append(v)
    if len(rows) < 2:
        return None
    sol, *_ = np.linalg.lstsq(np.array(rows), np.array(vals), rcond=None)
    if math.hypot(*sol) < 1e-9:
        return None
    return float(math.degrees(math.atan2(sol[1], sol[0])))


def qt_corrections(qt, rr_ms, hr):
    rr = rr_ms / 1000.0
    return dict(bazett=qt / math.sqrt(rr), fridericia=qt / rr ** (1 / 3),
                framingham=qt + 154 * (1 - rr), hodges=qt + 1.75 * (hr - 60))


def measure_median(bd, med_amp, med_dlt, fs, leads, rr_mean_ms, rr_sd_ms):
    """Returns (list[LeadMeasurements], GlobalMeasurements, extras dict)."""
    ms = 1000.0 / fs
    on, off = bd.qrs_on, bd.qrs_off
    lms = []
    areas_p, areas_q, areas_t = {}, {}, {}
    for li, lead in enumerate(leads):
        ld = bd.leads[lead]
        x, xd = med_amp[li], med_dlt[li]
        m = LeadMeasurements(lead=lead)
        m.qrs_ms = float((ld.qrs_off - ld.qrs_on) * ms)
        qs = [w for w in ld.waves if w.kind == "Q"]
        rs = [w for w in ld.waves if w.kind in ("R", "R'")]
        ss = [w for w in ld.waves if w.kind == "S"]
        if qs:
            q = qs[0]
            m.q_amplitude_mv = q.amp
            m.q_duration_ms = float((q.offset - q.onset) * ms)
        if rs:
            m.r_amplitude_mv = max(w.amp for w in rs)
        if ss:
            m.s_amplitude_mv = min(w.amp for w in ss)
        m.morphology = ld.morph
        if ld.main_peak is not None and ld.waves:
            tgt = next((w for w in ld.waves if w.kind == "R"), None) or max(ld.waves, key=lambda w: abs(w.amp))
            m.intrinsicoid_deflection_ms = float((tgt.peak - on) * ms)
        if ld.p is not None:
            m.p_duration_ms = float((ld.p.offset - ld.p.onset) * ms)
            m.p_amplitude_mv = ld.p.amp
            m.pr_ms = float((ld.qrs_on - ld.p.onset) * ms)
        if ld.t is not None:
            m.t_amplitude_mv = ld.t.amp
            m.qt_ms = float((ld.t.offset - ld.qrs_on) * ms)
        for attr, d in (("st_j_mv", 0), ("st_j60_mv", 60), ("st_j80_mv", 80)):
            k = off + int(round(d / ms))
            if k < len(xd) - 3:
                w = max(1, int(round(4 / ms)))
                setattr(m, attr, float(np.mean(xd[max(0, k - w):k + w + 1]) - ld.base))
        lms.append(m)
        if lead in LIMB:
            if bd.p_on is not None and ld.p is not None:
                areas_p[lead] = _net_area(xd, ld.base, ld.p.onset, ld.p.offset)
            elif bd.p_on is not None:
                areas_p[lead] = 0.0
            areas_q[lead] = _net_area(x, ld.base, on, off)
            areas_t[lead] = _net_area(xd, ld.base, ld.t.onset, ld.t.offset) if ld.t is not None else 0.0
    g = GlobalMeasurements()
    extras = {}
    if rr_mean_ms:
        g.rr_mean_ms = float(rr_mean_ms)
        g.rr_sd_ms = float(rr_sd_ms)
        g.heart_rate_bpm = 60000.0 / rr_mean_ms
    g.qrs_ms = float((off - on) * ms)
    if bd.p_on is not None:
        g.p_duration_ms = float((bd.p_off - bd.p_on) * ms)
        g.pr_ms = float((on - bd.p_on) * ms)
        pa = axis_from_areas(areas_p)
        # P axis only meaningful if P amplitude is relevant
        g.p_axis_deg = pa
    g.qrs_axis_deg = axis_from_areas(areas_q)
    if bd.t_off is not None:
        g.t_axis_deg = axis_from_areas(areas_t)
        g.qt_ms = float((bd.t_off - on) * ms)
        if rr_mean_ms:
            c = qt_corrections(g.qt_ms, rr_mean_ms, g.heart_rate_bpm)
            g.qtc_bazett_ms, g.qtc_fridericia_ms = c["bazett"], c["fridericia"]
            g.qtc_framingham_ms, g.qtc_hodges_ms = c["framingham"], c["hodges"]
    byl = {m.lead: m for m in lms}

    def s_depth(l):
        return -bd.leads[l].s_min if l in bd.leads else None

    def r_max(l):
        return bd.leads[l].r_max if l in bd.leads else None

    if "V1" in bd.leads and ("V5" in bd.leads or "V6" in bd.leads):
        rv = max([r_max(l) for l in ("V5", "V6") if l in bd.leads])
        g.sokolow_lyon_mv = float(s_depth("V1") + rv)
    if "aVL" in bd.leads and "V3" in bd.leads:
        g.cornell_mv = float(r_max("aVL") + s_depth("V3"))
    # precordial transition: first lead with R >= |S|
    tr = None
    pcs = [l for l in PRECORDIAL if l in bd.leads]
    for l in pcs:
        if r_max(l) >= s_depth(l):
            tr = l
            break
    if pcs:
        g.precordial_transition = tr if tr else "ausente (rS até V6)"
    extras.update(areas_q=areas_q, areas_p=areas_p, areas_t=areas_t, byl=byl)
    return lms, g, extras
