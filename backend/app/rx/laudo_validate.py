"""Contrato da IA do laudo RX (spec RX-LAUDO-CONFIAVEL §3, tarefa 8). A IA só REESCREVE frases a partir da ficha; todo
texto passa por este validador determinístico antes de ser exibido. Desligada por padrão (`MEDLENS_RX_LAUDO_IA=0`).

Regras por afirmação: (1) cita fato(s) existente(s) da ficha; (2) fontes verificadas; (3) números do texto = números dos
fatos citados; (4) léxico: grau de certeza <= nível do fato, sem termo proibido; (5) lastro por tópico só dos fatos
CITADOS (claim_check); (6) afirmação qualitativa de achado exige grau ("sugere"/"possível"); (7) descritor visual só com
imagem enviada. Rejeição > 50% das afirmações, ou qualquer rejeição na Impressão, vira abstenção."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import claim_check as CC
from . import fontes as FT
from . import lexico as LX
from .ficha import Ficha, Fato, Nivel
from .findings import PATHO_PT
from .laudo import NOMES

LIMITE_ABSTENCAO = 0.5
_PROMPT = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "rx_laudo_v1.md")
_CHAVE_MEDIDA = {"ict": "cardiothoracic_ratio", "mediastino_largura_pct": "mediastinal_width_ratio",
                 "mediastino_largura_mm": "mediastinal_width", "traqueia_desvio_pct": "tracheal_deviation_pct",
                 "cupulas_diferenca_pct": "hemidiaphragm_height_difference_pct"}
_CHAVE_CODIGO = {"ict": "rx.cardiomegaly", "mediastino_largura_pct": "rx.mediastinal_widening",
                 "mediastino_largura_mm": "rx.mediastinal_widening", "traqueia_desvio_pct": "rx.tracheal_deviation",
                 "cupulas_diferenca_pct": "rx.hemidiaphragm_elevation"}
_PATOLOGIA = {"modelo." + k.lower().replace(" ", "_"): k for k in PATHO_PT}
_NUM = re.compile(r"(?<![\w.,])[+-]?\d+(?:[.,]\d+)?(?![\w.,]*[ºª°])")
_IDS_FONTE = re.compile(r"\b[SN]\d+\b")
_RESTO_ID = re.compile(r"\b[SNF]\d+\b")
_ROTULOS = {n.lower() for n in NOMES.values()} | {"modelo auxiliar"}
_ROTULO_ABST = re.compile(r"^\s*([^:.]{1,40}):\s*(.+)$", re.DOTALL)
_LISTA_TOPICOS = re.compile(r"^[^.:;]{0,120}$")
_GRAU = re.compile(r"\bsuger\w*|\bsugestiv\w+|\bposs[ií]ve(?:l|is)\b|\bpossivelmente\b", re.IGNORECASE)
_CONSTANTES = (0.50, 0.5)      # limite clássico do ICT citado nos moldes


@dataclass(frozen=True)
class Rejeicao:
    texto: str
    motivos: tuple[str, ...]


@dataclass(frozen=True)
class Resultado:
    aceitas: tuple[dict, ...] = ()
    rejeicoes: tuple[Rejeicao, ...] = ()
    abstencao: bool = False
    aviso: str = ""


def ia_habilitada() -> bool:
    return os.environ.get("MEDLENS_RX_LAUDO_IA", "0").strip().lower() in {"1", "true", "on", "sim"}


def _numeros(texto: str) -> list[float]:
    limpo = _RESTO_ID.sub(" ", texto)
    out = []
    for m in _NUM.finditer(limpo):
        try:
            out.append(abs(float(m.group(0).replace(",", ".").replace("+", ""))))
        except ValueError:
            pass
    return out


def _confere(n: float, validos: list[float]) -> bool:
    cand = list(validos) + list(_CONSTANTES)
    return any(abs(n - v) < 1e-9 or any(abs(n - round(v, d)) < 1e-9 for d in (0, 1, 2, 3)) for v in cand)


def _fatos_de(citados: list[Fato]) -> CC.Fatos:
    medidas: dict[str, float] = {}
    codigos, zonas, probs = [], {}, {}
    for f in citados:
        if f.chave in _CHAVE_MEDIDA and isinstance(f.valor, (int, float)):
            medidas[_CHAVE_MEDIDA[f.chave]] = float(f.valor)
        if f.nivel == Nivel.REGRA and f.chave in _CHAVE_CODIGO:
            codigos.append(_CHAVE_CODIGO[f.chave])
        patologia = _PATOLOGIA.get(f.chave)
        if patologia and f.zona:
            zonas[patologia] = f.zona
            if isinstance(f.valor, (int, float)):
                probs[patologia] = float(f.valor)
    return CC.Fatos(medidas, tuple(codigos), zonas, probs)


def _abstencao(frase: str) -> bool:
    """Frase que só diz 'não avaliado/indeterminado', mesmo listando tópicos antes."""
    corpo = frase
    m = _ROTULO_ABST.match(frase)
    rotulo = bool(m and m.group(1).strip().lower() in _ROTULOS)
    if rotulo:
        corpo = m.group(2)
    a = CC._ABST.search(corpo)
    if not a or CC._NEG.search(corpo[:a.start()]):
        return False
    antes = corpo[:a.start()]
    if _GRAU.search(antes) or CC._VISUAL.search(antes) or CC._SIZE.search(antes) or re.search(r"\d", antes):
        return False
    return rotulo or bool(_LISTA_TOPICOS.match(antes) and len(antes.split()) <= 12)


def _afirma_topico_sem_grau(frase: str) -> bool:
    for cl in CC._SPLIT_CLAUSE.split(frase):
        for t in CC.TOPICOS:
            for m in t.achado.finditer(cl):
                if not CC._negada(cl, m):
                    return True
    return False


def _problemas(af: dict, ficha: Ficha, imagem: bool) -> list[str]:
    texto = str(af.get("texto") or "").strip()
    if not texto:
        return ["texto vazio"]
    ids = [str(i) for i in af.get("fatos") or []]
    por_id = {f.id: f for f in ficha.fatos}
    p: list[str] = []
    desconhecidos = [i for i in ids if i not in por_id]
    if desconhecidos:
        p.append("fato inexistente na ficha: " + ", ".join(desconhecidos))
    citados = [por_id[i] for i in ids if i in por_id]
    ver = FT.verificadas()
    citadas = [str(s) for s in af.get("fontes") or []] + _IDS_FONTE.findall(texto)
    ruins = sorted({s for s in citadas if s not in ver})
    if ruins:
        p.append("fonte inexistente ou não verificada: " + ", ".join(ruins))
    nums = _numeros(texto)
    validos = [float(f.valor) for f in citados if isinstance(f.valor, (int, float))]
    sem_lastro = [n for n in nums if not _confere(n, [abs(v) for v in validos])]
    if sem_lastro:
        p.append("número sem fato que o sustente: " + ", ".join(str(n) for n in sem_lastro))
    for niv in {f.nivel for f in citados} or {None}:
        if niv is None:
            ruim = LX.termos_proibidos(texto) or [g for g in LX.graus_usados(texto)
                                                   if g in {"sugere", "compativel_com", "possivel"}]
            p += [f"sem fato citado: {r}" for r in ruim]
        else:
            p += LX.problemas(texto, niv)
    if _abstencao(texto):
        return sorted(set(p))
    motivo = CC.problema_da_frase(texto, _fatos_de(citados), imagem=imagem)
    if motivo:
        p.append(motivo)
    if not nums and not _GRAU.search(texto) and _afirma_topico_sem_grau(texto):
        p.append("afirmação qualitativa sem grau de certeza ('sugere'/'possível')")
    return sorted(set(p))


def validar(afirmacoes: list[dict], ficha: Ficha, *, imagem_enviada: bool = False) -> Resultado:
    aceitas, rejeitadas = [], []
    for af in afirmacoes or []:
        motivos = _problemas(af if isinstance(af, dict) else {}, ficha, imagem_enviada)
        if motivos:
            rejeitadas.append((af, Rejeicao(str((af or {}).get("texto", "")) if isinstance(af, dict) else "",
                                            tuple(motivos))))
        else:
            aceitas.append(af)
    total = len(aceitas) + len(rejeitadas)
    na_impressao = any(isinstance(a, dict) and a.get("secao") == "impressao" for a, _ in rejeitadas)
    abst = bool(rejeitadas) and (na_impressao or len(rejeitadas) / total > LIMITE_ABSTENCAO)
    aviso = ""
    if abst:
        aviso = ("Texto da IA descartado pelo validador (afirmações sem lastro nos fatos); "
                 "vale o laudo determinístico.")
    return Resultado(tuple(aceitas), tuple(r for _, r in rejeitadas), abst, aviso)


def _contexto(ficha: Ficha) -> str:
    fatos = [{"id": f.id, "chave": f.chave, "valor": f.valor, "unidade": f.unidade, "nivel": f.nivel.value,
              "regiao": f.regiao, "zona": f.zona} for f in ficha.fatos]
    fontes = [{"id": i, "titulo": f.titulo} for i, f in sorted(FT.verificadas().items())]
    return json.dumps({"ficha": fatos, "fontes": fontes, "incidencias": ficha.incidencias},
                      ensure_ascii=False)


def reescrever(ficha: Ficha, cliente: Callable[[str, str], str], *, imagem_enviada: bool = False
               ) -> Optional[Resultado]:
    """Pede à IA a reescrita fluida e valida. `cliente(system, user) -> str` (JSON). None se a flag está desligada."""
    if not ia_habilitada():
        return None
    try:
        sistema = open(_PROMPT, encoding="utf-8").read()
    except OSError:
        sistema = "Reescreva as frases do laudo usando só os fatos fornecidos."
    try:
        bruto = json.loads(cliente(sistema, _contexto(ficha)))
        afs = bruto["afirmacoes"]
        assert isinstance(afs, list)
    except Exception:
        return Resultado((), (), True, "Resposta da IA inválida; vale o laudo determinístico.")
    return validar(afs, ficha, imagem_enviada=imagem_enviada)
