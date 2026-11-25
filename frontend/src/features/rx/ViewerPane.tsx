import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RXImageAnalysis, Structure } from "../../types/api";
import { renderUrl } from "../../api/client";
import { centroid, pointInPolygon, tintMask } from "./maskUtils";
import { placeLabel } from "./labelLayout";

export interface PaneProps {
  image: RXImageAnalysis;
  label: string;
  hidden: Set<string>;
  opacity: number;
  outlines: boolean;
  labels: boolean;
  measurements: boolean;
  hoverKey: string | null;
  onHover: (k: string | null) => void;
  highlightMeas: string | null;
  wl: { wc: number; ww: number } | null;
  apiBase: string;
}

const MEAS_COLOR = "#ffd400";

export default function ViewerPane(p: PaneProps) {
  const { image } = p;
  const boxRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 600, h: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [masks, setMasks] = useState<Record<string, HTMLCanvasElement | null>>({});
  const drag = useRef<{ x: number; y: number; px: number; py: number; moved: boolean } | null>(null);
  const [dragging, setDragging] = useState(false);

  const fit = Math.min(size.w / image.width, size.h / image.height) || 1;
  const s = fit * zoom;
  const tx = size.w / 2 + pan.x - (image.width * s) / 2;
  const ty = size.h / 2 + pan.y - (image.height * s) / 2;

  // reset view when image changes
  useEffect(() => { setZoom(1); setPan({ x: 0, y: 0 }); }, [image.instance_id]);

  // measure container
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const upd = () => { const r = el.getBoundingClientRect(); if (r.width > 0) setSize({ w: r.width, h: r.height || r.width }); };
    upd();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(upd);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // decode masks
  useEffect(() => {
    let alive = true;
    setMasks({});
    for (const st of image.structures) {
      if (!st.mask_png_b64) continue;
      tintMask(st.mask_png_b64, st.color, image.width, image.height).then((c) => {
        if (alive) setMasks((m) => ({ ...m, [st.key]: c }));
      });
    }
    return () => { alive = false; };
  }, [image]);

  const zoomAt = useCallback((factor: number, cx: number, cy: number) => {
    setZoom((z) => {
      const nz = Math.min(12, Math.max(1, z * factor));
      const ratio = nz / z;
      setPan((pp) => {
        if (nz === 1) return { x: 0, y: 0 };
        const ox = cx - size.w / 2, oy = cy - size.h / 2;
        return { x: ox - (ox - pp.x) * ratio, y: oy - (oy - pp.y) * ratio };
      });
      return nz;
    });
  }, [size.w, size.h]);

  // non-passive wheel
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const h = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", h, { passive: false });
    return () => el.removeEventListener("wheel", h);
  }, [zoomAt]);

  const toImage = (clientX: number, clientY: number): [number, number] => {
    const r = boxRef.current!.getBoundingClientRect();
    return [(clientX - r.left - tx) / s, (clientY - r.top - ty) / s];
  };

  const hit = (ix: number, iy: number): Structure | null => {
    let best: Structure | null = null, bestA = Infinity;
    for (const st of image.structures) {
      if (p.hidden.has(st.key) || st.polygon.length < 3) continue;
      if (pointInPolygon(ix, iy, st.polygon)) {
        const b = st.bbox;
        const a = b && b.length === 4 ? (b[2] - b[0]) * (b[3] - b[1]) : 1e12;
        if (a < bestA) { best = st; bestA = a; }
      }
    }
    return best;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y, moved: false };
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (d && e.buttons) {
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) { d.moved = true; setDragging(true); }
      if (d.moved && zoom > 1) setPan({ x: d.px + dx, y: d.py + dy });
      return;
    }
    const [ix, iy] = toImage(e.clientX, e.clientY);
    const h = hit(ix, iy);
    if ((h?.key ?? null) !== p.hoverKey) p.onHover(h?.key ?? null);
  };
  const onPointerUp = () => { drag.current = null; setDragging(false); };

  const onKey = (e: React.KeyboardEvent) => {
    const c = size.w / 2;
    if (e.key === "+" || e.key === "=") zoomAt(1.25, c, size.h / 2);
    else if (e.key === "-") zoomAt(1 / 1.25, c, size.h / 2);
    else if (e.key === "0") { setZoom(1); setPan({ x: 0, y: 0 }); }
    else if (e.key.startsWith("Arrow") && zoom > 1) {
      const st = 30;
      setPan((pp) => ({
        x: pp.x + (e.key === "ArrowLeft" ? st : e.key === "ArrowRight" ? -st : 0),
        y: pp.y + (e.key === "ArrowUp" ? st : e.key === "ArrowDown" ? -st : 0),
      }));
      e.preventDefault();
    }
  };

  // overlay drawing
  useEffect(() => {
    const cv = canvasRef.current;
    const ctx = cv?.getContext?.("2d");
    if (!cv || !ctx) return;
    ctx.clearRect(0, 0, cv.width, cv.height);
    const px = 1 / s;
    // viewport visível (em coordenadas de imagem) para posicionar rótulos sem corte
    const view = {
      left: Math.max(0, -tx / s), top: Math.max(0, -ty / s),
      right: Math.min(image.width, (size.w - tx) / s), bottom: Math.min(image.height, (size.h - ty) / s),
    };
    for (const st of image.structures) {
      if (p.hidden.has(st.key)) continue;
      const hov = p.hoverKey === st.key;
      const m = masks[st.key];
      if (m) {
        ctx.globalAlpha = hov ? Math.min(1, p.opacity + 0.35) : p.opacity;
        ctx.drawImage(m, 0, 0);
        ctx.globalAlpha = 1;
      }
      if ((p.outlines || hov) && st.polygon.length > 2) {
        ctx.beginPath();
        st.polygon.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        ctx.strokeStyle = st.color;
        ctx.lineWidth = (hov ? 3 : 1.5) * px;
        ctx.stroke();
        if (!m && hov) { ctx.fillStyle = st.color + "55"; ctx.fill(); }
      }
    }
    if (p.labels) {
      ctx.font = `${Math.round(12 * px)}px system-ui, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      for (const st of image.structures) {
        if (p.hidden.has(st.key) && p.hoverKey !== st.key) continue;
        const c = centroid(st.polygon, st.bbox);
        if (!c) continue;
        ctx.lineWidth = 3 * px; ctx.strokeStyle = "rgba(0,0,0,.8)"; ctx.strokeText(st.label, c[0], c[1]);
        ctx.fillStyle = "#fff"; ctx.fillText(st.label, c[0], c[1]);
      }
    }
    if (p.measurements) {
      for (const me of image.measurements) {
        if (me.drawing.length < 2) continue;
        const hl = p.highlightMeas === me.key;
        ctx.beginPath();
        me.drawing.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.strokeStyle = MEAS_COLOR; ctx.lineWidth = (hl ? 4 : 2) * px;
        ctx.setLineDash([6 * px, 4 * px]); ctx.stroke(); ctx.setLineDash([]);
        for (const [x, y] of me.drawing) { ctx.beginPath(); ctx.arc(x, y, 3 * px, 0, Math.PI * 2); ctx.fillStyle = MEAS_COLOR; ctx.fill(); }
        const mid = me.drawing[Math.floor(me.drawing.length / 2)];
        const txt = `${me.label}${me.value != null ? `: ${me.value}${me.unit ?? ""}` : ""}`;
        ctx.font = `${Math.round(12 * px)}px system-ui, sans-serif`;
        ctx.textAlign = "left"; ctx.textBaseline = "middle";
        const pl = placeLabel(txt, (t) => ctx.measureText(t).width, [mid[0], mid[1]], view, px);
        pl.lines.forEach((ln, i) => {
          const ly = pl.y + i * pl.lineHeight;
          ctx.lineWidth = 3 * px; ctx.strokeStyle = "rgba(0,0,0,.85)"; ctx.strokeText(ln, pl.x, ly);
          ctx.fillStyle = MEAS_COLOR; ctx.fillText(ln, pl.x, ly);
        });
      }
    }
  }, [image, masks, s, tx, ty, size.w, size.h, p.hidden, p.opacity, p.outlines, p.labels, p.measurements, p.hoverKey, p.highlightMeas]);

  const src = useMemo(
    () => (p.wl ? renderUrl(image.instance_id, p.wl.wc, p.wl.ww, p.apiBase) : `data:image/png;base64,${image.image_png_b64}`),
    [p.wl, image.instance_id, image.image_png_b64, p.apiBase],
  );

  return (
    <div className="viewport no-print" ref={boxRef} tabIndex={0} role="application"
      aria-label={`Imagem ${p.label}. Use + e - para zoom, setas para mover, 0 para reiniciar.`}
      style={{ aspectRatio: `${image.width} / ${image.height}` }}
      data-dragging={dragging || undefined}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
      onPointerLeave={() => p.onHover(null)} onKeyDown={onKey}>
      <span className="view-label">{p.label}</span>
      <div className="zoom-ctl">
        <button type="button" aria-label="Aumentar zoom" onClick={() => zoomAt(1.25, size.w / 2, size.h / 2)}>+</button>
        <button type="button" aria-label="Diminuir zoom" onClick={() => zoomAt(1 / 1.25, size.w / 2, size.h / 2)}>−</button>
        <button type="button" aria-label="Reiniciar zoom" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>⟲</button>
      </div>
      <div className="stage" style={{ width: image.width, height: image.height, transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        <img src={src} alt={`Radiografia ${p.label}`} draggable={false} />
        <canvas ref={canvasRef} width={image.width} height={image.height} aria-hidden="true" />
      </div>
    </div>
  );
}
