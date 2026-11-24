import type { Wave } from "../../types/api";
import type { Geometry, OverlayKey } from "./ecgMath";
import {
  WAVE_COLORS, beatIntervals, kindToOverlayKey, sampleAt, wavesOfLead, waveBounds, xOf, yOf,
} from "./ecgMath";

export interface HoverInfo { title: string; lines: string[] }
interface Props {
  geo: Geometry;
  waves: Wave[];
  leads: Record<string, number[]>;
  fs: number;
  overlay: Record<OverlayKey, boolean>;
  showFiducials: boolean;
  onHover: (info: HoverInfo | null, ev?: React.MouseEvent) => void;
  waveTooltip: (w: Wave) => HoverInfo;
}

const INTERVAL_ROWS: { key: "PR" | "QT" | "ST"; field: "pr" | "qt" | "st"; off: number; label: string }[] = [
  { key: "PR", field: "pr", off: 5, label: "PR" },
  { key: "QT", field: "qt", off: 11, label: "QT" },
  { key: "ST", field: "st", off: 17, label: "ST" },
];

export default function WaveOverlay({ geo, waves, leads, fs, overlay, showFiducials, onHover, waveTooltip }: Props) {
  return (
    <g data-testid="wave-overlay">
      {geo.panels.map((p, pi) => {
        const pw = wavesOfLead(waves, p.lead).filter((w) => {
          const [a, b] = waveBounds(w);
          return b >= p.t0 && a <= p.t1;
        });
        const sig = leads[p.lead];
        return (
          <g key={pi} data-lead={p.lead}>
            {pw.map((w, i) => {
              const key = kindToOverlayKey(w.kind);
              const on = overlay[key];
              const [a, b] = waveBounds(w);
              const x = xOf(geo, p, a);
              const width = Math.max(2, xOf(geo, p, b) - x);
              const color = WAVE_COLORS[w.kind];
              const isQrsMember = w.kind !== "QRS" && key === "QRS";
              return (
                <g key={i}>
                  {on && (
                    <rect
                      className={`wave-span wave-${w.kind.replace("'", "p")}`}
                      data-kind={w.kind}
                      x={x} y={p.y + 1} width={width} height={p.h - 2}
                      fill={color} fillOpacity={w.kind === "QRS" ? 0.1 : isQrsMember ? 0.18 : 0.16}
                      stroke={color} strokeOpacity={0.5} strokeWidth={0.6}
                      onMouseMove={(e) => onHover(waveTooltip(w), e)}
                      onMouseLeave={() => onHover(null)}
                    />
                  )}
                  {on && w.peak_ms != null && w.peak_ms >= p.t0 && w.peak_ms <= p.t1 && w.kind !== "QRS" && (
                    <g pointerEvents="none">
                      <circle cx={xOf(geo, p, w.peak_ms)} cy={yOf(geo, p, sampleAt(sig, fs, w.peak_ms))} r={2.6} fill={color} />
                      <text x={xOf(geo, p, w.peak_ms)} y={p.y + 9} fontSize={9} fontWeight={700} textAnchor="middle" fill={color}>{w.kind}</text>
                    </g>
                  )}
                  {showFiducials && (
                    <g pointerEvents="none" stroke={color} strokeWidth={0.8} strokeDasharray="2 2">
                      <line x1={x} x2={x} y1={p.y} y2={p.y + p.h} />
                      {w.offset_ms != null && <line x1={xOf(geo, p, w.offset_ms)} x2={xOf(geo, p, w.offset_ms)} y1={p.y} y2={p.y + p.h} />}
                    </g>
                  )}
                </g>
              );
            })}
            {beatIntervals(wavesOfLead(waves, p.lead)).map((bi, i) =>
              INTERVAL_ROWS.map((r) => {
                const iv = bi[r.field];
                if (!overlay[r.key] || !iv || iv[1] < p.t0 || iv[0] > p.t1) return null;
                const x1 = xOf(geo, p, iv[0]), x2 = xOf(geo, p, iv[1]);
                const y = p.y + p.h - r.off * (geo.pxPerMm / 3.78) - 1;
                const c = WAVE_COLORS[r.key];
                return (
                  <g
                    key={`${i}-${r.key}`}
                    className={`interval interval-${r.key}`}
                    onMouseMove={(e) => onHover({ title: `Intervalo ${r.label} — ${p.lead} (batimento ${bi.beat + 1})`, lines: [`${iv[0].toFixed(0)} → ${iv[1].toFixed(0)} ms`, `duração ${(iv[1] - iv[0]).toFixed(0)} ms`] }, e)}
                    onMouseLeave={() => onHover(null)}
                  >
                    <rect x={x1} y={y - 3} width={Math.max(1, x2 - x1)} height={6} fill="transparent" />
                    <path d={`M${x1} ${y - 3}V${y + 3}M${x1} ${y}H${x2}M${x2} ${y - 3}V${y + 3}`} stroke={c} strokeWidth={1.6} fill="none" />
                    {x2 - x1 > 26 && <text x={(x1 + x2) / 2} y={y - 4} fontSize={9} textAnchor="middle" fill={c} fontWeight={700}>{r.label} {(iv[1] - iv[0]).toFixed(0)}</text>}
                  </g>
                );
              }),
            )}
          </g>
        );
      })}
    </g>
  );
}
