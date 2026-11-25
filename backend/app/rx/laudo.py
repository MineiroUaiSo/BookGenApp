"""Laudo determinístico de RX de tórax (`rx_laudo/v1`, spec RX-LAUDO-CONFIAVEL §2). Sem IA: cada frase nasce de um fato da
ficha (`rx_ficha/v1`) ou de uma região sem fato ("não avaliado nesta análise automática"). Nunca diz normal/livre/afasta."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import fontes as FT
from . import lexico as LX
from .ficha import REGIOES, Ficha, Nivel, build_ficha
from .findings import PATHO_PT
from ..schemas import RXAnalysis

VERSAO = "rx_laudo/v1"
TITULOS = {"identificacao_tecnica": "Identificação e técnica", "qualidade": "Qualidade técnica e limitações",
           "achados": "Achados por região", "sinais_modelo": "Sinais do modelo auxiliar",
           "impressao": "Impressão", "recomendacoes": "Recomendações", "revisao_medica": "Revisão médica"}
NOMES = {"pleura": "Pleura", "pulmoes": "Pulmões", "mediastino_hilos": "Mediastino e hilos",
         "coracao_vasos": "Coração e vasos", "diafragma": "Diafragma", "ossos_partes_moles": "Ossos e partes moles",
         "dispositivos": "Dispositivos"}
# o que continua não avaliado quando a região foi medida só em parte
_RESTO = {"coracao_vasos": "contorno cardíaco e vasos não avaliados", "pulmoes": "opacidades, nódulos e padrão "
          "intersticial não avaliados", "mediastino_hilos": "hilos não avaliados",
          "diafragma": "ar livre subdiafragmático não avaliado"}
CRITICO = ("Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: "
           "revisar a imagem.")
_LIMIAR_LOCAL = "acima do limiar local (heurística local, sem fonte primária; correlacionar)"
_ROTULO = {"mediastino_largura_mm": "Largura do mediastino", "mediastino_largura_pct": "Largura do mediastino",
           "traqueia_desvio_pct": "Desvio traqueal", "cupulas_diferenca_pct": "Diferença de altura das cúpulas",
           "pulmoes_razao_area_E_D": "Razão de área pulmonar E/D", "ict": "Silhueta cardíaca"}
_ORDEM_IMPRESSAO = ("ict", "mediastino_largura_pct", "mediastino_largura_mm", "traqueia_desvio_pct",
                    "cupulas_diferenca_pct", "pulmoes_razao_area_E_D")
_PATOLOGIA_DE = {"modelo." + k.lower().replace(" ", "_"): v for k, v in PATHO_PT.items()}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Frase(_Frozen):
    secao: str
    texto: str
    fatos: tuple[str, ...] = ()
    fontes: tuple[str, ...] = ()
    nivel: Nivel


class Secao(_Frozen):
    id: str
    titulo: str
    frases: tuple[Frase, ...]


class LaudoRX(_Frozen):
    versao: str = VERSAO
    status: str = "rascunho"
    secoes: tuple[Secao, ...]


def _n(v: float, nd: int = 2) -> str:
    return f"{v:.{nd}f}".replace(".", ",")


def _sinal(v: float) -> str:
    return f"{v:+.1f}".replace(".", ",")


def _fr(secao: str, texto: str, nivel: Nivel, fatos=(), fontes=()) -> Frase:
    assert not LX.problemas(texto, nivel), (texto, LX.problemas(texto, nivel))   # tabela única de léxico
    FT.citar(fontes)
    return Frase(secao=secao, texto=texto, nivel=nivel, fatos=tuple(fatos), fontes=tuple(fontes))


def _ident(a: RXAnalysis, f: Ficha) -> list[Frase]:
    ids = [x.id for x in f.fatos if x.chave == "incidencia"]
    inc = ", ".join(sorted(set(f.incidencias))) or "não informada"
    return [_fr("identificacao_tecnica", f"Incidência(s): {inc}.", Nivel.QUALIDADE, ids, ("S1",) if ids else ()),
            _fr("identificacao_tecnica", f"Número de imagens: {len(a.images)}.", Nivel.QUALIDADE)]


_QUAL = {
    "rotacao": ("Rotação", "mediastino, traqueia e silhueta cardíaca"),
    "inspiracao": ("Inspiração", "volumes pulmonares e cúpulas"),
    "penetracao": ("Penetração", "parênquima e estruturas retrocardíacas"),
}


def _qualidade(f: Ficha) -> list[Frase]:
    out: list[Frase] = []
    for x in f.fatos:
        if x.chave not in _QUAL:
            continue
        nome, alvo = _QUAL[x.chave]
        if x.valor == "adequada":
            t = f"{nome}: estimativa automática adequada."
        elif x.valor == "possivelmente_inadequada":
            t = f"{nome} possivelmente inadequada (estimativa automática): limita a avaliação de {alvo}."
        else:
            t = f"{nome} indeterminada (estimativa automática): limita a avaliação de {alvo}."
        out.append(_fr("qualidade", t, Nivel.QUALIDADE, [x.id], x.fontes))
    if not out:
        out.append(_fr("qualidade", "Qualidade técnica: não avaliada (sem imagem de tórax analisável).",
                       Nivel.NAO_AVALIADO))
    return out


def _frase_fato(x) -> tuple[str, Nivel]:
    """Texto e nível da frase de uma medida da ficha."""
    rotulo = _ROTULO.get(x.chave, x.chave)
    if x.nivel == Nivel.NAO_AVALIADO:
        if x.chave == "ict":
            return "Silhueta cardíaca não medida com confiança (segmentação de baixa confiabilidade).", Nivel.NAO_AVALIADO
        return f"{rotulo} não medido com confiança (segmentação de baixa confiabilidade).", Nivel.NAO_AVALIADO
    v, regra = float(x.valor), x.nivel == Nivel.REGRA
    if x.chave == "ict":
        if any("magnifica" in r for r in x.ressalvas):
            return (f"ICT {_n(v)} em AP: a incidência magnifica o coração; não usar para afirmar cardiomegalia.",
                    Nivel.REGRA)
        if regra:
            return (f"Índice cardiotorácico medido {_n(v)}, acima de 0,50: sugere aumento da silhueta cardíaca "
                    "(critério de acurácia limitada; correlacionar).", Nivel.REGRA)
        return f"Índice cardiotorácico medido {_n(v)} (limite clássico 0,50 em PA).", Nivel.MEDIDO
    base = {
        "mediastino_largura_pct": f"Largura do mediastino medida {_n(v, 0)}% da largura torácica",
        "mediastino_largura_mm": f"Largura do mediastino medida {_n(v, 0)} mm",
        "traqueia_desvio_pct": f"Desvio traqueal medido {_sinal(v)}% da largura torácica",
        "cupulas_diferenca_pct": f"Diferença de altura das cúpulas medida {_sinal(v)}% da altura pulmonar",
        "pulmoes_razao_area_E_D": f"Razão de área pulmonar E/D medida {_n(v)}",
    }[x.chave]
    if regra:
        return f"{base}, {_LIMIAR_LOCAL}.", Nivel.REGRA
    return f"{base}.", Nivel.MEDIDO


def _achados(f: Ficha) -> list[Frase]:
    out: list[Frase] = []
    for c in f.cobertura:
        nome = NOMES[c.regiao]
        if c.avaliada:
            out.append(_fr("achados", f"{nome}: {_RESTO.get(c.regiao, 'parte da região não avaliada')} nesta análise "
                           "automática.", Nivel.NAO_AVALIADO, c.fatos))
        else:
            out.append(_fr("achados", f"{nome}: não avaliado nesta análise automática.", Nivel.NAO_AVALIADO, c.fatos))
        for x in (y for y in f.fatos if y.regiao == c.regiao and y.chave in _ROTULO):
            t, n = _frase_fato(x)
            out.append(_fr("achados", t, n, [x.id], x.fontes))
    return out


def _sinais(f: Ficha) -> list[Frase]:
    out = [_fr("sinais_modelo", "Caixa separada: escore de modelo auxiliar, fora da Impressão; não confirma nem afasta "
               "achados.", Nivel.SUGERIDO_MODELO, (), ("S5",))]
    for x in f.fatos:
        if x.nivel != Nivel.SUGERIDO_MODELO:
            continue
        nome = _PATOLOGIA_DE.get(x.chave, x.chave)
        if x.zona == "sugestivo":
            p = (f"probabilidade calibrada ≈ {_n(float(x.valor))}" if x.valor is not None
                 else "escore bruto, sem calibração")
            t = f"Modelo auxiliar: possível {nome} ({p}); escore de modelo; não confirma nem afasta."
        else:
            t = f"Modelo auxiliar: indeterminado para {nome}; não permite afirmar nem afastar."
        out.append(_fr("sinais_modelo", t, Nivel.SUGERIDO_MODELO, [x.id], x.fontes))
    return out


def _impressao(f: Ficha) -> list[Frase]:
    regras = sorted((x for x in f.fatos if x.nivel == Nivel.REGRA and x.chave in _ORDEM_IMPRESSAO),
                    key=lambda x: _ORDEM_IMPRESSAO.index(x.chave))
    out = []
    for x in regras:
        t, n = _frase_fato(x)
        out.append(_fr("impressao", t, n, [x.id], x.fontes))
    if not out:
        out.append(_fr("impressao", "Nenhum critério automático atingido nas medidas feitas; regiões não avaliadas "
                       "listadas em Achados.", Nivel.NAO_AVALIADO))
    out.append(_fr("impressao", CRITICO, Nivel.NAO_AVALIADO))
    return out


def _recomendacoes(f: Ficha) -> list[Frase]:
    out = [_fr("recomendacoes", "Correlacionar com a clínica.", Nivel.QUALIDADE, (), ("S2",))]
    if any("AP" == i for i in f.incidencias):
        out.append(_fr("recomendacoes", "Se a dúvida persistir, considerar incidência em perfil ou PA.",
                       Nivel.QUALIDADE, (), ("S1",)))
    if any(x.valor == "possivelmente_inadequada" for x in f.fatos):
        out.append(_fr("recomendacoes", "As limitações técnicas listadas podem justificar nova radiografia, a "
                       "critério do médico.", Nivel.QUALIDADE, (), ("S1",)))
    return out


def _revisao() -> list[Frase]:
    return [
        _fr("revisao_medica", "Rascunho gerado por análise automática; exige revisão médica e assinatura antes de "
            "qualquer uso. Status: rascunho.", Nivel.QUALIDADE, (), ("S2",)),
        _fr("revisao_medica", "Nota de IA: este texto usa análise computacional; a decisão final é do médico, sem "
            "aprovação automática de laudos.", Nivel.QUALIDADE, (), ("S8",)),
        _fr("revisao_medica", "Campos do médico: concordância por seção, comentário aberto para regiões não avaliadas e "
            "registro de comunicação não rotineira (somente local).", Nivel.QUALIDADE, (), ("S2",)),
    ]


def build_laudo(a: RXAnalysis) -> LaudoRX:
    f = build_ficha(a)
    aviso = []
    if f.fora_de_escopo:
        aviso = [_fr("identificacao_tecnica", "Imagem fora do escopo desta análise (radiografia de tórax adulto): "
                     f"{f.motivo_fora_de_escopo}.", Nivel.NAO_AVALIADO)]
    blocos = {"identificacao_tecnica": _ident(a, f) + aviso, "qualidade": _qualidade(f), "achados": _achados(f),
              "sinais_modelo": _sinais(f), "impressao": _impressao(f), "recomendacoes": _recomendacoes(f),
              "revisao_medica": _revisao()}
    return LaudoRX(secoes=tuple(Secao(id=i, titulo=TITULOS[i], frases=tuple(fr)) for i, fr in blocos.items()))


def render_markdown(l: LaudoRX) -> str:
    linhas = ["# Laudo de radiografia de tórax (rascunho para revisão médica)", ""]
    for s in l.secoes:
        linhas.append(f"## {s.titulo}")
        for fr in s.frases:
            fonte = f" ({', '.join(fr.fontes)})" if fr.fontes else ""
            pref = "> " if s.id == "sinais_modelo" else "- "
            linhas.append(f"{pref}{fr.texto}{fonte} _[{fr.nivel.value}]_")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"
