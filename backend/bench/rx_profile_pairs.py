"""Avalia a segmentação do PERFIL (heurística) e a reconstrução 3D em pares PA+perfil do mesmo paciente.

Dados: PAX-Ray++ (CC BY-NC, só avaliação) — radiografias SINTÉTICAS projetadas de TC, com máscaras de
pseudo-rótulo (não são ground truth de radiologista nem RX clínico real). As imagens e máscaras são lidas pelo
caminho absoluto e NUNCA copiadas para o repositório.

Uso (servidor de teste já no ar):
    PYTHONPATH=backend python backend/bench/rx_profile_pairs.py --n 40 --recon 6 --out /tmp/pares.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import random
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path("/Users/macbook/medlens/data/datasets/rx_masks_other")
API = "http://localhost:8066/api"
# estrutura -> (chaves do pipeline no perfil, máscaras de pseudo-rótulo)
GT = {
    "pulmao": (("lung_field", "lungs"), ("left_lung", "right_lung")),
    "coracao": (("heart",), ("heart",)),
    "coluna": (("spine",), ("spine",)),
    "traqueia": (("trachea",), ("trachea",)),
}


def _png(b64: str) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")) > 127


def _gt(pair_id: str, names, shape) -> np.ndarray:
    out = np.zeros(shape, bool)
    for n in names:
        f = ROOT / "masks" / pair_id / f"{n}.png"
        if f.exists():
            m = np.asarray(Image.open(f).convert("L").resize(shape[::-1], Image.NEAREST)) > 127
            out |= m
    return out


def iou(a: np.ndarray, b: np.ndarray) -> float | None:
    u = (a | b).sum()
    return None if u == 0 else float((a & b).sum() / u)


def eval_pair(stem: str, recon: bool) -> dict:
    fr, la = f"{stem}_frontal.png", f"{stem}_lateral.png"
    r = requests.post(f"{API}/ingest", files=[("files", open(ROOT / "images" / fr, "rb")),
                                              ("files", open(ROOT / "images" / la, "rb"))])
    sid = r.json()["studies"][0]["study_id"]
    a = requests.post(f"{API}/rx/{sid}/analyze", json={}).json()
    res: dict = {"par": stem, "study": sid, "views": [i["view"] for i in a["images"]]}
    lat = [i for i in a["images"] if i["view"] == "LATERAL"]
    res["lateral_detectada"] = bool(lat)
    if lat:
        im = lat[0]
        keys = {s["key"]: _png(s["mask_png_b64"]) for s in im["structures"] if s.get("mask_png_b64")}
        res["perfil_estruturas"] = sorted(keys)
        shape = (im["height"], im["width"])
        res["iou"] = {}
        for nome, (pk, gk) in GT.items():
            pred = np.zeros(shape, bool)
            for k in pk:
                if k in keys:
                    pred |= keys[k]
            g = _gt(f"{stem}_lateral", gk, shape)
            res["iou"][nome] = {"presente": bool(pred.any()), "iou": iou(pred, g) if g.any() else None,
                                "gt_px": int(g.sum()), "pred_px": int(pred.sum()),
                                "prec": float((pred & g).sum() / pred.sum()) if pred.any() else None,
                                "rec": float((pred & g).sum() / g.sum()) if g.any() else None}  # sem máscara de pseudo-rótulo (pulmão no perfil): iou=None
    if recon:
        b = requests.post(f"{API}/rx/{sid}/recon3d", json={})
        res["recon_status"] = b.status_code
        if b.status_code == 200:
            res["recon_meshes"] = [m["key"] for m in b.json()["meshes"]]
        else:
            res["recon_erro"] = b.json().get("detail", "")[:160]
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--recon", type=int, default=6, help="quantos pares também passam por /recon3d")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    stems = sorted(p.name[: -len("_frontal.png")] for p in (ROOT / "images").glob("*_frontal.png")
                   if (ROOT / "images" / (p.name.replace("_frontal", "_lateral"))).exists())
    random.Random(args.seed).shuffle(stems)
    out = [eval_pair(s, i < args.recon) for i, s in enumerate(stems[: args.n])]
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for nome in GT:
        v = [r["iou"][nome]["iou"] for r in out if r.get("iou") and r["iou"][nome]["iou"] is not None]
        pres = [r["iou"][nome]["presente"] for r in out if r.get("iou")]
        print(f"{nome}: segmentado em {sum(pres)}/{len(pres)} perfis detectados; IoU médio (todos, ausente=0) "
              f"{np.mean(v) if v else float('nan'):.2f}")
    for nome in ("coracao", "coluna", "traqueia"):
        pr = [r["iou"][nome]["prec"] for r in out if r.get("iou") and r["iou"][nome]["prec"] is not None]
        rc = [r["iou"][nome]["rec"] for r in out if r.get("iou") and r["iou"][nome]["rec"] is not None]
        print(f"{nome}: precisão média {np.mean(pr) if pr else float('nan'):.2f} | cobertura média {np.mean(rc) if rc else float('nan'):.2f}")
    print("perfil classificado como lateral:", sum(r["lateral_detectada"] for r in out), "/", len(out))
    print("3D montado:", sum(r.get("recon_status") == 200 for r in out), "/", sum("recon_status" in r for r in out))


if __name__ == "__main__":
    main()
