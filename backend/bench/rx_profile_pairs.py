"""Avalia a segmentação do PERFIL (heurística) e a reconstrução 3D em pares PA+perfil do mesmo paciente.

Dados: PAX-Ray++ (CC BY-NC, só avaliação) — radiografias SINTÉTICAS projetadas de TC, com máscaras de
pseudo-rótulo (não são ground truth de radiologista nem RX clínico real). As imagens e máscaras são lidas pelo
caminho absoluto e NUNCA copiadas para o repositório.

Uso (servidor de teste já no ar):
    PYTHONPATH=backend python backend/bench/rx_profile_pairs.py --n 40 --recon 6 --out /tmp/pares.json
Uso sem servidor (pipeline em processo, só o perfil; D4: antes/depois da segmentação lateral):
    cd backend && PYTHONPATH=. python bench/rx_profile_pairs.py --inproc --n 40 --out /tmp/pares_d4.json
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


def _analyze_inproc(stem: str) -> tuple[str, dict]:
    """Roda `analyze_image` direto no PNG lateral (sem servidor) e devolve o mesmo formato do /analyze."""
    from app.rx.analyze import analyze_image
    img = np.asarray(Image.open(ROOT / "images" / f"{stem}_lateral.png").convert("L"))
    return stem, {"images": [analyze_image(img, stem).model_dump()]}


def _analyze_remote(stem: str) -> tuple[str, dict]:
    r = requests.post(f"{API}/ingest", files=[("files", open(ROOT / "images" / f"{stem}_frontal.png", "rb")),
                                              ("files", open(ROOT / "images" / f"{stem}_lateral.png", "rb"))])
    sid = r.json()["studies"][0]["study_id"]
    return sid, requests.post(f"{API}/rx/{sid}/analyze", json={}).json()


def _lung_proxy(stem: str, keys: dict, shape) -> dict:
    """Sem máscara de pulmão no perfil, só proxies fracos (relativos, antes/depois):
    y_iou = IoU da extensão vertical do campo pulmonar contra a dos pulmões da PA do mesmo paciente (mesma TC);
    box_iou = IoU contra a caixa [linhas dos pulmões da PA] x [colunas entre os centros de coluna e esterno]
    do pseudo-rótulo (o pulmão projetado ocupa mais ou menos essa caixa)."""
    pred = np.zeros(shape, bool)
    for k in ("lung_field", "lungs"):
        if k in keys:
            pred |= keys[k]
    if not pred.any():
        return {"presente": False}
    fr = _gt(f"{stem}_frontal", ("left_lung", "right_lung"), shape)
    sp, stn = _gt(f"{stem}_lateral", ("spine",), shape), _gt(f"{stem}_lateral", ("sternum",), shape)
    out = {"presente": True, "area_frac": float(pred.mean())}
    if fr.any():
        a, b = pred.any(axis=1), fr.any(axis=1)
        out["y_iou"] = float((a & b).sum() / (a | b).sum())
        if sp.any() and stn.any():
            xs = sorted((np.nonzero(sp)[1].mean(), np.nonzero(stn)[1].mean()))
            box = np.zeros(shape, bool)
            box[np.ix_(b, (np.arange(shape[1]) >= xs[0]) & (np.arange(shape[1]) <= xs[1]))] = True
            out["box_iou"] = iou(pred, box)
    return out


def eval_pair(stem: str, recon: bool, inproc: bool = False) -> dict:
    sid, a = _analyze_inproc(stem) if inproc else _analyze_remote(stem)
    recon = recon and not inproc
    res: dict = {"par": stem, "study": sid, "views": [i["view"] for i in a["images"]]}
    lat = [i for i in a["images"] if i["view"] == "LATERAL"]
    res["lateral_detectada"] = bool(lat)
    if lat:
        im = lat[0]
        keys = {s["key"]: _png(s["mask_png_b64"]) for s in im["structures"] if s.get("mask_png_b64")}
        res["perfil_estruturas"] = sorted(keys)
        res["estruturas_meta"] = {s["key"]: {"conf": s["confidence"], "origin": s["origin"], "label": s["label"]}
                                  for s in im["structures"]}
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
        res["pulmao_proxy"] = _lung_proxy(stem, keys, shape)
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
    ap.add_argument("--inproc", action="store_true", help="pipeline em processo (sem servidor), só o perfil")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    stems = sorted(p.name[: -len("_frontal.png")] for p in (ROOT / "images").glob("*_frontal.png")
                   if (ROOT / "images" / (p.name.replace("_frontal", "_lateral"))).exists())
    random.Random(args.seed).shuffle(stems)
    out = [eval_pair(s, i < args.recon, args.inproc) for i, s in enumerate(stems[: args.n])]
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
    px = [r["pulmao_proxy"] for r in out if r.get("pulmao_proxy", {}).get("presente")]
    if px:
        m = lambda k: np.mean([p[k] for p in px if k in p])  # noqa: E731
        print(f"pulmão (proxy fraco): campo presente em {len(px)}/{len(out)}; IoU da extensão vertical (vs pulmões da PA) "
              f"{m('y_iou'):.2f}; IoU vs caixa coluna-esterno {m('box_iou'):.2f}; área média {m('area_frac'):.3f}")
    est = [r["estruturas_meta"] for r in out if r.get("estruturas_meta")]
    if est:
        marc = sum(any("estimativa" in v["label"] for v in e.values()) for e in est)
        print(f"perfis com alguma estrutura marcada como estimativa: {marc}/{len(est)}; "
              f"estruturas por perfil {np.mean([len(e) for e in est]):.2f}")
    print("perfil classificado como lateral:", sum(r["lateral_detectada"] for r in out), "/", len(out))
    print("3D montado:", sum(r.get("recon_status") == 200 for r in out), "/", sum("recon_status" in r for r in out))


if __name__ == "__main__":
    main()
