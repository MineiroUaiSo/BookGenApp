"""Ficha de medidas `ecg_features/v1`: fatos [F..] e cartões de critério [C..] com identificadores estáveis.

É a ÚNICA entrada do laudo v2 (só texto; nenhuma imagem). Tudo é determinístico e vem das medidas/regras/índices
já calculados localmente (analysis/indices.py, regras, cartões YAML + busca FTS5 em app/knowledge). A LLM não
mede, não soma e só pode citar os identificadores desta ficha (lista fechada).

Privacidade (LGPD): só entram números medidos, códigos/rótulos de regras, sexo (M/F) e avisos gerados pelo
próprio pipeline (lista de permissão). Nenhum campo livre do cabeçalho impresso, nome, data ou identificador.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..knowledge.cards import Cartao
from ..knowledge.search import LIMITE_PADRAO, select_cards
from .analysis import indices as ix
from .analysis.rules import ST_NOT_ASSESSABLE_CODE
from .plausibility import BBB, PREEXC, QTF, STFIND

SCHEMA = "ecg_features/v1"
LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
QUALIDADE_DERIV_MIN = 0.5          # abaixo disso a derivação é "não avaliável"
DERIV_INVALIDAS_MAX = 6            # >= 6 derivações não avaliáveis => digitalização inválida
GENERIC_CARDS = ("normal.convencoes_medida",)   # sempre disponível: convenções de grade/calibração

Nivel = Literal["ok", "suspeita", "invalida"]
Tipo = Literal["meta", "medida", "indice", "achado"]

# (campo, rótulo, unidade) das medidas globais, na ordem de apresentação
_GLOBAIS = [
    ("heart_rate_bpm", "Frequência cardíaca", "bpm"), ("rr_mean_ms", "Intervalo RR médio", "ms"),
    ("rr_sd_ms", "Desvio-padrão do RR", "ms"), ("p_duration_ms", "Duração da onda P", "ms"),
    ("pr_ms", "Intervalo PR", "ms"), ("qrs_ms", "Duração do QRS", "ms"), ("qt_ms", "Intervalo QT", "ms"),
    ("qtc_bazett_ms", "QTc (Bazett)", "ms"), ("qtc_fridericia_ms", "QTc (Fridericia)", "ms"),
    ("qtc_framingham_ms", "QTc (Framingham)", "ms"), ("qtc_hodges_ms", "QTc (Hodges)", "ms"),
    ("p_axis_deg", "Eixo de P", "graus"), ("qrs_axis_deg", "Eixo do QRS", "graus"), ("t_axis_deg", "Eixo de T", "graus"),
]
_QT_KEYS = {"qt_ms", "qtc_bazett_ms", "qtc_fridericia_ms", "qtc_framingham_ms", "qtc_hodges_ms"}
_ST_KEYS = ("st_j_mv", "st_j60_mv", "st_j80_mv")
_INDICE_LABEL = {
    "sokolow_lyon": "Sokolow-Lyon", "cornell_voltagem": "Cornell (voltagem)", "cornell_produto": "Cornell (produto)",
    "peguero_lo_presti": "Peguero-Lo Presti", "r_avl": "R em aVL", "r_d1": "R em D1",
    "r_d1_mais_s_d3": "R D1 + S D3", "angulo_qrs_t": "Ângulo QRS-T", "morris": "Índice de Morris",
    "romhilt_estes": "Romhilt-Estes",
}
_INDICE_CHAVES = {   # aliases usados em `medidas:` dos cartões
    "sokolow_lyon": ("indices.sokolow_mm", "sokolow_lyon_mv"), "cornell_voltagem": ("indices.cornell_mm", "cornell_mv"),
    "cornell_produto": ("indices.cornell_produto",), "peguero_lo_presti": ("indices.peguero_mm",),
}
# categoria suprimida -> (medidas globais, famílias de achados dependentes)
_AV_PREFIX = ("ecg.av_block_", "ecg.short_pr")
_WPW = ("ecg.wpw",)
_SUPRIME_ACHADOS = {"PR": PREEXC + _WPW + _AV_PREFIX, "QRS": BBB + PREEXC + _WPW, "QT": QTF, "ST": STFIND}
_SUPRIME_GLOBAIS = {"PR": {"pr_ms"}, "QRS": {"qrs_ms"}, "QT": _QT_KEYS, "ST": set()}
_SUPRIME_DEPENDE = {"PR": {"PR", "ST"}, "QRS": {"QRS", "ST"}, "QT": {"QT"}}   # divergência -> categorias afetadas
_IMPRESSO = {"PR": ("pr_ms", "pr_ms"), "QRS": ("qrs_ms", "qrs_ms"), "QT": ("qt_ms", "qt_ms")}
_IMPRESSO_OK = ("pr_ms", "qrs_ms", "qt_ms", "qtc_ms", "p_axis_deg", "qrs_axis_deg", "t_axis_deg")
_AVISO_OK = re.compile(r"^(Traçado digitalizado em segmentos|Derivaç(?:ão|ões) |Frequência de amostragem baixa|"
                       r"Registro muito curto|Qualidade do sinal baixa|Interferência de rede|Poucos batimentos|"
                       r"Ruído elevado|QRS global estimado|ST/Q não avaliados|grade impressa irregular|layout |"
                       r"Resolução baixa)")
_SEXO = {"M": "M", "F": "F"}
AVISO_ST_NAO_AVALIAVEL = ("ST/isquemia não avaliável de forma confiável com este padrão (bloqueio de ramo esquerdo, "
                          "marca-passo ventricular ou QRS >= 120 ms); considerar critérios de Sgarbossa/Smith; "
                          "avaliação médica obrigatória.")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)


class Fato(_Frozen):
    id: str
    chave: str                              # chave semântica estável (ex.: globais.pr_ms, derivacao.V5)
    tipo: Tipo
    texto: str                              # frase pt-BR; TODO número citável do fato está aqui
    valor: Optional[float] = None
    unidade: str = ""
    codigo: str = ""                        # código da regra (achados)
    severidade: str = ""
    chaves: tuple[str, ...] = ()            # chaves de medida (ligam a `medidas:` dos cartões)
    nao_avaliavel: bool = False


class CartaoRef(_Frozen):
    id: str
    card_id: str
    nome: str
    criterio: str
    limiares: dict[str, str] = Field(default_factory=dict)
    armadilhas: tuple[str, ...] = ()
    gatilhos: tuple[str, ...] = ()
    medidas: tuple[str, ...] = ()
    fonte: str = ""
    verificar: str = ""
    revisado_por_medico: bool = False


class Qualidade(_Frozen):
    nivel: Nivel
    motivos: list[str] = Field(default_factory=list)


class Suprimido(_Frozen):
    categoria: str
    motivo: str


class Ficha(_Frozen):
    schema_: str = Field(SCHEMA, alias="schema")
    qualidade: Qualidade
    aviso_topo: list[str] = Field(default_factory=list)   # texto composto em código (não pela LLM)
    contexto: dict[str, str] = Field(default_factory=dict)
    fatos: list[Fato] = Field(default_factory=list)
    cartoes: list[CartaoRef] = Field(default_factory=list)
    suprimidos: list[Suprimido] = Field(default_factory=list)

    # ---- acesso
    @property
    def fact_ids(self) -> list[str]:
        return [f.id for f in self.fatos]

    @property
    def card_ids(self) -> list[str]:
        return [c.id for c in self.cartoes]

    def fato(self, fid: str) -> Optional[Fato]:
        return next((f for f in self.fatos if f.id == fid), None)

    def cartao(self, cid: str) -> Optional[CartaoRef]:
        return next((c for c in self.cartoes if c.id == cid), None)

    def fato_por_chave(self, chave: str) -> Optional[Fato]:
        return next((f for f in self.fatos if f.chave == chave), None)

    def compat_summary(self) -> dict:
        """Forma mínima esperada por validate.is_supported (códigos de regra e medidas globais)."""
        return {"achados_por_regras": [{"code": f.codigo, "severity": f.severidade} for f in self.fatos if f.codigo],
                "medidas_globais": {f.chaves[0]: f.valor for f in self.fatos
                                    if f.chave.startswith("globais.") and f.valor is not None and f.chaves}}

    # ---- serialização
    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    def narrative(self) -> str:
        """Resumo determinístico: uma frase por fato, cada uma com seu [F..]."""
        return "\n".join(f"[{f.id}] {f.texto}" for f in self.fatos)

    def cards_block(self) -> str:
        out = []
        for c in self.cartoes:
            lim = "; ".join(f"{k} {v}" for k, v in c.limiares.items())
            out.append(f"[{c.id}] {c.nome}: {' '.join(c.criterio.split())}"
                       + (f" | Limiares: {lim}" if lim else "")
                       + (f" | Armadilhas: {' '.join(c.armadilhas)}" if c.armadilhas else "")
                       + (" | VERIFICAR (limiar/fonte não confirmado)" if c.verificar else ""))
        return "\n".join(out)


# ------------------------------------------------------------------ utilidades
def _n(x: float) -> str:
    """Número em pt-BR, até 1 casa decimal, sem zeros à direita."""
    r = round(float(x), 1)
    s = f"{int(r)}" if r == int(r) else f"{r:g}"
    return s.replace(".", ",")


def _mm(mv: float) -> float:
    return abs(float(mv)) * 10.0


def _smm(mv: float) -> float:
    return float(mv) * 10.0


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _fmt_dict(d: dict) -> str:
    return ", ".join(f"{k} {_n(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v}"
                     for k, v in d.items())


def _fmt_limiar(t: Any) -> str:
    if isinstance(t, dict):
        return "/".join(f"{k} {_n(v)}" for k, v in t.items())
    return _n(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else str(t)


class _Builder:
    def __init__(self) -> None:
        self.itens: list[dict] = []

    def add(self, chave: str, tipo: Tipo, texto: str, **kw: Any) -> None:
        self.itens.append({"chave": chave, "tipo": tipo, "texto": texto, **kw})

    def fatos(self) -> list[Fato]:
        return [Fato(id=f"F{i}", **it) for i, it in enumerate(self.itens, 1)]


# ------------------------------------------------------------------ qualidade / supressão
def _printed(summary: dict, override: Optional[dict]) -> dict[str, float]:
    src = override if override is not None else summary.get("cabecalho_impresso") or {}
    return {k: float(src[k]) for k in _IMPRESSO_OK if _num(src.get(k)) is not None}


def _divergencias(g: dict, printed: dict[str, float]) -> list[dict]:
    out = []
    for cat, (gk, pk) in _IMPRESSO.items():
        a, p = _num(g.get(gk)), printed.get(pk)
        if a is not None and p is not None and abs(a - p) > max(20.0, 0.2 * p):
            out.append({"cat": cat, "algoritmo": a, "impresso": p})
    return out


def _suspeita_generica(summary: dict) -> list[str]:
    motivos: list[str] = []
    if summary.get("digitalizacao_suspeita"):
        motivos.append(str(summary["digitalizacao_suspeita"]))
    for f in summary.get("achados_por_regras") or []:
        if str(f.get("code", "")) == "ecg.digitization_suspect":
            motivos += [str(e) for e in f.get("evidence") or []] or ["digitalização suspeita (regras)"]
    for w in summary.get("avisos") or []:
        if re.search(r"digitaliza[cç][aã]o suspeita", str(w), re.I):
            motivos.append(str(w))
    return list(dict.fromkeys(motivos))


def _aviso_texto(d: dict) -> str:
    return (f"Discordância: {d['cat']} do algoritmo {_n(d['algoritmo'])} ms diverge do impresso no aparelho "
            f"({_n(d['impresso'])} ms); provável erro de digitalização/delineação. Achados dependentes dessa medida "
            "não são diagnosticados; conferir no traçado original.")


# ------------------------------------------------------------------ construção
def _lead_texto(lead: str, m: dict, supr: set[str]) -> tuple[str, tuple[str, ...]]:
    partes: list[str] = []
    chaves: list[str] = []

    def add(key: str, label: str, val: Any, signed: bool = False, unit: str = "mm", conv: bool = True) -> None:
        v = _num(val)
        if v is None:
            return
        if conv:
            v = _smm(v) if signed else _mm(v)
        partes.append(f"{label} {_n(v)} {unit}")
        chaves.append(key)

    add("p_amplitude_mv", "P", m.get("p_amplitude_mv"))
    add("q_amplitude_mv", "Q", m.get("q_amplitude_mv"))
    add("r_amplitude_mv", "R", m.get("r_amplitude_mv"))
    add("s_amplitude_mv", "S", m.get("s_amplitude_mv"))
    add("t_amplitude_mv", "T", m.get("t_amplitude_mv"), signed=True)
    if "ST" not in supr:
        add("st_j_mv", "ST J", m.get("st_j_mv"), signed=True)
        add("st_j60_mv", "ST J60", m.get("st_j60_mv"), signed=True)
        add("st_j80_mv", "ST J80", m.get("st_j80_mv"), signed=True)
    add("p_duration_ms", "duração de P", m.get("p_duration_ms"), unit="ms", conv=False)
    if "QRS" not in supr:
        add("qrs_ms", "QRS", m.get("qrs_ms"), unit="ms", conv=False)
    if "PR" not in supr:
        add("pr_ms", "PR", m.get("pr_ms"), unit="ms", conv=False)
    add("intrinsicoid_deflection_ms", "deflexão intrinsecoide", m.get("intrinsicoid_deflection_ms"), unit="ms",
        conv=False)
    if m.get("morphology"):
        partes.append(f"morfologia {m['morphology']}")
    return f"{lead}: " + ", ".join(partes), tuple(chaves)


def _computar_indices(leads: dict, g: dict, sexo: Optional[str], supr: set[str], achados: list[dict]) -> dict:
    r = {l: _mm(m["r_amplitude_mv"]) for l, m in leads.items() if _num(m.get("r_amplitude_mv")) is not None}
    s = {l: _mm(m["s_amplitude_mv"]) for l, m in leads.items() if _num(m.get("s_amplitude_mv")) is not None}
    if not r and not s:
        return {}
    strain = any(str(a.get("code", "")).startswith("ecg.secondary_repolarization") for a in achados)
    qrs = None if "QRS" in supr else _num(g.get("qrs_ms"))
    return ix.compute_indices(r, s, sex=sexo, qrs_ms=qrs, qrs_axis=_num(g.get("qrs_axis_deg")),
                              t_axis=_num(g.get("t_axis_deg")), strain=strain)


def _indice_texto(nome: str, i: dict) -> str:
    comp = i.get("componentes") or {}
    fills = i.get("preenche")
    est = "preenche" if fills is True else ("não preenche" if fills is False else "preenche conforme o sexo")
    un = f" {i['unidade']}" if i.get("unidade") else ""
    base = f"{_INDICE_LABEL.get(nome, nome)} {_n(i['v'])}{un} (limiar {_fmt_limiar(i.get('limiar'))}; {est})"
    return base + (f"; componentes: {_fmt_dict(comp)}" if comp else "")


def _to_cartao(i: int, c: Cartao) -> CartaoRef:
    return CartaoRef(id=f"C{i}", card_id=c.id, nome=c.nome_pt, criterio=" ".join(c.criterio.split()),
                     limiares={k: str(v) for k, v in c.limiares.items()}, armadilhas=tuple(c.armadilhas),
                     gatilhos=tuple(c.gatilhos), medidas=tuple(c.medidas), fonte=f"{c.fonte.ref} ({c.fonte.local})",
                     verificar=c.verificar or "", revisado_por_medico=c.revisado_por_medico)


def _selecionar_cartoes(codes: list[str], keys: set[str]) -> list[CartaoRef]:
    from ..knowledge.cards import load_cards
    sel = select_cards(codes, keys, [], limite=LIMITE_PADRAO)
    por_id = {c.id: c for c in load_cards()}
    for gid in GENERIC_CARDS:
        if gid in por_id and gid not in {c.id for c in sel}:
            sel = (sel[: LIMITE_PADRAO - 1] if len(sel) >= LIMITE_PADRAO else sel) + [por_id[gid]]
    return [_to_cartao(i, c) for i, c in enumerate(sel, 1)]


def features_from_summary(summary: dict, *, sexo: Optional[str] = None, printed_header: Optional[dict] = None) -> Ficha:
    """Ficha a partir do resumo determinístico da análise (forma de `llm.ecg_data_summary`)."""
    g = dict(summary.get("medidas_globais") or {})
    leads = {m["lead"]: m for m in summary.get("medidas_por_derivacao") or [] if isinstance(m, dict) and m.get("lead")}
    achados = [a for a in summary.get("achados_por_regras") or [] if isinstance(a, dict)]
    sexo = _SEXO.get(str(sexo or (summary.get("contexto") or {}).get("sexo") or "").upper()[:1])
    printed = _printed(summary, printed_header)
    qual_deriv = {k: float(v) for k, v in (summary.get("qualidade_por_derivacao") or {}).items() if _num(v) is not None}

    # --- supressão e qualidade
    div = _divergencias(g, printed)
    generica = _suspeita_generica(summary)
    supr: dict[str, str] = {}
    for d in div:
        for cat in _SUPRIME_DEPENDE[d["cat"]]:
            supr.setdefault(cat, f"{d['cat']} do algoritmo diverge do cabeçalho impresso")
    if generica:
        for cat in ("PR", "QRS", "ST"):
            supr.setdefault(cat, "digitalização suspeita")
    baixa = sorted(l for l in leads if qual_deriv.get(l, 1.0) < QUALIDADE_DERIV_MIN)
    tem_dado = any(_num(g.get(k)) is not None for k in ("heart_rate_bpm", "pr_ms", "qrs_ms", "qt_ms", "rr_mean_ms")) \
        or bool(leads)
    motivos: list[str] = [_aviso_texto(d) for d in div] + generica
    if not tem_dado:
        nivel: Nivel = "invalida"
        motivos.append("sem medidas utilizáveis na análise")
    elif len(baixa) >= DERIV_INVALIDAS_MAX:
        nivel = "invalida"
        motivos.append(f"{len(baixa)} derivações com qualidade insuficiente")
    else:
        nivel = "suspeita" if supr else "ok"
    suprimidos = [Suprimido(categoria=c, motivo=m) for c, m in sorted(supr.items())]
    aviso_topo = [_aviso_texto(d) for d in div]
    if generica and not div:
        aviso_topo.append("Digitalização suspeita (" + "; ".join(generica) + "); achados dependentes de intervalos e "
                          "ST não são diagnosticados; conferir no traçado original.")
    if any(str(a.get("code", "")) == ST_NOT_ASSESSABLE_CODE for a in achados):
        aviso_topo.append(AVISO_ST_NAO_AVALIAVEL)
    suprimir_globais = set().union(*(_SUPRIME_GLOBAIS[c] for c in supr)) if supr else set()
    prefixos = tuple(p for c in supr for p in _SUPRIME_ACHADOS[c])

    # --- fatos
    b = _Builder()
    fonte = str(summary.get("fonte") or "desconhecida")
    est = {"ok": "adequada", "suspeita": "suspeita (medidas dependentes da digitalização foram descartadas)",
           "invalida": "inválida"}[nivel]
    cab = f"Estado da digitalização: fonte {fonte}"
    if _num(summary.get("fs_hz")) is not None:
        cab += f", {_n(summary['fs_hz'])} Hz"
    if _num(summary.get("duracao_s")) is not None:
        cab += f", {_n(summary['duracao_s'])} s"
    cab += f", {len(leads)} derivações com medidas; qualidade técnica {est}"
    b.add("aquisicao", "meta", cab, chaves=())
    if printed:
        b.add("cabecalho_impresso", "meta",
              "Cabeçalho impresso do aparelho: " + ", ".join(
                  f"{lab} {_n(printed[k])} {u}" for k, lab, u in (
                      ("pr_ms", "PR", "ms"), ("qrs_ms", "QRS", "ms"), ("qt_ms", "QT", "ms"), ("qtc_ms", "QTc", "ms"),
                      ("p_axis_deg", "eixo de P", "graus"), ("qrs_axis_deg", "eixo do QRS", "graus"),
                      ("t_axis_deg", "eixo de T", "graus")) if k in printed))
    for d in div:
        b.add(f"divergencia.{d['cat']}", "meta",
              f"Divergência: {d['cat']} do algoritmo diverge do impresso ({_n(d['impresso'])} ms); "
              "medida do algoritmo descartada")
    for cat, motivo in sorted(supr.items()):
        b.add(f"suprimido.{cat}", "meta", f"{cat}: não avaliável com segurança ({motivo}); achados dependentes "
              "não são diagnosticados", nao_avaliavel=True)
    if sexo:
        b.add("contexto.sexo", "meta", f"Contexto informado: sexo {sexo}")
    for key, label, unit in _GLOBAIS:
        v = _num(g.get(key))
        if v is None:
            continue
        if key in suprimir_globais:
            b.add(f"globais.{key}", "medida", f"{label}: não avaliável (digitalização suspeita)", chaves=(key,),
                  nao_avaliavel=True)
        else:
            b.add(f"globais.{key}", "medida", f"{label} {_n(v)} {unit}", valor=round(v, 1), unidade=unit,
                  chaves=(key,))
    if g.get("rhythm"):
        b.add("globais.rhythm", "medida", f"Ritmo (regras): {g['rhythm']}", chaves=("rhythm",))
    if g.get("precordial_transition"):
        b.add("globais.precordial_transition", "medida", f"Transição precordial em {g['precordial_transition']}",
              chaves=("precordial_transition",))
    for lead in LEADS:
        m = leads.get(lead)
        if not m:
            continue
        if qual_deriv.get(lead, 1.0) < QUALIDADE_DERIV_MIN:
            b.add(f"derivacao.{lead}", "medida", f"{lead}: não avaliável (qualidade do sinal {_n(qual_deriv[lead])})",
                  nao_avaliavel=True)
            continue
        texto, chaves = _lead_texto(lead, m, set(supr))
        if chaves or m.get("morphology"):
            b.add(f"derivacao.{lead}", "medida", texto, chaves=chaves)
    indices = g.get("indices") or _computar_indices(leads, g, sexo, set(supr), achados)
    for nome, i in indices.items():
        if "QRS" in supr and nome in ("cornell_produto", "romhilt_estes"):
            continue
        if _num(i.get("v")) is None:
            continue
        b.add(f"indice.{nome}", "indice", _indice_texto(nome, i), valor=round(float(i["v"]), 2),
              unidade=str(i.get("unidade") or ""), chaves=_INDICE_CHAVES.get(nome, (f"indices.{nome}",)))
    emitidos: list[str] = []
    for a in sorted(achados, key=lambda x: str(x.get("code", ""))):
        code = str(a.get("code", ""))
        if not code or code == "ecg.digitization_suspect" or code.startswith(prefixos):
            continue
        ev = "; ".join(str(e) for e in a.get("evidence") or [])
        sev = str(a.get("severity") or "")
        b.add(f"achado.{code}", "achado", f"Regra {code}: {a.get('label', code)}" + (f" ({sev})" if sev else "")
              + (f"; evidências: {ev}" if ev else ""), codigo=code, severidade=sev)
        emitidos.append(code)
    avisos = [str(w) for w in summary.get("avisos") or [] if _AVISO_OK.match(str(w))][:5]
    for i, w in enumerate(avisos, 1):
        b.add(f"aviso.{i}", "meta", f"Aviso do pipeline: {w}")
    fatos = b.fatos()

    # --- cartões de critério
    keys = {k for f in fatos if not f.nao_avaliavel for k in f.chaves}
    cartoes = _selecionar_cartoes(emitidos, keys) if fatos else []
    ctx = {"sexo": sexo} if sexo else {}
    return Ficha(qualidade=Qualidade(nivel=nivel, motivos=motivos), aviso_topo=aviso_topo, contexto=ctx, fatos=fatos,
                 cartoes=cartoes, suprimidos=suprimidos)


_PRINTED_CAL = {"printed.pr_ms": "pr_ms", "printed.qrs_ms": "qrs_ms", "printed.qt_ms": "qt_ms",
                "printed.qtc_ms": "qtc_ms", "printed.p_axis": "p_axis_deg", "printed.r_axis": "qrs_axis_deg",
                "printed.t_axis": "t_axis_deg"}


def features_from_analysis(a: Any, *, printed_header: Optional[dict] = None, sexo: Optional[str] = None) -> Ficha:
    """Ficha a partir de um `ECGAnalysis` (cabeçalho impresso: argumento ou `printed.*` da calibração)."""
    cal = a.signal.calibration or {}
    cab = printed_header if printed_header is not None else {
        dst: cal[src] for src, dst in _PRINTED_CAL.items() if src in cal}
    summary = {
        "fonte": a.signal.source.value, "fs_hz": a.signal.fs, "duracao_s": a.signal.duration_s,
        "qualidade_por_derivacao": a.signal.quality,
        "medidas_globais": a.global_measurements.model_dump(exclude_none=True),
        "medidas_por_derivacao": [m.model_dump(exclude_none=True) for m in a.lead_measurements],
        "achados_por_regras": [f.model_dump(include={"code", "label", "severity", "evidence"}) for f in a.findings],
        "avisos": a.warnings, "cabecalho_impresso": cab,
    }
    return features_from_summary(summary, sexo=sexo)
