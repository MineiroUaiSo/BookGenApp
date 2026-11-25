"""R1: ICT de segmentacao heuristica nao gera achado; rotulo D2; faixa cinzenta so com D-C (nao aprovada)."""
import pytest

from app.rx.findings import study_findings
from app.schemas import BodyRegion, RXImageAnalysis, RXMeasurement, RXView, Structure


def _img(ict, origin="model", view=RXView.PA):
    st = [Structure(key="heart", label="coracao", category="heart_vessels", color="#fff", origin=origin)]
    ms = [RXMeasurement(key="cardiothoracic_ratio", label="ICT", value=ict, unit="")]
    return RXImageAnalysis(instance_id="i1", view=view, region=BodyRegion.CHEST, image_png_b64="", width=8,
                           height=8, structures=st, measurements=ms)


def _ict_codes(img):
    return [f for f in study_findings([img]) if f.code in ("rx.cardiomegaly", "rx.cardiothoracic_ratio_normal")]


@pytest.mark.parametrize("ict", [0.62, 0.40])
def test_ict_heuristico_nao_gera_achado(ict):
    assert _ict_codes(_img(ict, origin="heuristic")) == []


def test_ict_sem_estrutura_heart_nao_gera_achado():
    img = _img(0.62)
    img.structures = []
    assert _ict_codes(img) == []


def test_ict_modelo_alto_pa_usa_rotulo_d2():
    fs = _ict_codes(_img(0.55))
    assert len(fs) == 1 and fs[0].code == "rx.cardiomegaly"
    assert fs[0].label == "Sugere aumento da silhueta cardíaca (ICT > 0,50 em PA)"


def test_ict_modelo_baixo_nao_gera_achado_normal():
    """H1: ICT de modelo <= 0,50 tem incerteza (±0,05) e tende a subestimar: nao afirma coracao normal."""
    assert _ict_codes(_img(0.40)) == []


def test_ict_cxas_conta_como_modelo():
    assert len(_ict_codes(_img(0.62, origin="cxas"))) == 1


def test_nenhum_rotulo_contem_cardiomegalia_com_parentese():
    for origin in ("model", "heuristic"):
        for ict in (0.40, 0.52, 0.55, 0.62):
            for view in (RXView.PA, RXView.AP):
                for f in study_findings([_img(ict, origin, view)]):
                    assert "Cardiomegalia (" not in f.label


def test_ict_049_modelo_sem_faixa_cinzenta_e_sem_achado():
    """D-C sem resposta do dono: nao cria faixa limitrofe; 0,49 nao vira achado nem 'normal' (H1)."""
    assert _ict_codes(_img(0.49)) == []
