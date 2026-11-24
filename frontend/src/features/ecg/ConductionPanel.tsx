import { useMemo, useState } from "react";
import type { ConductionStructure, ECGAnalysis } from "../../types/api";
import ConductionHeart from "./ConductionHeart";
import { useConductionPlayer } from "./useConductionPlayer";
import {
  LEAD_ORDER, MEDIAN_PRE_MS, STRUCTURE_COLORS, STRUCTURE_LABELS, STRUCTURE_ORDER,
  explainLead, rOffsetFromOrigin,
} from "./ecgMath";

const SPEEDS = [0.1, 0.25, 0.5, 1];
type Mode = "conjunto" | "isolar";

export default function ConductionPanel({ analysis }: { analysis: ECGAnalysis }) {
  const phases = analysis.conduction;
  const [mode, setMode] = useState<Mode>("conjunto");
  const [picked, setPicked] = useState<ConductionStructure | null>(null);
  const [leads, setLeads] = useState<string[]>(["II"]);
  const range = useMemo<[number, number] | null>(() => {
    if (mode !== "isolar" || !picked) return null;
    const ps = phases.filter((p) => p.structure === picked);
    if (!ps.length) return null;
    return [Math.min(...ps.map((p) => p.start_ms)), Math.max(...ps.map((p) => p.end_ms))];
  }, [mode, picked, phases]);
  const pl = useConductionPlayer(phases, range);
  const isolate = mode === "isolar";
  const litPhases = isolate ? phases.filter((p) => p.structure === picked) : pl.active;
  const lit = [...new Set(litPhases.map((p) => p.structure))];
  const rOff = rOffsetFromOrigin(analysis);
  const fs = analysis.signal.fs;

  const toggleLead = (l: string) => setLeads((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l]));
  const pickable = STRUCTURE_ORDER;
  const has = (s: ConductionStructure) => phases.some((p) => p.structure === s);

  // painel de 12 derivações (batimento mediano), eixo = tempo de condução
  const W = 200, H = 60;
  const tcOf = (i: number) => (i / fs) * 1000 - MEDIAN_PRE_MS + rOff; // ms relativos à origem
  const lenMs = (Object.values(analysis.median_beats)[0]?.length ?? 1) / fs * 1000;
  const t0 = tcOf(0), t1 = t0 + lenMs;
  const px = (tc: number) => ((tc - t0) / (t1 - t0)) * W;

  return (
    <div style={{ display: "grid", gap: 12 }} data-testid="conduction-panel">
      <div className="ecg-row" role="group" aria-label="Modo">
        <button aria-pressed={mode === "conjunto"} onClick={() => setMode("conjunto")}>Condução em conjunto</button>
        <button aria-pressed={mode === "isolar"} onClick={() => setMode("isolar")}>Isolar estrutura</button>
      </div>
      {isolate && (
        <div className="ecg-row" role="group" aria-label="Estrutura">
          {pickable.map((s) => (
            <button key={s} aria-pressed={picked === s} disabled={!has(s)} onClick={() => setPicked(s)}
              style={picked === s ? { background: STRUCTURE_COLORS[s], borderColor: STRUCTURE_COLORS[s] } : undefined}>
              {STRUCTURE_LABELS[s]}
            </button>
          ))}
        </div>
      )}
      <div className="ecg-row">
        <button onClick={pl.toggle} aria-label={pl.playing ? "Pausar" : "Reproduzir"}>{pl.playing ? "⏸ Pausar" : "▶ Reproduzir"}</button>
        <button onClick={pl.reset}>⏮ Reiniciar</button>
        <label>Velocidade{" "}
          <select value={pl.speed} onChange={(e) => pl.setSpeed(Number(e.target.value))} aria-label="Velocidade">
            {SPEEDS.map((s) => <option key={s} value={s}>{s}x</option>)}
          </select>
        </label>
        <label><input type="checkbox" checked={pl.loop} onChange={(e) => pl.setLoop(e.target.checked)} /> repetir</label>
        <input type="range" min={pl.lo} max={pl.hi} step={1} value={pl.t} onChange={(e) => pl.seek(Number(e.target.value))}
          aria-label="Posição no batimento" style={{ flex: 1, minWidth: 140 }} />
        <span className="ecg-muted" data-testid="conduction-time">{pl.t.toFixed(0)} ms</span>
      </div>

      <div className="ecg-grid-2">
        <div className="ecg-card">
          <ConductionHeart active={lit} onPick={(s) => { if (isolate && has(s)) setPicked(s); }} />
          <div className="ecg-row" aria-live="polite" data-testid="active-phases">
            {litPhases.length === 0 && <span className="ecg-muted">{isolate ? "Selecione uma estrutura." : "Sem ativação elétrica nesta fase (isoelétrico)."}</span>}
            {litPhases.map((p, i) => (
              <span key={i} className="ecg-badge" style={{ borderColor: STRUCTURE_COLORS[p.structure] }}>
                <strong>{STRUCTURE_LABELS[p.structure]}</strong> → {p.ecg_correlate}
              </span>
            ))}
          </div>
          {litPhases.map((p, i) => p.note && <p key={i} className="ecg-muted" style={{ margin: "4px 0" }}>{p.note}</p>)}
        </div>

        <div className="ecg-card">
          <div className="ecg-muted" style={{ marginBottom: 4 }}>Batimento mediano das 12 derivações — clique para escolher derivações a explicar.</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 6 }}>
            {LEAD_ORDER.map((l) => {
              const sig = analysis.median_beats[l];
              if (!sig) return null;
              const d = sig.map((v, i) => `${i ? "L" : "M"}${px(tcOf(i)).toFixed(1)} ${(H / 2 - v * 18).toFixed(1)}`).join("");
              const sel = leads.includes(l);
              return (
                <svg key={l} viewBox={`0 0 ${W} ${H}`} role="button" aria-label={`Derivação ${l}`} aria-pressed={sel} data-lead={l}
                  onClick={() => toggleLead(l)} style={{ width: "100%", background: "var(--ecg-paper)", border: `2px solid ${sel ? "var(--ecg-accent)" : "var(--ecg-line)"}`, borderRadius: 6, cursor: "pointer" }}>
                  {litPhases.map((p, i) => (
                    <rect key={i} data-testid="phase-band" x={px(p.start_ms)} width={Math.max(1, px(p.end_ms) - px(p.start_ms))} y={0} height={H}
                      fill={STRUCTURE_COLORS[p.structure]} fillOpacity={0.3} />
                  ))}
                  <path d={d} fill="none" style={{ stroke: "var(--ecg-trace)" }} strokeWidth={1.2} />
                  {!isolate && <line data-testid="cursor" x1={px(pl.t)} x2={px(pl.t)} y1={0} y2={H} stroke="var(--ecg-accent)" strokeWidth={1.5} />}
                  <text x={3} y={11} fontSize={10} fontWeight={700} style={{ fill: "var(--ecg-fg)" }}>{l}</text>
                </svg>
              );
            })}
          </div>
        </div>
      </div>

      <div className="ecg-card" data-testid="lead-explanations">
        <strong>Por que a deflexão é assim em cada derivação?</strong>
        {leads.length === 0 && <p className="ecg-muted">Selecione ao menos uma derivação.</p>}
        {leads.map((l) => (
          <div key={l} style={{ marginTop: 6 }}>
            <span className="ecg-badge" style={{ marginRight: 6 }}>{l}</span>
            {litPhases.length === 0
              ? <span className="ecg-muted">Nesta fase não há atividade registrável: linha de base isoelétrica.</span>
              : litPhases.map((p, i) => (
                <div key={i} style={{ marginLeft: 8 }}>
                  <em>{STRUCTURE_LABELS[p.structure]}:</em> {explainLead(p.structure, l, analysis.global_measurements, analysis.lead_measurements.find((x) => x.lead === l))}
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}
