import { useId, useMemo, useRef, useState } from "react";
import type { ECGAnalysis } from "../../types/api";
import type { LayoutKind, OverlayKey, Panel } from "./ecgMath";
import {
  buildGeometry, fiducialsMs, msAtX, mvAtY, PX_PER_MM_BASE, pxToMs, sampleAt, snapToNearest,
  tracePath, waveTooltip, msToMm,
} from "./ecgMath";
import WaveOverlay, { type HoverInfo } from "./WaveOverlay";
import { CaliperLayer, type CaliperMeasure } from "./Calipers";

export interface EcgPaperProps {
  analysis: ECGAnalysis;
  layout: LayoutKind;
  speed: number;
  gain: number;
  zoom: number;
  overlay: Record<OverlayKey, boolean>;
  isolateLead?: string | null;
  highlightLeads?: string[];
  tool: "pan" | "calipers";
  calipers: CaliperMeasure[];
  onCalipersChange: (m: CaliperMeasure[]) => void;
  onSelectLead: (lead: string) => void;
}

export default function EcgPaper(props: EcgPaperProps) {
  const { analysis, layout, speed, gain, zoom, overlay, isolateLead, highlightLeads = [], tool, calipers, onCalipersChange, onSelectLead } = props;
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const pxPerMm = PX_PER_MM_BASE * zoom;
  const { signal } = analysis;
  const durationMs = signal.duration_s * 1000;
  const geo = useMemo(
    () => buildGeometry({ layout: isolateLead ? "single" : layout, durationMs, speed, gain, pxPerMm, isolateLead }),
    [layout, durationMs, speed, gain, pxPerMm, isolateLead],
  );
  const paths = useMemo(
    () => geo.panels.map((p) => tracePath(geo, p, signal.leads[p.lead] ?? [], signal.fs)),
    [geo, signal],
  );
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ info: HoverInfo; x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<CaliperMeasure | null>(null);
  const pan = useRef<{ x: number; y: number; sl: number; st: number } | null>(null);
  const small = pxPerMm, big = pxPerMm * 5;
  const showFid = !!isolateLead;

  const toLocal = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const locate = (x: number, y: number): number => geo.panels.findIndex((p) => x >= p.x && x <= p.x + p.w && y >= p.y && y <= p.y + p.h);
  const point = (pi: number, x: number, y: number) => {
    const p: Panel = geo.panels[pi];
    const tol = pxToMs(8, speed, pxPerMm);
    const raw = msAtX(geo, p, x);
    const { value, snapped } = snapToNearest(raw, fiducialsMs(analysis.waves, p.lead), tol);
    const t = Math.min(p.t1, Math.max(p.t0, value));
    const v = snapped ? sampleAt(signal.leads[p.lead], signal.fs, t) : mvAtY(geo, p, y);
    return { t, v, snapped };
  };

  const down = (e: React.PointerEvent) => {
    if (tool === "pan") {
      const w = wrapRef.current!;
      pan.current = { x: e.clientX, y: e.clientY, sl: w.scrollLeft, st: w.scrollTop };
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
      return;
    }
    const { x, y } = toLocal(e);
    const pi = locate(x, y);
    if (pi < 0) return;
    const a = point(pi, x, y);
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    setDraft({ panel: pi, t1: a.t, v1: a.v, t2: a.t, v2: a.v, snapped: a.snapped });
  };
  const move = (e: React.PointerEvent) => {
    if (pan.current && wrapRef.current) {
      wrapRef.current.scrollLeft = pan.current.sl - (e.clientX - pan.current.x);
      wrapRef.current.scrollTop = pan.current.st - (e.clientY - pan.current.y);
    }
    if (draft) {
      const { x, y } = toLocal(e);
      const a = point(draft.panel, x, y);
      setDraft({ ...draft, t2: a.t, v2: a.v });
    }
  };
  const up = () => {
    pan.current = null;
    if (draft) {
      if (Math.abs(draft.t2 - draft.t1) > 1 || Math.abs(draft.v2 - draft.v1) > 0.005) onCalipersChange([...calipers, draft]);
      setDraft(null);
    }
  };
  const onHover = (info: HoverInfo | null, ev?: React.MouseEvent) =>
    setHover(info && ev ? { info, x: ev.clientX + 12, y: ev.clientY + 12 } : null);

  const first = geo.panels.filter((p) => p.col === 0);
  const rows = new Map<number, Panel>();
  for (const p of first) rows.set(p.row, p);

  return (
    <div ref={wrapRef} className="ecg-paper-wrap" data-testid="ecg-paper" style={{ cursor: tool === "pan" ? "grab" : "crosshair" }}>
      <svg
        ref={svgRef} width={geo.width} height={geo.height} viewBox={`0 0 ${geo.width} ${geo.height}`}
        role="img" aria-label="Traçado de ECG em papel milimetrado"
        style={{ touchAction: "none", userSelect: "none" }}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
      >
        <defs>
          <pattern id={`s${uid}`} width={small} height={small} patternUnits="userSpaceOnUse">
            <path d={`M${small} 0H0V${small}`} fill="none" style={{ stroke: "var(--ecg-grid-minor)" }} strokeWidth={0.5} />
          </pattern>
          <pattern id={`b${uid}`} width={big} height={big} patternUnits="userSpaceOnUse">
            <rect width={big} height={big} fill={`url(#s${uid})`} />
            <path d={`M${big} 0H0V${big}`} fill="none" style={{ stroke: "var(--ecg-grid-major)" }} strokeWidth={0.9} />
          </pattern>
        </defs>
        <rect width={geo.width} height={geo.height} style={{ fill: "var(--ecg-paper)" }} />
        <rect width={geo.width} height={geo.height} fill={`url(#b${uid})`} data-testid="ecg-grid" />
        {geo.panels.map((p, i) => (
          <g key={i}>
            {highlightLeads.includes(p.lead) && <rect x={p.x} y={p.y} width={p.w} height={p.h} fill="#ffd23f" fillOpacity={0.18} stroke="#d99a00" strokeWidth={1} data-testid="lead-highlight" />}
            <path d={paths[i]} className="ecg-trace" data-lead={p.lead} />
            <text x={p.x + 3} y={p.y + 12} className="ecg-label" onClick={() => onSelectLead(p.lead)}>
              {p.lead}{p.rhythm ? " (ritmo)" : ""}
              <title>Clique para isolar a derivação {p.lead}</title>
            </text>
            {i > 0 && p.col > 0 && geo.layout !== "single" && <line x1={p.x} x2={p.x} y1={p.y + p.h * 0.3} y2={p.y + p.h * 0.7} style={{ stroke: "var(--ecg-trace)" }} strokeWidth={0.8} />}
          </g>
        ))}
        {[...rows.values()].map((p) => {
          const x0 = 2 * pxPerMm, w = msToMm(200, speed) * pxPerMm, h = gain * pxPerMm;
          return (
            <path key={p.row} data-testid="calibration" d={`M${x0 - pxPerMm} ${p.baseY}H${x0}V${p.baseY - h}H${x0 + w}V${p.baseY}H${x0 + w + pxPerMm}`}
              className="ecg-trace" />
          );
        })}
        <WaveOverlay
          geo={geo} waves={analysis.waves} leads={signal.leads} fs={signal.fs}
          overlay={overlay} showFiducials={showFid} onHover={onHover} waveTooltip={waveTooltip}
        />
        <CaliperLayer geo={geo} measures={calipers} draft={draft} />
        <text x={geo.width - 6} y={geo.height - 5} textAnchor="end" fontSize={10} style={{ fill: "var(--ecg-muted)" }}>
          {speed} mm/s · {gain} mm/mV
        </text>
      </svg>
      {hover && (
        <div className="ecg-tooltip" style={{ left: hover.x, top: hover.y }} role="tooltip">
          <strong>{hover.info.title}</strong>
          {hover.info.lines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
    </div>
  );
}
