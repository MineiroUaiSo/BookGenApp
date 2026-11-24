"""CXAS runner: executed by the SEPARATE venv (/Users/macbook/medlens-venvs/cxas), never imported by the server.

Usage: python cxas_runner.py --out DIR [--model M2F_anatomy_v2] [--device auto|cpu|mps] [--view auto|frontal|lateral] IMG...
IMG: .png/.jpg/.dcm. Prints ONE JSON object on the last stdout line:
  {"ok": true, "device": ..., "load_s": ..., "results": [{"image", "view", "t", "shape", "masks": {key: png_path}}]}
Masks are 0/255 PNGs at the input image resolution, one per MedLens key (see KEYMAP). Stdlib + numpy + PIL + cxas only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# MedLens key -> CXAS structure name(s) (union). Names follow cxas.label_mapper.
KEYMAP = {
    "heart": ["heart"], "aorta": ["aorta"], "spine": ["spine"], "sternum": ["sternum"], "trachea": ["trachea"],
    "cardiomediastinum": ["cardiomediastinum"],
    "left_lung": ["left lung"], "right_lung": ["right lung"],
    "left_clavicle": ["clavicle left"], "right_clavicle": ["clavicle right"],
    "left_scapula": ["scapula left"], "right_scapula": ["scapula right"],
    "left_hemidiaphragm": ["left hemidiaphragm"], "right_hemidiaphragm": ["right hemidiaphragm"],
}
RIB_RE = re.compile(r"^(anterior|posterior) \d+(st|nd|rd|th) rib (left|right)$")


def _union(pred, index, names):
    import numpy as np
    out = None
    for n in names:
        i = index.get(n)
        if i is None:
            continue
        m = pred[i].cpu().numpy().astype(bool)
        out = m if out is None else (out | m)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="M2F_anatomy_v2")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--view", default="auto", choices=["auto", "frontal", "lateral"])
    ap.add_argument("images", nargs="+")
    a = ap.parse_args(argv)
    try:
        import numpy as np
        import torch
        from PIL import Image
        from cxas import CXAS
        from cxas.label_mapper import id2label_dict

        dev = a.device
        if dev == "auto":
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
        names = [id2label_dict[str(i)].strip() for i in range(len(id2label_dict))]
        index = {n: i for i, n in enumerate(names)}
        ribs = {"ribs_left": [n for n in names if RIB_RE.match(n) and n.endswith("left")],
                "ribs_right": [n for n in names if RIB_RE.match(n) and n.endswith("right")]}
        t0 = time.perf_counter()
        # CXAS only knows cpu/cuda; MPS is attempted by moving the bundles by hand (CPU fallback on error)
        model = CXAS(model_name=a.model, gpus="cpu")
        if dev == "mps":
            try:
                for b in model.model.bundles.values():
                    b.model = b.model.to("mps")
                    b.device = torch.device("mps")
                model.model.device_ = torch.device("mps")
            except Exception:
                dev = "cpu"
        if a.view != "auto" and hasattr(model.model, "view_override"):
            model.model.view_override = a.view
        load_s = time.perf_counter() - t0
        os.makedirs(a.out, exist_ok=True)
        results = []
        for k, path in enumerate(a.images):
            d = os.path.join(a.out, "%05d" % k)
            os.makedirs(d, exist_ok=True)
            t1 = time.perf_counter()
            pred = model.process_file(path)
            seg = pred["segmentation_preds"][0]
            dt = time.perf_counter() - t1
            masks = {}
            for key, nn_ in list(KEYMAP.items()) + list(ribs.items()):
                m = _union(seg, index, KEYMAP.get(key) or ribs[key])
                if m is None:
                    continue
                p = os.path.join(d, key + ".png")
                Image.fromarray((m * 255).astype("uint8")).save(p)
                masks[key] = p
            view = pred.get("view")
            results.append({"image": path, "view": view[0] if isinstance(view, list) and view else view,
                            "t": round(dt, 4), "shape": list(seg.shape[-2:]), "masks": masks})
        print(json.dumps({"ok": True, "device": dev, "load_s": round(load_s, 3), "results": results}))
        return 0
    except Exception as e:  # report as JSON so the caller can fall back
        print(json.dumps({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
