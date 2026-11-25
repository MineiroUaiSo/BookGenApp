"""Laudo de ECG completo em pt-BR (prompt ecg_laudo_v1): schema, gate de digitalização, validação e renderização.

Rascunho para revisão médica; não é dispositivo certificado. A LLM só recebe medidas/regras (sem imagem);
números fora das medidas e afirmações sobre achados "suprimidos" por divergência de digitalização são
marcados/removidos aqui, em código (não só no prompt).
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from pydantic import BaseModel, Field

from . import validate as V
from .guard import PayloadBloqueado, assert_text_only  # noqa: F401  (API pública do laudo)

if TYPE_CHECKING:
    from ..ecg.features import Ficha

log = logging.getLogger("medlens.laudo")

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
    """Cornell, Sokolow-Lyon e Peguero-Lo Presti em mm (1 mV = 10 mm), a partir de R/S por derivação.

    Fallback local: índices prontos vindos de fora (summary["indices_calculados"], ex.: futuro analysis/indices.py)
    têm precedência em prepare_summary."""
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
    r_avl, s_v3, s_v4 = amp("aVL", "r_amplitude_mv"), amp("V3", "s_amplitude_mv"), amp("V4", "s_amplitude_mv")
    if r_avl is not None and s_v3 is not None:
        out["cornell_mm"] = round(r_avl + s_v3, 1)
        if male is not None:
            out["cornell_limite_mm"] = 28 if male else 20
    s_all = [amp(k, "s_amplitude_mv") for k in leads]
    s_all = [x for x in s_all if x is not None]
    if s_all and s_v4 is not None:   # Peguero 2017: S mais profunda em qualquer derivação + S de V4
        pg = round(max(s_all) + s_v4, 1)
        out["peguero_lo_presti_mm"] = pg
        if male is not None:
            lim = 28 if male else 23      # >= 28 mm homens / >= 23 mm mulheres (JACC 2017;69:1694)
            out["peguero_limite_mm"] = lim
            out["peguero_preenchido"] = pg >= lim
    return out


# ------------------------------------------------------------ gate de digitalização
_SUPPRESS = V.SUPPRESS_PATTERNS   # padrões compartilhados com o validador v2
_PRINTED = {"PR": ("pr_ms", "pr_ms"), "QRS": ("qrs_ms", "qrs_ms"), "QT": ("qt_ms", "qt_ms")}
_HEDGE_RE = V.HEDGE_RE


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
    return number_stats(text, summary)[1]


def number_stats(text: str, summary: dict) -> tuple[int, list[str]]:
    """(total de números checados, lista dos que não constam nas medidas)."""
    known = _all_numbers({k: v for k, v in summary.items() if k != "contexto"})
    known |= {k * 10 for k in known} | {k / 10 for k in known}
    known |= {float(x) for x in _REF_LIMITS}
    bad: list[str] = []
    total = 0
    clean = _LEAD_RE.sub(" ", text or "")
    for m in _NUMTOK.finditer(clean):
        v = float(m.group(1).replace(",", "."))
        unit = (m.group(2) or "").lower()
        if unit in ("mm/mv", "mm/s"):
            continue
        if not unit and v <= 12 and float(v).is_integer():
            continue
        total += 1
        tol = max(0.51, 0.02 * v)
        if not any(abs(v - k) <= tol for k in known):
            bad.append(m.group(0).strip())
    return total, bad


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


# =============================================================== laudo v2: citações [F]/[C], só texto
PROMPT_VERSION_V2 = "ecg_laudo_v2"
PROMPT_PATH_V2 = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION_V2}.md"
ABSTENCAO_TEXTO = "Sem laudo automático confiável."
_V2_STR_SECTIONS = ("qualidade_tecnica", "ritmo_frequencia", "intervalos", "eixos", "onda_p", "complexo_qrs", "st_t",
                    "recomendacao")
_V2_LIST_SECTIONS = ("impressao", "limitrofes")


def v2_enabled() -> bool:
    """Laudo v2 (citações) só liga com MEDLENS_LAUDO_V2=1; padrão desligado até aprovação médica."""
    return os.environ.get("MEDLENS_LAUDO_V2", "0") == "1"


class Citacao(BaseModel):
    n: int
    secao: str
    texto: str
    fatos: list[str]
    criterios: list[str]


class RejeicaoV2(BaseModel):
    indice: int
    secao: str
    motivos: list[str]          # o texto rejeitado NÃO é guardado: nada inventado chega ao consumidor


class Abstencao(BaseModel):
    texto: str = ABSTENCAO_TEXTO
    motivos: list[str] = Field(default_factory=list)


class LaudoV2(LaudoECG):
    versao: str = "v2"
    comparacao: str = ""        # sem fato que o sustente: não afirmamos nada sobre ECG anterior
    abstencao: Optional[Abstencao] = None
    citacoes: list[Citacao] = Field(default_factory=list)
    rejeitadas: list[RejeicaoV2] = Field(default_factory=list)


# Barreira LGPD: padrões e verificação vivem em guard.py (aplicada também em client.run_resilient).


def system_prompt_v2() -> str:
    return PROMPT_PATH_V2.read_text(encoding="utf-8")


def output_schema_v2(ficha: "Ficha") -> dict:
    """JSON Schema estrito; fatos/critérios são enums da lista fechada enviada (mínimo 1 de cada)."""
    item = {"type": "object", "additionalProperties": False,
            "required": ["secao", "texto", "fatos", "criterios"],
            "properties": {
                "secao": {"type": "string", "enum": list(V.SECOES_V2)},
                "texto": {"type": "string"},
                "fatos": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ficha.fact_ids}},
                "criterios": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ficha.card_ids}}}}
    return {"type": "object", "additionalProperties": False, "required": ["afirmacoes"],
            "properties": {"afirmacoes": {"type": "array", "items": item}}}


def user_message_v2(ficha: "Ficha") -> str:
    return "\n".join([
        "FICHA ecg_features/v1 (somente texto)",
        f"Qualidade técnica da digitalização: {ficha.qualidade.nivel}",
        "", "FATOS (cite pelo identificador)", ficha.narrative(),
        "", "CRITÉRIOS (cite pelo identificador)", ficha.cards_block(),
        "", "LISTA FECHADA DE IDENTIFICADORES",
        "fatos: " + ", ".join(ficha.fact_ids), "criterios: " + ", ".join(ficha.card_ids)])


def _marca(a: V.Afirmacao) -> str:
    return f"[{', '.join(a.fatos)}; {', '.join(a.criterios)}]"


def _rej(bad: list[V.Rejeicao]) -> list[RejeicaoV2]:
    return [RejeicaoV2(indice=r.indice, secao=r.secao, motivos=list(r.motivos)) for r in bad]


def _abstem(ficha: "Ficha", motivos: list[str], rejeitadas: Optional[list[V.Rejeicao]] = None,
            stats: Optional[dict[str, int]] = None) -> LaudoV2:
    uniq = list(dict.fromkeys(m for m in motivos if m))
    return LaudoV2(aviso_topo=list(ficha.aviso_topo), abstencao=Abstencao(motivos=uniq),
                   rejeitadas=_rej(rejeitadas or []), validacao=stats or {}, avisos_validacao=uniq)


def generate_laudo_v2(ficha: "Ficha", call: LLMCall) -> LaudoV2:
    """Chama a LLM (injetável), valida cada afirmação contra a ficha e devolve o laudo ou a abstenção explícita.

    Nunca levanta: falha de chamada, JSON fora do esquema, payload bloqueado, qualidade inválida ou maioria de
    afirmações rejeitadas viram abstenção com motivos; nenhum texto não validado é emitido."""
    if ficha.qualidade.nivel == "invalida":
        return _abstem(ficha, ["digitalização/medidas inválidas: " + m for m in ficha.qualidade.motivos])
    try:
        system, user = system_prompt_v2(), user_message_v2(ficha)
        assert_text_only(system, user)
    except PayloadBloqueado as e:
        return _abstem(ficha, [f"payload bloqueado pela barreira LGPD ({e}); nada foi enviado ao provedor"])
    try:
        raw = call(system, user)
    except Exception as e:  # noqa: BLE001 - qualquer falha de rede/provedor vira abstenção
        log.warning("laudo v2: falha na chamada da LLM (%s)", type(e).__name__)
        return _abstem(ficha, [f"falha na chamada da LLM ({type(e).__name__})"])
    try:
        claims = json.loads(raw)["afirmacoes"]
        if not isinstance(claims, list):
            raise TypeError("afirmacoes não é lista")
    except (ValueError, KeyError, TypeError):
        return _abstem(ficha, ["resposta da LLM fora do esquema (JSON inválido ou sem 'afirmacoes')"])
    if not claims:
        return _abstem(ficha, ["a LLM não emitiu nenhuma afirmação"])
    ok, bad = V.validate_claims(claims, ficha)
    cobertura = sum(1 for a in ok if a.fatos and a.criterios and all(ficha.fato(i) for i in a.fatos)
                    and all(ficha.cartao(i) for i in a.criterios))
    stats = {"afirmacoes_total": len(claims), "afirmacoes_emitidas": len(ok), "afirmacoes_rejeitadas": len(bad),
             "cobertura_citacao_pct": round(100 * cobertura / len(ok)) if ok else 0}
    motivos_rej = [f"afirmação {r.indice + 1}: {m}" for r in bad for m in r.motivos]
    if not ok or len(bad) / len(claims) > V.MAX_REJEICAO:
        return _abstem(ficha, [f"{len(bad)} de {len(claims)} afirmações da LLM rejeitadas pelo validador"]
                       + motivos_rej, bad, stats)
    upd: dict[str, Any] = {k: [] if k in _V2_LIST_SECTIONS else "" for k in (*_V2_STR_SECTIONS, *_V2_LIST_SECTIONS)}
    for a in ok:
        t = f"{a.texto} {_marca(a)}"
        if a.secao in _V2_LIST_SECTIONS:
            upd[a.secao].append(t)
        else:
            upd[a.secao] = (upd[a.secao] + " " + t).strip()
    cits = [Citacao(n=i, secao=a.secao, texto=a.texto, fatos=list(a.fatos), criterios=list(a.criterios))
            for i, a in enumerate(ok, 1)]
    return LaudoV2(**upd, aviso_topo=list(ficha.aviso_topo), citacoes=cits, rejeitadas=_rej(bad),
                   validacao=stats, avisos_validacao=motivos_rej)


def _fontes(l: LaudoV2, ficha: "Ficha") -> list[str]:
    fids = list(dict.fromkeys(i for c in l.citacoes for i in c.fatos))
    cids = list(dict.fromkeys(i for c in l.citacoes for i in c.criterios))
    out = ["## Fontes das citações"]
    for i in fids:
        f = ficha.fato(i)
        if f:
            out.append(f"- [{i}] {f.texto}")
    for i in cids:
        k = ficha.cartao(i)
        if k:
            out.append(f"- [{i}] {k.nome}: {k.criterio}")
    return out


def render_markdown_v2(l: LaudoV2, ficha: "Ficha") -> str:
    out = ["# Laudo de ECG - rascunho para revisão médica", ""]
    if l.aviso_topo:
        out += ["> **ATENÇÃO - DISCORDÂNCIA DE MEDIDAS**"] + [f"> {x}" for x in l.aviso_topo] + [""]
    if l.abstencao is not None:
        out += [f"> **{ABSTENCAO_TEXTO}**", ""] + [f"- {m}" for m in l.abstencao.motivos]
        out += ["", "Conferir o traçado original e laudar manualmente.", "", f"_{DISCLAIMER}_"]
        return "\n".join(out)
    sec = [("Qualidade técnica", l.qualidade_tecnica), ("Ritmo e frequência", l.ritmo_frequencia),
           ("Intervalos", l.intervalos), ("Eixos", l.eixos), ("Onda P", l.onda_p), ("Complexo QRS", l.complexo_qrs),
           ("Segmento ST e onda T", l.st_t)]
    for title, body in sec:
        if body:
            out += [f"## {title}", body, ""]
    if l.impressao:
        out += ["## IMPRESSÃO DIAGNÓSTICA"] + [f"{i}. {x}" for i, x in enumerate(l.impressao, 1)]
    if l.limitrofes:
        out += ["", "**Limítrofes:** " + "; ".join(l.limitrofes)]
    if l.recomendacao:
        out += ["", f"**Recomendação:** {l.recomendacao}"]
    out += [""] + _fontes(l, ficha) + ["", f"_{DISCLAIMER}_"]
    return "\n".join(out)


_MARCA_RE = re.compile(r"\s*\[F\d+[^\]]*\]")


def render_short_v2(l: LaudoV2) -> str:
    if l.abstencao is not None:
        return " ".join([ABSTENCAO_TEXTO, *l.abstencao.motivos[:3], "Rascunho para revisão médica."])
    return _MARCA_RE.sub("", render_short(l))
