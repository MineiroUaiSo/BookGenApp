"""Tarefa 8: contrato da IA do laudo RX: validador determinístico (regras 1-7 §3), abstenção e flag desligada."""
import json

import pytest

from app.rx import ficha as FI
from app.rx import laudo_validate as LV
from app.schemas import BodyRegion, Finding, RXAnalysis, RXImageAnalysis, RXMeasurement, RXView, Structure


def _ficha():
    st = [Structure(key=k, label=k, category="other", color="#fff", origin="model") for k in ("heart", "right_lung")]
    ms = [RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=0.46),
          RXMeasurement(key="mediastinal_width_ratio", label="m", value=40.0, unit="%"),
          RXMeasurement(key="tracheal_deviation_pct", label="t", value=6.0, unit="%")]
    img = RXImageAnalysis(instance_id="i", view=RXView.PA, region=BodyRegion.CHEST, image_png_b64="", width=8,
                          height=8, structures=st, measurements=ms,
                          model_zones={"Effusion": "sugestivo", "Consolidation": "indeterminado",
                                       "Pneumothorax": "sugestivo"},
                          model_probs={"Effusion": 0.7, "Consolidation": 0.3, "Pneumothorax": 0.9},
                          quality={"rotação": "possível rotação", "inspiração": "adequada", "penetração": "indeterminada"})
    return FI.build_ficha(RXAnalysis(study_id="s", images=[img], findings=[
        Finding(code="rx.mediastinal_widening", label="x"), Finding(code="rx.tracheal_deviation", label="x")]))


FICHA = _ficha()
ID = {f.chave: f.id for f in FICHA.fatos}


def _v(texto, *chaves, secao="achados", fontes=(), imagem=False):
    af = [{"secao": secao, "texto": texto, "fatos": [ID.get(c, c) for c in chaves], "fontes": list(fontes)}]
    r = LV.validar(af, FICHA, imagem_enviada=imagem)
    return bool(r.aceitas), r


ICT, MED, TRA = "ict", "mediastino_largura_pct", "traqueia_desvio_pct"
EFF, CON, PNX, DEV = "modelo.effusion", "modelo.consolidation", "modelo.pneumothorax", "dispositivos"

LEGITIMAS = [
    ("O índice cardiotorácico medido foi 0,46 (limite clássico 0,50 em PA).", [ICT]),
    ("Índice cardiotorácico medido 0,46.", [ICT]),
    ("ICT de 0,46 em incidência PA.", [ICT]),
    ("Medida compatível com a faixa de referência: ICT 0,46.", [ICT]),
    ("Não há cardiomegalia pelo ICT medido 0,46.", [ICT]),
    ("Largura do mediastino medida 40% da largura torácica, acima do limiar local (heurística local, sem fonte primária; correlacionar).", [MED]),
    ("Mediastino com largura medida de 40%, acima do limiar local.", [MED]),
    ("Desvio traqueal medido +6,0% da largura torácica, acima do limiar local (heurística local).", [TRA]),
    ("Desvio traqueal de 6,0% acima do limiar local; correlacionar.", [TRA]),
    ("Modelo auxiliar: possível derrame pleural (probabilidade calibrada ≈ 0,70); escore de modelo; não confirma nem afasta.", [EFF]),
    ("O modelo auxiliar indica possível derrame pleural, probabilidade calibrada 0,70; isso não confirma nem afasta o achado.", [EFF]),
    ("Possível derrame pleural segundo o escore do modelo auxiliar (0,70), sem valor de decisão.", [EFF]),
    ("Modelo auxiliar: indeterminado para derrame pleural; não permite afirmar nem afastar.", [EFF]),
    ("Modelo auxiliar: indeterminado para consolidação; não permite afirmar nem afastar.", [CON]),
    ("Para consolidação o escore do modelo é indeterminado.", [CON]),
    ("Modelo auxiliar: indeterminado para pneumotórax; não permite afirmar nem afastar.", [PNX]),
    ("Rotação possivelmente inadequada (estimativa automática): limita a avaliação de mediastino, traqueia e silhueta cardíaca.", ["rotacao"]),
    ("A rotação é possivelmente inadequada e limita a avaliação do mediastino.", ["rotacao"]),
    ("Inspiração: estimativa automática adequada.", ["inspiracao"]),
    ("Penetração indeterminada (estimativa automática): limita a avaliação do parênquima.", ["penetracao"]),
    ("Incidência: PA.", ["incidencia"]),
    ("Dispositivos: tubos, cateteres e marca-passo não são avaliados por esta análise.", [DEV]),
    ("Tubos e cateteres não foram avaliados nesta análise.", [DEV]),
    ("Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: revisar a imagem.", [DEV]),
    ("Pleura: não avaliado nesta análise automática.", []),
    ("Ossos e partes moles: não avaliado nesta análise automática.", []),
    ("Diafragma: ar livre subdiafragmático não avaliado nesta análise automática.", []),
    ("Pulmões: opacidades, nódulos e padrão intersticial não avaliados nesta análise automática.", []),
    ("Mediastino e hilos: não avaliado nesta análise automática.", []),
    ("Correlacionar com a clínica.", []),
    ("O índice cardiotorácico de 0,46 foi medido em incidência PA.", [ICT, "incidencia"]),
]

ILEGITIMAS = [
    ("Derrame pleural à direita.", []),
    ("Cardiomegalia.", []),
    ("Consolidação no lobo inferior direito com broncograma aéreo.", []),
    ("Nódulo pulmonar de 12 mm.", []),
    ("Fratura do 6º arco costal.", []),
    ("Sem pneumotórax.", []),
    ("Seios costofrênicos livres.", []),
    ("Pulmões sem opacidades.", []),
    ("O índice cardiotorácico medido foi 0,46.", ["F999"]),
    ("Índice cardiotorácico medido 0,52.", [ICT]),
    ("Largura do mediastino medida 55%.", [MED]),
    ("Possível derrame pleural.", [ICT]),
    ("Possível derrame pleural de 8 mm.", [EFF]),
    ("Derrame pleural.", [EFF]),
    ("Consolidação.", [CON]),
    ("Possível consolidação.", [CON]),
    ("Possível pneumotórax.", [PNX]),
    ("Pneumotórax.", [PNX]),
    ("O modelo sugere derrame pleural.", [EFF]),
    ("Achado compatível com derrame pleural.", [EFF]),
    ("Sem derrame pleural.", [EFF]),
    ("Não há derrame pleural.", [EFF]),
    ("Pulmões limpos.", [CON]),
    ("Sem cardiomegalia.", [MED]),
    ("Silhueta cardíaca normal.", [ICT]),
    ("Exame sem alterações.", [ICT]),
    ("Tórax dentro da normalidade.", [ICT]),
    ("Isso afasta pneumotórax.", [PNX]),
    ("Descarta derrame pleural.", [EFF]),
    ("O modelo confirma derrame pleural.", [EFF]),
    ("Ausência de derrame pleural.", [EFF]),
    ("Diagnóstico de cardiomegalia.", [ICT]),
    ("Possível derrame pleural na base direita.", [EFF]),
    ("Possível derrame pleural no hemitórax esquerdo.", [EFF]),
    ("Cateter venoso central bem posicionado.", [DEV]),
    ("Presença de marca-passo.", [DEV]),
    ("Cardiomegalia (ICT 0,46).", [ICT]),
    ("Aumento da silhueta cardíaca.", [ICT]),
    ("Alargamento do mediastino.", [MED]),
    ("Sugere derrame pleural.", [DEV]),
    ("Pleura sem alterações.", []),
    ("Ar livre subdiafragmático ausente.", []),
    ("Possível derrame pleural.", ["F1000"]),
    ("Derrame pleural conforme S99.", [EFF]),
    ("Edema pulmonar.", [EFF]),
    ("Atelectasia no lobo inferior.", [CON]),
]


def test_rx_laudo_validate_suite_adversarial_tem_pelo_menos_60_frases():
    assert len(LEGITIMAS) + len(ILEGITIMAS) >= 60


@pytest.mark.parametrize("texto,chaves", ILEGITIMAS)
def test_rx_laudo_validate_frase_sem_lastro_nunca_passa(texto, chaves):
    ok, r = _v(texto, *chaves)
    assert not ok, (texto, r.aceitas)
    assert r.rejeicoes and r.rejeicoes[0].motivos


def test_rx_laudo_validate_legitimas_passam_95_por_cento():
    falhas = [t for t, c in LEGITIMAS if not _v(t, *c)[0]]
    assert len(falhas) <= 0.05 * len(LEGITIMAS), falhas


def test_rx_laudo_validate_fonte_fora_da_lista_ou_nao_verificada_rejeita():
    assert not _v("Índice cardiotorácico medido 0,46.", ICT, fontes=["S99"])[0]
    assert not _v("Índice cardiotorácico medido 0,46.", ICT, fontes=["N1"])[0]
    assert _v("Índice cardiotorácico medido 0,46.", ICT, fontes=["S6"])[0]


def test_rx_laudo_validate_descritor_visual_so_com_imagem_enviada():
    t = "Possível derrame pleural na base direita."
    assert not _v(t, EFF, imagem=False)[0]
    assert _v(t, EFF, imagem=True)[0]


def test_rx_laudo_validate_abstencao_acima_de_50_por_cento():
    af = [{"secao": "achados", "texto": "Derrame pleural.", "fatos": [], "fontes": []},
          {"secao": "achados", "texto": "Cardiomegalia.", "fatos": [], "fontes": []},
          {"secao": "achados", "texto": "Correlacionar com a clínica.", "fatos": [], "fontes": []}]
    r = LV.validar(af, FICHA)
    assert r.abstencao and len(r.rejeicoes) == 2 and "descartado pelo validador" in r.aviso


def test_rx_laudo_validate_rejeicao_na_impressao_forca_abstencao():
    af = [{"secao": "impressao", "texto": "Derrame pleural.", "fatos": [], "fontes": []}] + [
        {"secao": "achados", "texto": "Incidência: PA.", "fatos": [ID["incidencia"]], "fontes": []}] * 6
    assert LV.validar(af, FICHA).abstencao


def test_rx_laudo_validate_sem_rejeicao_nao_abstem():
    af = [{"secao": "achados", "texto": "Incidência: PA.", "fatos": [ID["incidencia"]], "fontes": []}]
    r = LV.validar(af, FICHA)
    assert not r.abstencao and len(r.aceitas) == 1 and r.aviso == ""


def test_rx_laudo_validate_flag_desligada_por_padrao(monkeypatch):
    monkeypatch.delenv("MEDLENS_RX_LAUDO_IA", raising=False)
    assert LV.ia_habilitada() is False
    monkeypatch.setenv("MEDLENS_RX_LAUDO_IA", "1")
    assert LV.ia_habilitada() is True


def test_rx_laudo_validate_reescrever_usa_cliente_falso_e_valida(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_LAUDO_IA", "1")
    chamadas = []

    def falso(system, user):
        chamadas.append((system, user))
        return json.dumps({"afirmacoes": [
            {"secao": "achados", "texto": "Índice cardiotorácico medido 0,46.", "fatos": [ID["ict"]], "fontes": ["S6"]},
            {"secao": "achados", "texto": "Derrame pleural.", "fatos": [], "fontes": []}]})

    r = LV.reescrever(FICHA, falso)
    assert len(chamadas) == 1 and "F1" in chamadas[0][1] and "S6" in chamadas[0][1]
    assert len(r.aceitas) == 1 and len(r.rejeicoes) == 1 and r.abstencao is False


def test_rx_laudo_validate_reescrever_desligada_nao_chama(monkeypatch):
    monkeypatch.delenv("MEDLENS_RX_LAUDO_IA", raising=False)
    assert LV.reescrever(FICHA, lambda s, u: pytest.fail("não deveria chamar")) is None


def test_rx_laudo_validate_json_invalido_vira_abstencao(monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_LAUDO_IA", "1")
    r = LV.reescrever(FICHA, lambda s, u: "isto não é json")
    assert r.abstencao and not r.aceitas
