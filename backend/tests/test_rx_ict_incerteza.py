"""H1: ICT de modelo declara incerteza (±0,05, pode estar subestimado) e nunca exclui cardiomegalia."""
import numpy as np
import pytest

from app.rx import claim_check as CC
from app.rx import ficha as FI
from app.rx import laudo as LA
from app.rx import measure
from app.rx.findings import study_findings
from app.schemas import BodyRegion, RXAnalysis, RXImageAnalysis, RXMeasurement, RXView, Structure


def _masks():
    h = w = 100
    r, l, c = (np.zeros((h, w), bool) for _ in range(3))
    r[10:90, 5:45] = True
    l[10:90, 55:95] = True
    c[40:80, 30:60] = True
    return {"right_lung": r, "left_lung": l, "heart": c}


def _ict(origin):
    ms, _ = measure.measure_frontal(_masks(), measure.Conv((1.0, 1.0), None), "PA", origin=origin)
    return next(m for m in ms if m.key == "cardiothoracic_ratio")


@pytest.mark.parametrize("origin", ["model", "cxas"])
def test_measure_ict_de_modelo_declara_incerteza_e_subestimado(origin):
    txt = " ".join(_ict(origin).limitations)
    assert "±0,05" in txt and "subestimad" in txt


def test_measure_ict_heuristico_nao_leva_limitacao_de_modelo():
    assert _ict("heuristic").limitations == []


def _img(ict, origin="model", view=RXView.PA):
    st = [Structure(key="heart", label="c", category="heart_vessels", color="#fff", origin=origin),
          Structure(key="right_lung", label="p", category="lung", color="#fff", origin=origin)]
    ms = [RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=ict, unit="")]
    return RXImageAnalysis(instance_id="i1", view=view, region=BodyRegion.CHEST, image_png_b64="", width=8, height=8,
                           structures=st, measurements=ms,
                           quality={"rotação": "adequada", "inspiração": "adequada", "penetração": "adequada"})


def _analise(img, findings=()):
    return RXAnalysis(study_id="s", images=[img], findings=list(findings))


@pytest.mark.parametrize("v", [0.40, 0.58])
def test_ficha_ict_de_modelo_leva_ressalva_de_incerteza(v):
    f = FI.build_ficha(_analise(_img(v)))
    ict = next(x for x in f.fatos if x.chave == "ict")
    txt = " ".join(ict.ressalvas)
    assert "±0,05" in txt and "subestimad" in txt


def test_laudo_ict_baixo_nao_exclui_aumento_da_silhueta():
    a = _analise(_img(0.40))
    md = LA.render_markdown(LA.build_laudo(a))
    assert "incerteza" in md and "não exclui aumento da silhueta" in md
    assert "limite clássico" not in md


def test_laudo_ict_alto_mantem_sugere_e_cita_incerteza():
    a = _analise(_img(0.58), [__import__("app.schemas", fromlist=["Finding"]).Finding(code="rx.cardiomegaly", label="x")])
    md = LA.render_markdown(LA.build_laudo(a))
    assert "sugere aumento da silhueta cardíaca" in md and "±0,05" in md


@pytest.mark.parametrize("v", [0.30, 0.40, 0.46, 0.49, 0.50])
def test_findings_ict_abaixo_de_050_nunca_afirma_coracao_normal(v):
    fs = [f for f in study_findings([_img(v)]) if "cardio" in f.code]
    assert all(f.severity != "normal" and "normal" not in (f.label + f.code).lower() for f in fs)


def test_findings_ict_alto_continua_sugerindo_aumento_com_incerteza():
    fs = [f for f in study_findings([_img(0.58)]) if f.code == "rx.cardiomegaly"]
    assert len(fs) == 1 and fs[0].label.startswith("Sugere aumento da silhueta cardíaca")
    assert "subestimad" in " ".join(fs[0].evidence)


def _summary(ict):
    return {"imagens": [{"incidencia": "PA", "estruturas_segmentadas": [{"chave": "heart", "origem": "modelo"}],
                         "medidas": [{"key": "cardiothoracic_ratio", "value": ict}]}], "achados_por_regras": []}


@pytest.mark.parametrize("frase", ["Área cardíaca normal.", "Sem cardiomegalia (ICT 0,46).", "Não há cardiomegalia."])
def test_claim_check_ict_baixo_nao_sustenta_negar_cardiomegalia(frase):
    assert CC.problema_da_frase(frase, CC.Fatos.de(_summary(0.46))) is not None
