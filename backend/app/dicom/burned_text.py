"""PHI em pixels: detecta e mascara texto queimado (burned-in) em radiografias.

Detector: top-hat morfológico (claro e escuro) -> componentes conectados pequenos tipo caractere ->
agrupados em linhas de texto concentradas nas bordas do quadro. Mascara com a mediana local.
Política de envio externo (external_send_blocked): BurnedInAnnotation == YES, ou texto detectado e
máscara não aplicada com sucesso => a imagem NÃO vai ao provedor externo (regras locais seguem).

Limitação: não é OCR; texto muito grande, curvo ou fora das bordas pode escapar. Marcadores L/R isolados
(poucos caracteres) não são mascarados de propósito.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from scipy import ndimage as ndi

WORK_MAX_SIDE = 1100
TOPHAT_SIZE_FRAC = 0.012        # elemento estruturante ~ maior que um traço de caractere
TOPHAT_MIN_CONTRAST = 55        # contraste mínimo (0-255) do caractere sobre o entorno
BORDER_FRAC_Y, BORDER_FRAC_X = 0.22, 0.18
CHAR_H_FRAC = (0.006, 0.05)     # altura do caractere / lado maior do quadro
MIN_CHARS_PER_LINE = 5
SENS_CONTRAST, SENS_MIN_CHARS = 40, 3     # passe de verificação de resíduo
MAX_HEIGHT_CV = 0.22
MAX_BASELINE_STD = 0.3
MIN_LINE_ASPECT = 2.0
MAX_REGION_AREA_FRAC = 0.12
PAD_PX = 4


@dataclass(frozen=True)
class BurnedTextResult:
    tag: str = ""                 # valor de BurnedInAnnotation (0028,0301): "YES" | "NO" | ""
    detected: bool = False
    n_regions: int = 0
    area_frac: float = 0.0
    masked: bool = False          # máscara aplicada e re-verificada sem texto residual

    @property
    def tag_yes(self) -> bool:
        return self.tag == "YES"

    @property
    def block_external(self) -> bool:
        return external_send_blocked(self)

    def summary(self) -> str:
        parts = [f"BurnedInAnnotation={self.tag or 'ausente'}"]
        if self.detected:
            parts.append(f"texto detectado em {self.n_regions} região(ões) ({self.area_frac * 100:.1f}% do quadro)")
            parts.append("mascarado" if self.masked else "NÃO mascarado com segurança")
        else:
            parts.append("sem texto detectado")
        return "; ".join(parts)


def scrub_enabled() -> bool:
    """MEDLENS_BURNED_TEXT=off|0|false desliga a detecção/máscara de texto queimado (padrão: ligada)."""
    return os.environ.get("MEDLENS_BURNED_TEXT", "on").lower() not in ("off", "0", "false")


def external_send_blocked(res: BurnedTextResult) -> bool:
    return res.tag_yes or (res.detected and not res.masked)


def burned_in_tag(ds: Any) -> str:
    if ds is None:
        return ""
    try:
        return str(ds.get("BurnedInAnnotation", "") or "").strip().upper()
    except Exception:
        return ""


def _work(img: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = img.shape
    s = min(1.0, WORK_MAX_SIDE / max(h, w))
    if s >= 1.0:
        return img, 1.0
    return ndi.zoom(img.astype(np.float32), s, order=1).astype(np.uint8), s


def _char_candidates(w: np.ndarray, contrast: int = TOPHAT_MIN_CONTRAST) -> list[np.ndarray]:
    """Máscaras de pixels de alto contraste fino: [top-hat claro (texto claro), top-hat escuro (texto escuro)].
    Polaridades ficam separadas: a união preenche os vãos entre letras e funde a linha em bloco."""
    h, wd = w.shape
    k = max(5, int(round(TOPHAT_SIZE_FRAC * max(h, wd))))
    f = w.astype(np.int16)
    white = f - ndi.grey_opening(w, size=(k, k)).astype(np.int16)
    black = ndi.grey_closing(w, size=(k, k)).astype(np.int16) - f
    return [white > contrast, black > contrast]


def _in_border(cy: float, cx: float, h: int, wd: int) -> bool:
    return (cy < BORDER_FRAC_Y * h or cy > (1 - BORDER_FRAC_Y) * h
            or cx < BORDER_FRAC_X * wd or cx > (1 - BORDER_FRAC_X) * wd)


def _stroke_transitions(m: np.ndarray) -> int:
    """Nº de transições vazio->ocupado ao longo das colunas (um traço de letra = 1)."""
    occ = m.any(axis=0).astype(np.int8)
    return int(np.count_nonzero(np.diff(occ) == 1))


def _regular_line(bxs: list[tuple[int, int, int, int]], horizontal: bool, min_chars: int = 5) -> bool:
    """Caracteres de uma linha de texto: alturas parecidas e centros alinhados na linha-base."""
    ext = np.array([(b[1] - b[0]) if horizontal else (b[3] - b[2]) for b in bxs], float)
    cen = np.array([((b[0] + b[1]) if horizontal else (b[2] + b[3])) / 2 for b in bxs], float)
    m = float(np.median(ext))
    if m <= 0:
        return False
    keep = np.abs(ext - m) <= 0.5 * m           # tolera pontuação/minúsculas
    if keep.sum() < min_chars:
        return False
    return float(np.std(ext[keep]) / m) <= MAX_HEIGHT_CV and float(np.std(cen[keep])) <= MAX_BASELINE_STD * m


def detect_text_mask(img: np.ndarray, sensitive: bool = False) -> tuple[np.ndarray, int]:
    """(máscara bool no tamanho de img, nº de regiões de texto).
    sensitive=True (verificação de resíduo): contraste menor e linhas mais curtas; mais falsos positivos."""
    contrast = SENS_CONTRAST if sensitive else TOPHAT_MIN_CONTRAST
    min_chars = SENS_MIN_CHARS if sensitive else MIN_CHARS_PER_LINE
    h0, w0 = img.shape
    w, s = _work(img)
    h, wd = w.shape
    region = np.zeros((h, wd), bool)
    n_reg = 0
    for cand in _char_candidates(w, contrast):
        r, k = _polarity_regions(cand, h, wd, min_chars)
        region |= r
        n_reg += k
    return _upscale(region, n_reg, h0, w0, s)


def _polarity_regions(cand: np.ndarray, h: int, wd: int, min_chars: int = 5) -> tuple[np.ndarray, int]:
    lab, n = ndi.label(cand, structure=np.ones((3, 3)))
    if n == 0:
        return np.zeros((h, wd), bool), 0
    objs = ndi.find_objects(lab)
    side = max(h, wd)
    lo, hi = CHAR_H_FRAC[0] * side, CHAR_H_FRAC[1] * side
    chars = np.zeros(n + 1, bool)
    boxes = {}
    merged: list[tuple[int, int, int, int]] = []
    areas = ndi.sum(cand, lab, index=np.arange(1, n + 1))
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        bh, bw = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if lo <= max(bh, 1) <= hi and bw > 2.2 * hi:
            # caracteres fundidos em palavra/linha pelo reamostrado: exige estrutura de traços (colunas alternadas)
            cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
            if bw / bh >= 2.5 and _in_border(cy, cx, h, wd) and _stroke_transitions(lab[sl] == i) >= min_chars \
                    and bh * bw <= MAX_REGION_AREA_FRAC * h * wd and 0.12 <= areas[i - 1] / float(bh * bw) <= 0.8:
                merged.append((sl[0].start, sl[0].stop, sl[1].start, sl[1].stop))
            continue
        if not (lo <= max(bh, 1) <= hi) or bw < 1:
            continue
        fill = areas[i - 1] / float(bh * bw)
        if fill < 0.12 or bh / max(bw, 1) > 12:
            continue
        cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
        if not _in_border(cy, cx, h, wd):
            continue
        chars[i] = True
        boxes[i] = (sl[0].start, sl[0].stop, sl[1].start, sl[1].stop)
    region = np.zeros((h, wd), bool)
    n_reg = 0
    for (y0, y1, x0, x1) in merged:
        pad = int(PAD_PX + 0.3 * (y1 - y0))
        region[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = True
        n_reg += 1
    if not boxes:
        return region, n_reg
    cm = chars[lab]
    # une caracteres vizinhos em linhas (dilatação horizontal ~ 1.6x altura do caractere)
    med_h = float(np.median([b[1] - b[0] for b in boxes.values()]))
    gap_x, gap_y = max(3, int(1.8 * med_h)), max(1, int(0.35 * med_h))
    joined = ndi.maximum_filter1d(ndi.maximum_filter1d(cm.astype(np.uint8), 2 * gap_x + 1, axis=1),
                                  2 * gap_y + 1, axis=0) > 0   # dilatação separável (rápida)
    llab, ln = ndi.label(joined)
    groups: dict[int, list[int]] = {}
    for i, b in boxes.items():
        groups.setdefault(int(llab[(b[0] + b[1]) // 2, (b[2] + b[3]) // 2]), []).append(i)
    for members in groups.values():
        if len(members) < min_chars:
            continue
        y0 = min(boxes[i][0] for i in members)
        y1 = max(boxes[i][1] for i in members)
        x0 = min(boxes[i][2] for i in members)
        x1 = max(boxes[i][3] for i in members)
        bh, bw = y1 - y0, x1 - x0
        if not _regular_line([boxes[i] for i in members], bw >= bh, min_chars):
            continue
        text_like = bw / max(bh, 1) >= MIN_LINE_ASPECT or bh / max(bw, 1) >= MIN_LINE_ASPECT
        if not text_like or bh * bw > MAX_REGION_AREA_FRAC * h * wd:
            continue
        pad = int(PAD_PX + 0.3 * med_h)
        region[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = True
        n_reg += 1
    return region, n_reg


def _upscale(region: np.ndarray, n_reg: int, h0: int, w0: int, s: float) -> tuple[np.ndarray, int]:
    if n_reg == 0:
        return np.zeros((h0, w0), bool), 0
    if s < 1.0:
        full = ndi.zoom(region.astype(np.uint8), (h0 / region.shape[0], w0 / region.shape[1]), order=0).astype(bool)
        out = np.zeros((h0, w0), bool)
        hh, ww = min(h0, full.shape[0]), min(w0, full.shape[1])
        out[:hh, :ww] = full[:hh, :ww]
        region = out
    return region, n_reg


def _fill_regions(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Preenche cada região com a mediana do anel ao redor (fora da máscara), trabalhando só na janela local."""
    out = img.copy()
    lab, n = ndi.label(mask)
    ring_w = max(6, int(0.01 * max(img.shape)))
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        if sl is None:
            continue
        y0, y1 = max(0, sl[0].start - ring_w - 1), min(img.shape[0], sl[0].stop + ring_w + 1)
        x0, x1 = max(0, sl[1].start - ring_w - 1), min(img.shape[1], sl[1].stop + ring_w + 1)
        win = (slice(y0, y1), slice(x0, x1))
        reg = lab[win] == i
        ring = ndi.binary_dilation(reg, iterations=ring_w) & ~mask[win]
        vals = img[win][ring]
        out[win][reg] = int(np.median(vals)) if vals.size else 0
    return out


def scrub(img: np.ndarray, ds: Any = None) -> tuple[np.ndarray, BurnedTextResult]:
    """Devolve (imagem sem o texto queimado, resultado). Nunca levanta: erro => detected=True, masked=False."""
    tag = burned_in_tag(ds)
    try:
        g = img if img.ndim == 2 else img[..., 0]
        mask, n = detect_text_mask(g)
        if n == 0:
            return img, BurnedTextResult(tag=tag)
        out = _fill_regions(img if img.ndim == 2 else g, mask)
        _, residual = detect_text_mask(out, sensitive=True)
        return out, BurnedTextResult(tag=tag, detected=True, n_regions=n, area_frac=float(mask.mean()),
                                     masked=residual == 0)
    except Exception:
        return img, BurnedTextResult(tag=tag, detected=True, n_regions=0, masked=False)
