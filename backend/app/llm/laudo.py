"""Laudo de ECG completo em pt-BR (prompt ecg_laudo_v1): schema, gate de digitalização, validação e renderização.

Rascunho para revisão médica; não é dispositivo certificado. A LLM só recebe medidas/regras (sem imagem);
números fora das medidas e afirmações sobre achados "suprimidos" por divergência de digitalização são
marcados/removidos aqui, em código (não só no prompt).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from . import validate as V

PROMPT_VERSION = "ecg_laudo_v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"
DISCLAIMER = "Rascunho gerado por IA para revisão médica. Não substitui laudo médico."
REMOVED = "[removido pelo validador: afirmação sobre achado não confiável com digitalização divergente]"


class LaudoECG(BaseModel):
    aviso_topo: list[str] = Field(default_factory=list)
    qualidade_tecnica: str = ""
    ritmo_frequencia: str = ""
    intervalos: str = ""
    qtc_formula: str = ""
    eixos: str = ""
    onda_p: str = ""
    complexo_qrs: str = ""
    st_t: str = ""
    comparacao: str = "Sem ECG anterior para comparação."
    impressao: list[str] = Field(default_factory=list)
    limitrofes: list[str] = Field(default_factory=list)
    recomendacao: str = ""
    # preenchidos pelo validador (não fazem parte do schema enviado à LLM)
    validacao: dict[str, int] = Field(default_factory=dict)
    avisos_validacao: list[str] = Field(default_factory=list)


_LLM_FIELDS = [k for k in LaudoECG.model_fields if k not in ("validacao", "avisos_validacao")]
_LIST_FIELDS = {"aviso_topo", "impressao", "limitrofes"}
_TEXT_SECTIONS = ["qualidade_tecnica", "ritmo_frequencia", "intervalos", "eixos", "onda_p", "complexo_qrs",
                  "st_t", "comparacao", "recomendacao"]


def output_schema() -> dict:
    props = {k: ({"type": "array", "items": {"type": "string"}} if k in _LIST_FIELDS else {"type": "string"})
             for k in _LLM_FIELDS}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ------------------------------------------------------------ índices de HVE (determinístico)
def _lead_vals(summary: dict) -> dict[str, dict]:
    return {m.get("lead"): m for m in summary.get("medidas_por_derivacao") or [] if isinstance(m, dict)}


def compute_indices(summary: dict, sexo: Optional[str] = None) -> dict[str, Any]:
    """Cornell, Sokolow-Lyon e Peguero-Lo Presti em mm (1 mV = 10 mm), a partir de R/S por derivação."""
    leads = _lead_vals(summary)

    def amp(lead: str, key: str) -> Optional[float]:
        v = (leads.get(lead) or {}).get(key)
        return abs(float(v)) * 10 if isinstance(v, (int, float)) else None

    out: dict[str, Any] = {}
    male = {"M": True, "F": False}.get((sexo or "").upper()[:1])
    s_v1, r5, r6 = amp("V1", "s_amplitude_mv"), amp("V5", "r_amplitude_mv"), amp("V6", "r_amplitude_mv")
    if s_v1 is not None and (r5 is not None or r6 is not None):
        out["sokolow_lyon_mm"] = round(s_v1 + max(x for x in (r5, r6) if x is not None), 1)
        out["sokolow_lyon_limite_mm"] = 35
    r_avl, s_v3 = amp("aVL", "r_amplitude_mv"), amp("V3", "s_amplitude_mv")
    if r_avl is not None and s_v3 is not None:
        out["cornell_mm"] = round(r_avl + s_v3, 1)
        if male is not None:
            out["cornell_limite_mm"] = 28 if male else 20
    s_all = [amp(k, "s_amplitude_mv") for k in leads]
    s_all = [x for x in s_all if x is not None]
    if s_all and s_v3 is not None:
        pg = round(max(s_all) + s_v3, 1)
        out["peguero_lo_presti_mm"] = pg
        if male is not None:
            lim = 23 if male else 28
            out["peguero_limite_mm"] = lim
            out["peguero_preenchido"] = pg > lim
    return out


# ------------------------------------------------------------ gate de digitalização
_PRE = r"pr[eé]-?excita\w+|onda delta|\bWPW\b|wolff"
_SUPPRESS = {
    "PR": _PRE + r"|\bBAV\b|bloqueio atrioventricular|PR (?:curto|longo|prolongad\w+)",
    "QRS": _PRE + r"|bloqueio de ramo|\bB[RE]D\b|\bBRE\b|QRS (?:largo|alargad\w+)|dist[uú]rbio de condu[cç][aã]o",
    "QT": r"QT\w*\s+(?:longo|curto|prolongad\w+)|s[ií]ndrome do QT",
    "ST": r"isqu[eê]mi\w+|infra\w*\s*(?:de\s*)?ST|supra\w*\s*(?:de\s*)?ST|les[aã]o subepic\w+|\bIAM\b|infarto",
}
_PRINTED = {"PR": ("pr_ms", "pr_ms"), "QRS": ("qrs_ms", "qrs_ms"), "QT": ("qt_ms", "qt_ms")}
_HEDGE_RE = re.compile(r"n[aã]o (?:avali|diagnost|afirm|conclu|confi)|n[aã]o foi poss|diverg|discord|poss[ií]vel erro|"
                       r"suspeit|sem seguran|n[aã]o h[aá]|sem sinais|aus[eê]ncia|n[aã]o se|descart", re.IGNORECASE)


def digitization_alerts(summary: dict) -> list[dict]:
    """Divergência algoritmo x cabeçalho impresso (PR/QRS/QT) e flag externa de digitalização suspeita."""
    alerts: list[dict] = []
    g = summary.get("medidas_globais") or {}
    printed = summary.get("cabecalho_impresso") or {}
    for name, (gk, pk) in _PRINTED.items():
        a, p = g.get(gk), printed.get(pk)
        if isinstance(a, (int, float)) and isinstance(p, (int, float)) and abs(a - p) > max(20.0, 0.2 * p):
            alerts.append({"medida": name, "algoritmo": a, "impresso": p, "suprimir": [name]})
    if alerts and any(x["medida"] in ("PR", "QRS") for x in alerts):
        alerts[0] = {**alerts[0], "suprimir": sorted(set(alerts[0]["suprimir"]) | {"ST"})}
    if summary.get("digitalizacao_suspeita") and not alerts:
        alerts.append({"medida": "digitalização", "algoritmo": None, "impresso": None,
                       "suprimir": ["PR", "QRS", "ST"], "motivo": str(summary["digitalizacao_suspeita"])})
    return alerts


def alert_text(a: dict) -> str:
    if a.get("algoritmo") is not None:
        return (f"Discordância: {a['medida']} do algoritmo {V._fmt(a['algoritmo'])} ms diverge do impresso no "
                f"aparelho ({V._fmt(a['impresso'])} ms); provável erro de digitalização/delineação. "
                "Achados dependentes dessa medida não são diagnosticados; conferir no traçado original.")
    return ("Digitalização suspeita (" + a.get("motivo", "sem detalhe") + "); achados dependentes de intervalos e "
            "ST não são diagnosticados; conferir no traçado original.")


def _suppress_regex(alerts: list[dict]) -> Optional[re.Pattern]:
    keys = {k for a in alerts for k in a["suprimir"]}
    pats = [_SUPPRESS[k] for k in sorted(keys) if k in _SUPPRESS]
    return re.compile("|".join(pats), re.IGNORECASE) if pats else None


def _sentences(text: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def _scrub(text: str, rx: re.Pattern) -> tuple[str, int]:
    n, out = 0, []
    for s in _sentences(text):
        if rx.search(s) and not _HEDGE_RE.search(s):
            out.append(REMOVED)
            n += 1
        else:
            out.append(s)
    return " ".join(out), n


# ------------------------------------------------------------ números fora das medidas
_REF_LIMITS = {20, 23, 25, 28, 35, 90, 100, 110, 120, 200, 440, 450, 460, 470, 480, 500, 10, 12, 1000}
_LEAD_RE = re.compile(r"\b(?:V[1-6]R?|D[123I]{1,3}|aV[RLF]|DII+|[IV]{1,3})\b|\b12\s+deriva", re.IGNORECASE)
_NUMTOK = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(ms|mm/mv|mm/s|mm|mv|bpm|%|pontos?|graus|°)?", re.IGNORECASE)


def _all_numbers(o: Any, acc: Optional[set] = None) -> set:
    acc = set() if acc is None else acc
    if isinstance(o, bool):
        return acc
    if isinstance(o, (int, float)):
        acc.add(abs(float(o)))
    elif isinstance(o, dict):
        for v in o.values():
            _all_numbers(v, acc)
    elif isinstance(o, list):
        for v in o:
            _all_numbers(v, acc)
    elif isinstance(o, str):
        for m in re.finditer(r"\d+(?:[.,]\d+)?", o):
            acc.add(float(m.group().replace(",", ".")))
    return acc


def unverified_numbers(text: str, summary: dict) -> list[str]:
    """Números do texto sem correspondente na entrada (x1, x10 mV->mm, x1000 mV->uV) nem limite de referência."""
    known = _all_numbers({k: v for k, v in summary.items() if k != "contexto"})
    known |= {k * 10 for k in known} | {k / 10 for k in known}
    known |= {float(x) for x in _REF_LIMITS}
    bad: list[str] = []
    clean = _LEAD_RE.sub(" ", text or "")
    for m in _NUMTOK.finditer(clean):
        v = float(m.group(1).replace(",", "."))
        unit = (m.group(2) or "").lower()
        if unit in ("mm/mv", "mm/s"):
            continue
        if not unit and v <= 12 and float(v).is_integer():
            continue
        tol = max(0.51, 0.02 * v)
        if not any(abs(v - k) <= tol for k in known):
            bad.append(m.group(0).strip())
    return bad


# ------------------------------------------------------------ validação
def _all_texts(l: LaudoECG) -> list[tuple[str, str]]:
    out = [(k, getattr(l, k)) for k in _TEXT_SECTIONS + ["qtc_formula"]]
    out += [("impressao", x) for x in l.impressao] + [("limitrofes", x) for x in l.limitrofes]
    return out


def validate_laudo(l: LaudoECG, summary: dict) -> LaudoECG:
    """Aplica: aviso no topo, supressão de achados dependentes de medida divergente e conferência de números."""
    alerts = digitization_alerts(summary)
    stats = {"numeros_conferem": 0, "numeros_divergentes": 0, "numeros_nao_verificaveis": 0,
             "numeros_fora_das_medidas": 0, "afirmacoes_removidas": 0, "alertas_digitalizacao": len(alerts)}
    notes: list[str] = []
    upd = l.model_dump()
    if alerts:
        top = list(upd["aviso_topo"])
        for a in alerts:
            top.append(alert_text(a))
        if len(top) > len(alerts) and any(re.search(r"discord|diverg|suspeit", t, re.I) for t in upd["aviso_topo"]):
            top = list(upd["aviso_topo"])   # a LLM já abriu com a discordância: não duplica
        upd["aviso_topo"] = top
        rx = _suppress_regex(alerts)
        if rx:
            for k in _TEXT_SECTIONS:
                upd[k], n = _scrub(upd[k], rx)
                stats["afirmacoes_removidas"] += n
            for k in ("impressao", "limitrofes"):
                new = []
                for item in upd[k]:
                    s, n = _scrub(item, rx)
                    stats["afirmacoes_removidas"] += n
                    new.append(s)
                upd[k] = new
    ref = V.reference_values(summary)
    for src, vals in (("cabecalho_impresso", {"ms:PR": "pr_ms", "ms:QRS": "qrs_ms", "ms:QT": "qt_ms",
                                              "ms:QTc": "qtc_ms"}),):
        for pool, key in vals.items():
            v = (summary.get(src) or {}).get(key)
            if isinstance(v, (int, float)):
                ref.setdefault(pool, []).append(float(v))
                ref.setdefault("ms:*", []).append(float(v))
    for k, v in (summary.get("indices_calculados") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            ref.setdefault("mm", []).append(float(v))
    marked = LaudoECG(**{**upd, "validacao": {}, "avisos_validacao": []})
    for field in _TEXT_SECTIONS + ["qtc_formula"]:
        txt = getattr(marked, field)
        issues, _ = V._check_text(txt, ref, stats)
        if issues:
            upd[field] = txt + " [⚠ " + "; ".join(issues) + "]"
            notes.extend(f"{field}: {x}" for x in issues)
    for field in ("impressao", "limitrofes"):
        new = []
        for item in getattr(marked, field):
            issues, _ = V._check_text(item, ref, stats)
            if issues:
                item = item + " [⚠ " + "; ".join(issues) + "]"
                notes.extend(f"{field}: {x}" for x in issues)
            new.append(item)
        upd[field] = new
    for field, txt in _all_texts(LaudoECG(**{**upd, "validacao": {}, "avisos_validacao": []})):
        extra = unverified_numbers(txt, summary)
        stats["numeros_fora_das_medidas"] += len(extra)
        notes.extend(f"{field}: número '{x}' não consta nas medidas" for x in extra)
    stats["criticos_sem_lastro"] = 0
    for field in ("impressao", "limitrofes"):
        new = []
        for item in upd[field]:
            for rule in V.critical_mentions(item):
                if not V.is_supported(rule, summary):
                    item += f" ({V.FLAG_UNSUPPORTED})"
                    stats["criticos_sem_lastro"] += 1
                    notes.append(f"{field}: achado crítico '{rule.name}' sem regra de apoio: {V.FLAG_UNSUPPORTED}")
            new.append(item)
        upd[field] = new
    upd["validacao"] = stats
    upd["avisos_validacao"] = notes
    return LaudoECG(**upd)


# ------------------------------------------------------------ renderização
def render_markdown(l: LaudoECG) -> str:
    L = ["# Laudo de ECG - rascunho para revisão médica", ""]
    if l.aviso_topo:
        L += ["> **ATENÇÃO - DISCORDÂNCIA DE MEDIDAS**"] + [f"> {x}" for x in l.aviso_topo] + [""]
    sec = [("Qualidade técnica", l.qualidade_tecnica), ("Ritmo e frequência", l.ritmo_frequencia),
           ("Intervalos", (l.intervalos + (f" QTc: {l.qtc_formula}." if l.qtc_formula else "")).strip()),
           ("Eixos", l.eixos), ("Onda P", l.onda_p), ("Complexo QRS", l.complexo_qrs),
           ("Segmento ST e onda T", l.st_t), ("Comparação", l.comparacao)]
    for title, body in sec:
        if body:
            L += [f"## {title}", body, ""]
    L += ["## IMPRESSÃO DIAGNÓSTICA"] + [f"{i}. {x}" for i, x in enumerate(l.impressao, 1)]
    if l.limitrofes:
        L += ["", "**Limítrofes:** " + "; ".join(l.limitrofes)]
    if l.recomendacao:
        L += ["", f"**Recomendação:** {l.recomendacao}"]
    L += ["", f"_{DISCLAIMER}_"]
    return "\n".join(L)


def render_short(l: LaudoECG) -> str:
    """Um parágrafo para prontuário (texto corrido, sem markdown)."""
    parts = []
    if l.aviso_topo:
        parts.append("ATENÇÃO: " + " ".join(l.aviso_topo))
    parts += [x for x in (l.ritmo_frequencia, l.intervalos) if x]
    if l.impressao:
        parts.append("Impressão: " + "; ".join(x.rstrip(".") for x in l.impressao) + ".")
    if l.recomendacao:
        parts.append(l.recomendacao)
    parts.append("Rascunho para revisão médica.")
    return " ".join(p.strip() for p in parts)


# ------------------------------------------------------------ geração
LLMCall = Callable[[str, str], str]   # (system, user_text) -> JSON str


def user_message(summary: dict) -> str:
    return "ENTRADA (JSON)\n" + json.dumps(summary, ensure_ascii=False, sort_keys=True)


def parse_laudo(text: str) -> LaudoECG:
    data = json.loads(text)
    return LaudoECG(**{k: data[k] for k in _LLM_FIELDS if k in data})


def prepare_summary(summary: dict, *, printed_header: Optional[dict] = None, sexo: Optional[str] = None,
                    digitalizacao_suspeita: Optional[str] = None) -> dict:
    out = dict(summary)
    if printed_header:
        out["cabecalho_impresso"] = dict(printed_header)
    if digitalizacao_suspeita:
        out["digitalizacao_suspeita"] = digitalizacao_suspeita
    idx = {**compute_indices(out, sexo), **(out.get("indices_calculados") or {})}
    if idx:
        out["indices_calculados"] = idx
    if sexo:
        out["contexto"] = {**(out.get("contexto") or {}), "sexo": sexo}
    out["alertas_digitalizacao"] = [alert_text(a) for a in digitization_alerts(out)]
    return out


def generate_laudo(summary: dict, call: LLMCall) -> LaudoECG:
    """Chama a LLM (injetável p/ testes offline), valida e devolve o laudo."""
    raw = call(system_prompt(), user_message(summary))
    return validate_laudo(parse_laudo(raw), summary)
