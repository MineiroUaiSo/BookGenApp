"""Perfil (lateral) de tórax: segmentação clássica por SINAL de imagem (sem ML), com marca explícita de estimativa.

Entradas: imagem float 0..1 em resolução de trabalho. Convenção: o lado posterior (coluna) pode estar à
esquerda ou à direita da imagem. Nada aqui devolve retângulo/elipse como se fosse medida: quando uma estrutura
só pode ser posicionada por prior geométrico, ela sai em `estimativa` (e quem monta a estrutura rebaixa a
confiança e marca o rótulo).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import gaussian, threshold_multiotsu, threshold_otsu
from skimage.measure import label
from skimage.morphology import convex_hull_image, disk


def _open(m: np.ndarray, r: int) -> np.ndarray:
    return ndi.binary_opening(m.astype(bool), structure=disk(max(1, r)).astype(bool))


def _close(m: np.ndarray, r: int) -> np.ndarray:
    return ndi.binary_closing(m.astype(bool), structure=disk(max(1, r)).astype(bool))


def body_mask(s: np.ndarray) -> np.ndarray:
    """Corpo = tudo que não é ar de fundo conectado à borda (fundo escuro fora do paciente)."""
    g = gaussian(s, sigma=1.5)
    try:
        t0 = float(threshold_multiotsu(g, classes=3)[0])
    except Exception:
        t0 = float(threshold_otsu(g)) * 0.5
    dark = g < t0
    lab = label(dark)
    ids = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(ids)) if ids else np.zeros_like(dark)
    return ndi.binary_fill_holes(~bg)


def lung_field(s: np.ndarray, hint: Optional[np.ndarray] = None) -> Optional[dict]:
    """Campo pulmonar lateral por claridade: região de baixa atenuação contígua DENTRO do corpo (entre esterno e
    coluna, acima das cúpulas). Devolve {'mask', 'body', 'g', 't'} ou None. `hint` (PSPNet) só ajuda a escolher
    qual região clara é o pulmão; a forma vem da imagem."""
    H, W = s.shape
    body = body_mask(s)
    if body.sum() < 0.15 * H * W:
        return None
    g = gaussian(s, sigma=max(1.5, max(H, W) / 170.0))
    try:
        ts = threshold_multiotsu(g[body], classes=3)
        t = float(ts[1])
        if (body & (g <= t)).sum() > 0.72 * body.sum():      # nível alto engoliu o corpo (sem classe "mole" própria)
            t = float(ts[0])
    except Exception:
        t = float(threshold_otsu(g[body]))
    dist = ndi.distance_transform_edt(body)
    dark = body & (g <= t)
    # semente: longe da pele (a parede fina também é escura) e separada de pontes finas por abertura
    seed = _open(dark & (dist > 0.11 * W), max(3, int(round(0.016 * max(H, W)))))
    lab = label(seed)
    if lab.max() == 0:
        return None
    counts = np.bincount(lab.ravel())
    counts[0] = 0
    best, best_sc = 0, -1.0
    for i in np.nonzero(counts >= 0.01 * H * W)[0]:
        cov = (((lab == i) & hint).sum() / max(1, hint.sum())) if hint is not None else 0.0
        sc = counts[i] * (1.0 + 3.0 * cov)
        if sc > best_sc:
            best, best_sc = i, sc
    if best == 0:
        return None
    main = lab == best
    keep = main.copy()
    for i in np.nonzero(counts >= 0.15 * counts[best])[0]:     # regiões claras grandes vizinhas (retroesternal)
        if i != best:
            keep |= lab == i
    grown = ndi.binary_dilation(keep, iterations=max(2, int(0.03 * W))) & dark & (dist > 0.045 * W)
    m = _open(grown, max(3, int(0.022 * W)))
    # base do campo: abre mais forte no terço inferior para cortar a faixa da parede abdominal anterior
    # (escura por ser fina) que escorre por baixo das cúpulas
    if m.any():
        yy_ = np.nonzero(m.any(axis=1))[0]
        cut = int(yy_.min() + 0.60 * (yy_.max() - yy_.min()))
        low = _open(m, max(4, int(0.045 * W)))
        m = np.vstack([m[:cut], low[cut:]])
    lab2 = label(m)
    if lab2.max() > 1:
        c2 = np.bincount(lab2.ravel())
        c2[0] = 0
        m = lab2 == c2.argmax()
    return {"mask": m, "body": body, "g": g, "t": t}


# --------------------------------------------------------------------------------------------- por linha
def _fill_rows(a: np.ndarray, k: int) -> np.ndarray:
    """Interpola NaN por vizinho mais próximo e suaviza por mediana (k linhas)."""
    a = a.astype(float).copy()
    ok = ~np.isnan(a)
    if not ok.any():
        return a
    idx = np.arange(len(a))
    a[~ok] = np.interp(idx[~ok], idx[ok], a[ok])
    return ndi.median_filter(a, size=max(3, k), mode="nearest")


def _row_extent(m: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(xmin, xmax, tem) por linha; NaN onde a linha está vazia."""
    W = m.shape[1]
    has = m.any(axis=1)
    xmin = np.where(has, m.argmax(axis=1), np.nan)
    xmax = np.where(has, W - 1 - m[:, ::-1].argmax(axis=1), np.nan)
    return xmin, xmax, has


def _band(shape: tuple[int, int], rows: np.ndarray, x0: np.ndarray, x1: np.ndarray) -> np.ndarray:
    """Máscara com, em cada linha r de `rows`, as colunas [x0[r], x1[r]]."""
    H, W = shape
    xx = np.arange(W)[None, :]
    m = np.zeros(shape, bool)
    r = np.asarray(rows, int)
    m[r] = (xx >= np.round(x0[r])[:, None]) & (xx <= np.round(x1[r])[:, None])
    return m


def diaphragm_line(lung: np.ndarray, H: int) -> np.ndarray:
    """Contorno inferior do campo pulmonar (envelope das cúpulas: o hemidiafragma mais alto e o mais baixo
    se projetam juntos; sem separá-los, o contorno é declarado como 'diafragma (cúpulas)')."""
    cols = lung.any(axis=0)
    bot = np.where(cols, H - 1 - lung[::-1].argmax(axis=0), -1)
    thick = max(2, int(0.01 * H))
    band = np.zeros(lung.shape, bool)
    for c in np.nonzero(cols)[0]:
        band[max(0, bot[c] - thick):min(H, bot[c] + thick), c] = True
    # só o trecho inferior: descarta o "teto" do campo (a banda acompanha a base de cada coluna)
    return band


def _heart_gap(lung: np.ndarray, body: np.ndarray, g: np.ndarray, t: float, W: int) -> np.ndarray:
    """Tecido denso encerrado pelo campo claro: casco convexo do pulmão menos pulmão, acima da base do campo."""
    ys = np.nonzero(lung.any(axis=1))[0]
    r0, r1 = int(ys.min()), int(ys.max())
    Hl = r1 - r0 + 1
    gap = convex_hull_image(lung) & ~lung & body & (g > t)
    gap[: int(r0 + 0.30 * Hl)] = False
    # o casco inclui a cunha ABAIXO das cúpulas (abdome): só vale tecido acima da base do campo em cada coluna
    # (colunas sem pulmão, sob o coração, herdam a base por interpolação)
    cols = lung.any(axis=0)
    bot = np.where(cols, lung.shape[0] - 1 - lung[::-1].argmax(axis=0), np.nan)
    ok = ~np.isnan(bot)
    xs = np.arange(lung.shape[1])
    bot = np.interp(xs, xs[ok], bot[ok])
    gap &= np.arange(lung.shape[0])[:, None] <= bot[None, :]
    gap = _open(gap, max(2, int(0.018 * W)))
    return gap


def _boxiness(h: np.ndarray) -> float:
    """Fração máxima, entre topo/esquerda/direita, de posições cuja aresta cai em trechos retos (>= 8 px iguais)
    alinhados aos eixos: 0 = contorno curvo, 1 = retângulo."""
    def straight(edge: np.ndarray) -> float:
        e = edge[~np.isnan(edge)]
        if len(e) < 8:
            return 0.0
        run, best_tot = 1, 0
        for i in range(1, len(e)):
            if abs(e[i] - e[i - 1]) <= 0.5:
                run += 1
            else:
                best_tot += run if run >= 8 else 0
                run = 1
        best_tot += run if run >= 8 else 0
        return best_tot / len(e)

    cols = h.any(axis=0)
    rows = h.any(axis=1)
    top = np.where(cols, h.argmax(axis=0), np.nan)
    xmin = np.where(rows, h.argmax(axis=1), np.nan)
    xmax = np.where(rows, h.shape[1] - 1 - h[:, ::-1].argmax(axis=1), np.nan)
    return max(straight(top), straight(xmin), straight(xmax))


def heart_from_signal(lung: np.ndarray, body: np.ndarray, g: np.ndarray, t: float, W: int) -> Optional[np.ndarray]:
    """Silhueta cardíaca por densidade: na metade inferior/anterior do campo (posterior À ESQUERDA da imagem),
    a parte mais densa do próprio campo (Otsu interno) mais a lacuna de tecido que ele deixa. Só devolve com sinal
    (componente compacto de tamanho plausível); senão None e quem chama marca a elipse-prior como estimativa."""
    H = lung.shape[0]
    ys, xs = np.nonzero(lung)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    Hl, Wl = r1 - r0 + 1, c1 - c0 + 1
    yy, xx = np.mgrid[0:H, 0:lung.shape[1]]
    win = lung & (yy > r0 + 0.35 * Hl) & (xx > c0 + 0.30 * Wl)
    if win.sum() < 0.05 * lung.sum():
        return None
    try:
        thr = float(threshold_otsu(g[win]))
    except Exception:
        return None
    dense = win & (g > thr)
    dense |= _heart_gap(lung, body, g, t, W) & (xx > c0 + 0.30 * Wl)
    dense = _open(dense, max(2, int(0.02 * W)))
    lab = label(dense)
    if lab.max() == 0:
        return None
    c = np.bincount(lab.ravel())
    c[0] = 0
    h = convex_hull_image(_close(lab == c.argmax(), 3))     # silhueta cardíaca é convexa
    h &= body
    frac = h.sum() / lung.sum()
    if not 0.04 <= frac <= 0.40:
        return None
    # arestas retas alinhadas aos eixos = recorte da janela/borda (forma artificial): o sinal continua além dela
    if _boxiness(h) > 0.45:
        return None
    return h


def _ridge_track(gs: np.ndarray, rows: np.ndarray, lo: np.ndarray, hi: np.ndarray, W: int,
                 min_prom: float) -> Optional[tuple[np.ndarray, float, float]]:
    """Segue uma crista de brilho (osso) por linha na janela [lo[r], hi[r]]. Devolve (x_central por linha, meia
    largura mediana, fração de linhas com crista) ou None. Crista = topo-de-chapéu horizontal do perfil suavizado
    na vertical (as costelas somem, a coluna vertical fica)."""
    H = gs.shape[0]
    P = ndi.uniform_filter1d(gs, size=max(3, int(0.06 * H)), axis=0, mode="nearest")
    top = P - ndi.grey_opening(P, size=(1, max(5, int(0.20 * W))))
    xc = np.full(H, np.nan)
    hw = []
    for r in rows:
        a, b = int(max(0, lo[r])), int(min(W - 1, hi[r]))
        if b - a < 4:
            continue
        seg = top[r, a:b + 1]
        k = int(seg.argmax())
        if seg[k] < min_prom:
            continue
        xc[r] = a + k
        half = seg[k] * 0.5
        l = k
        while l > 0 and seg[l - 1] >= half:
            l -= 1
        h = k
        while h < len(seg) - 1 and seg[h + 1] >= half:
            h += 1
        hw.append((h - l + 1) / 2.0)
    frac = float(np.isfinite(xc[rows]).mean()) if len(rows) else 0.0
    if frac == 0.0:
        return None
    return xc, float(np.median(hw)), frac


def posterior_by_strip(s: np.ndarray, lung: np.ndarray) -> str:
    """Lado (na imagem) da coluna sem tag DICOM: a faixa ao lado do pulmão do lado posterior (dorso, escápulas,
    coluna) é mais densa. 38/41 acertos (5 RX reais + 36 pares sintéticos); empata em ~1/41: prefira a tag."""
    H, W = s.shape
    ys, xs = np.nonzero(lung)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    sw = max(2, int(0.10 * W))
    lm = s[r0:r1 + 1, max(0, c0 - sw):c0].mean() if c0 > 0 else 0.0
    rm = s[r0:r1 + 1, c1 + 1:c1 + 1 + sw].mean() if c1 + 1 < W else 0.0
    return "left" if lm > rm else "right"


def segment_lateral(s: np.ndarray, posterior: Optional[str] = None,
                    hint: Optional[np.ndarray] = None) -> Optional[dict]:
    """Perfil por sinal de imagem. `posterior` in {'left','right'} = lado da coluna na imagem (None = estimar).
    Devolve máscaras (resolução de trabalho) + '_posterior' + '_estimativa' (chaves só posicionadas por prior
    geométrico) ou None quando não há campo pulmonar claro."""
    body0 = body_mask(s)
    if body0.sum() < 0.15 * s.size or np.ptp(np.percentile(s[body0], [5, 95])) < 0.08:
        return None            # sem contraste interno: não há o que segmentar por sinal
    found0 = lung_field(s, hint)
    if found0 is None:
        return None
    if posterior not in ("left", "right"):
        posterior = posterior_by_strip(s, found0["mask"])
    flip = posterior == "right"
    sf = s[:, ::-1] if flip else s
    found = {k: (v[:, ::-1] if flip and isinstance(v, np.ndarray) else v) for k, v in found0.items()}
    H, W = sf.shape
    lung, body, g, t = found["mask"], found["body"], found["g"], found["t"]
    ys = np.nonzero(lung.any(axis=1))[0]
    r0, r1 = int(ys.min()), int(ys.max())
    Hl = r1 - r0 + 1
    cs = np.nonzero(lung.any(axis=0))[0]
    c0, c1 = int(cs.min()), int(cs.max())
    Wl = c1 - c0 + 1
    gs = gaussian(sf, sigma=2.0)
    rows_all = np.arange(H)
    xp_, xa_, has = _row_extent(lung)
    xp, xa = _fill_rows(xp_, max(5, int(0.04 * H))), _fill_rows(xa_, max(5, int(0.04 * H)))
    bx0, bx1, _ = _row_extent(body)
    bx0, bx1 = _fill_rows(bx0, 9), _fill_rows(bx1, 9)
    out: dict = {"lung_field": lung}
    est: list[str] = []

    # ---- diafragma: contorno inferior das cúpulas
    out["diaphragm"] = diaphragm_line(lung, H)

    # ---- coluna: crista de brilho vertical atrás do pulmão; sem crista = faixa-prior (estimativa)
    rr = np.arange(int(r0 + 0.10 * Hl), int(r0 + 0.85 * Hl))
    sp_lo = np.maximum(bx0, xp - 0.10 * W)
    sp_hi = xp + 0.45 * (xa - xp)
    trk = _ridge_track(gs, rr, sp_lo, sp_hi, W, 0.03)
    # a coluna continua acima do ápice e abaixo das cúpulas: estende a faixa pela posição já seguida
    spine_rows = np.arange(max(0, int(r0 - 0.30 * Hl)), min(H, int(r1 + 0.30 * Hl)))
    # a crista tracejada localiza a faixa, mas NÃO foi validada em RX real (acha a parede posterior, não a coluna
    # com segurança): a coluna fica sempre como ESTIMATIVA (faixa posicionada pelo contorno), nunca como medida
    if trk is not None and trk[2] >= 0.5:
        xc = _fill_rows(trk[0], max(9, int(0.08 * H)))
        hw = float(np.clip(trk[1], 0.07 * W, 0.10 * W))
        sp = _band((H, W), spine_rows, xc - hw, xc + hw) & body
    else:
        sp = _band((H, W), spine_rows, bx0 + 0.02 * W, bx0 + 0.02 * W + 0.15 * Wl) & body
    est.append("spine")
    out["spine"] = sp

    # ---- esterno: crista clara na parede anterior; sem crista = faixa junto à borda anterior do pulmão
    sr = np.arange(int(r0 + 0.02 * Hl), int(r0 + 0.80 * Hl))
    st_lo = xa - 0.01 * W
    st_hi = np.minimum(xa + 0.12 * W, bx1)
    st_rows = np.arange(max(0, int(r0 + 0.02 * Hl)), min(H, int(r0 + 0.80 * Hl)))
    trk = _ridge_track(gs, sr, st_lo, st_hi, W, 0.035)
    if trk is not None and trk[2] >= 0.5:
        xc = _fill_rows(trk[0], max(9, int(0.08 * H)))
        hw = float(np.clip(trk[1], 0.012 * W, 0.04 * W))
        stm = _band((H, W), st_rows, xc - hw, xc + hw) & body
    else:
        stm = _band((H, W), st_rows, xa - 0.005 * W, xa + 0.045 * W) & body
        est.append("sternum")
    out["sternum"] = stm

    # ---- coração: lacuna compacta de tecido denso entre as áreas claras; sem lacuna = elipse-prior (estimativa)
    h = heart_from_signal(lung, body, g, t, W)
    if h is not None:
        out["heart"] = h
    else:
        yy, xx = np.mgrid[0:H, 0:W]
        v = (yy - r0) / Hl
        u = (c1 - xx) / Wl                                              # 0 anterior -> 1 posterior
        ell = (((1.0 - u - 0.62) / 0.30) ** 2 + ((v - 0.72) / 0.26) ** 2 <= 1.0) & body
        out["heart"] = ell & (yy <= r1)                       # a elipse-prior não passa da base do campo
        est.append("heart")

    # ---- traqueia: tubo escuro fino na região central alta, fora do campo pulmonar aberto
    opened = _open(lung, max(3, int(0.04 * W)))
    reg = np.zeros((H, W), bool)
    reg[max(0, int(r0 - 0.20 * Hl)):int(r0 + 0.40 * Hl), int(c0 + 0.20 * Wl):int(c0 + 0.80 * Wl)] = True
    cand = _open(reg & (g <= t) & ~opened & body, 1)
    lab = label(cand)
    best, bh = 0, 0
    for i in range(1, lab.max() + 1):
        yy_, xx_ = np.nonzero(lab == i)
        h_, w_ = yy_.max() - yy_.min() + 1, xx_.max() - xx_.min() + 1
        if h_ >= 2 * w_ and h_ > bh and len(yy_) > 40:
            best, bh = i, h_
    if best:
        out["trachea"] = lab == best
    else:
        regp = np.zeros((H, W), bool)
        regp[max(0, int(r0 - 0.25 * Hl)):int(r0 + 0.35 * Hl), int(c0 + 0.25 * Wl):int(c0 + 0.60 * Wl)] = True
        tp = regp & (g <= t) & body
        if tp.any():
            out["trachea"] = tp
            est.append("trachea")

    if flip:
        out = {k: v[:, ::-1] for k, v in out.items()}
    out["_posterior"] = np.array([1 if flip else 0])
    out["_estimativa"] = tuple(est)
    return out


ESTIMATIVA_CONF = 0.1
ESTIMATIVA_SUFIXO = " (estimativa geométrica, sem sinal na imagem)"


def marcar_estimativas(structures, keys) -> None:
    """Estruturas só posicionadas por prior geométrico: confiança mínima e rótulo declarando 'estimativa'
    (mesmo termo do recon3d, que passa a rótulo do 3D). Altera a lista no lugar."""
    for st in structures:
        if st.key in keys:
            st.confidence = min(st.confidence, ESTIMATIVA_CONF)
            if ESTIMATIVA_SUFIXO not in st.label:
                st.label = st.label + ESTIMATIVA_SUFIXO
