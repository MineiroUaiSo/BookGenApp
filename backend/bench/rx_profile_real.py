"""Overlays e métricas da segmentação do PERFIL em RX REAIS (NLM Open-i / Indiana University, CC BY-NC-ND).

SOMENTE avaliação local: as imagens são lidas pelo caminho absoluto e NUNCA são copiadas para o repositório nem
commitadas (os overlays vão para ~/medlens-shots, fora do repositório). Sem rótulo de referência: as métricas são
descritivas (área, marca de estimativa, lado da coluna) e a avaliação é visual.

Uso:
    cd backend && PYTHONPATH=. python bench/rx_profile_real.py            # 5 pares do lote D4
    cd backend && PYTHONPATH=. python bench/rx_profile_real.py --out ~/medlens-shots --prefix d4
"""
from __future__ import annotations

import argparse
import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from app.rx._common import PALETTE
from app.rx.analyze import analyze_image

PAIRS = Path("/Users/macbook/medlens-openi/pairs")
IDS = ("CXR1000", "CXR1208", "CXR1521", "CXR2915", "CXR3971")
TILE_H = 520


def _mask(b64: str) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")) > 127


def overlay(img: np.ndarray, structures) -> np.ndarray:
    """Preenchimento translúcido para estruturas com sinal; só contorno para diafragma e estimativas."""
    rgb = np.stack([img / 255.0] * 3, -1)
    for st in structures:
        m = _mask(st.mask_png_b64)
        c = np.array([int(PALETTE[st.key][2][i:i + 2], 16) for i in (1, 3, 5)]) / 255.0
        if st.key == "diaphragm" or "estimativa" in st.label:
            rgb[m ^ ndi.binary_erosion(m, iterations=2)] = c
        else:
            rgb[m] = rgb[m] * 0.55 + c * 0.45
    return (rgb * 255).astype(np.uint8)


def run(ids, out_dir: Path, prefix: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        files = sorted((PAIRS / cid).glob("*-2001.png"))
        if not files:
            print(f"{cid}: sem perfil (-2001.png)")
            continue
        img = np.asarray(Image.open(files[0]).convert("L"))
        a = analyze_image(img, cid)
        tile = Image.fromarray(overlay(img, a.structures))
        tile = tile.resize((int(tile.width * TILE_H / tile.height), TILE_H))
        dest = out_dir / f"{prefix}-{cid}.png"
        tile.save(dest)
        total = img.shape[0] * img.shape[1]
        parts = []
        for st in a.structures:
            area = int(_mask(st.mask_png_b64).sum())
            tag = "ESTIMATIVA" if "estimativa" in st.label else "sinal"
            parts.append(f"{st.key} {100 * area / total:.1f}% conf {st.confidence:.2f} {tag}")
        print(f"{cid} {a.view.value} | coluna: {a.quality.get('orientação', '?')} | " + "; ".join(parts))
        print(f"   overlay: {dest}")
    # painel com os cinco, lado a lado
    tiles = [Image.open(out_dir / f"{prefix}-{c}.png") for c in ids if (out_dir / f"{prefix}-{c}.png").exists()]
    if tiles:
        panel = Image.new("RGB", (sum(t.width for t in tiles), TILE_H))
        x = 0
        for t in tiles:
            panel.paste(t, (x, 0))
            x += t.width
        panel.save(out_dir / f"{prefix}-lateral-overlay.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "medlens-shots"))
    ap.add_argument("--prefix", default="d4")
    ap.add_argument("--ids", nargs="*", default=list(IDS))
    args = ap.parse_args()
    run(args.ids, Path(args.out), args.prefix)


if __name__ == "__main__":
    main()
