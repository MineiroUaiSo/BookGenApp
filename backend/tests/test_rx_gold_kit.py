"""Tarefa 10: casos-ouro (download controlado por licença) e kit de revisão. Sem imagem em git; teste real dá skip."""
import csv
import json
from pathlib import Path

import pytest

from bench import rx_gold_fetch as GF
from bench import rx_review_kit as RK

GOLD = Path(__file__).resolve().parents[2] / "data" / "gold_rx"


@pytest.mark.parametrize("lic,ok", [("CC0", True), ("CC0 1.0", True), ("Public domain", True), ("PD-USGov", True),
                                    ("CC BY-SA 4.0", False), ("CC BY 2.0", False), ("", False), (None, False)])
def test_rx_gold_fetch_so_aceita_cc0_ou_dominio_publico(lic, ok):
    assert GF.licenca_livre(lic) is ok


def test_rx_gold_fetch_nao_baixa_licenca_nao_livre(tmp_path, monkeypatch):
    monkeypatch.setattr(GF, "consultar", lambda t: {"titulo": t, "url": "http://x/y.jpg", "licenca": "CC BY-SA 4.0"})
    monkeypatch.setattr(GF, "_get", lambda u: pytest.fail("não deveria baixar"))
    m = GF.baixar(tmp_path, ("File:A.jpg",))
    assert m[0]["baixado"] is False and "licença não livre" in m[0]["motivo"]
    assert json.loads((tmp_path / "manifest.json").read_text())[0]["baixado"] is False


def test_rx_gold_fetch_baixa_e_registra_manifesto(tmp_path, monkeypatch):
    monkeypatch.setattr(GF, "consultar", lambda t: {"titulo": t, "url": "http://x/y.jpg", "licenca": "CC0"})
    monkeypatch.setattr(GF, "_get", lambda u: b"imagem")
    m = GF.baixar(tmp_path, ("File:Chest Xray PA.png",))
    assert m[0]["baixado"] and (tmp_path / m[0]["arquivo"]).read_bytes() == b"imagem"


def test_rx_gold_fetch_falha_de_rede_nao_derruba(tmp_path, monkeypatch):
    def boom(t):
        raise OSError("sem rede")
    monkeypatch.setattr(GF, "consultar", boom)
    assert GF.baixar(tmp_path, ("File:A.jpg",))[0]["baixado"] is False


def test_rx_review_kit_exporta_markdown_e_planilha(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    falso = lambda p: {"laudo_rx_markdown": "# Laudo\n- Pleura: não avaliado nesta análise automática.\n",
                       "laudo_rx": {"secoes": [{"frases": [{"texto": "Pleura: não avaliado nesta análise automática.",
                                                            "nivel": "NAO_AVALIADO"}]}]}}
    feitos = RK.exportar(tmp_path, tmp_path / "out", 5, analisar=falso)
    assert feitos[0].read_text().startswith("# Laudo")
    linhas = list(csv.reader(open(tmp_path / "out" / "a.severidade.csv", encoding="utf-8")))
    assert tuple(linhas[0]) == RK.CABECALHO and linhas[1][2] == "NAO_AVALIADO" and linhas[1][3] == ""


@pytest.mark.skipif(not (GOLD.is_dir() and any(GOLD.glob("*.jp*g")) or GOLD.is_dir() and any(GOLD.glob("*.png"))),
                    reason="sem imagens em data/gold_rx (rode python -m bench.rx_gold_fetch)")
def test_rx_review_kit_com_imagens_reais_nunca_diz_normal(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDLENS_RX_MODELS", "0")
    from app.rx import lexico as LX
    feitos = RK.exportar(GOLD, tmp_path, 3)
    assert feitos
    for f in feitos:
        assert LX.termos_proibidos(f.read_text(encoding="utf-8")) == []
