"""L1: descrição completa redigida por IA (FakeClient, nunca chamada real): verificada ou cai no determinístico."""
import json

import pytest

from app.llm import guard
from app.rx import descricao_ia as DI
from app.rx import ficha as FI
from app.rx import laudo as LA
from app.rx import lexico as LX
from test_rx_laudo import CENARIOS


class FakeClient:
    """Devolve JSON de afirmações; registra o que recebeu (para provar que só vai texto estruturado)."""

    def __init__(self, afirmacoes=None, erro=None, bruto=None):
        self.afirmacoes, self.erro, self.bruto, self.chamadas = afirmacoes, erro, bruto, []

    def __call__(self, sistema, usuario):
        self.chamadas.append((sistema, usuario))
        if self.erro:
            raise self.erro
        return self.bruto if self.bruto is not None else json.dumps({"afirmacoes": self.afirmacoes}, ensure_ascii=False)


def _base(nome="pa_modelo"):
    a = CENARIOS[nome]
    laudo, ficha = LA.build_laudo(a), FI.build_ficha(a)
    boas = [{"texto": t, "fatos": list(ids)} for t, ids in LA.oracoes_descricao(laudo, ficha) if t != LA.CRITICO]
    return a, laudo, boas


def test_ia_aceita_reescrita_verificada_e_marca_origem():
    a, laudo, boas = _base()
    fake = FakeClient(boas)
    novo = DI.aplicar(laudo, a, fake)
    assert novo.descricao_origem == "ia" and novo.descricao_validacao == {"frases": len(boas), "removidas": 0}
    assert novo.descricao_completa.endswith(LA.CRITICO) and "\n" not in novo.descricao_completa


def test_ia_so_recebe_texto_estruturado_sem_imagem_nem_phi():
    a, laudo, boas = _base()
    fake = FakeClient(boas)
    DI.aplicar(laudo, a, fake)
    sistema, usuario = fake.chamadas[0]
    assert guard.scan_text(sistema + usuario) is None and "base64" not in usuario
    assert json.loads(usuario)["fatos"] and "image_png_b64" not in usuario


def test_ia_inventa_pulmoes_livres_frase_removida():
    a, laudo, boas = _base()
    inventada = {"texto": "Os pulmões estão livres de consolidação e sem alterações.", "fatos": []}
    novo = DI.aplicar(laudo, a, FakeClient(boas[:3] + [inventada] + boas[3:]))
    assert novo.descricao_origem == "ia" and novo.descricao_validacao["removidas"] == 1
    d = novo.descricao_completa.lower()
    assert "livres" not in d and "sem alterações" not in d and LX.termos_proibidos(novo.descricao_completa) == []


def test_ia_afirma_achado_sem_lastro_e_removida():
    a, laudo, boas = _base()
    derrame = {"texto": "Há derrame pleural volumoso à direita.", "fatos": []}
    novo = DI.aplicar(laudo, a, FakeClient(boas + [derrame]))
    assert "derrame" not in novo.descricao_completa.lower() and novo.descricao_validacao["removidas"] == 1


def test_ia_numero_sem_fato_e_fato_inexistente_removidos():
    a, laudo, boas = _base()
    ruins = [{"texto": "O índice cardiotorácico foi medido em 0,61.", "fatos": ["F1"]},
             {"texto": "A pleura foi avaliada.", "fatos": ["F999"]}]
    novo = DI.aplicar(laudo, a, FakeClient(boas + ruins))
    assert "0,61" not in novo.descricao_completa and novo.descricao_validacao["removidas"] == 2


def test_ia_falha_cai_no_deterministico():
    a, laudo, _ = _base()
    for erro in (RuntimeError("boom"), TimeoutError()):
        novo = DI.aplicar(laudo, a, FakeClient(erro=erro))
        assert novo.descricao_origem == "deterministico" and novo.descricao_completa == laudo.descricao_completa


def test_ia_resposta_invalida_cai_no_deterministico():
    a, laudo, _ = _base()
    for bruto in ("não é json", json.dumps({"x": 1}), json.dumps({"afirmacoes": "texto"})):
        novo = DI.aplicar(laudo, a, FakeClient(bruto=bruto))
        assert novo.descricao_origem == "deterministico" and novo.descricao_completa == laudo.descricao_completa


def test_ia_resposta_com_quebra_de_linha_vira_paragrafo_unico():
    a, laudo, boas = _base()
    boas[0] = {"texto": boas[0]["texto"].replace(", descrita", ",\n\n descrita"), "fatos": boas[0]["fatos"]}
    novo = DI.aplicar(laudo, a, FakeClient(boas))
    assert novo.descricao_origem == "ia"
    assert "\n" not in novo.descricao_completa and "\r" not in novo.descricao_completa and "  " not in novo.descricao_completa


def test_ia_maioria_sem_lastro_cai_no_deterministico():
    a, laudo, boas = _base()
    lixo = [{"texto": f"Pulmões livres, achado {i}.", "fatos": []} for i in range(8)]
    novo = DI.aplicar(laudo, a, FakeClient(boas[:2] + lixo))
    assert novo.descricao_origem == "deterministico" and novo.descricao_completa == laudo.descricao_completa
    assert novo.descricao_validacao["removidas"] == 8


def test_ia_que_perde_regiao_ou_ict_cai_no_deterministico():
    a, laudo, boas = _base()
    sem_limitacoes = [b for b in boas if not b["texto"].startswith("Não foram avaliados")]
    assert DI.aplicar(laudo, a, FakeClient(sem_limitacoes)).descricao_origem == "deterministico"
    sem_ict = [b for b in boas if "cardiotorácico" not in b["texto"]]
    assert DI.aplicar(laudo, a, FakeClient(sem_ict)).descricao_origem == "deterministico"


def test_ia_frase_critico_e_sempre_a_ultima_e_a_da_ia_sobre_pneumotorax_e_descartada():
    a, laudo, boas = _base()
    extra = {"texto": "Pneumotórax não avaliado nesta análise.", "fatos": []}
    d = DI.aplicar(laudo, a, FakeClient(boas + [extra])).descricao_completa
    assert d.endswith(LA.CRITICO) and d.lower().count("pneumotórax") == 1


def test_ia_phi_no_texto_cai_no_deterministico():
    a, laudo, boas = _base()
    boas[0] = {"texto": boas[0]["texto"] + " Paciente CPF 529.982.247-25.", "fatos": boas[0]["fatos"]}
    novo = DI.aplicar(laudo, a, FakeClient(boas))
    assert "529.982" not in novo.descricao_completa


def test_ia_ict_heuristico_nao_vira_medida():
    a, laudo, boas = _base("heuristica")
    boas.insert(2, {"texto": "O índice cardiotorácico foi medido em 0,64.", "fatos": []})
    novo = DI.aplicar(laudo, a, FakeClient(boas))
    assert "0,64" not in novo.descricao_completa


def test_ia_desligada_ou_sem_provedor_nao_chama(monkeypatch):
    a, laudo, boas = _base()
    monkeypatch.setenv("MEDLENS_RX_DESCRICAO_IA", "0")
    fake = FakeClient(boas)
    assert DI.aplicar(laudo, a, fake) is laudo and not fake.chamadas
    monkeypatch.setenv("MEDLENS_RX_DESCRICAO_IA", "1")
    from app.llm import client as c
    monkeypatch.setattr(c, "ai_available", lambda: False)
    assert DI.aplicar(laudo, a) is laudo


def test_ia_laudo_sem_descricao_deterministica_nao_chama():
    a, laudo, boas = _base()
    vazio = laudo.model_copy(update={"descricao_completa": ""})
    fake = FakeClient(boas)
    assert DI.aplicar(vazio, a, fake) is vazio and not fake.chamadas


def test_ia_anexar_laudo_expoe_origem_e_markdown(monkeypatch):
    from app.api import analysis
    from app.llm import client as c

    a, laudo, boas = _base()
    monkeypatch.setattr(c, "ai_available", lambda: True)
    monkeypatch.setattr(DI, "_chamar_padrao", FakeClient(boas))
    r = CENARIOS["pa_modelo"].model_copy(deep=True)
    analysis._anexar_laudo_rx(r, ai=True)
    assert r.laudo_rx["descricao_origem"] == "ia" and r.laudo_rx["descricao_validacao"]["removidas"] == 0
    assert r.laudo_rx_markdown.rstrip().endswith(r.laudo_rx["descricao_completa"])
    r2 = CENARIOS["pa_modelo"].model_copy(deep=True)
    analysis._anexar_laudo_rx(r2, ai=False)
    assert r2.laudo_rx["descricao_origem"] == "deterministico"


def test_endpoint_descricao_devolve_laudo_com_origem_ia(monkeypatch):
    from app.api import analysis
    from app.llm import client as c

    a, laudo, boas = _base()
    monkeypatch.setattr(c, "ai_available", lambda: True)
    monkeypatch.setattr(DI, "_chamar_padrao", FakeClient(boas))
    monkeypatch.setattr(analysis, "_study", lambda sid: None)
    monkeypatch.setattr(analysis, "_recall", lambda kind, sid: (CENARIOS["pa_modelo"].model_copy(deep=True), None))
    r = analysis.rx_descricao("x")
    assert r.laudo_rx["descricao_origem"] == "ia"
    assert r.laudo_rx_markdown.rstrip().endswith(r.laudo_rx["descricao_completa"])
