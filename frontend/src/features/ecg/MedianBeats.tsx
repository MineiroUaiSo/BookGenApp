import type { ECGAnalysis } from "../../types/api";
import { MEDIAN_PRE_MS, WAVE_COLORS, beatIntervals, kindToOverlayKey, waveBounds, wavesOfLead, LEAD_ORDER } from "./ecgMath";

const MM_S = 50, MM_MV = 10; // escala interna do mini-painel (unidades = mm)

function MedianLead({ a, lead }: { a: ECGAnalysis; lead: string }) {
  const sig = a.median_beats[lead];
  const fs = a.signal.fs;
  if (!sig) return null;
  const r0 = a.r_peaks_ms[0] ?? MEDIAN_PRE_MS;
  const toX = (ms: number) => ((ms - r0 + MEDIAN_PRE_MS) / 1000) * MM_S; // ms absoluto do 1º batimento -> mm
  const totalMs = (sig.length / fs) * 1000;
  const W = (totalMs / 1000) * MM_S, H = 30;
  const y = (mv: number) => H / 2 - mv * MM_MV;
  const d = sig.map((v, i) => `${i ? "L" : "M"}${((i / fs) * MM_S).toFixed(2)} ${y(v).toFixed(2)}`).join("");
  const ws = wavesOfLead(a.waves, lead).filter((w) => w.beat_index === 0);
  const iv = beatIntervals(ws, lead)[0];
  const br = (r: [number, number] | undefined, yy: number, color: string, label: string) => r && (
    <g key={label}>
      <path d={`M${toX(r[0])} ${yy - 1}V${yy + 1}M${toX(r[0])} ${yy}H${toX(r[1])}M${toX(r[1])} ${yy - 1}V${yy + 1}`} stroke={color} strokeWidth={0.5} fill="none" />
      <text x={(toX(r[0]) + toX(r[1])) / 2} y={yy - 1.5} fontSize={2.6} textAnchor="middle" fill={color}>{label} {(r[1] - r[0]).toFixed(0)}</text>
    </g>
  );
  return (
    <figure className="ecg-card" style={{ margin: 0, padding: 6 }} data-lead={lead}>
      <figcaption style={{ fontWeight: 600, fontSize: 12 }}>{lead}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Batimento mediano ${lead}`}>
        <rect width={W} height={H} style={{ fill: "var(--ecg-paper)" }} />
        {Array.from({ length: Math.floor(W / 5) + 1 }, (_, i) => <line key={i} x1={i * 5} x2={i * 5} y1={0} y2={H} style={{ stroke: "var(--ecg-grid-major)" }} strokeWidth={0.15} />)}
        {Array.from({ length: Math.floor(H / 5) + 1 }, (_, i) => <line key={i} y1={i * 5} y2={i * 5} x1={0} x2={W} style={{ stroke: "var(--ecg-grid-major)" }} strokeWidth={0.15} />)}
        <path d={d} fill="none" style={{ stroke: "var(--ecg-trace)" }} strokeWidth={0.45} />
        {ws.map((w, i) => {
          const [on, off] = waveBounds(w);
          const key = kindToOverlayKey(w.kind);
          if (key === "QRS" && w.kind !== "QRS") return null;
          const c = WAVE_COLORS[w.kind];
          return (
            <g key={i}>
              <line x1={toX(on)} x2={toX(on)} y1={0} y2={H} stroke={c} strokeWidth={0.2} strokeDasharray="1 1" />
              <line x1={toX(off)} x2={toX(off)} y1={0} y2={H} stroke={c} strokeWidth={0.2} strokeDasharray="1 1" />
              {w.peak_ms != null && <circle cx={toX(w.peak_ms)} cy={y(sig[Math.round(((w.peak_ms - r0 + MEDIAN_PRE_MS) / 1000) * fs)] ?? 0)} r={0.7} fill={c} />}
            </g>
          );
        })}
        {iv && <>
          {br(iv.pr, H - 3, WAVE_COLORS.PR, "PR")}
          {br(iv.qrs, H - 6.5, WAVE_COLORS.QRS, "QRS")}
          {br(iv.qt, H - 10, WAVE_COLORS.QT, "QT")}
        </>}
      </svg>
    </figure>
  );
}

export default function MedianBeats({ analysis }: { analysis: ECGAnalysis }) {
  return (
    <div className="ecg-median-grid" data-testid="median-beats">
      {LEAD_ORDER.map((l) => <MedianLead key={l} a={analysis} lead={l} />)}
    </div>
  );
}
