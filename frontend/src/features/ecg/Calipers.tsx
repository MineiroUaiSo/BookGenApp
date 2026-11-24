import type { Geometry } from "./ecgMath";
import { rrToBpm, xOf, yOf } from "./ecgMath";

export interface CaliperMeasure {
  panel: number; t1: number; v1: number; t2: number; v2: number; snapped?: boolean;
}
export function measureStats(m: CaliperMeasure) {
  const dtMs = Math.abs(m.t2 - m.t1);
  const dMv = Math.abs(m.v2 - m.v1);
  return { dtMs, dMv, bpm: dtMs > 0 ? rrToBpm(dtMs) : null };
}
export function caliperLabel(m: CaliperMeasure) {
  const s = measureStats(m);
  return `Δt ${s.dtMs.toFixed(0)} ms · ΔmV ${s.dMv.toFixed(2)}${s.bpm ? ` · ≈ ${s.bpm.toFixed(0)} bpm (RR)` : ""}`;
}

export function CaliperLayer({ geo, measures, draft }: { geo: Geometry; measures: CaliperMeasure[]; draft?: CaliperMeasure | null }) {
  const all = draft ? [...measures, draft] : measures;
  return (
    <g data-testid="calipers" pointerEvents="none">
      {all.map((m, i) => {
        const p = geo.panels[m.panel];
        if (!p) return null;
        const x1 = xOf(geo, p, m.t1), x2 = xOf(geo, p, m.t2);
        const y1 = yOf(geo, p, m.v1), y2 = yOf(geo, p, m.v2);
        const text = caliperLabel(m);
        const lx = Math.min(x1, x2);
        const ly = Math.max(p.y + 12, Math.min(y1, y2) - 6);
        return (
          <g key={i} stroke="#0b7285" strokeWidth={1.2} fill="none">
            <line x1={x1} x2={x1} y1={p.y} y2={p.y + p.h} strokeDasharray="4 2" />
            <line x1={x2} x2={x2} y1={p.y} y2={p.y + p.h} strokeDasharray="4 2" />
            <line x1={x1} x2={x2} y1={y1} y2={y1} />
            <line x1={x2} x2={x2} y1={y1} y2={y2} />
            <circle cx={x1} cy={y1} r={3} fill="#0b7285" />
            <circle cx={x2} cy={y2} r={3} fill="#0b7285" />
            <rect x={lx} y={ly - 12} width={text.length * 5.6 + 8} height={16} rx={3} fill="#0b7285" stroke="none" />
            <text x={lx + 4} y={ly} fill="#fff" stroke="none" fontSize={11} fontFamily="sans-serif">{text}</text>
          </g>
        );
      })}
    </g>
  );
}
