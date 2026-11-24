"""Avaliação EXTERNA gratuita de nódulo no JSRT (154 com nódulo, 93 sem) com o escore Nodule do TorchXRayVision.

    python -m bench.jsrt_nodule [--workers 3] [--max-side 1024] [--cache PATH] [--out-json PATH]

Nada é ajustado aqui: AUC + IC95% bootstrap, sens/espec no limiar-padrão do app (0,65) e sens a 90% de espec (limiar
derivado dos próprios negativos do JSRT: número DESCRITIVO, não limiar a adotar). Rótulos = manifest local
(labels rx.nodule / rx.normal; ids JPCLN = nódulo, JPCNN = sem nódulo). Escores 1 imagem por estudo (PA).
Caveat: JSRT não foi usado para ajustar nada neste repositório de calibração; a presença nos dados de treino do TXRV não foi verificada.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bench.rx_bench import auc_ci, load_gray, wilson  # noqa: E402

DEFAULT_THR = 0.65


def _score(task: tuple[str, str, int]) -> dict:
    from bench.rx_bench import _analyze, _fake_ds
    iid, path, max_side = task
    try:
        a, _ = _analyze(load_gray(Path(path), max_side), iid, "model", _fake_ds("PA"))
        return {"id": iid, "scores": {k: a.model_scores.get(k) for k in ("Nodule", "Mass", "Lung Lesion")}}
    except Exception as e:  # keep going; counted as error
        return {"id": iid, "error": str(e)[:120]}


def sens_at_spec(y, s, spec: float = 0.90) -> dict:
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    neg = np.sort(s[~y])
    t = neg[int(np.ceil(spec * len(neg))) - 1] if len(neg) else 1.0   # >= spec of negatives are <= t
    pred = s > t
    tp, fn = int((y & pred).sum()), int((y & ~pred).sum())
    tn, fp = int((~y & ~pred).sum()), int((~y & pred).sum())
    return {"threshold": float(t), "sens": tp / (tp + fn), "sens_ci": list(wilson(tp, tp + fn)),
            "spec": tn / (tn + fp), "spec_ci": list(wilson(tn, tn + fp))}


def evaluate(y, s, n_boot: int = 1000) -> dict:
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    a, lo, hi = auc_ci(y, s, n_boot=n_boot)
    pred = s >= DEFAULT_THR
    tp, fn = int((y & pred).sum()), int((y & ~pred).sum())
    tn, fp = int((~y & ~pred).sum()), int((~y & pred).sum())
    return {"n": len(y), "pos": int(y.sum()), "auc": a, "auc_ci": [lo, hi],
            "at_default_0.65": {"sens": tp / (tp + fn), "sens_ci": list(wilson(tp, tp + fn)),
                                "spec": tn / (tn + fp), "spec_ci": list(wilson(tn, tn + fp))},
            "at_spec90_descriptive": sens_at_spec(y, s, 0.90)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.jsrt_nodule")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--cache", type=Path, default=None, help="JSON com escores por id (reuso; contém só ids públicos JSRT)")
    ap.add_argument("--out-json", type=Path, default=None)
    a = ap.parse_args(argv)
    from medlens_data import read_manifest
    from bench.rx_bench import data_root
    root = data_root() / "jsrt_masks"
    recs = [r for r in read_manifest("jsrt_masks") if r.kind == "image" and (root / r.path).exists()]
    lab = {r.id: ("rx.nodule" in r.labels) for r in recs if ("rx.nodule" in r.labels) != ("rx.normal" in r.labels)}
    if a.cache and a.cache.exists():
        res = json.loads(a.cache.read_text())
    else:
        tasks = [(r.id, str(root / r.path), a.max_side) for r in recs if r.id in lab]
        with ProcessPoolExecutor(a.workers) as ex:
            res = list(ex.map(_score, tasks))
        if a.cache:
            a.cache.write_text(json.dumps(res))
    ok = [r for r in res if "error" not in r and r["scores"].get("Nodule") is not None]
    print(f"imagens: {len(res)} avaliadas, {len(ok)} com escore, {len(res) - len(ok)} erro/sem modelo")
    out = {}
    for name, fn in (("Nodule", lambda r: r["scores"]["Nodule"]),
                     ("max(Nodule,Mass)", lambda r: max(r["scores"]["Nodule"], r["scores"].get("Mass") or 0.0))):
        out[name] = ev = evaluate([lab[r["id"]] for r in ok], [fn(r) for r in ok])
        d, s90 = ev["at_default_0.65"], ev["at_spec90_descriptive"]
        print(f"{name}: n={ev['n']} pos={ev['pos']} AUC={ev['auc']:.3f} [{ev['auc_ci'][0]:.3f},{ev['auc_ci'][1]:.3f}] | "
              f"@0.65 sens={d['sens']:.3f} [{d['sens_ci'][0]:.3f},{d['sens_ci'][1]:.3f}] spec={d['spec']:.3f} | "
              f"sens@spec90={s90['sens']:.3f} [{s90['sens_ci'][0]:.3f},{s90['sens_ci'][1]:.3f}] (spec={s90['spec']:.3f}, thr={s90['threshold']:.3f})")
    if a.out_json:
        a.out_json.write_text(json.dumps(out, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
