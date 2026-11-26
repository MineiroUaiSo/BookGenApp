"""'Descrição completa' do ECG em parágrafo único (pt-BR), no fim do relatório.

Base DETERMINÍSTICA (`montar_deterministico`): cada oração nasce de uma medida, de um achado de regra
(`achados_por_regras`) ou de uma abstenção explícita ("não avaliado"/"sem regra automática para ..."). Nenhuma IA.
Redação opcional por IA (`compor_descricao` com `call`): o modelo só recebe FATOS estruturados (sem imagem e sem o
cabeçalho impresso) e a saída passa por: normalização em parágrafo único, ecg_claim_check (frase sem lastro é
removida), conferência de números contra os fatos e barreira de PHI. Qualquer falha cai na base determinística
(falha fechada); se a própria barreira quebrar, o parágrafo é descartado com a limitação registrada.
Decisões do dono respeitadas: QRS largo sem BRE segue "limítrofe"; normalidade só com ecg.within_normal_limits e
com o qualificador "regras automáticas"; nunca nega isquemia/BAV/bloqueio sem regra que sustente.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import ecg_claim_check as EC
from . import laudo as L
from .guard import scan_text

log = logging.getLogger("medlens.descricao_ecg")

LLMCall = Callable[[str, str], str]
PROMPT_PATH = Path(__file__).parent / "prompts" / "ecg_descricao_v1.md"
ORIGEM_IA, ORIGEM_DET = "ia", "deterministico"
FALHA_BARREIRA = "barreira de verificação falhou: descrição completa descartada"
_ST_NA, _NORMAL = "ecg.st_not_assessable", "ecg.within_normal_limits"

# grupos por prefixo de código de regra
_RITMO = ("ecg.atrial_fibrillation", "ecg.atrial_flutter", "ecg.sinus_", "ecg.irregular_rhythm", "ecg.no_p_wave",
          "ecg.non_sinus_p", "ecg.paced_rhythm", "ecg.rhythm_unclassified_")
_IRREGULAR = ("ecg.atrial_fibrillation", "ecg.irregular_rhythm")
_AV = ("ecg.av_block_", "ecg.short_pr", "ecg.preexcitation", "ecg.pr_gt200_unconfirmed")
_BBB = ("ecg.lbbb", "ecg.rbbb", "ecg.ilbbb", "ecg.irbbb", "ecg.ivcd", "ecg.qrs_borderline", "ecg.lafb", "ecg.lpfb")
_EIXO = ("ecg.left_axis", "ecg.right_axis")
_CAMARAS = ("ecg.lae", "ecg.rae", "ecg.lvh", "ecg.rvh", "ecg.hcm_pattern")
_VOLT = ("ecg.low_voltage",)
_Q = ("ecg.pathologic_q_",)
_STT = ("ecg.st_elevation_", "ecg.st_depression_", "ecg.t_inversion_", "ecg.secondary_repolarization")
_QT = ("ecg.long_qt", "ecg.short_qt")
_TEC = ("ecg.digitization_suspect", "ecg.implausible_measurement")
_QTC = (("qtc_bazett_ms", "Bazett"), ("qtc_fridericia_ms", "Fridericia"), ("qtc_framingham_ms", "Framingham"),
        ("qtc_hodges_ms", "Hodges"))
_DERIV = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
_QUAL_MIN = 0.5
_AVISO_OK = re.compile(r"^(Traçado digitalizado em segmentos|Derivaç(?:ão|ões) |Frequência de amostragem baixa|"
                       r"Registro muito curto|Qualidade do sinal baixa|Interferência de rede|Poucos batimentos|"
                       r"Ruído elevado|Resolução baixa)")


@dataclass(frozen=True)
class Descricao:
    texto: str
    origem: str                      # "ia" | "deterministico" | "" (descartada)
    removidas: int = 0               # frases removidas pela barreira
    limitacoes: tuple[str, ...] = ()


# ------------------------------------------------------------------ utilidades
def _n(x: float) -> str:
    r = round(float(x), 1)
    return (f"{int(r)}" if r == int(r) else f"{r:g}").replace(".", ",")


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _lc(label: str) -> str:
    s = " ".join(str(label).split()).rstrip(".")
    return s[0].lower() + s[1:] if len(s) > 1 and s[1].islower() else s


def _juntar(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _tem(code: str, grupo: tuple[str, ...]) -> bool:
    return any(code.startswith(p) for p in grupo)


def _evid(f: dict) -> str:
    ev = [str(e).strip().rstrip(".") for e in f.get("evidence") or [] if str(e).strip()]
    return ev[0] if ev else ""


def _com_evid(f: dict) -> str:
    e = _evid(f)
    return f"{_lc(f['label'])} ({e})" if e else _lc(f["label"])


@dataclass(frozen=True)
class _Ctx:
    g: dict
    leads: list[dict]
    achados: list[dict]
    idx: dict
    supr: frozenset
    alertas: list[dict]
    paced: bool
    st_na: bool

    def f(self, *grupos: tuple[str, ...]) -> list[dict]:
        return [a for a in self.achados if any(_tem(a["code"], g) for g in grupos)]

    def m(self, k: str) -> Optional[float]:
        return _num(self.g.get(k))


def _ctx(summary: dict) -> _Ctx:
    from ..ecg import plausibility as P   # import tardio: evita ciclo llm <-> ecg
    achados = [{**a, "code": str(a.get("code", "")).lower(), "label": str(a.get("label") or a.get("code") or ""),
                "severity": str(a.get("severity", ""))}
               for a in summary.get("achados_por_regras") or [] if isinstance(a, dict) and a.get("code")]
    alertas = L.digitization_alerts(summary)
    supr = {k for a in alertas for k in a["suprimir"]}
    if any(a["code"] == "ecg.digitization_suspect" for a in achados):
        supr |= {"PR", "QRS", "ST"}
    mapa = {"PR": P.PREEXC + ("ecg.wpw", "ecg.av_block_"), "QRS": P.BBB + P.PREEXC + ("ecg.wpw",),
            "QT": P.QTF, "ST": P.STFIND}
    achados = [a for a in achados if not any(_tem(a["code"], mapa[k]) for k in supr if k in mapa)]
    return _Ctx(g=summary.get("medidas_globais") or {},
                leads=[m for m in summary.get("medidas_por_derivacao") or [] if isinstance(m, dict)],
                achados=achados, idx=summary.get("indices_calculados") or {}, supr=frozenset(supr),
                alertas=alertas, paced=any(a["code"] == "ecg.paced_rhythm" for a in achados),
                st_na=any(a["code"] == _ST_NA for a in achados))


# ------------------------------------------------------------------ seções (cada uma devolve frases)
def _ritmo(c: _Ctx) -> list[str]:
    hr = c.m("heart_rate_bpm")
    fc = f"frequência cardíaca de {_n(hr)} bpm" if hr is not None else "frequência cardíaca não avaliada (medida ausente)"
    rit = c.f(_RITMO)
    if rit:
        s = f"Quanto ao ritmo, as regras automáticas acionaram {_juntar([_lc(a['label']) for a in rit])}, com {fc}."
    elif c.g.get("rhythm"):
        s = f"Quanto ao ritmo, a classificação automática o descreveu como {str(c.g['rhythm']).strip()}, com {fc}."
    else:
        s = ("O ritmo não foi avaliado, pois nenhuma regra de ritmo foi acionada e não há classificação do ritmo, e a "
             + (f"frequência cardíaca foi de {_n(hr)} bpm." if hr is not None else "frequência cardíaca não foi avaliada (medida ausente)."))
    rr, sd = c.m("rr_mean_ms"), c.m("rr_sd_ms")
    medidas = (f"O intervalo RR médio foi de {_n(rr)} ms" + (f", com desvio-padrão de {_n(sd)} ms" if sd is not None else "")
               if rr is not None else "")
    if any(_tem(a["code"], _IRREGULAR) for a in c.achados):
        reg = (medidas + ", e o RR é irregular segundo a regra acionada." if medidas else
               "O RR é irregular segundo a regra acionada.")
    elif medidas:
        reg = medidas + (", sem regra automática de ritmo irregular acionada." if rit else ".")
    else:
        reg = "A regularidade do ritmo não foi avaliada por falta de medida do intervalo RR."
    return [s, reg]


def _p_pr(c: _Ctx) -> str:
    pd, pa = c.m("p_duration_ms"), c.m("p_axis_deg")
    p = [x for x in (f"duração de {_n(pd)} ms" if pd is not None else "",
                     f"eixo de {_n(pa)} graus" if pa is not None else "") if x]
    onda = f"a onda P teve {' e '.join(p)}" if p else "a onda P não foi avaliada (sem medida de duração ou de eixo)"
    fa = next((a for a in c.achados if a["code"] in ("ecg.atrial_fibrillation", "ecg.no_p_wave")), None)
    ev = next((e for e in (fa or {}).get("evidence") or [] if re.search(r"ondas? P", str(e))), None)
    if ev:
        onda += f" (regra: {str(ev).strip().rstrip('.')})"
    pr = c.m("pr_ms")
    if "PR" in c.supr:
        ipr = "o intervalo PR não foi descrito por divergência com o valor impresso"
    elif pr is not None:
        ipr = f"o intervalo PR foi de {_n(pr)} ms"
    else:
        ipr = "o intervalo PR não avaliado (medida ausente ou não aplicável ao ritmo)"
    return f"Em relação à onda P e ao intervalo PR, {onda}, e {ipr}."


def _eixos(c: _Ctx) -> str:
    q, t = c.m("qrs_axis_deg"), c.m("t_axis_deg")
    p = [x for x in (f"o eixo do QRS foi de {_n(q)} graus" if q is not None else "",
                     f"o eixo de T foi de {_n(t)} graus" if t is not None else "") if x]
    if not p:
        return "Os eixos do QRS e de T não foram avaliados (sem medida)."
    ach = c.f(_EIXO)
    tail = (f", e as regras automáticas acionaram {_juntar([_lc(a['label']) for a in ach])}" if ach else
            (", sem regra automática de desvio de eixo acionada" if q is not None else ""))
    return f"Quanto aos eixos, {' e '.join(p)}{tail}."


def _indices(c: _Ctx) -> str:
    i, p = c.idx, []
    for chave, nome, lim in (("sokolow_lyon_mm", "Sokolow-Lyon", "sokolow_lyon_limite_mm"),
                             ("cornell_mm", "Cornell", "cornell_limite_mm"),
                             ("peguero_lo_presti_mm", "Peguero-Lo Presti", "peguero_limite_mm")):
        v, lm = _num(i.get(chave)), _num(i.get(lim))
        if v is not None:
            p.append(f"{nome} de {_n(v)} mm" + (f" (limite de {_n(lm)} mm)" if lm is not None else ""))
    return f"os índices de voltagem foram {_juntar(p)}" if p else "a voltagem não foi avaliada por índices (medidas de R e S insuficientes)"


def _qrs(c: _Ctx) -> list[str]:
    q = c.m("qrs_ms")
    dur = (f"a duração foi de {_n(q)} ms" if q is not None and "QRS" not in c.supr else
           "a duração não foi descrita por divergência com o valor impresso" if "QRS" in c.supr else
           "a duração não foi avaliada (medida ausente)")
    out = [f"No complexo QRS, {dur}, e {_indices(c)}."]
    vol = c.f(_VOLT)
    if vol:
        out.append(f"As regras automáticas acionaram {_juntar([_com_evid(a) for a in vol])}.")
    qs = c.f(_Q)
    if qs:
        out.append(f"Quanto às ondas Q, as regras automáticas acionaram {_juntar([_com_evid(a) for a in qs])}.")
    elif any(_num(m.get("q_amplitude_mv")) is not None for m in c.leads) and _st_ok(c):
        out.append("Quanto às ondas Q, as regras automáticas não identificaram onda Q patológica.")
    else:
        out.append("As ondas Q não foram avaliadas de forma confiável (sem medida de Q ou padrão não interpretável).")
    tr = str(c.g.get("precordial_transition") or "").strip()
    out.append(f"Quanto à progressão da onda R nas precordiais, a transição precordial {'em ' + tr if tr[:1] == 'V' else tr}."
               if tr else "A progressão da onda R nas precordiais não foi avaliada (sem medida de transição precordial).")
    return out


def _st_ok(c: _Ctx) -> bool:
    return not c.st_na and "ST" not in c.supr and not c.paced


def _stt(c: _Ctx) -> list[str]:
    if c.st_na:
        why = next((a for a in c.achados if a["code"] == _ST_NA), {})
        out = ["O segmento ST e a onda T não foram avaliados de forma confiável com este padrão, e a avaliação médica é obrigatória."]
        if _evid(why):
            out.append(f"O motivo registrado pelas regras foi {_evid(why)}.")
        return out
    if "ST" in c.supr:
        return ["O segmento ST e a onda T não foram descritos por divergência de digitalização."]
    ach = c.f(_STT)
    if ach:
        return [("No segmento ST e na onda T, " if i == 0 else "") + f"as regras automáticas acionaram {_com_evid(a)}."
                for i, a in enumerate(ach)]
    if any(_num(m.get("st_j_mv")) is not None or _num(m.get("st_j60_mv")) is not None for m in c.leads) and _st_ok(c):
        return ["No segmento ST e na onda T, o ST foi medido nas derivações disponíveis e as regras automáticas "
                "não identificaram alterações de ST/T, o que não exclui isquemia nem infarto."]
    return ["O segmento ST e a onda T não foram avaliados por falta de medida do ST."]


def _qt(c: _Ctx) -> str:
    if "QT" in c.supr:
        return "O intervalo QT e o QTc não foram descritos por divergência com o valor impresso."
    qt = c.m("qt_ms")
    qtcs = [f"{_n(v)} ms pela fórmula de {nome}" for k, nome in _QTC if (v := c.m(k)) is not None]
    if qt is None and not qtcs:
        return "O intervalo QT e o QTc não foram avaliados (medida ausente)."
    p = ([f"o QT foi de {_n(qt)} ms"] if qt is not None else []) + ([f"o QTc foi de {_juntar(qtcs)}"] if qtcs else [])
    ach = c.f(_QT)
    tail = (f", e as regras automáticas acionaram {_juntar([_lc(a['label']) for a in ach])}" if ach else
            (", sem regra automática de QT longo ou curto acionada" if qtcs else ""))
    return f"Quanto ao intervalo QT, {' e '.join(p)}{tail}."


def _camaras(c: _Ctx) -> str:
    ach = c.f(_CAMARAS)
    if ach:
        return f"Quanto à sobrecarga de câmaras, as regras automáticas acionaram {_juntar([_lc(a['label']) for a in ach])}."
    if c.m("p_duration_ms") is not None or c.idx or any(_num(m.get("r_amplitude_mv")) is not None for m in c.leads):
        return "Quanto à sobrecarga de câmaras, nenhuma regra automática de sobrecarga atrial ou ventricular foi acionada."
    return "A sobrecarga de câmaras não foi avaliada por falta de medidas."


def _conducao(c: _Ctx) -> list[str]:
    av, bb = c.f(_AV), c.f(_BBB)
    out: list[str] = []
    if av or bb:
        out.append(f"Quanto à condução, as regras automáticas acionaram {_juntar([_lc(a['label']) for a in av + bb])}.")
    if any(a["code"] == "ecg.qrs_borderline" for a in bb):
        out.append("Para esse QRS limítrofe, as regras automáticas não identificaram critérios de bloqueio de ramo "
                   "esquerdo nem direito.")
    av_ok = c.m("pr_ms") is not None and "PR" not in c.supr and not c.st_na
    bb_ok = c.m("qrs_ms") is not None and "QRS" not in c.supr and not c.paced and not c.st_na
    if not av:
        out.append("Quanto à condução, as regras automáticas não identificaram bloqueio atrioventricular nem pré-excitação."
                   if av_ok else "A condução atrioventricular não foi avaliada (sem medida confiável do PR).")
    if not bb:
        out.append("No QRS, as regras automáticas também não identificaram bloqueio de ramo esquerdo nem direito."
                   if bb_ok else "A condução intraventricular não foi avaliada (sem medida confiável do QRS, ou padrão não interpretável).")
    return out


def _qualidade(c: _Ctx, summary: dict) -> list[str]:
    fonte = str(summary.get("fonte") or "").lower()
    origem = "imagem digitalizada" if fonte in ("image", "photo", "digitized", "digitalizado") else (
        f"sinal de origem {fonte}" if fonte else "sinal de origem não informada")
    fs, dur = _num(summary.get("fs_hz")), _num(summary.get("duracao_s"))
    cal = summary.get("calibracao") if isinstance(summary.get("calibracao"), dict) else {}
    gan, vel = _num(cal.get("gain_mm_mv")), _num(cal.get("paper_speed_mm_s"))
    det = [x for x in (f"taxa de amostragem de {_n(fs)} Hz" if fs else "", f"duração de {_n(dur)} s" if dur else "",
                       f"calibração de {_n(gan)} mm/mV e {_n(vel)} mm/s" if gan and vel else "") if x]
    out = [f"Do ponto de vista técnico, o traçado foi analisado a partir de {origem}" + (f", com {_juntar(det)}" if det else "") + "."]
    medidos = {m.get("lead") for m in c.leads}
    if not c.leads:
        out.append("Não há medidas por derivação disponíveis.")
    elif ausentes := [d for d in _DERIV if d not in medidos]:
        out.append(f"Não houve medida nas derivações {_juntar(ausentes)}.")
    ruins = sorted(k for k, v in (summary.get("qualidade_por_derivacao") or {}).items()
                   if _num(v) is not None and float(v) < _QUAL_MIN)
    if ruins:
        out.append(f"A qualidade do sinal foi baixa nas derivações {_juntar(ruins)}.")
    out += [f"Como aviso do processamento, {_lc(str(w))}." for w in (summary.get("avisos") or []) if _AVISO_OK.match(str(w))][:3]
    for a in c.alertas:
        if a.get("algoritmo") is not None:
            out.append(f"A medida de {a['medida']} do algoritmo ({_n(a['algoritmo'])} ms) diverge do valor impresso no "
                       f"aparelho ({_n(a['impresso'])} ms), então os achados dependentes dessa medida não foram descritos.")
        else:
            out.append(f"A digitalização é suspeita ({str(a.get('motivo', 'sem detalhe')).strip().rstrip('.')}), então os "
                       "achados dependentes de intervalos e de ST não foram descritos.")
    tec = c.f(_TEC)
    if tec:
        out.append(f"As regras automáticas acionaram {_juntar([_lc(a['label']) for a in tec])}.")
    out.append("Entre as limitações, não houve ECG anterior para comparação, e esta descrição depende da qualidade da "
               "aquisição e da digitalização, não substituindo a leitura médica do traçado original.")
    return out


def _impressao(c: _Ctx) -> str:
    vis = [a for a in c.achados if a["code"] not in (_ST_NA, _NORMAL) and a["code"].startswith("ecg.")]
    anorm = [_lc(a["label"]) for a in vis if a["severity"] in ("abnormal", "critical")]
    lim = [_lc(a["label"]) for a in vis if a["severity"] == "borderline"]
    normal = any(a["code"] == _NORMAL for a in c.achados)
    tec = bool(c.alertas) or c.st_na or any(_tem(a["code"], _TEC) for a in c.achados)
    st = " e o ST e a onda T não puderam ser interpretados por este padrão" if c.st_na else ""
    if anorm:
        return (f"Impressão: pelas regras automáticas, o traçado apresenta {_juntar(anorm)}"
                + (f", com as observações limítrofes de {_juntar(lim)}" if lim else "") + st + ".")
    if normal and not tec:
        return ("Impressão: pelas regras automáticas, o traçado está dentro dos limites da normalidade, o que não exclui "
                "IAM nem BAV nem outras alterações" + (f", com a observação limítrofe de {_juntar(lim)}" if lim else "") + ".")
    if lim:
        return f"Impressão: pelas regras automáticas, o traçado apresenta as observações limítrofes de {_juntar(lim)}{st}."
    if tec:
        return "Impressão: a interpretação automática ficou limitada pelas condições técnicas descritas, sem conclusão pelas regras automáticas."
    return ("Impressão: as regras automáticas não acionaram achados nem a regra de normalidade, de modo que não há "
            "como afirmar nada sem a leitura médica.")


def montar_deterministico(summary: dict) -> str:
    """Parágrafo único montado só de medidas, achados de regra e abstenções; sem IA."""
    c = _ctx(summary)
    frases = ["Esta descrição foi montada por regras automáticas, apenas a partir das medidas e dos achados do traçado.",
              *_ritmo(c), _p_pr(c), _eixos(c), *_qrs(c), *_stt(c), _qt(c), _camaras(c), *_conducao(c),
              *_qualidade(c, summary), _impressao(c)]
    return " ".join(" ".join(f.split()) for f in frases if f)


# ------------------------------------------------------------------ verificação
def _normalizar(texto: str) -> str:
    t = re.sub(r"(?m)^\s*(?:[-•*]|\d+[.)])\s+", "", str(texto))
    return " ".join(re.sub(r"[*#`]+", "", t).split())


def _verificar(texto: str, summary: dict) -> tuple[str, int]:
    """(parágrafo, frases removidas): sem lastro qualitativo ou com número fora dos fatos => removida."""
    manter, removidas = [], 0
    for fr in re.split(r"(?<=[.!?])\s+", _normalizar(texto)):
        if not fr.strip():
            continue
        if EC.sentence_problem(fr, summary) or L.unverified_numbers(fr, summary):
            removidas += 1
        else:
            manter.append(fr)
    final = " ".join(manter)
    if scan_text(final):
        raise ValueError("dado pessoal na descrição")
    return final, removidas


# ------------------------------------------------------------------ IA
def output_schema() -> dict:
    return {"type": "object", "properties": {"descricao": {"type": "string"}}, "required": ["descricao"],
            "additionalProperties": False}


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def facts_for_llm(summary: dict) -> dict:
    """Só fatos estruturados: sem cabeçalho impresso nem campos livres de contexto (LGPD)."""
    fatos = {k: v for k, v in summary.items() if k not in ("cabecalho_impresso", "contexto", "digitalizacao_suspeita")}
    if (summary.get("contexto") or {}).get("sexo"):
        fatos["sexo"] = summary["contexto"]["sexo"]
    return fatos


def user_message(summary: dict, base: str) -> str:
    return ("FATOS (JSON)\n" + json.dumps(facts_for_llm(summary), ensure_ascii=False, sort_keys=True)
            + "\n\nRASCUNHO DETERMINÍSTICO (já verificado; reescreva com mais coesão, sem acrescentar fatos)\n" + base)


def _redigir_ia(summary: dict, base: str, call: LLMCall) -> Optional[Descricao]:
    try:
        bruto = json.loads(call(system_prompt(), user_message(summary, base)))
        texto = bruto.get("descricao") if isinstance(bruto, dict) else None
        if not isinstance(texto, str) or not texto.strip():
            return None
        final, removidas = _verificar(texto, summary)
        if final and not any(f.lower().startswith("impressão") for f in re.split(r"(?<=[.!?])\s+", final)):
            imp, _ = _verificar(_impressao(_ctx(summary)), summary)   # fecha com a impressão determinística verificada
            final = f"{final} {imp}".strip()
    except Exception as e:   # recusa, truncamento, PHI bloqueado, JSON, rede, barreira: cai no determinístico
        log.warning("descrição por IA descartada (%s)", type(e).__name__)
        return None
    return Descricao(final, ORIGEM_IA, removidas) if final else None


def compor_descricao(summary: dict, call: Optional[LLMCall] = None) -> Descricao:
    """IA (se `call`) verificada; senão ou se falhar, base determinística; se a barreira falhar, descarta."""
    try:
        base = montar_deterministico(summary)
        if call is not None:
            ia = _redigir_ia(summary, base, call)
            if ia is not None:
                return ia
        final, removidas = _verificar(base, summary)
        return Descricao(final, ORIGEM_DET, removidas) if final else Descricao("", "", removidas, (FALHA_BARREIRA,))
    except Exception as e:   # falha FECHADA: nada sai sem verificação
        log.error("barreira da descrição completa falhou (%s)", type(e).__name__)
        return Descricao("", "", 0, (FALHA_BARREIRA,))
