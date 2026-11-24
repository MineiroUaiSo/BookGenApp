"""Validador pós-LLM: confere o texto da IA contra as medidas/regras determinísticas.

Não é um dispositivo de decisão: só marca divergências para o médico. Sem rede, puro Python.
(a) números com unidade vs. medidas; (b) achado crítico sem lastro em regra/escore;
(c) "normal" com regra crítica disparada; (d) confiança autodeclarada não é exibida.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from ..schemas import AIReport, Finding

NOT_APPLICABLE = "não aplicável"
FLAG_DIVERGENT = "valor divergente da medida"
FLAG_UNSUPPORTED = "não corroborado"
CRITICAL_SEVERITY = "critical"

# ---------------------------------------------------------------- (a) números
_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(ms|milissegundos?|mm|mv|[µμu]v|bpm|%|bat(?:imentos)?/min)"
_CLAIM_RE = re.compile(r"(?<![\w.,])" + _NUM + r"(?:\s*(?:-|–|a)\s*" + _NUM + r")?\s*" + _UNIT + r"(?![A-Za-z/])",
                       re.IGNORECASE)
_ICT_RE = re.compile(r"(?:\bICT\b|[íi]ndice cardiotor[aá]cico|raz[aã]o cardiotor[aá]cica|cardiotor[aá]cic\w*)"
                     r"[^\d\n]{0,30}?(0[.,]\d+|\d{2}(?:[.,]\d+)?\s*%)", re.IGNORECASE)
_SKIP_SENTENCE_RE = re.compile(r"\b1\s*mm\b|25\s*mm/s|10\s*mm/mv|\bgrade\b|calibra", re.IGNORECASE)
_THRESHOLD_CTX_RE = re.compile(r"normal|refer[eê]ncia|limite|esperad|acima de|abaixo de|maior que|menor que|"
                               r"superior a|inferior a|[<>≥≤]|crit[eé]rio|considera|defin", re.IGNORECASE)
_MS_KEYS = [("QTc", re.compile(r"qtc|qt\s*corrigido", re.I)), ("QT", re.compile(r"\bqt\b", re.I)),
            ("QRS", re.compile(r"qrs", re.I)), ("PR", re.compile(r"\bpr\b", re.I)),
            ("RR", re.compile(r"\brr\b", re.I)), ("P", re.compile(r"onda p\b|\bp\b", re.I))]
TOL_MS_ABS, TOL_MS_REL, TOL_BPM, TOL_ICT, TOL_MM, TOL_MV_ABS, TOL_PCT = 10.0, 0.10, 5.0, 0.03, 0.5, 0.1, 5.0


@dataclass(frozen=True)
class Claim:
    lo: float
    hi: float
    unit: str            # ms | mm | mv | bpm | pct | ict
    key: str             # QRS, PR... ou ""
    start: int
    end: int
    text: str


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def _unit_norm(u: str) -> str:
    u = u.lower()
    if u.startswith("ms") or u.startswith("milis"):
        return "ms"
    if u in ("mv", "µv", "μv", "uv"):
        return "mv" if u == "mv" else "uv"
    if u.startswith("bat") or u == "bpm":
        return "bpm"
    return "pct" if u == "%" else u


def _ms_key(text: str, start: int, end: int) -> str:
    before = text[max(0, start - 35):start]
    best, best_pos = "", -1
    for name, rx in _MS_KEYS:
        for m in rx.finditer(before):
            if m.end() > best_pos:
                best, best_pos = name, m.end()
    if best:
        return best
    after = text[end:end + 20]
    for name, rx in _MS_KEYS:
        if rx.search(after):
            return name
    return ""


def extract_claims(text: str) -> list[Claim]:
    """Números com unidade citados em UMA frase (referências/limiares e constantes de grade ficam de fora)."""
    if not text or _SKIP_SENTENCE_RE.search(text):
        return []
    out: list[Claim] = []
    ict_spans: list[tuple[int, int]] = []
    for m in _ICT_RE.finditer(text):
        raw = m.group(1)
        v = _f(re.sub(r"\s*%", "", raw))
        v = v / 100.0 if (v >= 1 or "%" in raw) else v
        ict_spans.append(m.span(1))
        out.append(Claim(v, v, "ict", "ICT", m.start(1), m.end(1), m.group(0)))
    for m in _CLAIM_RE.finditer(text):
        if any(a <= m.start() < b for a, b in ict_spans):
            continue
        if _THRESHOLD_CTX_RE.search(text[max(0, m.start() - 40):m.start()]):
            continue
        lo = _f(m.group(1))
        hi = _f(m.group(2)) if m.group(2) else lo
        unit = _unit_norm(m.group(3))
        if unit == "uv":
            lo, hi, unit = lo / 1000.0, hi / 1000.0, "mv"
        key = _ms_key(text, m.start(), m.end()) if unit == "ms" else ""
        out.append(Claim(min(lo, hi), max(lo, hi), unit, key, m.start(), m.end(), m.group(0)))
    return out


def _vals(d: dict, keys: Iterable[str]) -> list[float]:
    return [float(d[k]) for k in keys if isinstance(d.get(k), (int, float))]


def reference_values(summary: dict) -> dict[str, list[float]]:
    """Mede-se o que o pipeline determinístico produziu: chaves ms:QRS, mv, mm, bpm, pct, ict."""
    ref: dict[str, list[float]] = {}

    def add(k: str, vs: Iterable[float]) -> None:
        ref.setdefault(k, []).extend(vs)

    g = summary.get("medidas_globais") or {}
    leads = summary.get("medidas_por_derivacao") or []
    srcs = [g] + [m for m in leads if isinstance(m, dict)]
    for s in srcs:
        add("ms:PR", _vals(s, ["pr_ms"]))
        add("ms:QRS", _vals(s, ["qrs_ms"]))
        add("ms:QT", _vals(s, ["qt_ms"]))
        add("ms:QTc", _vals(s, ["qtc_bazett_ms", "qtc_fridericia_ms", "qtc_framingham_ms", "qtc_hodges_ms"]))
        add("ms:P", _vals(s, ["p_duration_ms"]))
        add("ms:RR", _vals(s, ["rr_mean_ms", "rr_sd_ms"]))
        add("ms:*", _vals(s, ["q_duration_ms", "intrinsicoid_deflection_ms"]))
        add("mv", [abs(x) for x in _vals(s, ["sokolow_lyon_mv", "cornell_mv", "p_amplitude_mv", "q_amplitude_mv",
                                             "r_amplitude_mv", "s_amplitude_mv", "t_amplitude_mv", "st_j_mv",
                                             "st_j60_mv", "st_j80_mv"])])
    for k in ("PR", "QRS", "QT", "QTc", "P", "RR"):
        add("ms:*", ref.get("ms:" + k, []))
    hr = _vals(g, ["heart_rate_bpm"])
    add("bpm", hr)
    rr = _vals(g, ["rr_mean_ms"])
    add("bpm", [60000.0 / x for x in rr if x > 0])
    add("mm", [x * 10 for x in ref.get("mv", [])])
    # RX
    for im in summary.get("imagens") or []:
        for m in im.get("medidas") or []:
            v, u, key = m.get("value"), (m.get("unit") or "").lower(), m.get("key")
            if not isinstance(v, (int, float)):
                continue
            if key == "cardiothoracic_ratio":
                add("ict", [float(v)])
            elif u == "mm":
                add("mm", [float(v)])
            elif u == "%":
                add("pct", [float(v)])
        add("pct", [100.0 * float(x) for x in (im.get("probabilidades_modelo_auxiliar") or {}).values()
                    if isinstance(x, (int, float))])
    return {k: v for k, v in ref.items() if v}


def _tol(claim: Claim, ref: float) -> float:
    if claim.unit == "ms":
        return max(TOL_MS_ABS, TOL_MS_REL * abs(ref))
    return {"bpm": TOL_BPM, "ict": TOL_ICT, "mm": TOL_MM, "pct": TOL_PCT}.get(claim.unit,
                                                                              max(TOL_MV_ABS, 0.1 * abs(ref)))


def check_claim(c: Claim, ref: dict[str, list[float]]) -> tuple[str, Optional[float]]:
    """('ok'|'mismatch'|'unverifiable', medida mais próxima)."""
    if c.unit == "ms":
        pool = ref.get("ms:" + c.key) if c.key else ref.get("ms:*")
    else:
        pool = ref.get(c.unit)
    if not pool:
        return "unverifiable", None
    sign = abs if c.unit == "mv" else (lambda x: x)
    for r in pool:
        r2 = sign(r)
        t = _tol(c, r2)
        if c.lo - t <= r2 <= c.hi + t:
            return "ok", r2
    mid = (c.lo + c.hi) / 2
    return "mismatch", min((sign(r) for r in pool), key=lambda r: abs(r - mid))


def _fmt(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",") if x < 10 else f"{x:.0f}"


_UNIT_LABEL = {"ms": "ms", "mm": "mm", "mv": "mV", "bpm": "bpm", "pct": "%", "ict": ""}


def _claim_issue(c: Claim, closest: float) -> str:
    unit = _UNIT_LABEL[c.unit]
    cl = f"{_fmt(c.lo)}" if c.lo == c.hi else f"{_fmt(c.lo)}-{_fmt(c.hi)}"
    name = f" {c.key}" if c.key else ""
    return f"valor {cl} {unit}".strip() + f" não confere com a medida{name} {_fmt(closest)} {unit}".rstrip()


# ---------------------------------------------------------------- (b)(c) críticos / normal
@dataclass(frozen=True)
class CriticalRule:
    name: str
    pattern: re.Pattern
    support_codes: re.Pattern            # código de regra que dá lastro
    support_scores: Optional[re.Pattern] = None   # chave em probabilidades_modelo_auxiliar (>= 0.5)
    extra_support: Optional[Any] = None  # callable(summary) -> bool


def _max_qtc(s: dict) -> float:
    g = s.get("medidas_globais") or {}
    return max(_vals(g, ["qtc_bazett_ms", "qtc_fridericia_ms", "qtc_framingham_ms", "qtc_hodges_ms"]) or [0.0])


def _hr_high(s: dict) -> bool:
    g = s.get("medidas_globais") or {}
    return (g.get("heart_rate_bpm") or 0) >= 110


def _ctr_cardiomegaly(s: dict) -> bool:
    for im in s.get("imagens") or []:
        for m in im.get("medidas") or []:
            if m.get("key") == "cardiothoracic_ratio" and isinstance(m.get("value"), (int, float)) \
                    and m["value"] >= 0.5:
                return True
    return False


def _fa_rvr(s: dict) -> bool:
    codes = _rule_codes(s)
    return any("atrial_fibrillation" in c for c in codes) and _hr_high(s)


def _qt_severe(s: dict) -> bool:
    return any("long_qt" in c for c in _rule_codes(s)) and _max_qtc(s) >= 500


def _re(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


CRITICAL_RULES: list[CriticalRule] = [
    CriticalRule("IAM/supra de ST", _re(r"\bIAM(CSST)?\b|infarto|supradesnivel\w*|supra\s*(?:de\s*)?ST|"
                                        r"eleva[cç][aã]o d[oe] (?:segmento )?ST|STEMI"), _re(r"st_elevation")),
    CriticalRule("BAV total (3º grau)", _re(r"\bBAVT\b|BAV\s*(?:de\s*)?(?:total|3\s*[ºo°]?\s*grau)|"
                                            r"bloqueio atrioventricular (?:total|de (?:3|terceiro)\s*[ºo°]?\s*grau)"),
                 _re(r"av_block_3")),
    CriticalRule("BAV 2º grau Mobitz II", _re(r"mobitz\s*(?:ii|2)\b|2\s*[ºo°]?\s*grau\s*tipo\s*ii\b"),
                 _re(r"mobitz2")),
    CriticalRule("TV/FV", _re(r"taquicardia ventricular|fibrila[cç][aã]o ventricular|\bTV\b|"
                              r"\bFV\b"), _re(r"ventricular_tachy|vtach|\bvt\b|vfib|ventricular_fib")),
    CriticalRule("FA de alta resposta", _re(r"(?:fibrila[cç][aã]o atrial|\bFA\b)[^.]{0,40}(?:alta resposta|"
                                            r"resposta ventricular r[aá]pida|\bRVR\b)|"
                                            r"alta resposta ventricular|\bFA\s*(?:de\s*)?alta resposta"),
                 _re(r"$^"), extra_support=_fa_rvr),
    CriticalRule("QT longo grave", _re(r"(?:qt\s*longo|qtc?\s+prolongad\w+)[^.]{0,40}(?:grave|importante|acentuad\w+)|"
                                       r"(?:grave|importante)[^.]{0,20}qt\s*longo"), _re(r"$^"),
                 extra_support=_qt_severe),
    CriticalRule("pneumotórax", _re(r"pneumot[oó]rax"), _re(r"pneumothorax"), _re(r"pneumothorax")),
    CriticalRule("derrame pleural volumoso", _re(r"derrame pleural\s*(?:volumoso|extenso|maci[cç]o|grande)|"
                                                 r"(?:volumoso|extenso|maci[cç]o)\s+derrame"),
                 _re(r"pleural_effusion|effusion"), _re(r"effusion")),
    CriticalRule("pneumoperitônio", _re(r"pneumoperit\w+|ar livre (?:sob|subdiafragm|intraperiton)\w*"),
                 _re(r"pneumoperit"), _re(r"pneumoperit|free_air")),
    CriticalRule("edema agudo de pulmão", _re(r"edema agudo|edema (?:pulmonar|de pulm[aã]o)\b"),
                 _re(r"pulmonary_edema|\bedema"), _re(r"edema")),
    CriticalRule("cardiomegalia", _re(r"cardiomegalia|aumento (?:da )?(?:[aá]rea )?card[ií]ac\w+|"
                                      r"c[aá]rdio?megalia"), _re(r"cardiomegaly"), _re(r"cardiomegaly"),
                 extra_support=_ctr_cardiomegaly),
]
_NEGATION_RE = re.compile(r"\b(sem|aus[eê]ncia|n[aã]o h[aá]|n[aã]o se observa|n[aã]o evidencia|descart\w*|afasta\w*|"
                          r"exclu\w+|nega|negativo|sem sinais de)\b", re.IGNORECASE)
_NORMAL_RE = re.compile(r"dentro (?:d[ao]s? )?(?:limites? d[ao] )?normalidade|dentro dos limites normais|"
                        r"sem altera[cç][oõ]es(?: significativas| relevantes)?|"
                        r"(?:ecg|tra[cç]ado|exame|radiografia|rx|achados)\s+(?:est[aá]\s+)?normais?\b", re.IGNORECASE)


def _rule_codes(s: dict) -> list[str]:
    return [str(f.get("code", "")).lower() for f in s.get("achados_por_regras") or []]


def is_supported(rule: CriticalRule, summary: dict) -> bool:
    if any(rule.support_codes.search(c) for c in _rule_codes(summary)):
        return True
    if rule.support_scores is not None:
        for im in summary.get("imagens") or []:
            for k, v in (im.get("probabilidades_modelo_auxiliar") or {}).items():
                if isinstance(v, (int, float)) and v >= 0.5 and rule.support_scores.search(str(k)):
                    return True
    return bool(rule.extra_support and rule.extra_support(summary))


def critical_mentions(text: str) -> list[CriticalRule]:
    """Regras críticas citadas (afirmativamente) no texto."""
    hits = []
    for r in CRITICAL_RULES:
        for m in r.pattern.finditer(text or ""):
            if _NEGATION_RE.search(text[max(0, m.start() - 40):m.start()]):
                continue
            hits.append(r)
            break
    return hits


def critical_rules_fired(summary: dict) -> list[str]:
    out = []
    for f in summary.get("achados_por_regras") or []:
        code = str(f.get("code", "")).lower()
        if f.get("severity") == CRITICAL_SEVERITY or any(r.support_codes.search(code) for r in CRITICAL_RULES
                                                         if r.support_codes.pattern != "$^"):
            out.append(str(f.get("label") or code))
    return out


def says_normal(rep: AIReport) -> bool:
    if any(f.severity == "normal" and "normal" in (f.label + f.code).lower() for f in rep.findings):
        return True
    return bool(_NORMAL_RE.search(rep.description or ""))


# ---------------------------------------------------------------- orquestração
def _check_text(text: str, ref: dict[str, list[float]], stats: dict[str, int]) -> tuple[list[str], list[tuple[Claim, str]]]:
    issues: list[str] = []
    bad: list[tuple[Claim, str]] = []
    for c in extract_claims(text):
        status, closest = check_claim(c, ref)
        if status == "ok":
            stats["numeros_conferem"] += 1
        elif status == "mismatch":
            stats["numeros_divergentes"] += 1
            issue = _claim_issue(c, closest)  # type: ignore[arg-type]
            issues.append(issue)
            bad.append((c, issue))
        else:
            stats["numeros_nao_verificaveis"] += 1
    return issues, bad


def _mark_description(desc: str, ref: dict, stats: dict, disc: list[str]) -> str:
    parts = re.split(r"((?<=[.!?])\s+|\n+)", desc)
    for i in range(0, len(parts), 2):
        issues, _ = _check_text(parts[i], ref, stats)
        if issues:
            parts[i] = parts[i].rstrip() + " [⚠ " + "; ".join(issues) + "]"
            disc.extend(issues)
    return "".join(parts)


def validate_report(rep: AIReport, summary: dict, rule_findings: Optional[list[Finding]] = None) -> AIReport:
    """Devolve cópia do AIReport com marcações; nunca levanta (falha de validação = relatório intacto)."""
    if not rep.available:
        return rep
    stats = {"numeros_conferem": 0, "numeros_divergentes": 0, "numeros_nao_verificaveis": 0,
             "criticos_sem_lastro": 0, "normal_com_regra_critica": 0}
    ref = reference_values(summary)
    disc: list[str] = list(rep.disagreements_with_measurements)
    limitations = list(rep.limitations)
    rules_conf = {f.code: f.confidence for f in (rule_findings or [])}

    desc = _mark_description(rep.description, ref, stats, disc) if rep.description else rep.description

    findings = []
    for f in rep.findings:
        flags = list(f.validation_flags)
        texts = list(f.evidence) + [f.label]
        new_ev = []
        for e in f.evidence:
            issues, _ = _check_text(e, ref, stats)
            if issues:
                flags.append(FLAG_DIVERGENT)
                disc.extend(f"{f.label}: {x}" for x in issues)
                e = e + " [⚠ " + "; ".join(issues) + "]"
            new_ev.append(e)
        label = f.label
        for rule in critical_mentions(" ".join([f.code, *texts])):
            if not is_supported(rule, summary):
                flags.append(FLAG_UNSUPPORTED)
                stats["criticos_sem_lastro"] += 1
                disc.append(f"Achado crítico '{rule.name}' citado pela IA sem regra/escore de apoio nas medidas: "
                            f"{FLAG_UNSUPPORTED}.")
                if FLAG_UNSUPPORTED not in label:
                    label = f"{label} ({FLAG_UNSUPPORTED})"
        known = f.code in rules_conf
        findings.append(f.model_copy(update={
            "evidence": new_ev, "label": label, "validation_flags": sorted(set(flags)),
            "confidence": rules_conf[f.code] if known else 0.0,
            "confidence_source": "rules" if known else "n/a",
            "confidence_display": None if known else NOT_APPLICABLE}))

    diffs = []
    for d in rep.differentials:
        flags = list(d.validation_flags)
        diag = d.diagnosis
        for t in [d.rationale, *d.supporting, *d.against]:
            issues, _ = _check_text(t, ref, stats)
            if issues:
                flags.append(FLAG_DIVERGENT)
                disc.extend(f"{d.diagnosis}: {x}" for x in issues)
        for rule in critical_mentions(d.diagnosis):
            if not is_supported(rule, summary):
                flags.append(FLAG_UNSUPPORTED)
                stats["criticos_sem_lastro"] += 1
                disc.append(f"Diagnóstico diferencial crítico '{rule.name}' citado pela IA sem regra/escore de "
                            f"apoio nas medidas: {FLAG_UNSUPPORTED}.")
                if FLAG_UNSUPPORTED not in diag:
                    diag = f"{diag} ({FLAG_UNSUPPORTED})"
        diffs.append(d.model_copy(update={
            "diagnosis": diag, "validation_flags": sorted(set(flags)), "confidence": 0.0,
            "confidence_source": "n/a", "confidence_display": NOT_APPLICABLE}))

    # críticos citados só na descrição
    already = {r.name for f in findings for r in critical_mentions(f.label + " " + f.code)} \
        | {r.name for d in diffs for r in critical_mentions(d.diagnosis)}
    for rule in critical_mentions(rep.description or ""):
        if rule.name in already or is_supported(rule, summary):
            continue
        stats["criticos_sem_lastro"] += 1
        disc.append(f"Achado crítico '{rule.name}' citado na descrição da IA sem regra/escore de apoio nas "
                    f"medidas: {FLAG_UNSUPPORTED}.")

    fired = critical_rules_fired(summary)
    if fired and says_normal(rep):
        stats["normal_com_regra_critica"] += 1
        msg = ("ALERTA: a IA descreve o exame como normal/sem alterações, mas há regra crítica disparada: "
               + "; ".join(sorted(set(fired))) + ". Revisão médica obrigatória.")
        disc.append(msg)
        limitations.append(msg)

    seen: set[str] = set()
    disc_u = [x for x in disc if not (x in seen or seen.add(x))]
    return rep.model_copy(update={"description": desc, "findings": findings, "differentials": diffs,
                                  "disagreements_with_measurements": disc_u, "limitations": limitations,
                                  "validation": stats})
