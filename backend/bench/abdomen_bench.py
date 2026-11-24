"""Benchmark de abdome (esqueleto). Spec: docs/benchmarks/abdome_spec.md

    python -m bench.abdomen_bench flow [--dir DIR] [--json OUT]
    python -m bench.abdomen_bench drr --ct ct.nii.gz --masks-dir DIR [--axis 1]
    python -m bench.abdomen_bench gas --csv anot.csv

Modos: flow (regiao/incidencia/polaridade em DICOM), drr (DRR AP de TC + Dice), gas (MAE de diametro de alca vs CSV).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from bench.report import pct, table

DEFAULT_DICOM_DIR = "~/Downloads/dicom-exemplos"
EXPECTED_REGIONS = {"abdome": {"abdomen", "pelvis"}, "torax": {"chest"}}
MU_WATER = 0.02   # mm^-1; so escala, o DRR e normalizado
GAS_THRESHOLD_MM = 60.0


# ---------------------------------------------------------------- flow
def dicom_dir() -> Path:
    return Path(os.environ.get("MEDLENS_DICOM_EXAMPLES", DEFAULT_DICOM_DIR)).expanduser()


def find_dicoms(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.dcm") if p.is_file())


def expected_regions(path: Path, root: Path) -> Optional[set[str]]:
    """Verdade de regiao pela subpasta de topo (abdome/torax)."""
    try:
        top = path.relative_to(root).parts[0]
    except ValueError:
        return None
    return EXPECTED_REGIONS.get(top)


def _tag(ds: Any, name: str) -> str:
    v = getattr(ds, name, None)
    return "" if v is None else str(v)


def _header_row(path: Path) -> dict:
    """Linha minima so com o cabecalho (usada quando o pixel data nao decodifica)."""
    import pydicom

    row = {"file": f"{path.parent.name}/{path.name}"}
    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        row.update(photometric=_tag(ds, "PhotometricInterpretation"), view_tag=_tag(ds, "ViewPosition"),
                   body_part=_tag(ds, "BodyPartExamined"), modality=_tag(ds, "Modality"),
                   transfer_syntax=_tag(getattr(ds, "file_meta", None), "TransferSyntaxUID"))
    except Exception:  # noqa: BLE001
        pass
    return row


def flow_one(path: Path, root: Path, use_model: bool = False) -> dict:
    from app.dicom.render import load_dicom, render_to_uint8
    from app.rx.analyze import analyze_image

    ds = load_dicom(path)
    img = render_to_uint8(ds)
    a = analyze_image(img, path.parent.name, ds, use_model=use_model)
    exp = expected_regions(path, root)
    region = a.region.value if hasattr(a.region, "value") else str(a.region)
    notes = list(getattr(a, "notes", []) or [])
    return {
        "file": f"{path.parent.name}/{path.name}", "modality": _tag(ds, "Modality"),
        "photometric": _tag(ds, "PhotometricInterpretation"), "view_tag": _tag(ds, "ViewPosition"),
        "body_part": _tag(ds, "BodyPartExamined"), "region": region,
        "view": a.view.value if hasattr(a.view, "value") else str(a.view),
        "extra_inversion": any("polaridade invertida" in n for n in notes),
        "expected": sorted(exp) if exp else None,
        "region_ok": (region in exp) if exp else None,
    }


def run_flow(root: Path, use_model: bool = False) -> dict:
    rows = []
    for p in find_dicoms(root):
        try:
            rows.append(flow_one(p, root, use_model))
        except Exception as e:  # noqa: BLE001 - bench deve seguir
            rows.append({**_header_row(p), "error": f"{type(e).__name__}: {str(e)[:70]}"})
    scored = [r for r in rows if r.get("region_ok") is not None]
    ok = sum(1 for r in scored if r["region_ok"])
    return {"n": len(rows), "n_undecodable": sum(1 for r in rows if "error" in r),
            "region_accuracy": pct(ok, len(scored)) if scored else "-", "rows": rows}


def flow_markdown(res: dict) -> str:
    hdr = ["arquivo", "photometric", "view_tag", "body_part", "regiao", "incid.", "inv. extra", "esperado", "ok"]
    rs = [[r["file"], r.get("photometric", ""), r.get("view_tag", ""), r.get("body_part", ""), r.get("region", r.get("error", "")),
           r.get("view", ""), r.get("extra_inversion", ""), "/".join(r.get("expected") or []), r.get("region_ok", "")]
          for r in res["rows"]]
    return table(rs, hdr)


# ---------------------------------------------------------------- drr
def drr_ap(volume_hu: np.ndarray, axis: int = 1) -> np.ndarray:
    """DRR por soma de atenuacao ao longo de 'axis' (AP). HU -> mu linear; normaliza 0..1 (Beer-Lambert)."""
    mu = MU_WATER * np.clip(1.0 + volume_hu.astype(np.float32) / 1000.0, 0.0, None)
    line = mu.sum(axis=axis)
    d = 1.0 - np.exp(-(line - line.min()) / max(float(np.ptp(line)), 1e-6) * 3.0)
    return (d / max(float(d.max()), 1e-6)).astype(np.float32)


def project_mask(mask: np.ndarray, axis: int = 1) -> np.ndarray:
    return np.asarray(mask, bool).any(axis=axis)


def dice(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    s = a.sum() + b.sum()
    return 1.0 if s == 0 else float(2 * (a & b).sum() / s)


def dice_by_structure(pred: dict[str, np.ndarray], gt: dict[str, np.ndarray]) -> dict[str, float]:
    return {k: dice(pred[k], gt[k]) for k in gt if k in pred}


def _load_nifti(path: Path) -> np.ndarray:
    try:
        import nibabel as nib  # opcional
    except ImportError as e:
        raise SystemExit("nibabel nao instalado (requirements-optional); modo drr real indisponivel") from e
    return np.asarray(nib.load(str(path)).dataobj)


def run_drr(ct: Path, masks_dir: Path, axis: int = 1) -> dict:
    vol = _load_nifti(ct)
    gt = {p.name.split(".")[0]: project_mask(_load_nifti(p), axis) for p in sorted(masks_dir.glob("*.nii*"))}
    return {"drr_shape": list(drr_ap(vol, axis).shape), "structures": sorted(gt),
            "note": "Dice vs heuristica: conectar segment_abdomen ao DRR quando houver TC real"}


# ---------------------------------------------------------------- gas
def read_gas_csv(path: Path) -> list[dict]:
    """CSV: image,diameter_mm. Levanta ValueError se faltar coluna/valor invalido."""
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or not {"image", "diameter_mm"} <= set(rd.fieldnames):
            raise ValueError("CSV precisa das colunas image,diameter_mm")
        out = []
        for i, r in enumerate(rd, 2):
            try:
                d = float(r["diameter_mm"])
            except (TypeError, ValueError) as e:
                raise ValueError(f"linha {i}: diameter_mm invalido") from e
            out.append({"image": (path.parent / r["image"]).as_posix(), "diameter_mm": d})
        return out


def gas_metrics(gt: list[float], pred: list[Optional[float]]) -> dict:
    pairs = [(g, p) for g, p in zip(gt, pred) if p is not None]
    if not pairs:
        return {"n": 0, "mae_mm": None, "bias_mm": None, "coverage": pct(0, len(gt))}
    err = np.array([p - g for g, p in pairs])
    tp = sum(1 for g, p in pairs if g >= GAS_THRESHOLD_MM and p >= GAS_THRESHOLD_MM)
    fn = sum(1 for g, p in pairs if g >= GAS_THRESHOLD_MM and p < GAS_THRESHOLD_MM)
    return {"n": len(pairs), "mae_mm": float(np.abs(err).mean()), "bias_mm": float(err.mean()),
            "coverage": pct(len(pairs), len(gt)), "sens_60mm": pct(tp, tp + fn) if tp + fn else "-"}


def run_gas(csv_path: Path, use_model: bool = False) -> dict:
    from app.dicom.render import load_dicom, render_to_uint8
    from app.rx.analyze import analyze_image

    rows = read_gas_csv(csv_path)
    preds: list[Optional[float]] = []
    for r in rows:
        try:
            p = Path(r["image"])
            ds = load_dicom(p) if p.suffix.lower() == ".dcm" else None
            if ds is not None:
                img = render_to_uint8(ds)
            else:
                from PIL import Image
                img = np.asarray(Image.open(p).convert("L"))
            a = analyze_image(img, p.stem, ds, use_model=use_model)
            m = next((x for x in a.measurements if x.name == "max_gas_lumen_diameter" and x.unit == "mm"), None)
            preds.append(float(m.value) if m else None)
        except Exception:  # noqa: BLE001
            preds.append(None)
    return gas_metrics([r["diameter_mm"] for r in rows], preds)


# ---------------------------------------------------------------- cli
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="bench.abdomen_bench")
    sub = ap.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("flow")
    f.add_argument("--dir", type=Path, default=None)
    f.add_argument("--model", action="store_true")
    f.add_argument("--json", type=Path, default=None)
    d = sub.add_parser("drr")
    d.add_argument("--ct", type=Path, required=True)
    d.add_argument("--masks-dir", type=Path, required=True)
    d.add_argument("--axis", type=int, default=1)
    g = sub.add_parser("gas")
    g.add_argument("--csv", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.mode == "flow":
        res = run_flow(args.dir or dicom_dir(), args.model)
        print(f"regiao: {res['region_accuracy']} (n={res['n']}, sem decodificar={res['n_undecodable']})\n")
        print(flow_markdown(res))
        if args.json:
            args.json.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    elif args.mode == "drr":
        print(json.dumps(run_drr(args.ct, args.masks_dir, args.axis), indent=1))
    else:
        print(json.dumps(run_gas(args.csv), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
