import type { ConductionPhase, ECGAnalysis, LeadMeasurements, Wave } from "../../../types/api";
import { LEAD_ORDER, LIMB_LEAD_ANGLES, MEDIAN_PRE_MS } from "../ecgMath";

const FS = 500, DUR = 10, RR = 833, R0 = 600;
const PRE = MEDIAN_PRE_MS, POST = 500;
const QRS_AXIS = 60, P_AXIS = 50, T_AXIS = 45;

const PREC: Record<string, { r: number; s: number; t: number; p: number }> = {
  V1: { r: 0.2, s: -1.1, t: -0.1, p: 0.05 }, V2: { r: 0.5, s: -1.4, t: 0.3, p: 0.1 },
  V3: { r: 0.9, s: -0.9, t: 0.5, p: 0.12 }, V4: { r: 1.4, s: -0.5, t: 0.6, p: 0.13 },
  V5: { r: 1.6, s: -0.2, t: 0.5, p: 0.13 }, V6: { r: 1.3, s: -0.1, t: 0.4, p: 0.12 },
};
const cosd = (a: number, b: number) => Math.cos(((a - b) * Math.PI) / 180);

interface Amp { p: number; q: number; r: number; s: number; t: number }
function amps(lead: string): Amp {
  const pr = PREC[lead];
  if (pr) return { p: pr.p, q: lead === "V5" || lead === "V6" ? -0.1 : 0, r: pr.r, s: pr.s, t: pr.t };
  const a = LIMB_LEAD_ANGLES[lead];
  const qrs = 1.4 * cosd(QRS_AXIS, a);
  return {
    p: 0.16 * cosd(P_AXIS, a), q: qrs > 0.3 ? -0.08 * qrs : 0,
    r: qrs > 0 ? qrs : 0.05, s: qrs < 0 ? qrs : -0.05 * Math.abs(qrs) - 0.02, t: 0.45 * cosd(T_AXIS, a),
  };
}
const g = (t: number, c: number, s: number) => Math.exp(-0.5 * ((t - c) / s) ** 2);
/** Forma de onda de um batimento em t relativo ao pico R (ms). */
export function beatValue(a: Amp, t: number): number {
  return a.p * g(t, -150, 22) + a.q * g(t, -25, 6) + a.r * g(t, 0, 9) + a.s * g(t, 25, 8) + a.t * g(t, 215, 42);
}

let seed = 7;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296 - 0.5);

export function makeSampleAnalysis(): ECGAnalysis {
  seed = 7;
  const n = FS * DUR;
  const rPeaks: number[] = [];
  for (let r = R0; r < DUR * 1000 - 400; r += RR) rPeaks.push(r);
  const leads: Record<string, number[]> = {};
  const median: Record<string, number[]> = {};
  for (const l of LEAD_ORDER) {
    const a = amps(l);
    const arr = new Array<number>(n);
    for (let i = 0; i < n; i++) {
      const ms = (i / FS) * 1000;
      let v = 0.04 * Math.sin(2 * Math.PI * 0.25 * (i / FS)) + 0.008 * rnd();
      for (const r of rPeaks) if (Math.abs(ms - r) < 450) v += beatValue(a, ms - r);
      arr[i] = Number(v.toFixed(4));
    }
    leads[l] = arr;
    const m: number[] = [];
    for (let k = 0; k < ((PRE + POST) / 1000) * FS; k++) m.push(Number(beatValue(a, (k / FS) * 1000 - PRE).toFixed(4)));
    median[l] = m;
  }
  const waves: Wave[] = [];
  const leadAmp = (l: string, v: number) => Number(v.toFixed(2));
  rPeaks.forEach((r, b) => {
    for (const l of LEAD_ORDER) {
      const a = amps(l);
      const add = (kind: Wave["kind"], on: number, pk: number, off: number, amp: number, morph: string) =>
        waves.push({ kind, lead: l, beat_index: b, onset_ms: r + on, peak_ms: r + pk, offset_ms: r + off, amplitude_mv: leadAmp(l, amp), duration_ms: off - on, morphology: morph });
      add("P", -200, -150, -100, a.p, a.p >= 0.02 ? "positiva monofásica" : "negativa");
      if (a.q < -0.02) add("Q", -40, -25, -12, a.q, "q septal");
      add("R", -12, 0, 12, a.r, "R");
      if (a.s < -0.05) add("S", 12, 25, 40, a.s, "S");
      add("QRS", -40, 0, 40, a.r, a.r > Math.abs(a.s) ? "Rs" : "rS");
      add("T", 115, 215, 315, a.t, a.t >= 0 ? "positiva assimétrica" : "negativa");
    }
  });
  const lead_measurements: LeadMeasurements[] = LEAD_ORDER.map((l) => {
    const a = amps(l);
    return {
      lead: l, p_duration_ms: 100, p_amplitude_mv: Number(a.p.toFixed(2)), pr_ms: 160, qrs_ms: 80,
      q_amplitude_mv: Number(a.q.toFixed(2)), q_duration_ms: a.q < -0.02 ? 16 : 0,
      r_amplitude_mv: Number(a.r.toFixed(2)), s_amplitude_mv: Number(a.s.toFixed(2)), t_amplitude_mv: Number(a.t.toFixed(2)),
      qt_ms: 355, st_j_mv: 0.02, st_j60_mv: 0.03, st_j80_mv: 0.04, intrinsicoid_deflection_ms: 35,
      morphology: a.r > Math.abs(a.s) ? "Rs" : "rS",
    };
  });
  const hr = 60000 / RR, qt = 355, rrS = RR / 1000;
  const conduction: ConductionPhase[] = [
    { structure: "SA", start_ms: 0, end_ms: 30, ecg_correlate: "pré-P (invisível)", note: "O nó sinusal despolariza espontaneamente (automatismo)." },
    { structure: "atria", start_ms: 30, end_ms: 100, ecg_correlate: "onda P", note: "Átrio direito e depois esquerdo: vetor para baixo e à esquerda." },
    { structure: "AV_node", start_ms: 100, end_ms: 140, ecg_correlate: "segmento PR", note: "Atraso fisiológico do nó AV." },
    { structure: "His", start_ms: 140, end_ms: 150, ecg_correlate: "fim do segmento PR" },
    { structure: "RBB", start_ms: 150, end_ms: 162, ecg_correlate: "início do QRS" },
    { structure: "LBB", start_ms: 150, end_ms: 162, ecg_correlate: "início do QRS (septo: q em V5-V6)" },
    { structure: "purkinje", start_ms: 158, end_ms: 185, ecg_correlate: "QRS (ativação endo→epicárdica)" },
    { structure: "ventricles_depol", start_ms: 160, end_ms: 240, ecg_correlate: "complexo QRS" },
    { structure: "ventricles_repol", start_ms: 240, end_ms: 515, ecg_correlate: "segmento ST e onda T" },
  ];
  return {
    study_id: "demo-ecg",
    signal: { fs: FS, leads, duration_s: DUR, source: "csv", quality: Object.fromEntries(LEAD_ORDER.map((l, i) => [l, i === 3 ? 0.62 : 0.95 - (i % 3) * 0.05])), calibration: { mm_per_s: 25, mm_per_mv: 10 } },
    r_peaks_ms: rPeaks, waves, median_beats: median, lead_measurements,
    global_measurements: {
      heart_rate_bpm: Number(hr.toFixed(0)), rr_mean_ms: RR, rr_sd_ms: 12, p_duration_ms: 100, pr_ms: 160, qrs_ms: 80, qt_ms: qt,
      qtc_bazett_ms: Math.round(qt / Math.sqrt(rrS)), qtc_fridericia_ms: Math.round(qt / Math.cbrt(rrS)),
      qtc_framingham_ms: Math.round(qt + 154 * (1 - rrS)), qtc_hodges_ms: Math.round(qt + 1.75 * (hr - 60)),
      p_axis_deg: P_AXIS, qrs_axis_deg: QRS_AXIS, t_axis_deg: T_AXIS, sokolow_lyon_mv: 2.7, cornell_mv: 1.6,
      precordial_transition: "V3", rhythm: "Ritmo sinusal",
    },
    conduction,
    findings: [
      { code: "SINUS_RHYTHM", label: "Ritmo sinusal regular", severity: "normal", evidence: ["P positiva em I, II e aVF", "PR 160 ms"], references: [], confidence: 0.9, origin: "rules" },
      { code: "ST_V4", label: "Discreta elevação do ST em V4-V5", severity: "borderline", evidence: ["ST J+60 de 0,03 mV em V4 e V5"], references: [], confidence: 0.5, origin: "rules" },
    ],
    ai: null,
    warnings: ["Sinal sintético de demonstração: não é um registro real."],
  };
}
export const sampleAnalysis = makeSampleAnalysis();
