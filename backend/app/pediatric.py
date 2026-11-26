"""Modo pediátrico: converte uma análise de ECG/RX do MedLens no contrato de resposta pediátrico.

Regras (docs/PEDIATRIA-INTEGRACAO-PLANO.md §3):
  * nenhuma classificação diagnóstica adulta: sem achados, laudo, índices ou rótulos de normal/alterado;
  * ECG: só FC, RR, PR, QRS, QT, QTc (Bazett) e eixo do QRS, com unidade e flag de confiabilidade do sinal;
  * RX: só incidência, região e qualidade técnica; ICT, áreas e desvio traqueal nunca saem;
  * descrição técnica por template, com filtro de vocabulário (ValueError se um template gerar termo vetado).

O resultado é montado só a partir de campos estruturados da análise. Texto livre do motor (warnings, quality,
laudo, scope_reason) nunca é copiado para a resposta. Sem IA, sem rede, sem disco.
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable, Literal, Optional, Union

from app.schemas import BodyRegion, ECGAnalysis, RXAnalysis, RXImageAnalysis, RXView

IDADE_MAX_MESES = 215  # 17 anos e 11 meses: o serviço é pediátrico

VOCAB_VETADO = re.compile(
    r"\b(normal|anormal|aumentad|reduzid|prolongad|curto|hipertrofi|sobrecarga|cardiomegalia|bloqueio|"
    r"desvio do eixo|isquemi|infarto|pneumonia|derrame|consolida)", re.I)

AVISO_PEDIATRICO = (
    "Apoio técnico, não é laudo. Os valores de referência do ECG e do raio-X mudam com a idade da criança. "
    "Esta ferramenta mostra medidas e qualidade da imagem e não classifica o exame. Compare com uma tabela por "
    "faixa etária e confirme com o radiologista ou o cardiologista pediátrico.")
AVISO_ICT = ("Índice cardiotorácico não exibido: o limite de adulto não vale para criança e a medida automática "
             "desta versão não é confiável.")
AVISO_IDADE_AUSENTE = ("Idade não informada: a interpretação por faixa etária depende da idade da criança, "
                       "e nenhuma referência de adulto foi aplicada.")
AVISO_RX_QUALIDADE = ("Incidência, região e qualidade técnica são estimadas por método automático de baixa "
                      "confiança: confirme visualmente na imagem.")
AVISO_REFERENCIA_ECG = ("Referência de consulta para limites do ECG por idade: Rijnbeek PR et al., "
                        "Eur Heart J 2001;22:702-711 (PMID 11286528). Nenhum valor foi aplicado por esta ferramenta.")
NOTA_BAZETT = "Bazett superestima o QTc com FC alta, comum em lactentes; compare QT e RR"

NIVEL_GRADE_MIN = 0.5      # grid_confidence abaixo disso: escala de tempo e amplitude sob dúvida
QUALIDADE_LEAD_MIN = 0.5   # qualidade por derivação (0..1) para contar como legível
FRACAO_LEADS_MIN = 0.75    # menos que isso de derivações legíveis vira alerta

_REGIAO_PT = {BodyRegion.CHEST: "tórax", BodyRegion.ABDOMEN: "abdome", BodyRegion.EXTREMITY: "extremidade",
              BodyRegion.SPINE: "coluna", BodyRegion.SKULL: "crânio", BodyRegion.PELVIS: "pelve",
              BodyRegion.OTHER: "outra"}

# (campo de GlobalMeasurements, código, rótulo, unidade, casas decimais, depende de delineação das ondas)
_MEDIDAS_ECG = (
    ("heart_rate_bpm", "fc", "Frequência cardíaca", "bpm", 0, False),
    ("rr_mean_ms", "rr", "Intervalo RR médio", "ms", 0, False),
    ("pr_ms", "pr", "Intervalo PR", "ms", 0, True),
    ("qrs_ms", "qrs", "Duração do QRS", "ms", 0, True),
    ("qt_ms", "qt", "Intervalo QT", "ms", 0, True),
    ("qtc_bazett_ms", "qtc_bazett", "QTc (Bazett)", "ms", 0, True),
    ("qrs_axis_deg", "eixo_qrs", "Eixo do QRS", "graus", 0, True),
)
_SO_RITMO = {"fc", "rr"}


def versao_motor() -> str:
    """Commit curto do deploy (VERCEL_GIT_COMMIT_SHA), senão MEDLENS_VERSION, senão a versão do pacote."""
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip()
    if sha:
        return sha[:7]
    return os.environ.get("MEDLENS_VERSION", "").strip() or "0.1.0"


def checar_vocabulario(textos: Iterable[str]) -> None:
    """ValueError se algum texto contiver termo de classificação (normal, anormal, prolongado, hipertrofia...)."""
    for t in textos:
        m = VOCAB_VETADO.search(t)
        if m:
            raise ValueError(f"termo vetado no modo pediátrico: {m.group(0)!r}")


def _q(codigo: str, texto: str, nivel: str = "info") -> dict[str, str]:
    return {"codigo": codigo, "texto": texto, "nivel": nivel}


def _num(v: Optional[float], casas: int) -> Optional[Union[int, float]]:
    if v is None:
        return None
    return int(round(v)) if casas == 0 else round(float(v), casas)


# ------------------------------------------------------------------ ECG
def _ecg_contexto(a: ECGAnalysis) -> dict[str, Any]:
    cal = a.signal.calibration or {}
    quals = list((a.signal.quality or {}).values())
    n_total = len(a.signal.leads)
    n_ok = sum(1 for q in quals if q >= QUALIDADE_LEAD_MIN) if quals else n_total
    grade = cal.get("grid_confidence")
    avisos_txt = " ".join(a.warnings).lower()
    return {
        "rhythm_only": bool(cal.get("rhythm_only")),
        "n_total": n_total, "n_ok": n_ok,
        "grade": grade,
        "ruido": "ruído elevado" in avisos_txt,
        "ganho": cal.get("gain_mm_mv"), "velocidade": cal.get("paper_speed_mm_s"),
    }


def _ecg_medidas(a: ECGAnalysis, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    gm = a.global_measurements
    sinal_ok = (not ctx["rhythm_only"] and ctx["n_total"] > 0 and ctx["n_ok"] >= ctx["n_total"] * FRACAO_LEADS_MIN
                and (ctx["grade"] is None or ctx["grade"] >= NIVEL_GRADE_MIN))
    out: list[dict[str, Any]] = []
    for campo, codigo, rotulo, unidade, casas, depende_ondas in _MEDIDAS_ECG:
        v = getattr(gm, campo)
        if v is None or (ctx["rhythm_only"] and codigo not in _SO_RITMO):
            continue
        m: dict[str, Any] = {"codigo": codigo, "rotulo": rotulo, "valor": _num(v, casas), "unidade": unidade,
                             "confiavel": bool(sinal_ok and not (depende_ondas and ctx["ruido"]))}
        if codigo == "qtc_bazett":
            m["nota"] = NOTA_BAZETT
        out.append(m)
    return out


def _ecg_qualidade(medidas: list[dict[str, Any]], ctx: dict[str, Any]) -> list[dict[str, str]]:
    q: list[dict[str, str]] = []
    if ctx["n_total"]:
        ok = ctx["n_ok"] >= ctx["n_total"] * FRACAO_LEADS_MIN
        q.append(_q("derivacoes", f"{ctx['n_ok']} de {ctx['n_total']} derivações legíveis", "info" if ok else "alerta"))
    if ctx["ganho"] and ctx["velocidade"]:
        q.append(_q("calibracao", f"Calibração utilizada: {ctx['ganho']:g} mm/mV e {ctx['velocidade']:g} mm/s"))
    if ctx["grade"] is not None:
        if ctx["grade"] >= NIVEL_GRADE_MIN:
            q.append(_q("grade", "Grade do papel reconhecida na imagem"))
        else:
            q.append(_q("grade", "Pouca confiança na grade do papel: escalas de tempo e amplitude podem estar "
                                 "imprecisas", "alerta"))
    if ctx["ruido"]:
        q.append(_q("ruido", "Ruído elevado no traçado: a delimitação das ondas pode ser imprecisa", "alerta"))
    if ctx["rhythm_only"]:
        q.append(_q("digitalizacao_reduzida", "Foto com grade irregular ou distorcida: só FC e RR informados; "
                                              "refaça a foto com a folha plana e de frente", "alerta"))
    if not medidas:
        q.append(_q("sem_medidas", "Nenhuma medida pôde ser obtida com segurança desta imagem", "alerta"))
    return q


def _fmt_ecg_descricao(medidas: list[dict[str, Any]], qualidade: list[dict[str, str]]) -> str:
    by = {m["codigo"]: m["valor"] for m in medidas}
    partes: list[str] = []
    if "fc" in by:
        partes.append(f"FC {by['fc']} bpm")
    if "rr" in by:
        partes.append(f"RR {by['rr']} ms")
    for cod, rot in (("pr", "PR"), ("qrs", "QRS"), ("qt", "QT")):
        if cod in by:
            partes.append(f"{rot} {by[cod]} ms")
    if "qtc_bazett" in by:
        partes.append(f"QTc (Bazett) {by['qtc_bazett']} ms")
    if "eixo_qrs" in by:
        partes.append(f"eixo do QRS {by['eixo_qrs']:+d}°")
    txt = "ECG digitalizado de imagem. "
    txt += ("; ".join(partes) + ". ") if partes else "Nenhuma medida obtida com segurança. "
    qs = [q["texto"] for q in qualidade if q["codigo"] in ("derivacoes", "calibracao")]
    if qs:
        txt += "Qualidade: " + "; ".join(t[0].lower() + t[1:] for t in qs) + ". "
    duvidosas = [m["codigo"].upper().replace("_BAZETT", "") for m in medidas if not m["confiavel"]]
    if duvidosas:
        txt += "Medidas com baixa confiança do sinal: " + ", ".join(duvidosas) + "."
    return txt.strip()


# ------------------------------------------------------------------ RX
def _rx_img(a: RXAnalysis) -> RXImageAnalysis:
    if not a.images:
        raise ValueError("análise de RX sem imagem")
    return a.images[0]


def _grau(valor: str) -> str:
    v = valor.strip().lower()
    if v.startswith("adequad"):
        return "adequada"
    if v.startswith("possiv") or v.startswith("possív"):
        return "possivel_problema"
    return "indeterminada"


def _rx_qualidade(im: RXImageAnalysis) -> list[dict[str, str]]:
    q: list[dict[str, str]] = []
    if im.view == RXView.OTHER or im.out_of_scope or im.region_uncertain:
        q.append(_q("incidencia", "Incidência indeterminada", "alerta"))
    else:
        q.append(_q("incidencia", f"Incidência estimada: {im.view.value}"))
    if im.region_uncertain:
        q.append(_q("regiao_incerta", "Região do exame incerta: confirme a região na imagem", "alerta"))
    for chave, cod, rot, ruim in (("rotação", "rotacao", "Rotação", "possível rotação do tórax"),
                                  ("inspiração", "inspiracao", "Inspiração", "possivelmente insuficiente"),
                                  ("penetração", "exposicao", "Exposição", "possível erro de exposição")):
        if chave not in im.quality:
            continue
        g = _grau(im.quality[chave])
        if g == "adequada":
            q.append(_q(cod, f"{rot}: adequada pelo critério automático"))
        elif g == "possivel_problema":
            q.append(_q(cod, f"{rot}: {ruim} pelo critério automático", "alerta"))
        else:
            q.append(_q(cod, f"{rot}: indeterminada"))
    bt = (im.burned_text or im.quality.get("texto queimado") or "")
    if "NÃO mascarado" in bt:
        q.append(_q("texto_queimado", "Texto queimado detectado na imagem e não mascarado com segurança", "alerta"))
    elif "texto detectado" in bt:
        q.append(_q("texto_queimado", "Texto queimado detectado e mascarado antes da análise"))
    else:
        q.append(_q("texto_queimado", "Nenhum texto queimado detectado na imagem"))
    if im.out_of_scope:
        q.append(_q("escopo", "A imagem pode não ser do tipo esperado para esta análise: confirme o arquivo enviado",
                    "alerta"))
    return q


def _rx_descricao(im: RXImageAnalysis, regiao: str, incidencia: str, qualidade: list[dict[str, str]]) -> str:
    txt = f"Radiografia digitalizada de imagem. Incidência {incidencia}; região {regiao}. Qualidade técnica: "
    itens = [q["texto"][0].lower() + q["texto"][1:] for q in qualidade if q["codigo"] != "incidencia"]
    return txt + "; ".join(itens) + ". Nenhuma medida da imagem é exibida nesta versão."


# ------------------------------------------------------------------ API
def aplicar_modo_pediatrico(kind: Literal["ecg", "rx"], analise: Union[ECGAnalysis, RXAnalysis],
                            idade_meses: Optional[int], *, versao: Optional[str] = None) -> dict[str, Any]:
    """Contrato de resposta pediátrico (snake_case). idade_meses None (ausente) continua pediátrico."""
    if kind not in ("ecg", "rx"):
        raise ValueError(f"tipo de exame desconhecido: {kind!r}")
    if idade_meses is not None and not (0 <= idade_meses <= IDADE_MAX_MESES):
        raise ValueError("idade fora da faixa pediátrica (0 a 215 meses)")
    res: dict[str, Any] = {"tipo": kind, "modo": "pediatrico", "idade_meses": idade_meses}
    avisos = [AVISO_PEDIATRICO]
    if kind == "ecg":
        if not isinstance(analise, ECGAnalysis):
            raise ValueError("análise de ECG esperada")
        ctx = _ecg_contexto(analise)
        medidas = _ecg_medidas(analise, ctx)
        qualidade = _ecg_qualidade(medidas, ctx)
        descricao = _fmt_ecg_descricao(medidas, qualidade)
        avisos.append(AVISO_REFERENCIA_ECG)
    else:
        if not isinstance(analise, RXAnalysis):
            raise ValueError("análise de RX esperada")
        im = _rx_img(analise)
        # sem o modelo de segmentação (esta hospedagem) a região de uma incidência atípica (ex.: perfil) erra:
        # fora de escopo ou região incerta nunca afirmam incidência nem região
        duvida = im.out_of_scope or im.region_uncertain
        incidencia = "indeterminada" if duvida or im.view == RXView.OTHER else im.view.value
        regiao = "indeterminada" if duvida else _REGIAO_PT[im.region]
        res["incidencia"], res["regiao"] = incidencia, regiao
        medidas = []
        qualidade = _rx_qualidade(im)
        descricao = _rx_descricao(im, regiao, incidencia, qualidade)
        avisos += [AVISO_ICT, AVISO_RX_QUALIDADE]
    if idade_meses is None:
        avisos.append(AVISO_IDADE_AUSENTE)
    res.update(medidas=medidas, qualidade=qualidade, descricao_tecnica=descricao, avisos=avisos,
               versao_motor=versao or versao_motor())
    checar_vocabulario([res["descricao_tecnica"], *res["avisos"], *(q["texto"] for q in res["qualidade"])])
    return res
