import { useMemo, useState } from "react";
import type { ECGAnalysis, Finding } from "../../types/api";
import "./ecg.css";
import EcgPaper from "./EcgPaper";
import { GlobalTable, LeadTable } from "./MeasurementsTable";
import AxisWheel from "./AxisWheel";
import MedianBeats from "./MedianBeats";
import ConductionPanel from "./ConductionPanel";
import { caliperLabel, type CaliperMeasure } from "./Calipers";
import {
  GAINS, OVERLAY_KEYS, OVERLAY_LABEL, SPEEDS, WAVE_COLORS, allOverlays, inferEvidence,
  type LayoutKind, type OverlayKey,
} from "./ecgMath";

type Tab = "tracado" | "medidas" | "mediano" | "conducao";
const TABS: [Tab, string][] = [["tracado", "Traçado"], ["medidas", "Medidas"], ["mediano", "Batimento mediano"], ["conducao", "Condução cardíaca"]];
const LAYOUTS: [LayoutKind, string][] = [["3x4+1", "3×4 + ritmo II"], ["6x2", "6×2"], ["12x1", "12×1 (10 s cada)"]];
const SEV_LABEL: Record<Finding["severity"], string> = { normal: "normal", borderline: "limítrofe", abnormal: "anormal", critical: "crítico" };

function qualityColor(q: number) { return q >= 0.8 ? "var(--ecg-ok)" : q >= 0.5 ? "var(--ecg-warn)" : "var(--ecg-bad)"; }

export default function ECGWorkspace({ analysis }: { analysis: ECGAnalysis }) {
  const [tab, setTab] = useState<Tab>("tracado");
  const [layout, setLayout] = useState<LayoutKind>("3x4+1");
  const [speed, setSpeed] = useState<number>(25);
  const [gain, setGain] = useState<number>(10);
  const [zoom, setZoom] = useState(1);
  const [overlay, setOverlay] = useState<Record<OverlayKey, boolean>>(allOverlays(false));
  const [isolate, setIsolate] = useState<string | null>(null);
  const [tool, setTool] = useState<"pan" | "calipers">("pan");
  const [calipers, setCalipers] = useState<CaliperMeasure[]>([]);
  const [highlight, setHighlight] = useState<string[]>([]);
  const [activeFinding, setActiveFinding] = useState<string | null>(null);

  const allOn = OVERLAY_KEYS.every((k) => overlay[k]);
  const g = analysis.global_measurements;
  const leadOrder = useMemo(() => Object.keys(analysis.signal.quality), [analysis]);

  const pickFinding = (f: Finding) => {
    if (activeFinding === f.code) { setActiveFinding(null); setHighlight([]); return; }
    const ev = inferEvidence(f);
    setActiveFinding(f.code);
    setHighlight(ev.leads);
    if (ev.keys.length) setOverlay((o) => ({ ...o, ...Object.fromEntries(ev.keys.map((k) => [k, true])) }));
    setTab("tracado");
  };

  return (
    <section className="ecg-ws" aria-label="Área de trabalho do ECG">
      {analysis.warnings.length > 0 && (
        <div className="ecg-card" role="alert" style={{ borderColor: "var(--ecg-warn)" }}>
          {analysis.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}

      <div className="ecg-card">
        <div className="ecg-row" aria-label="Achados">
          <strong>Achados:</strong>
          {analysis.findings.length === 0 && <span className="ecg-muted">nenhum achado automático</span>}
          {analysis.findings.map((f) => (
            <button key={f.code} className={`ecg-chip ${f.severity}`} aria-pressed={activeFinding === f.code}
              title={f.evidence.join(" · ")} onClick={() => pickFinding(f)}>
              {f.label} <small>({SEV_LABEL[f.severity]})</small>
            </button>
          ))}
        </div>
        {activeFinding && (
          <div className="ecg-muted" style={{ marginTop: 6 }}>
            Evidência: {analysis.findings.find((f) => f.code === activeFinding)?.evidence.join(" · ") || "—"}
            {highlight.length > 0 && ` — derivações destacadas: ${highlight.join(", ")}`}
          </div>
        )}
        <div className="ecg-row" style={{ marginTop: 8 }} aria-label="Qualidade do sinal">
          <strong>Qualidade:</strong>
          {leadOrder.map((l) => {
            const q = analysis.signal.quality[l];
            return <span key={l} className="ecg-badge" data-testid={`quality-${l}`} style={{ color: qualityColor(q), borderColor: qualityColor(q) }}
              title={q < 0.5 ? "Qualidade ruim: medidas pouco confiáveis" : q < 0.8 ? "Qualidade regular" : "Boa qualidade"}>{l} {(q * 100).toFixed(0)}%</span>;
          })}
        </div>
      </div>

      <div className="ecg-tabs" role="tablist">
        {TABS.map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>)}
      </div>

      {tab === "tracado" && (
        <div style={{ display: "grid", gap: 8 }}>
          <div className="ecg-card ecg-row">
            {isolate ? <button onClick={() => setIsolate(null)}>← Voltar às 12 derivações</button> : (
              <label>Layout <select value={layout} onChange={(e) => setLayout(e.target.value as LayoutKind)} aria-label="Layout">
                {LAYOUTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            )}
            <label>Velocidade <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Velocidade do papel">
              {SPEEDS.map((s) => <option key={s} value={s}>{s} mm/s</option>)}</select></label>
            <label>Ganho <select value={gain} onChange={(e) => setGain(Number(e.target.value))} aria-label="Ganho">
              {GAINS.map((s) => <option key={s} value={s}>{s} mm/mV</option>)}</select></label>
            <label>Zoom <input type="range" min={0.5} max={3} step={0.1} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} aria-label="Zoom" /></label>
            <button aria-pressed={tool === "pan"} onClick={() => setTool("pan")}>✋ Mover</button>
            <button aria-pressed={tool === "calipers"} onClick={() => setTool("calipers")}>📏 Compasso</button>
            {calipers.length > 0 && <button onClick={() => setCalipers([])}>Limpar medidas</button>}
          </div>
          <div className="ecg-card ecg-row" role="group" aria-label="Destacar ondas">
            <strong>Destacar:</strong>
            {OVERLAY_KEYS.map((k) => (
              <label key={k} style={{ color: WAVE_COLORS[k] }}>
                <input type="checkbox" checked={overlay[k]} onChange={(e) => setOverlay((o) => ({ ...o, [k]: e.target.checked }))} aria-label={`destacar ${OVERLAY_LABEL[k]}`} /> {OVERLAY_LABEL[k]}
              </label>
            ))}
            <button onClick={() => setOverlay(allOverlays(!allOn))}>{allOn ? "Nenhum" : "Todos"}</button>
          </div>
          <EcgPaper analysis={analysis} layout={layout} speed={speed} gain={gain} zoom={zoom} overlay={overlay}
            isolateLead={isolate} highlightLeads={highlight} tool={tool} calipers={calipers}
            onCalipersChange={setCalipers} onSelectLead={(l) => setIsolate(l)} />
          {tool === "calipers" && <div className="ecg-muted">Arraste sobre o traçado para medir (encaixa nos pontos fiduciais).</div>}
          {calipers.length > 0 && <ul style={{ margin: 0 }}>{calipers.map((m, i) => <li key={i}>{caliperLabel(m)}</li>)}</ul>}
        </div>
      )}

      {tab === "medidas" && (
        <div style={{ display: "grid", gap: 12 }}>
          <div className="ecg-grid-2">
            <div className="ecg-card"><GlobalTable g={g} /></div>
            <div className="ecg-card"><AxisWheel p={g.p_axis_deg} qrs={g.qrs_axis_deg} t={g.t_axis_deg} /></div>
          </div>
          <div className="ecg-card"><LeadTable rows={analysis.lead_measurements} highlight={highlight} /></div>
        </div>
      )}

      {tab === "mediano" && <div className="ecg-card"><MedianBeats analysis={analysis} /></div>}
      {tab === "conducao" && <ConductionPanel analysis={analysis} />}
    </section>
  );
}
