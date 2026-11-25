"""Lastro SEMÂNTICO das afirmações do laudo v2.

Ids válidos não bastam: o achado (código de regra) ou a medida (chave) mencionados no TEXTO da afirmação têm de
coincidir com os de um fato [F] citado, que não seja "meta" nem "não avaliável". Negação ("não há", "sem sinais")
e "normal" global não podem contradizer regra ativa, e ausência de regra não exclui doença: negação só vale se
qualificada como resultado das regras automáticas. Puro Python, sem rede.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ecg.features import Ficha

_I = re.IGNORECASE


def _rx(p: str) -> re.Pattern:
    return re.compile(p, _I)


@dataclass(frozen=True)
class Topico:
    nome: str
    texto: re.Pattern                       # como aparece na afirmação
    codigos: Optional[re.Pattern] = None    # código de regra do fato que dá lastro
    chaves: Optional[re.Pattern] = None     # chave do fato (ou de suas medidas) que dá lastro
    fato_texto: Optional[re.Pattern] = None  # texto do fato (só medidas; ex.: ritmo sinusal)
    medida: bool = False                    # medida/índice: só é checada quando afirmada


_IDX = r"^indice\.(sokolow|cornell|peguero|r_avl|r_d1|romhilt)"
TOPICOS: tuple[Topico, ...] = (
    # ---- achados (códigos de regra)
    Topico("bloqueio de ramo esquerdo", _rx(r"bloqueio (?:completo )?de ramo esquerdo|\bBRE\b|\bLBBB\b"),
           _rx(r"^ecg\.i?lbbb")),
    Topico("bloqueio de ramo direito", _rx(r"bloqueio (?:completo )?de ramo direito|\bBRD\b|\bRBBB\b"),
           _rx(r"^ecg\.i?rbbb")),
    Topico("distúrbio de condução intraventricular", _rx(r"dist[uú]rbio (?:inespec[ií]fico )?de condu[cç][aã]o"
                                                         r"|\bIVCD\b"), _rx(r"^ecg\.ivcd")),
    Topico("hemibloqueio anterior esquerdo", _rx(r"hemibloqueio anterior|\bBDAS\b|\bHBAE\b"), _rx(r"^ecg\.lafb")),
    Topico("hemibloqueio posterior esquerdo", _rx(r"hemibloqueio posterior|\bBDPI\b|\bHBPE\b"), _rx(r"^ecg\.lpfb")),
    Topico("hipertrofia ventricular esquerda", _rx(r"hipertrofia ventricular esquerda|sobrecarga ventricular esquerda"
                                                    r"|\bHVE\b|miocardiopatia hipertr[oó]fica|\bCMH\b"),
           _rx(r"^ecg\.lvh"), _rx(_IDX)),
    Topico("hipertrofia ventricular direita", _rx(r"hipertrofia ventricular direita|sobrecarga ventricular direita"
                                                   r"|\bHVD\b"), _rx(r"^ecg\.rvh")),
    Topico("sobrecarga atrial esquerda", _rx(r"sobrecarga atrial esquerda|aumento atrial esquerdo|\bSAE\b"
                                              r"|\bHAE\b"), _rx(r"^ecg\.(lae|left_atrial)")),
    Topico("sobrecarga atrial direita", _rx(r"sobrecarga atrial direita|aumento atrial direito|\bSAD\b|P pulmonale"),
           _rx(r"^ecg\.(rae|right_atrial)")),
    Topico("supradesnivelamento de ST / infarto", _rx(r"supra\w*\s*(?:de\s*)?ST|supradesnivel\w*|eleva[cç][aã]o d[oe] "
                                                       r"(?:segmento )?ST|\bIAM(?:CSST)?\b|infarto|\bSTEMI\b"),
           _rx(r"^ecg\.(st_elevation_|pathologic_q_)")),
    Topico("infradesnivelamento de ST", _rx(r"infra\w*\s*(?:de\s*)?ST|infradesnivel\w*|depress[aã]o d[oe] "
                                             r"(?:segmento )?ST"), _rx(r"^ecg\.(st_depression_|secondary_repol)")),
    Topico("isquemia", _rx(r"isqu[eê]mi\w+|les[aã]o subepic\w+|les[aã]o subendoc\w+"),
           _rx(r"^ecg\.(st_elevation_|st_depression_|t_inversion_)")),
    Topico("inversão de onda T", _rx(r"invers[aã]o d[ae] onda T|onda T (?:invertida|negativa)"),
           _rx(r"^ecg\.(t_inversion_|secondary_repol)"), _rx(r"^derivacao\."), medida=True),
    Topico("repolarização ventricular alterada", _rx(r"repolariza[cç][aã]o|\bstrain\b|altera[cç][oõ]es? de ST-?T"),
           _rx(r"^ecg\.(secondary_repol|st_|t_inversion_)"), _rx(r"^derivacao\."), medida=True),
    Topico("onda Q patológica / área inativa", _rx(r"onda Q patol[oó]gica|[aá]rea inativa|necrose"),
           _rx(r"^ecg\.pathologic_q_")),
    Topico("pré-excitação", _rx(r"pr[eé]-?excita\w+|onda delta|\bWPW\b|wolff"), _rx(r"^ecg\.(preexcitation|wpw)")),
    Topico("PR curto", _rx(r"PR (?:curto|encurtad\w+)"), _rx(r"^ecg\.(short_pr|preexcitation|wpw)")),
    Topico("bloqueio atrioventricular", _rx(r"\bBAV\b|bloqueio atrioventricular|mobitz"), _rx(r"^ecg\.av_block_")),
    Topico("fibrilação atrial", _rx(r"fibrila[cç][aã]o atrial|\bFA\b"), _rx(r"^ecg\.atrial_fibrillation")),
    Topico("flutter atrial", _rx(r"flutter"), _rx(r"^ecg\.atrial_flutter")),
    Topico("ritmo irregular", _rx(r"ritmo irregular|arritmia"), _rx(r"^ecg\.(irregular_rhythm|atrial_f)")),
    Topico("taquicardia sinusal", _rx(r"taquicardia sinusal"), _rx(r"^ecg\.sinus_tachycardia")),
    Topico("bradicardia sinusal", _rx(r"bradicardia sinusal"), _rx(r"^ecg\.sinus_bradycardia")),
    Topico("ritmo sinusal", _rx(r"ritmo sinusal"), _rx(r"^ecg\.sinus_"), _rx(r"^globais\.rhythm$"),
           fato_texto=_rx(r"sinusal")),
    Topico("ritmo de marca-passo", _rx(r"marca-?passo|ritmo estimulado"), _rx(r"^ecg\.paced_rhythm")),
    Topico("QT longo/curto", _rx(r"QTc?\s+(?:longo|curto|prolongad\w+|encurtad\w+)|s[ií]ndrome do QT"),
           _rx(r"^ecg\.(long_qt|short_qt|qtc_)")),
    Topico("desvio de eixo", _rx(r"desvio d[eo] eixo|eixo (?:desviado|\w+ à (?:esquerda|direita))"),
           _rx(r"^ecg\.(left_axis|right_axis|lafb|lpfb)"), _rx(r"^globais\.qrs_axis_deg$")),
    Topico("baixa voltagem", _rx(r"baixa voltagem"), _rx(r"^ecg\.low_voltage")),
    # ---- medidas / índices (só afirmações; a chave do texto tem de casar com a do fato)
    Topico("frequência cardíaca", _rx(r"frequ[eê]ncia card[ií]aca|\bFC\b|\bbpm\b"),
           _rx(r"^ecg\.(sinus_(tachy|brady)|atrial_f|irregular_rhythm)"),
           _rx(r"^globais\.(heart_rate_bpm|rr_mean_ms)$"), medida=True),
    Topico("intervalo PR", _rx(r"\bPR\b"), _rx(r"^ecg\.(av_block_|short_pr|preexcitation|wpw)"),
           _rx(r"^globais\.pr_ms$|^derivacao\."), medida=True),
    Topico("duração do QRS", _rx(r"dura[cç][aã]o do QRS|QRS (?:alargad\w+|estreit\w+|de \d)"),
           _rx(r"^ecg\.(i?lbbb|i?rbbb|ivcd|qrs_borderline|preexcitation|wpw|paced_rhythm)"),
           _rx(r"^globais\.qrs_ms$|^derivacao\."), medida=True),
    Topico("intervalo QT/QTc", _rx(r"\bQTc?\b"), _rx(r"^ecg\.(long_qt|short_qt|qtc_)"),
           _rx(r"^globais\.qt"), medida=True),
    Topico("eixo", _rx(r"\beixo\b"), _rx(r"^ecg\.(left_axis|right_axis|lafb|lpfb)"),
           _rx(r"^globais\.[pqrst]+_axis_deg$"), medida=True),
    Topico("onda P", _rx(r"\bonda P\b|dura[cç][aã]o de P"), _rx(r"^ecg\.(lae|left_atrial|rae|right_atrial|non_sinus_p|"
                                                                  r"no_p_wave)"),
           _rx(r"^globais\.p_|^derivacao\."), medida=True),
    Topico("índice Sokolow-Lyon", _rx(r"sokolow"), None, _rx(r"^indice\.sokolow"), medida=True),
    Topico("índice Cornell", _rx(r"cornell"), None, _rx(r"^indice\.cornell"), medida=True),
    Topico("índice Peguero-Lo Presti", _rx(r"peguero"), None, _rx(r"^indice\.peguero"), medida=True),
    Topico("índice Romhilt-Estes", _rx(r"romhilt"), None, _rx(r"^indice\.romhilt"), medida=True),
    Topico("ângulo QRS-T", _rx(r"[aâ]ngulo QRS-?T"), None, _rx(r"^indice\.angulo_qrs_t"), medida=True),
)

_NEGACAO = _rx(r"\b(?:n[aã]o (?:h[aá]|se observ\w*|evidenc\w*|identific\w*|apresent\w*|exist\w*|detect\w*|"
               r"mostr\w*|demonstr\w*)|sem|aus[eê]ncia|descart\w*|afast\w*|exclu\w*|nega\w*|nenhum\w*)\b")
_QUALIFICADOR = _rx(r"regras? autom[aá]tic\w*|nenhuma regra|n[aã]o detectad\w+ pel\w+ regra")
_FIM_FRASE = re.compile(r"[.;:!?\n]")
# a negação não atravessa vírgula nem conectivo de contraste/afirmação ("sem BAV, com hemibloqueio", "sem WPW, observa-se BRD")
_CORTE_NEG = _rx(r",|\bcom\b|\bmas\b|\bpor[eé]m\b|\bobserva\w*|\bnota-se\b")
_JANELA_NEG = 70

_NORMAL_ECG = _rx(r"(?:\bECG\b|eletrocardiograma|tra[cç]ado|exame)\b[^.;]{0,40}\b(?:normal|normais|normalidade|"
                  r"sem altera[cç][oõ]es)")
_NORMAL_FRASE = _rx(r"dentro (?:d[ao]s? )?(?:limites? d[ao] )?normalidade|dentro dos limites normais|"
                    r"\bsem altera[cç][oõ]es\b")
_MEDIDA_NA_FRASE = _rx(r"\bPR\b|\bQRS\b|\bQTc?\b|\bST\b|frequ[eê]ncia|\bFC\b|\beixo\b|\bonda\b|ritmo|intervalo|"
                       r"segmento|\bbpm\b|\bms\b|\bmm\b|voltagem|[ií]ndice")
_PREENCHE = _rx(r"preenche(?:m|u|ndo)?\b|preenchid\w+|atingid\w+|positiv\w+")

CODIGO_NORMAL = "ecg.within_normal_limits"
SEVERIDADES_ANORMAIS = ("abnormal", "critical")


def _suporta(t: Topico, f) -> bool:
    if f.tipo == "meta" or f.nao_avaliavel:
        return False
    if t.codigos and f.codigo and t.codigos.search(f.codigo):
        return True
    if t.chaves and (t.chaves.search(f.chave) or any(t.chaves.search(k) for k in f.chaves)):
        return not t.fato_texto or bool(t.fato_texto.search(f.texto))
    return False


def _negado(texto: str, inicio: int) -> bool:
    """Há negação na mesma oração, ANTES do tópico e sem separador/contraste entre ambos."""
    janela = texto[max(0, inicio - _JANELA_NEG):inicio]
    corte = max((m.end() for m in _FIM_FRASE.finditer(janela)), default=0)
    janela = janela[corte:]
    return any(not _CORTE_NEG.search(janela[m.end():]) for m in _NEGACAO.finditer(janela))


def _topicos_no_texto(texto: str) -> list[tuple[Topico, bool]]:
    """(tópico, negado?) para cada tópico citado; negado se QUALQUER ocorrência estiver afirmada → afirmado."""
    out: list[tuple[Topico, bool]] = []
    for t in TOPICOS:
        ocorr = [_negado(texto, m.start()) for m in t.texto.finditer(texto)]
        if not ocorr:
            continue
        if all(ocorr):
            if not t.medida:
                out.append((t, True))
        else:
            out.append((t, False))
    return out


def normal_global(texto: str) -> bool:
    """Afirmação de normalidade do exame inteiro (e não de uma medida: 'PR dentro dos limites normais')."""
    if _NORMAL_ECG.search(texto):
        return True
    return bool(_NORMAL_FRASE.search(texto)) and not _MEDIDA_NA_FRASE.search(texto)


def _regras_ativas(ficha: "Ficha") -> list:
    return [f for f in ficha.fatos if f.codigo and f.severidade in SEVERIDADES_ANORMAIS]


def semantic_issues(texto: str, secao: str, fatos: list, ficha: "Ficha", generic_cards_only: bool) -> list[str]:
    """Motivos (lista vazia = ok) de a afirmação não ter lastro semântico nos fatos citados."""
    issues: list[str] = []
    if secao != "qualidade_tecnica":
        if all(f.tipo == "meta" for f in fatos):
            issues.append("somente fatos meta (aquisição/aviso) citados: não sustentam afirmação clínica")
        if generic_cards_only:
            issues.append("somente cartão genérico citado: não sustenta afirmação clínica")
    for t, negado in _topicos_no_texto(texto):
        if negado:
            contra = [f for f in ficha.fatos if f.tipo != "meta" and f.codigo and t.codigos
                      and t.codigos.search(f.codigo)]
            if contra:
                issues.append(f"negação de {t.nome} contradiz regra ativa ({', '.join(sorted({f.codigo for f in contra}))})")
            elif not _QUALIFICADOR.search(texto):
                issues.append(f"negação de {t.nome} sem qualificador: ausência de regra automática não exclui o achado")
        elif not any(_suporta(t, f) for f in fatos):
            issues.append(f"afirmação sobre {t.nome} sem fato [F] do mesmo achado/medida citado")
    issues += _normal_issues(texto, fatos, ficha)
    issues += _preenchimento_issues(texto, fatos)
    return issues


def _normal_issues(texto: str, fatos: list, ficha: "Ficha") -> list[str]:
    if not normal_global(texto):
        return []
    ativas = _regras_ativas(ficha)
    if ativas:
        return ["afirmação de normalidade contradiz regra anormal/crítica ativa ("
                + ", ".join(sorted({f.codigo for f in ativas})) + ")"]
    if ficha.suprimidos or ficha.qualidade.nivel != "ok":
        return ["afirmação de normalidade com digitalização suspeita/medidas suprimidas"]
    if not any(f.codigo == CODIGO_NORMAL for f in fatos):
        return [f"afirmação de normalidade sem o fato da regra {CODIGO_NORMAL} citado"]
    if not _QUALIFICADOR.search(texto):
        return ["normalidade só pode ser expressa como resultado das regras automáticas (não exclui doença)"]
    return []


def _preenchimento_issues(texto: str, fatos: list) -> list[str]:
    idx = [f for f in fatos if f.tipo == "indice"]
    if not idx or not all("não preenche" in f.texto for f in idx):
        return []
    for m in _PREENCHE.finditer(texto):
        if not _negado(texto, m.start()) and not re.search(r"n[aã]o\s*$", texto[max(0, m.start() - 6):m.start()], _I):
            return ["índice citado não preenche o critério, mas a afirmação diz que preenche"]
    return []
