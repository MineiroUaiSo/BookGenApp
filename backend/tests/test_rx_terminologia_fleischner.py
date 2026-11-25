"""Tarefa 2 (spec RX-LAUDO-CONFIAVEL): Fleischner 2024 chama 'infiltrado' de termo obsoleto; o app diz 'opacidade'."""
from pathlib import Path

from app.rx import findings as F
from app.schemas import BodyRegion, RXImageAnalysis, RXView


def test_rx_rotulos_patologia_nao_usam_infiltrado():
    assert all("infiltrad" not in v.lower() for v in F.PATHO_PT.values())
    assert F.PATHO_PT["Infiltration"] == "opacidade"


def test_rx_achado_do_modelo_infiltration_sai_como_opacidade():
    img = RXImageAnalysis(instance_id="i", view=RXView.PA, region=BodyRegion.CHEST, image_png_b64="", width=8,
                          height=8, model_scores={"Infiltration": 0.99})
    textos = [t.lower() for f in F._model_findings(img) for t in (f.label, *f.evidence)]
    assert textos and all("infiltrad" not in t for t in textos)


def test_rx_nenhum_texto_de_app_rx_usa_infiltrado():
    base = Path(F.__file__).parent
    for p in base.glob("*.py"):
        assert "infiltrad" not in p.read_text(encoding="utf-8").lower(), p.name
