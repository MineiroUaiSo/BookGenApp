"""Collector "rx-masks": chest radiographs WITH pixel-level ground-truth masks (for segmentation Dice).

Sources actually reachable from the sandbox (huggingface.co *file* downloads are blocked: the HF xet CDN host
us.aws.cdn.hf.co is denied by the egress proxy, so HF-only mirrors cannot be fetched; Zenodo works):

  jsrt_masks    Zenodo 7056076 "SCR database" (van Ginneken 2006, CC BY 4.0): 247 JSRT PA images (the Zenodo copy
                is only 256x256 JPEG; the full 2048x2048 12-bit JSRT needs db.jsrt.or.jp, not reachable) +
                manual contour points (right/left lung, heart, right/left clavicle) rasterised here.
  montgomery    Montgomery County CXR set (NLM official zip from openi.nlm.nih.gov, 138 native-res images + lung
                masks) + heart & clavicle masks (Brioso et al., Zenodo 8108809, CC BY 4.0).
  shenzhen      Shenzhen CXR images (NLM zip, fetched member-wise by HTTP Range) + lung masks (Stirenko et al.,
                CC BY-NC-SA 4.0) from the Zenodo 14059288 mirror (only the 395 masks that exist there).
  rx_masks_other  PAX-Ray++ (Zenodo 23627483, CC BY-NC 4.0): synthetic frontal + LATERAL radiographs projected from
                CT, with dense masks (ribs, trachea, clavicles, heart, lungs ...); test split only.

Patient-side convention: in a standard PA/AP display the patient's RIGHT is on the image LEFT.  So the structure
whose centroid lies on the image-left is "right_*".  For LATERAL views left/right is not defined; PAX-Ray++ lateral
masks keep the dataset's own names and are flagged view=LATERAL.

Raw JSRT format (if full-res files are ever obtained): 2048x2048, 12-bit stored as 16-bit BIG-endian unsigned, no
header, .IMG; read with numpy.fromfile(f, '>u2').reshape(2048, 2048). Pixel size 0.175 mm; check polarity
(some .IMG have bone dark) before display. SCR contours are given in 1024x1024 coordinates (the 2048 image downsampled by 2).
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from PIL import Image, ImageDraw

from medlens_data import DATA_ROOT, Record, source_dir, write_manifest

# --------------------------------------------------------------------------- generic mask utilities

def binarize(arr: np.ndarray, thr: int = 127) -> np.ndarray:
    """Antialiased / 0-255 / 0-1 mask -> bool. Values 0/1 are treated as already binary."""
    a = np.asarray(arr)
    if a.ndim == 3:
        a = a[..., 0]
    if a.max() <= 1:
        return a.astype(bool)
    return a > thr


def split_left_right(mask: np.ndarray, min_frac: float = 0.02) -> tuple[np.ndarray, np.ndarray]:
    """Split a mask holding two separate structures (lungs, clavicles) into (image_left, image_right).

    Uses the two largest connected components (merged lungs touching in the middle are cut at the column
    midpoint of the union bounding box instead). Returns bool arrays; either may be empty.
    """
    from scipy import ndimage as ndi

    m = np.asarray(mask, dtype=bool)
    lab, n = ndi.label(m)
    if n >= 2:
        sizes = ndi.sum(m, lab, index=range(1, n + 1))
        order = np.argsort(sizes)[::-1]
        big = [int(i) + 1 for i in order[:2] if sizes[i] >= min_frac * max(sizes.max(), 1)]
        if len(big) == 2:
            cx = [ndi.center_of_mass(m, lab, b)[1] for b in big]
            lo, hi = (big[0], big[1]) if cx[0] <= cx[1] else (big[1], big[0])
            return lab == lo, lab == hi
    # single blob (touching) or single component: cut at the middle column of the bounding box
    cols = np.where(m.any(axis=0))[0]
    if cols.size == 0:
        z = np.zeros_like(m)
        return z, z
    mid = (cols[0] + cols[-1]) // 2
    left, right = m.copy(), m.copy()
    left[:, mid + 1:] = False
    right[:, :mid + 1] = False
    return left, right


def centroid_x(mask: np.ndarray) -> float:
    xs = np.where(np.asarray(mask, bool).any(axis=0))[0]
    return float(xs.mean()) if xs.size else float("nan")


def polygon_mask(points: Iterable[tuple[float, float]], size: tuple[int, int], scale: float = 1.0) -> np.ndarray:
    """Rasterise a closed polygon (x, y) points to a bool mask of `size` = (width, height)."""
    pts = [(x * scale, y * scale) for x, y in points]
    im = Image.new("L", size, 0)
    ImageDraw.Draw(im).polygon(pts, fill=1, outline=1)
    return np.asarray(im, dtype=bool)


def parse_pfs(text: str) -> dict[str, list[tuple[float, float]]]:
    """Parse the SCR/ASM '.pfs' point-set files into {label: [(x, y), ...]} (skips *fixed* landmark sets)."""
    out: dict[str, list[tuple[float, float]]] = {}
    for block in re.split(r"\n\},?\s*\n", text):
        m = re.search(r"\[Label=([^\]]+)\]", block)
        if not m:
            continue
        label = m.group(1).strip()
        pts = [(float(a), float(b)) for a, b in re.findall(r"\{\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\}", block)]
        if pts and "fixed" not in label:
            out[label] = pts
    return out


def rle_decode(counts, size: tuple[int, int]) -> np.ndarray:
    """COCO RLE (uncompressed list or compressed str) -> bool (h, w) mask. size = (h, w)."""
    h, w = size
    if isinstance(counts, str):
        counts = _rle_str_to_counts(counts)
    flat = np.zeros(h * w, dtype=bool)
    pos, val = 0, False
    for c in counts:
        if val:
            flat[pos:pos + c] = True
        pos += c
        val = not val
    return flat.reshape((w, h)).T  # COCO RLE is column-major


def _rle_str_to_counts(s: str) -> list[int]:
    """Decode pycocotools' compressed RLE string."""
    cnts, p, m = [], 0, 0
    b = s.encode() if isinstance(s, str) else s
    while p < len(b):
        x, k, more = 0, 0, True
        while more:
            c = b[p] - 48
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and (c & 0x10):
                x |= -1 << (5 * k)
        if m > 2:
            x += cnts[m - 2]
        cnts.append(x)
        m += 1
    return cnts


def save_mask(mask: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.asarray(mask, bool) * 255).astype(np.uint8), "L").save(path, optimize=True)


def dice(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    s = a.sum() + b.sum()
    return 1.0 if s == 0 else float(2 * (a & b).sum() / s)


def _lic(name: str) -> tuple[str, str]:
    return LICENSES[name]


LICENSES = {
    "jsrt": ("CC BY 4.0 (SCR database, Zenodo 7056076; JSRT images (c) Japanese Society of Radiological Technology, "
             "free for research)",
             "van Ginneken B, Stegmann MB, Loog M. Med Image Anal 2006;10(1):19-40; Shiraishi J et al. AJR 2000;174:71-74"),
    "montgomery": ("NLM Montgomery CXR set (open for research; Zenodo mirror record 14059288 CC BY 4.0); heart/clavicle "
                   "masks CC BY 4.0 (Zenodo 8108809)",
                   "Jaeger S et al. Quant Imaging Med Surg 2014;4(6):475-477; Brioso R et al. CBMS 2023 (heart/clavicle masks)"),
    "shenzhen": ("Shenzhen CXR images: NLM open data; lung masks CC BY-NC-SA 4.0 (Stirenko et al. 2018); Zenodo "
                 "mirror 14059288 CC BY 4.0 record. NON-COMMERCIAL use only",
                 "Jaeger S et al. 2014; Stirenko S et al. IEEE UKRCON 2018 (arXiv:1803.01199)"),
    "paxrayplusplus": ("CC BY-NC 4.0 (PAX-Ray++, Zenodo 23627483) - non-commercial evaluation only; synthetic "
                       "(CT-projected) radiographs with pseudo-label masks, NOT radiologist ground truth",
                       "Seibold C et al. 'Accurate fine-grained segmentation of human anatomy in radiographs via "
                       "volumetric pseudo-labeling' 2023; Seibold C et al. BMVC 2022 (PAX-Ray)"),
}

# --------------------------------------------------------------------------- remote zip (HTTP Range) helper

class RangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range requests (lets zipfile pull single members from a multi-GB zip)."""

    def __init__(self, url: str, session=None, size: int = 0):
        import requests
        from medlens_data import USER_AGENT
        self.url, self.s = url, session or requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        import time
        self.size = size or 0
        for attempt in range(0 if self.size else 5):   # the proxy sometimes answers HEAD without Content-Length
            try:
                r = self.s.head(url, allow_redirects=True, timeout=60)
                if "Content-Length" in r.headers:
                    self.size = int(r.headers["Content-Length"])
                    break
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        if not self.size:
            raise RuntimeError("could not determine remote size")
        self.pos = 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        import time
        last = None
        for attempt in range(8):
            try:
                r = self.s.get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}, timeout=300)
                if r.status_code == 206 and len(r.content) == n:
                    self.pos += n
                    return r.content
                last = f"status {r.status_code} len {len(r.content)} != {n}"
            except Exception as e:  # proxy resets / timeouts
                last = repr(e)
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"range read failed at {self.pos}+{n}: {last}")

    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)


def fetch_shenzhen_images(zen_dir: Path, out_dir: Path, url: str = "https://openi.nlm.nih.gov/imgs/collections/ChinaSet_AllFiles.zip",
                          max_side: int = 1536, delay: float = 1.0) -> list[str]:
    """Download (via Range requests, one member at a time) only the Shenzhen images that have a lung mask in the
    Zenodo mask mirror, store them down-scaled (max_side) as 8-bit PNG in out_dir. Returns the stems fetched."""
    import time
    mz = zipfile.ZipFile(next(zen_dir.glob("train_masks-*.zip")))
    stems = sorted(Path(n).name[:-len("_mask.png")] for n in mz.namelist() if Path(n).name.startswith("CHN") and n.endswith("_mask.png"))
    out_dir.mkdir(parents=True, exist_ok=True)
    zf = zipfile.ZipFile(RangeFile(url, size=3770205534 if "ChinaSet" in url else 0))
    index = {Path(n).stem: n for n in zf.namelist() if n.lower().endswith(".png")}
    done = []
    for st in stems:
        dst = out_dir / f"{st}.png"
        if dst.exists():
            done.append(st); continue
        if st not in index:
            continue
        im = _png_to_8bit(Image.open(io.BytesIO(zf.read(index[st]))))
        meta = {"orig_size": list(im.size)}
        f = max_side / max(im.size)
        if f < 1:
            im = im.resize((round(im.width * f), round(im.height * f)), Image.BILINEAR)
        im.save(dst, optimize=True)
        (out_dir / f"{st}.json").write_text(json.dumps(meta))
        done.append(st)
        time.sleep(delay)
    return done


# --------------------------------------------------------------------------- JSRT / SCR

JSRT_LABELS = {"right lung": "right_lung", "left lung": "left_lung", "heart": "heart",
               "right clavicle": "right_clavicle", "left clavicle": "left_clavicle"}


def build_jsrt(raw: Optional[Path] = None, source: str = "jsrt_masks") -> list[Record]:
    """raw dir must hold the extracted Zenodo zips: jpg/jpg/*.jpg and points/*.pfs (or the zip files themselves)."""
    out_dir = source_dir(source)
    raw = raw or out_dir / "raw"
    work = out_dir / "_x"
    for z in ("jpg", "points"):
        zp = raw / f"{z}.zip"
        if zp.exists() and not (work / z).exists():
            zipfile.ZipFile(zp).extractall(work / z)
    recs = []
    for jpg in sorted((work / "jpg").rglob("*.jpg")):
        sid = jpg.stem
        pfs = next((work / "points").rglob(f"{sid}.pfs"), None)
        if pfs is None:
            continue
        shapes = parse_pfs(pfs.read_text(errors="replace"))
        im = Image.open(jpg).convert("L")
        w, h = im.size
        scale = w / 1024.0   # contours live in the 1024x1024 downsample of the 2048 original
        rel_img = f"images/{sid}.png"
        (out_dir / "images").mkdir(exist_ok=True)
        im.save(out_dir / rel_img)
        masks = {}
        for lab, name in JSRT_LABELS.items():
            if lab in shapes:
                rel = f"masks/{sid}/{name}.png"
                save_mask(polygon_mask(shapes[lab], (w, h), scale), out_dir / rel)
                masks[name] = rel
        nodule = sid.startswith("JPCLN")
        spec = _lic("jsrt")
        recs.append(Record(
            id=sid, source=source, modality="RX", kind="image", path=rel_img,
            url="https://zenodo.org/records/7056076", license=spec[0], attribution=spec[1],
            labels=["rx.nodule"] if nodule else ["rx.normal"], view="PA", group=sid,
            extra={"masks": masks, "image_size": [w, h], "orientation": "patient right = image left",
                   "pixel_spacing_mm": 0.175 * 2048 / w, "downscaled_from": 2048,
                   "note": "256px JPEG from Zenodo SCR; full-res JSRT not reachable",
                   "mask_source": "manual contours (SCR gold standard), rasterised"}))
    shutil.rmtree(work, ignore_errors=True)
    write_manifest(source, recs)
    return recs


# --------------------------------------------------------------------------- Montgomery + Shenzhen (Kaggle mirror)

def _png_to_8bit(im: Image.Image) -> Image.Image:
    if im.mode in ("I;16", "I"):
        a = np.asarray(im, dtype=np.float64)
        a = (a - a.min()) / max(a.max() - a.min(), 1) * 255
        return Image.fromarray(a.astype(np.uint8), "L")
    return im.convert("L")


def _resize_mask(m: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    if m.shape == (size[1], size[0]):
        return m
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize(size, Image.NEAREST)) > 127


def build_montgomery(official_zip: Path, mont_raw: Path, source: str = "montgomery") -> list[Record]:
    """NLM Montgomery County set (official zip) + Brioso heart/clavicle masks (Zenodo 8108809).

    NOTE: NLM names the lung masks in IMAGE perspective: 'leftMask' lies on the image-LEFT (centroid check on all
    138 cases) which is the patient's RIGHT (the R marker is on image-left). We therefore map leftMask->right_lung
    and rightMask->left_lung. Verified: the Brioso heart lies on the image-right in 137/138 cases."""
    d = source_dir(source)
    z = zipfile.ZipFile(official_zip)
    heart = zipfile.ZipFile(mont_raw / "masksheart.zip")
    clav = zipfile.ZipFile(mont_raw / "masksclavicles.zip")
    spec = _lic("montgomery")
    recs = []
    (d / "images").mkdir(exist_ok=True)
    for n in sorted(x for x in z.namelist() if x.startswith("MontgomerySet/CXR_png/MCUCXR_") and x.endswith(".png")):
        base = Path(n).stem
        rel_img = f"images/{base}.png"
        (d / rel_img).write_bytes(z.read(n))                      # original 8-bit PNG, native 4892x4020 / 4020x4892
        size = Image.open(d / rel_img).size
        masks = {}
        for zname, key in (("leftMask", "right_lung"), ("rightMask", "left_lung")):
            m = np.asarray(Image.open(io.BytesIO(z.read(f"MontgomerySet/ManualMask/{zname}/{base}.png")))) > 0
            rel = f"masks/{base}/{key}.png"; save_mask(_resize_mask(m, size), d / rel); masks[key] = rel
        try:
            hm = _resize_mask(binarize(np.asarray(Image.open(io.BytesIO(heart.read(f"masks_heart/{base}.png"))))), size)
            rel = f"masks/{base}/heart.png"; save_mask(hm, d / rel); masks["heart"] = rel
            cm = _resize_mask(binarize(np.asarray(Image.open(io.BytesIO(clav.read(f"masks_clavicles/{base}.png"))))), size)
            a, b = split_left_right(cm)   # image-left = patient right
            for nm, mm in (("right_clavicle", a), ("left_clavicle", b)):
                if mm.any():
                    rel = f"masks/{base}/{nm}.png"; save_mask(mm, d / rel); masks[nm] = rel
        except KeyError:
            pass
        txt = z.read(f"MontgomerySet/ClinicalReadings/{base}.txt").decode("utf8", "replace").strip()
        tb = base.endswith("_1")
        recs.append(Record(
            id=base, source=source, modality="RX", kind="image", path=rel_img,
            url="https://openi.nlm.nih.gov/imgs/collections/NLM-MontgomeryCXRSet.zip; https://zenodo.org/records/8108809",
            license=spec[0], attribution=spec[1] + ". Credit: National Library of Medicine, NIH, Bethesda MD, USA. "
            "Terms: do not share the dataset outside the research group/organisation.",
            caption=txt, labels=["rx.tuberculosis"] if tb else ["rx.normal"], view="PA", group=base,
            extra={"masks": masks, "image_size": list(size), "pixel_spacing_mm": 0.0875,
                   "orientation": "patient right = image left (R marker on image-left); NLM 'leftMask' is image-left",
                   "mask_source": "manual (lungs: NLM/Candemir; heart+clavicles: Brioso et al. 2023)"}))
    write_manifest(source, recs)
    return recs


def build_shenzhen(zen_dir: Path, img_dir: Path, source: str = "shenzhen") -> list[Record]:
    """Shenzhen CXR images (fetch_shenzhen_images output, down-scaled) + Stirenko lung masks (Zenodo mirror).
    The mirror's masks are one combined mask per image: split into patient-right (image-left) / patient-left."""
    d = source_dir(source)
    mz = zipfile.ZipFile(next(zen_dir.glob("train_masks-*.zip")))
    spec = _lic("shenzhen")
    recs = []
    (d / "images").mkdir(exist_ok=True)
    for png in sorted(img_dir.glob("CHNCXR_*.png")):
        base = png.stem
        try:
            raw = mz.read(f"train_masks/{base}_mask.png")
        except KeyError:
            continue
        im = Image.open(png)
        lung = _resize_mask(binarize(np.asarray(Image.open(io.BytesIO(raw)))), im.size)
        shutil.copyfile(png, d / "images" / png.name)
        a, b = split_left_right(lung)
        masks = {}
        for nm, mm in (("right_lung", a), ("left_lung", b)):
            if mm.any():
                rel = f"masks/{base}/{nm}.png"; save_mask(mm, d / rel); masks[nm] = rel
        tb = base.endswith("_1")
        meta = json.loads((img_dir / f"{base}.json").read_text()) if (img_dir / f"{base}.json").exists() else {}
        recs.append(Record(
            id=base, source=source, modality="RX", kind="image", path=f"images/{png.name}",
            url="https://openi.nlm.nih.gov/imgs/collections/ChinaSet_AllFiles.zip; https://zenodo.org/records/14059288",
            license=spec[0], attribution=spec[1], labels=["rx.tuberculosis"] if tb else ["rx.normal"], view="PA",
            group=base, extra={"masks": masks, "image_size": list(im.size), "orig_size": meta.get("orig_size"),
                               "orientation": "patient right = image left (assumed; masks split by image side)",
                               "mask_source": "manual lung masks (Stirenko et al. 2018), left/right split by connected component"}))
    write_manifest(source, recs)
    return recs


# --------------------------------------------------------------------------- PAX-Ray++ (synthetic frontal + lateral)

PAX_DIRECT = {  # PAX-Ray++ category -> our structure name (patient-side anatomical names: derived from CT)
    "right lung": "right_lung", "left lung": "left_lung", "heart": "heart", "trachea": "trachea",
    "clavicle right": "right_clavicle", "clavicle left": "left_clavicle", "spine": "spine", "sternum": "sternum",
    "right hemidiaphragm": "right_hemidiaphragm", "left hemidiaphragm": "left_hemidiaphragm",
    "aorta": "aorta", "cardiomediastinum": "cardiomediastinum",
    "scapula right": "right_scapula", "scapula left": "left_scapula",
}
_RIB_RE = re.compile(r"^(anterior|posterior) \d+(st|nd|rd|th) rib (left|right)$")


def pax_structure(cat_name: str) -> Optional[str]:
    """Map a PAX-Ray++ category name to our structure name; individual ribs -> 'ribs_left'/'ribs_right' (union)."""
    n = cat_name.strip().lower()
    if n in PAX_DIRECT:
        return PAX_DIRECT[n]
    m = _RIB_RE.match(n)
    return f"ribs_{m.group(3)}" if m else None


def build_paxray(raw: Path, source: str = "rx_masks_other", max_volumes: Optional[int] = 400) -> list[Record]:
    """raw: dir with paxray_test.json (COCO), paxray_images.tar.gz, metadata.csv (pixel spacing).
    Keeps the first `max_volumes` test volumes (frontal + lateral each). Masks 512x512, aligned with the image."""
    import csv
    d = source_dir(source)
    coco = json.loads((raw / "paxray_test.json").read_text())
    cats = {c["id"]: c["name"] for c in coco["categories"]}
    anns: dict[int, list] = {}
    for a in coco["annotations"]:
        anns.setdefault(a["image_id"], []).append(a)
    meta = {}
    mp = raw / "metadata.csv"
    if mp.exists():
        for row in csv.DictReader(mp.open()):
            meta[row["volume_id"]] = row
    imgs = sorted(coco["images"], key=lambda i: i["file_name"])
    vols = sorted({re.sub(r"_(frontal|lateral)\.png$", "", i["file_name"]) for i in imgs})
    if max_volumes:
        step = max(1, len(vols) // max_volumes)
        vols = set(vols[::step][:max_volumes])
    else:
        vols = set(vols)
    wanted = {i["file_name"]: i for i in imgs if re.sub(r"_(frontal|lateral)\.png$", "", i["file_name"]) in vols}
    spec = _lic("paxrayplusplus")
    recs = []
    (d / "images").mkdir(exist_ok=True)
    with tarfile.open(raw / "paxray_images.tar.gz") as tf:
        for member in tf:
            nm = Path(member.name).name
            if not member.isfile() or nm not in wanted:
                continue
            info = wanted[nm]
            im = Image.open(io.BytesIO(tf.extractfile(member).read())).convert("L")
            stem = Path(nm).stem
            view = "LATERAL" if stem.endswith("_lateral") else "PA"   # PAX-Ray++ frontal = AP/PA projection of CT
            rel_img = f"images/{stem}.png"
            im.save(d / rel_img, optimize=True)
            h, w = info["height"], info["width"]
            acc: dict[str, np.ndarray] = {}
            for a in anns.get(info["id"], []):
                key = pax_structure(cats[a["category_id"]])
                if key is None:
                    continue
                seg = a["segmentation"]
                if isinstance(seg, dict):
                    m = rle_decode(seg["counts"], tuple(seg["size"]))
                else:
                    m = np.zeros((h, w), bool)
                    for poly in seg:
                        m |= polygon_mask(list(zip(poly[0::2], poly[1::2])), (w, h))
                acc[key] = acc[key] | m if key in acc else m
            masks = {}
            for key, m in sorted(acc.items()):
                if m.any():
                    rel = f"masks/{stem}/{key}.png"; save_mask(m, d / rel); masks[key] = rel
            vol = re.sub(r"_(frontal|lateral)$", "", stem)
            mm = meta.get(vol) or {}
            sp = None
            try:
                sp = [float(mm[f"{'frontal' if view == 'PA' else 'lateral'}_mm_per_px_x"]),
                      float(mm[f"{'frontal' if view == 'PA' else 'lateral'}_mm_per_px_y"])]
            except (KeyError, ValueError, TypeError):
                pass
            recs.append(Record(
                id=stem, source=source, modality="RX", kind="image", path=rel_img,
                url="https://zenodo.org/records/23627483", license=spec[0], attribution=spec[1], labels=[],
                view=view, group=vol,
                extra={"masks": masks, "image_size": [w, h], "synthetic": True, "ct_source": mm.get("source"),
                       "pixel_spacing_mm": sp,
                       "left_right": "patient-anatomical names (from CT); in LATERAL views the side is not visible",
                       "ribs": "ribs_left/ribs_right = union of anterior+posterior ribs 1-12 of that side",
                       "mask_source": "CT projection of volumetric pseudo-labels (not radiologist GT)"}))
    write_manifest(source, recs)
    return recs


if __name__ == "__main__":  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["jsrt", "montgomery_shenzhen", "paxray"])
    ap.add_argument("--max-side", type=int, default=None)
    a = ap.parse_args()
    if a.what == "jsrt":
        print(len(build_jsrt()))
    elif a.what == "montgomery_shenzhen":
        m = build_montgomery(DATA_ROOT / "montgomery" / "raw" / "NLM-MontgomeryCXRSet.zip", DATA_ROOT / "montgomery" / "raw")
        sz = build_shenzhen(DATA_ROOT / "shenzhen" / "raw", DATA_ROOT / "shenzhen" / "raw" / "images_ds")
        print({"montgomery": len(m), "shenzhen": len(sz)})
    else:
        print(len(build_paxray(DATA_ROOT / "rx_masks_other" / "paxrayplusplus_raw")))
