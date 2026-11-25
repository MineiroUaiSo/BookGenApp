"""Kit de revisão do laudo RX: exporta N laudos em markdown + planilha de severidade 0-3 (spec §4.3). Sem IA, sem nuvem:
roda a análise local (MEDLENS_RX_MODELS=0 por padrão) nas imagens de `data/gold_rx/`.
Severidade: 0 = correto, 1 = impreciso sem risco, 2 = afirmação sem lastro, 3 = afirmação perigosa (normal/afasta/livre).
Uso: python -m bench.rx_review_kit [--src data/gold_rx] [--out data/rx_review] [--n 20]"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

IMAGENS = {".png", ".jpg", ".jpeg"}
CABECALHO = ("arquivo", "frase", "nivel", "severidade_0a3", "comentario")


def listar(src: Path, n: int) -> list[Path]:
    return sorted(p for p in src.glob("*") if p.suffix.lower() in IMAGENS)[:n] if src.is_dir() else []


def analisar_via_api(path: Path):
    """Usa o TestClient da própria API (sem rede): ingest -> analyze RX."""
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.post("/api/ingest", files=[("files", (path.name, path.read_bytes(), "image/png"))])
    r.raise_for_status()
    est = r.json()["studies"][0]
    sid = est["study_id"]
    r = c.post(f"/api/rx/{sid}/analyze?ai=false", json={})
    r.raise_for_status()
    return r.json()


def exportar(src: Path, out: Path, n: int, analisar=analisar_via_api) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    feitos = []
    for img in listar(src, n):
        a = analisar(img)
        md = a.get("laudo_rx_markdown") or ""
        (out / f"{img.stem}.md").write_text(md, encoding="utf-8")
        feitos.append(out / f"{img.stem}.md")
        with open(out / f"{img.stem}.severidade.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CABECALHO)
            for s in (a.get("laudo_rx") or {}).get("secoes", []):
                for fr in s["frases"]:
                    w.writerow([img.name, fr["texto"], fr["nivel"], "", ""])
    return feitos


def main(argv=None) -> int:
    raiz = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(raiz / "data" / "gold_rx"))
    ap.add_argument("--out", default=str(raiz / "data" / "rx_review"))
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args(argv)
    os.environ.setdefault("MEDLENS_RX_MODELS", "0")
    feitos = exportar(Path(a.src), Path(a.out), a.n)
    print(f"{len(feitos)} laudo(s) em {a.out}")
    return 0 if feitos else 1


if __name__ == "__main__":
    sys.exit(main())
