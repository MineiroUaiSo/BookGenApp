"""Region bench on real DICOMs (dicom-exemplos): expected region per folder, categories 'ok' / 'tag divergente'.

python -m bench.rx_region_bench [--mode model|heur] [--root DIR] [--out FILE.md]
Never versions or uploads the DICOMs; only prints folder names and results.
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

EXPECTED = {"torax": "chest", "abdome": "abdomen", "torax-tag-errada": "chest"}


def run(root: Path, use_model: bool) -> list[dict]:
    from app.dicom.render import load_dicom, render_to_uint8
    from app.rx.analyze import analyze_image
    rows = []
    for p in sorted(glob.glob(str(root / "*" / "*" / "*.dcm"))):
        parts = Path(p).parts
        folder, case = parts[-3], parts[-2]
        if folder not in EXPECTED:
            continue
        ds = load_dicom(p)
        a = analyze_image(render_to_uint8(ds), "b", ds, use_model=use_model)
        tag = str(getattr(ds, "BodyPartExamined", "") or "")
        divergent = bool(tag) and (tag.lower()[:3] == "abd") != (EXPECTED[folder] == "abdomen")
        rows.append({"case": f"{folder}/{case}", "tag": tag, "expected": EXPECTED[folder], "region": a.region.value,
                     "view": a.view.value, "correct": a.region.value == EXPECTED[folder],
                     "tag_divergent": divergent, "warned": a.region_conflict or a.region_uncertain,
                     "uncertain": a.region_uncertain})
    return rows


def table(rows: list[dict]) -> str:
    out = ["| caso | tag | esperado | obtido | correto | tag divergente | aviso |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['case']} | {r['tag']} | {r['expected']} | {r['region']} | {r['correct']} | "
                   f"{r['tag_divergent']} | {r['warned']} |")
    n = len(rows)
    div = [r for r in rows if r["tag_divergent"]]
    out.append("")
    out.append(f"região correta: {sum(r['correct'] for r in rows)}/{n}")
    out.append(f"categoria 'tag divergente': {sum(r['correct'] for r in div)}/{len(div)} corretos, "
               f"{sum(r['warned'] for r in div)}/{len(div)} com aviso")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["model", "heur"], default="model")
    ap.add_argument("--root", default=os.environ.get("MEDLENS_DICOM_EXAMPLES",
                                                    str(Path.home() / "Downloads" / "dicom-exemplos")))
    ap.add_argument("--out")
    a = ap.parse_args()
    md = table(run(Path(a.root), a.mode == "model"))
    print(md)
    if a.out:
        Path(a.out).write_text(md + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
