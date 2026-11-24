"""ECG voltage / hypertrophy indices (pure functions; all amplitudes in mm = 10 x mV, S as positive depth).

Each index is a dict {v, unidade, limiar, preenche, componentes}. 'preenche' is True/False, or the string
"depende_do_sexo" when the value crosses only the lower (female) limit and sex is unknown.

References (cited as sources only):
  Samesima N et al. Diretriz SBC de Laudos Eletrocardiograficos 2022. Arq Bras Cardiol 119(4):638-680.
  Peguero JG et al. J Am Coll Cardiol 2017;69(13):1694-1703 (S deepest + S V4: >=2.8 mV men, >=2.3 mV women).
  Romhilt DW, Estes EH. Am Heart J 1968;75:752-758 (point score).
  Hancock EW et al. AHA/ACCF/HRS recommendations Part V. Circulation 2009;119:e251 (Sokolow-Lyon, Cornell).
"""
from __future__ import annotations

from typing import Any, Optional

SOKOLOW_MM = 35.0
CORNELL_MM = {"M": 28.0, "F": 20.0}
CORNELL_PRODUCT = 2440.0       # mm.ms
CORNELL_PRODUCT_F_ADD = 6.0    # mm added to Cornell voltage in women
PEGUERO_MM = {"M": 28.0, "F": 23.0}
R_AVL_MM = 11.0
R_D1_MM = 20.0                 # Romhilt-Estes limb-lead voltage criterion (R or S >= 20 mm)
GUBNER_MM = 25.0               # R D1 + S D3
QRST_ANGLE_DEG = 100.0
MORRIS_MM_S = 0.04
RE_PROBABLE, RE_DEFINITE = 4, 5


def _idx(v: Optional[float], unit: str, thr: Any, fills: Any, comp: dict) -> dict:
    return {"v": None if v is None else round(float(v), 2), "unidade": unit, "limiar": thr, "preenche": fills,
            "componentes": comp}


def _sexed(v: float, thr: dict, sex: Optional[str]) -> tuple[Any, Any]:
    """(limiar, preenche) for a criterion with distinct male/female limits."""
    if sex in thr:
        return thr[sex], v > thr[sex] if thr is CORNELL_MM else v >= thr[sex]
    lo, hi = min(thr.values()), max(thr.values())
    ok_hi = v > hi if thr is CORNELL_MM else v >= hi
    ok_lo = v > lo if thr is CORNELL_MM else v >= lo
    return {"M": hi, "F": lo}, (True if ok_hi else ("depende_do_sexo" if ok_lo else False))


def sokolow_lyon(r: dict, s: dict) -> Optional[dict]:
    if "V1" not in s or not any(l in r for l in ("V5", "V6")):
        return None
    rv = max(r[l] for l in ("V5", "V6") if l in r)
    v = s["V1"] + rv
    return _idx(v, "mm", SOKOLOW_MM, v > SOKOLOW_MM, {"S_V1": round(s["V1"], 2), "R_V5_V6": round(rv, 2)})


def cornell_voltage(r: dict, s: dict, sex: Optional[str] = None) -> Optional[dict]:
    if "aVL" not in r or "V3" not in s:
        return None
    v = r["aVL"] + s["V3"]
    thr, fills = _sexed(v, CORNELL_MM, sex)
    return _idx(v, "mm", thr, fills, {"R_aVL": round(r["aVL"], 2), "S_V3": round(s["V3"], 2)})


def cornell_product(r: dict, s: dict, qrs_ms: Optional[float], sex: Optional[str] = None) -> Optional[dict]:
    if "aVL" not in r or "V3" not in s or not qrs_ms:
        return None
    base = r["aVL"] + s["V3"]
    add = CORNELL_PRODUCT_F_ADD if sex == "F" else 0.0
    v = (base + add) * qrs_ms
    if sex in ("M", "F"):
        fills: Any = v > CORNELL_PRODUCT
    else:
        v_f = (base + CORNELL_PRODUCT_F_ADD) * qrs_ms
        fills = True if v > CORNELL_PRODUCT else ("depende_do_sexo" if v_f > CORNELL_PRODUCT else False)
    return _idx(v, "mm.ms", CORNELL_PRODUCT, fills,
                {"cornell_mm": round(base, 2), "mulher_mais_6mm": sex == "F", "QRS_ms": round(qrs_ms, 1)})


def peguero_lo_presti(s: dict, sex: Optional[str] = None) -> Optional[dict]:
    if "V4" not in s or not s:
        return None
    deepest_lead = max(s, key=lambda l: s[l])
    v = s[deepest_lead] + s["V4"]
    thr, fills = _sexed(v, PEGUERO_MM, sex)
    return _idx(v, "mm", thr, fills, {"S_mais_profunda": round(s[deepest_lead], 2), "derivacao": deepest_lead,
                                      "S_V4": round(s["V4"], 2)})


def r_avl(r: dict) -> Optional[dict]:
    return None if "aVL" not in r else _idx(r["aVL"], "mm", R_AVL_MM, r["aVL"] > R_AVL_MM, {})


def r_d1(r: dict) -> Optional[dict]:
    return None if "I" not in r else _idx(r["I"], "mm", R_D1_MM, r["I"] >= R_D1_MM, {})


def gubner(r: dict, s: dict) -> Optional[dict]:
    if "I" not in r or "III" not in s:
        return None
    v = r["I"] + s["III"]
    return _idx(v, "mm", GUBNER_MM, v > GUBNER_MM, {"R_D1": round(r["I"], 2), "S_D3": round(s["III"], 2)})


def qrst_angle(qrs_axis: Optional[float], t_axis: Optional[float]) -> Optional[dict]:
    if qrs_axis is None or t_axis is None:
        return None
    v = abs((qrs_axis - t_axis + 180.0) % 360.0 - 180.0)
    return _idx(v, "graus", QRST_ANGLE_DEG, v > QRST_ANGLE_DEG, {"eixo_QRS": round(qrs_axis, 1), "eixo_T": round(t_axis, 1)})


def morris(neg_depth_mm: Optional[float], neg_dur_ms: Optional[float]) -> Optional[dict]:
    """Morris index: terminal negative phase of P in V1, depth (mm) x duration (s)."""
    if neg_depth_mm is None or neg_dur_ms is None:
        return None
    v = neg_depth_mm * neg_dur_ms / 1000.0
    return _idx(v, "mm.s", MORRIS_MM_S, v >= MORRIS_MM_S,
                {"profundidade_mm": round(neg_depth_mm, 2), "duracao_ms": round(neg_dur_ms, 1)})


def romhilt_estes(r: dict, s: dict, *, strain: bool, digitalis: bool = False, morris_fills: bool = False,
                  axis_deg: Optional[float] = None, qrs_ms: Optional[float] = None,
                  idt_ms: Optional[float] = None) -> dict:
    """Romhilt-Estes point score, item by item. 4 = probable LVH, >= 5 = definite."""
    limb = [x for l in ("I", "II", "III", "aVR", "aVL", "aVF") for x in (r.get(l), s.get(l)) if x is not None]
    volt = (any(x >= 20.0 for x in limb) or any(s.get(l, 0) >= 30.0 for l in ("V1", "V2"))
            or any(r.get(l, 0) >= 30.0 for l in ("V5", "V6")))
    comp = {
        "voltagem": 3 if volt else 0,
        "st_t_strain": (1 if digitalis else 3) if strain else 0,
        "aumento_atrial_esquerdo": 3 if morris_fills else 0,
        "desvio_eixo_esquerda": 2 if axis_deg is not None and axis_deg <= -30.0 else 0,
        "qrs_ge_90ms": 1 if qrs_ms is not None and qrs_ms >= 90.0 else 0,
        "deflexao_intrinsecoide_v5v6_ge_50ms": 1 if idt_ms is not None and idt_ms >= 50.0 else 0,
    }
    total = sum(comp.values())
    comp["classe"] = "definida" if total >= RE_DEFINITE else ("provavel" if total == RE_PROBABLE else "nao_preenche")
    return _idx(total, "pontos", {"provavel": RE_PROBABLE, "definida": RE_DEFINITE}, total >= RE_DEFINITE, comp)


def compute_indices(r: dict, s: dict, *, sex: Optional[str] = None, qrs_ms: Optional[float] = None,
                    qrs_axis: Optional[float] = None, t_axis: Optional[float] = None,
                    p_neg_depth_mm: Optional[float] = None, p_neg_dur_ms: Optional[float] = None,
                    strain: bool = False, digitalis: bool = False, idt_ms: Optional[float] = None) -> dict:
    """r/s: lead -> mm (S positive depth). Indices that cannot be computed are omitted."""
    mor = morris(p_neg_depth_mm, p_neg_dur_ms)
    out = {
        "sokolow_lyon": sokolow_lyon(r, s),
        "cornell_voltagem": cornell_voltage(r, s, sex),
        "cornell_produto": cornell_product(r, s, qrs_ms, sex),
        "peguero_lo_presti": peguero_lo_presti(s, sex),
        "r_avl": r_avl(r),
        "r_d1": r_d1(r),
        "r_d1_mais_s_d3": gubner(r, s),
        "angulo_qrs_t": qrst_angle(qrs_axis, t_axis),
        "morris": mor,
        "romhilt_estes": romhilt_estes(r, s, strain=strain, digitalis=digitalis,
                                       morris_fills=bool(mor and mor["preenche"]), axis_deg=qrs_axis,
                                       qrs_ms=qrs_ms, idt_ms=idt_ms),
    }
    return {k: v for k, v in out.items() if v is not None}
