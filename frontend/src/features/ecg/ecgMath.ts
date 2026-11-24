import type {
  ConductionPhase, ConductionStructure, ECGAnalysis, Finding, GlobalMeasurements,
  LeadMeasurements, Wave, WaveKind,
} from "../../types/api";

/* ------------------------------------------------------------------ unidades */
export const PX_PER_MM_BASE = 96 / 25.4; // 1 mm real em uma tela de 96 dpi
export const SPEEDS = [12.5, 25, 50] as const;
export const GAINS = [5, 10, 20] as const;
export type PaperSpeed = (typeof SPEEDS)[number];
export type PaperGain = (typeof GAINS)[number];

export const msToMm = (ms: number, speed: number) => (ms / 1000) * speed;
export const mmToMs = (mm: number, speed: number) => (mm / speed) * 1000;
export const mvToMm = (mv: number, gain: number) => mv * gain;
export const mmToMv = (mm: number, gain: number) => mm / gain;
export const mmToPx = (mm: number, pxPerMm: number) => mm * pxPerMm;
export const pxToMm = (px: number, pxPerMm: number) => px / pxPerMm;
export const msToPx = (ms: number, speed: number, pxPerMm: number) => msToMm(ms, speed) * pxPerMm;
export const pxToMs = (px: number, speed: number, pxPerMm: number) => mmToMs(px / pxPerMm, speed);
export const mvToPx = (mv: number, gain: number, pxPerMm: number) => mvToMm(mv, gain) * pxPerMm;
export const pxToMv = (px: number, gain: number, pxPerMm: number) => mmToMv(px / pxPerMm, gain);
export const rrToBpm = (rrMs: number) => 60000 / rrMs;

/* ------------------------------------------------------------------ layout */
export type LayoutKind = "3x4+1" | "6x2" | "12x1" | "single";
export const LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"];

export interface Panel {
  lead: string; x: number; y: number; w: number; h: number; baseY: number;
  t0: number; t1: number; row: number; col: number; rhythm: boolean;
}
export interface Geometry {
  panels: Panel[]; width: number; height: number; marginLeft: number;
  speed: number; gain: number; pxPerMm: number; layout: LayoutKind;
}

export function buildGeometry(o: {
  layout: LayoutKind; durationMs: number; speed: number; gain: number; pxPerMm: number;
  isolateLead?: string | null;
}): Geometry {
  const { layout, durationMs, speed, gain, pxPerMm } = o;
  const marginLeft = mmToPx(msToMm(200, speed) + 4, pxPerMm);
  const topPad = mmToPx(2, pxPerMm);
  const mk = (lead: string, row: number, col: number, ncols: number, rowMm: number, rhythm = false): Panel => {
    const colMs = durationMs / ncols;
    const w = msToPx(colMs, speed, pxPerMm);
    const h = mmToPx(rowMm, pxPerMm);
    const y = topPad + row * h;
    return { lead, x: marginLeft + col * w, y, w, h, baseY: y + h / 2, t0: col * colMs, t1: (col + 1) * colMs, row, col, rhythm };
  };
  const panels: Panel[] = [];
  let rows = 0;
  let rowMm = 30;
  if (layout === "3x4+1") {
    for (let c = 0; c < 4; c++) for (let r = 0; r < 3; r++) panels.push(mk(LEAD_ORDER[c * 3 + r], r, c, 4, rowMm));
    panels.push(mk("II", 3, 0, 1, rowMm, true));
    rows = 4;
  } else if (layout === "6x2") {
    for (let c = 0; c < 2; c++) for (let r = 0; r < 6; r++) panels.push(mk(LEAD_ORDER[c * 6 + r], r, c, 2, rowMm));
    rows = 6;
  } else if (layout === "12x1") {
    rowMm = 26;
    LEAD_ORDER.forEach((l, r) => panels.push(mk(l, r, 0, 1, rowMm)));
    rows = 12;
  } else {
    rowMm = Math.max(60, gain * 6);
    panels.push(mk(o.isolateLead ?? "II", 0, 0, 1, rowMm));
    rows = 1;
  }
  const width = marginLeft + msToPx(durationMs, speed, pxPerMm) + mmToPx(2, pxPerMm);
  const height = topPad + rows * mmToPx(rowMm, pxPerMm) + mmToPx(2, pxPerMm);
  return { panels, width, height, marginLeft, speed, gain, pxPerMm, layout };
}
export const xOf = (g: Geometry, p: Panel, ms: number) => p.x + msToPx(ms - p.t0, g.speed, g.pxPerMm);
export const yOf = (g: Geometry, p: Panel, mv: number) => p.baseY - mvToPx(mv, g.gain, g.pxPerMm);
export const msAtX = (g: Geometry, p: Panel, x: number) => p.t0 + pxToMs(x - p.x, g.speed, g.pxPerMm);
export const mvAtY = (g: Geometry, p: Panel, y: number) => pxToMv(p.baseY - y, g.gain, g.pxPerMm);

/* ------------------------------------------------------------------ sinal */
export function sampleAt(samples: number[] | undefined, fs: number, ms: number): number {
  if (!samples || samples.length === 0) return 0;
  const f = (ms / 1000) * fs;
  const i = Math.floor(f);
  if (i < 0) return samples[0];
  if (i >= samples.length - 1) return samples[samples.length - 1];
  const a = f - i;
  return samples[i] * (1 - a) + samples[i + 1] * a;
}

/** Caminho SVG (decimado) de um trecho do traçado. */
export function tracePath(g: Geometry, p: Panel, samples: number[], fs: number): string {
  const i0 = Math.max(0, Math.floor((p.t0 / 1000) * fs));
  const i1 = Math.min(samples.length - 1, Math.ceil((p.t1 / 1000) * fs));
  const pxPerSample = msToPx(1000 / fs, g.speed, g.pxPerMm);
  const stride = Math.max(1, Math.floor(0.6 / Math.max(pxPerSample, 1e-6)));
  const parts: string[] = [];
  for (let i = i0; i <= i1; i += stride) {
    const x = p.x + msToPx((i / fs) * 1000 - p.t0, g.speed, g.pxPerMm);
    const yy = Math.max(p.y, Math.min(p.y + p.h, yOf(g, p, samples[i])));
    parts.push(`${parts.length ? "L" : "M"}${x.toFixed(1)} ${yy.toFixed(1)}`);
  }
  return parts.join("");
}

/* ------------------------------------------------------------------ ondas */
export type OverlayKey = "P" | "QRS" | "T" | "U" | "PR" | "QT" | "ST";
export const OVERLAY_KEYS: OverlayKey[] = ["P", "QRS", "T", "U", "PR", "QT", "ST"];
export const OVERLAY_LABEL: Record<OverlayKey, string> = {
  P: "P", QRS: "QRS", T: "T", U: "U", PR: "intervalo PR", QT: "intervalo QT", ST: "segmento ST",
};
export const WAVE_COLORS: Record<WaveKind | "PR" | "QT" | "ST", string> = {
  P: "#2f80ed", Q: "#8e44ad", R: "#d62828", S: "#e67e22", "R'": "#c2185b",
  T: "#2e9e5b", U: "#8d6e63", QRS: "#d62828", PR: "#12a594", QT: "#7b61ff", ST: "#d99a00",
};
export const WAVE_NAMES: Record<WaveKind, string> = {
  P: "onda P", Q: "onda Q", R: "onda R", S: "onda S", "R'": "onda R'", T: "onda T", U: "onda U", QRS: "complexo QRS",
};
export const allOverlays = (v: boolean): Record<OverlayKey, boolean> =>
  ({ P: v, QRS: v, T: v, U: v, PR: v, QT: v, ST: v });

export function kindToOverlayKey(k: WaveKind): "P" | "QRS" | "T" | "U" {
  if (k === "P") return "P";
  if (k === "T") return "T";
  if (k === "U") return "U";
  return "QRS";
}
export function waveBounds(w: Wave): [number, number] {
  const b = w.offset_ms ?? (w.duration_ms != null ? w.onset_ms + w.duration_ms : w.peak_ms ?? w.onset_ms);
  return [w.onset_ms, Math.max(b, w.onset_ms)];
}
export const wavesOfLead = (waves: Wave[], lead: string) => waves.filter((w) => w.lead === lead);

export interface BeatIntervals {
  lead: string; beat: number;
  p?: [number, number]; qrs?: [number, number]; t?: [number, number];
  pr?: [number, number]; qt?: [number, number]; st?: [number, number];
}
export function beatIntervals(waves: Wave[], lead?: string): BeatIntervals[] {
  const map = new Map<string, Wave[]>();
  for (const w of waves) {
    if (lead && w.lead !== lead) continue;
    const k = `${w.lead}|${w.beat_index}`;
    (map.get(k) ?? map.set(k, []).get(k)!).push(w);
  }
  const out: BeatIntervals[] = [];
  for (const [k, ws] of map) {
    const [l, b] = k.split("|");
    const item: BeatIntervals = { lead: l, beat: Number(b) };
    const P = ws.find((w) => w.kind === "P");
    const T = ws.find((w) => w.kind === "T");
    const Q = ws.find((w) => w.kind === "QRS");
    if (P) item.p = waveBounds(P);
    if (T) item.t = waveBounds(T);
    if (Q) item.qrs = waveBounds(Q);
    else {
      const parts = ws.filter((w) => ["Q", "R", "S", "R'"].includes(w.kind)).map(waveBounds);
      if (parts.length) item.qrs = [Math.min(...parts.map((x) => x[0])), Math.max(...parts.map((x) => x[1]))];
    }
    if (item.p && item.qrs) item.pr = [item.p[0], item.qrs[0]];
    if (item.qrs && item.t) { item.qt = [item.qrs[0], item.t[1]]; item.st = [item.qrs[1], item.t[0]]; }
    out.push(item);
  }
  return out.sort((a, b) => a.beat - b.beat);
}
export function fiducialsMs(waves: Wave[], lead: string): number[] {
  const s = new Set<number>();
  for (const w of waves) {
    if (w.lead !== lead) continue;
    s.add(w.onset_ms);
    if (w.peak_ms != null) s.add(w.peak_ms);
    if (w.offset_ms != null) s.add(w.offset_ms);
  }
  return [...s].sort((a, b) => a - b);
}
export function snapToNearest(ms: number, list: number[], tolMs: number): { value: number; snapped: boolean } {
  let best = ms, d = tolMs, snapped = false;
  for (const f of list) {
    const dd = Math.abs(f - ms);
    if (dd <= d) { best = f; d = dd; snapped = true; }
  }
  return { value: best, snapped };
}

const f1 = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toFixed(d));
export function waveTooltip(w: Wave): { title: string; lines: string[] } {
  const [a, b] = waveBounds(w);
  return {
    title: `${WAVE_NAMES[w.kind]} — ${w.lead} (batimento ${w.beat_index + 1})`,
    lines: [
      `início ${f1(a)} ms · pico ${f1(w.peak_ms)} ms · fim ${f1(w.offset_ms ?? b)} ms`,
      `duração ${f1(w.duration_ms ?? b - a)} ms · amplitude ${f1(w.amplitude_mv, 2)} mV`,
      `morfologia: ${w.morphology ?? "–"}`,
    ],
  };
}

/* ------------------------------------------------------------------ faixas normais */
export interface Range { min?: number; max?: number; label: string }
export const inRange = (v: number | null | undefined, r?: Range) =>
  v == null || !r ? true : (r.min == null || v >= r.min) && (r.max == null || v <= r.max);

export interface GlobalRow {
  key: keyof GlobalMeasurements; label: string; unit: string; decimals: number; range?: Range;
}
export const GLOBAL_ROWS: GlobalRow[] = [
  { key: "heart_rate_bpm", label: "Frequência cardíaca", unit: "bpm", decimals: 0, range: { min: 60, max: 100, label: "60–100" } },
  { key: "rr_mean_ms", label: "RR médio", unit: "ms", decimals: 0, range: { min: 600, max: 1000, label: "600–1000" } },
  { key: "rr_sd_ms", label: "RR desvio-padrão", unit: "ms", decimals: 0, range: { max: 120, label: "< 120" } },
  { key: "p_duration_ms", label: "Duração da P", unit: "ms", decimals: 0, range: { max: 120, label: "< 120" } },
  { key: "pr_ms", label: "Intervalo PR", unit: "ms", decimals: 0, range: { min: 120, max: 200, label: "120–200" } },
  { key: "qrs_ms", label: "Duração do QRS", unit: "ms", decimals: 0, range: { max: 110, label: "< 110" } },
  { key: "qt_ms", label: "QT", unit: "ms", decimals: 0, range: { min: 320, max: 440, label: "320–440" } },
  { key: "qtc_bazett_ms", label: "QTc Bazett", unit: "ms", decimals: 0, range: { max: 450, label: "< 450 (H) / 460 (M)" } },
  { key: "qtc_fridericia_ms", label: "QTc Fridericia", unit: "ms", decimals: 0, range: { max: 450, label: "< 450" } },
  { key: "qtc_framingham_ms", label: "QTc Framingham", unit: "ms", decimals: 0, range: { max: 450, label: "< 450" } },
  { key: "qtc_hodges_ms", label: "QTc Hodges", unit: "ms", decimals: 0, range: { max: 450, label: "< 450" } },
  { key: "p_axis_deg", label: "Eixo da P", unit: "°", decimals: 0, range: { min: 0, max: 75, label: "0 a +75" } },
  { key: "qrs_axis_deg", label: "Eixo do QRS", unit: "°", decimals: 0, range: { min: -30, max: 90, label: "−30 a +90" } },
  { key: "t_axis_deg", label: "Eixo da T", unit: "°", decimals: 0, range: { min: 0, max: 90, label: "0 a +90" } },
  { key: "sokolow_lyon_mv", label: "Sokolow-Lyon (S V1 + R V5/V6)", unit: "mV", decimals: 2, range: { max: 3.5, label: "< 3,5" } },
  { key: "cornell_mv", label: "Cornell (R aVL + S V3)", unit: "mV", decimals: 2, range: { max: 2.8, label: "< 2,8 (H) / 2,0 (M)" } },
  { key: "precordial_transition", label: "Transição precordial", unit: "", decimals: 0 },
  { key: "rhythm", label: "Ritmo", unit: "", decimals: 0 },
];

export interface LeadCol {
  key: keyof LeadMeasurements; label: string; decimals: number; range?: Range; abs?: boolean;
}
export const LEAD_COLS: LeadCol[] = [
  { key: "p_duration_ms", label: "P (ms)", decimals: 0, range: { max: 120, label: "" } },
  { key: "p_amplitude_mv", label: "P (mV)", decimals: 2, range: { max: 0.25, label: "" } },
  { key: "pr_ms", label: "PR (ms)", decimals: 0, range: { min: 120, max: 200, label: "" } },
  { key: "qrs_ms", label: "QRS (ms)", decimals: 0, range: { max: 110, label: "" } },
  { key: "q_amplitude_mv", label: "Q (mV)", decimals: 2 },
  { key: "q_duration_ms", label: "Q (ms)", decimals: 0, range: { max: 40, label: "" } },
  { key: "r_amplitude_mv", label: "R (mV)", decimals: 2 },
  { key: "s_amplitude_mv", label: "S (mV)", decimals: 2 },
  { key: "t_amplitude_mv", label: "T (mV)", decimals: 2 },
  { key: "qt_ms", label: "QT (ms)", decimals: 0, range: { min: 320, max: 440, label: "" } },
  { key: "st_j_mv", label: "ST J", decimals: 2, range: { min: -0.1, max: 0.1, label: "" } },
  { key: "st_j60_mv", label: "ST J+60", decimals: 2, range: { min: -0.1, max: 0.1, label: "" } },
  { key: "st_j80_mv", label: "ST J+80", decimals: 2, range: { min: -0.1, max: 0.1, label: "" } },
  { key: "intrinsicoid_deflection_ms", label: "DI (ms)", decimals: 0, range: { max: 50, label: "" } },
];

/* ------------------------------------------------------------------ eixos */
export const LIMB_LEAD_ANGLES: Record<string, number> = { I: 0, II: 60, III: 120, aVR: -150, aVL: -30, aVF: 90 };
export function normDeg(d: number) {
  let x = ((d + 180) % 360 + 360) % 360 - 180;
  if (x === -180) x = 180;
  return x;
}
export function classifyAxis(deg: number): string {
  const a = normDeg(deg);
  if (a >= -30 && a <= 90) return "normal";
  if (a < -30 && a >= -90) return "desvio para a esquerda";
  if (a > 90) return "desvio para a direita";
  return "desvio extremo (terra de ninguém)";
}
/** cos(Δ) entre o vetor e o eixo da derivação (null se não for derivação de membros). */
export function projection(axisDeg: number, lead: string): number | null {
  const a = LIMB_LEAD_ANGLES[lead];
  if (a == null) return null;
  return Math.cos(((axisDeg - a) * Math.PI) / 180);
}
export function polarityLabel(proj: number): "positiva" | "negativa" | "isobifásica" {
  if (proj > 0.2) return "positiva";
  if (proj < -0.2) return "negativa";
  return "isobifásica";
}

/* ------------------------------------------------------------------ condução */
export const STRUCTURE_LABELS: Record<ConductionStructure, string> = {
  SA: "Nó sinusal (SA)", atria: "Átrios", AV_node: "Nó AV", His: "Feixe de His",
  RBB: "Ramo direito", LBB: "Ramo esquerdo", purkinje: "Rede de Purkinje",
  ventricles_depol: "Despolarização ventricular", ventricles_repol: "Repolarização ventricular",
};
export const STRUCTURE_ORDER: ConductionStructure[] = [
  "SA", "atria", "AV_node", "His", "RBB", "LBB", "purkinje", "ventricles_depol", "ventricles_repol",
];
export const STRUCTURE_COLORS: Record<ConductionStructure, string> = {
  SA: "#ffd23f", atria: "#2f80ed", AV_node: "#ff8a00", His: "#ff5d73", RBB: "#e6007a",
  LBB: "#b100ff", purkinje: "#00c2a8", ventricles_depol: "#e63946", ventricles_repol: "#2e9e5b",
};
export const conductionTotal = (ph: ConductionPhase[]) => ph.reduce((m, p) => Math.max(m, p.end_ms), 0);
export const phasesAt = (ph: ConductionPhase[], t: number) => ph.filter((p) => t >= p.start_ms && t < p.end_ms);
export function advanceTime(t: number, dtMs: number, speed: number, lo: number, hi: number, loop: boolean) {
  let n = t + dtMs * speed;
  if (hi <= lo) return { t: lo, ended: true };
  if (n >= hi) { if (loop) n = lo + ((n - lo) % (hi - lo)); else return { t: hi, ended: true }; }
  return { t: Math.max(lo, n), ended: false };
}

/** Janela do batimento mediano: R em MEDIAN_PRE_MS a partir do início do vetor. */
export const MEDIAN_PRE_MS = 300;
export const medianRelR = (i: number, fs: number) => (i / fs) * 1000 - MEDIAN_PRE_MS;

/** Origem (t=0) do tempo de condução: início da P do 1º batimento (senão R − 200 ms). */
export function conductionOrigin(a: ECGAnalysis): number {
  const ps = a.waves.filter((w) => w.kind === "P" && w.beat_index === 0);
  const pref = ps.find((w) => w.lead === "II") ?? ps[0];
  if (pref) return pref.onset_ms;
  return (a.r_peaks_ms[0] ?? 200) - 200;
}
/** Instante do R do 1º batimento relativo à origem de condução. */
export const rOffsetFromOrigin = (a: ECGAnalysis) => (a.r_peaks_ms[0] ?? 200) - conductionOrigin(a);

const SMALL_TISSUE: ConductionStructure[] = ["SA", "AV_node", "His", "RBB", "LBB"];
function axisFor(s: ConductionStructure, g: GlobalMeasurements): { name: string; deg: number | null | undefined } | null {
  if (s === "atria") return { name: "onda P", deg: g.p_axis_deg };
  if (s === "ventricles_depol" || s === "purkinje") return { name: "complexo QRS", deg: g.qrs_axis_deg };
  if (s === "ventricles_repol") return { name: "onda T", deg: g.t_axis_deg };
  return null;
}
export function explainLead(s: ConductionStructure, lead: string, g: GlobalMeasurements, lm?: LeadMeasurements): string {
  const ax = axisFor(s, g);
  if (!ax) {
    const extra = s === "SA" ? "A despolarização do nó sinusal ocorre antes da P e não é visível no ECG de superfície."
      : s === "AV_node" ? "O atraso fisiológico no nó AV forma o segmento PR (linha isoelétrica)."
      : s === "His" ? "A condução His-Purkinje precede o QRS e fica no fim do segmento PR."
      : "A condução pelos ramos precede e desencadeia o QRS.";
    return `${STRUCTURE_LABELS[s]}: massa de tecido muito pequena e/ou sem sincronismo suficiente para gerar voltagem na superfície; traçado isoelétrico em ${lead}. ${extra}`;
  }
  const pr = ax.deg == null ? null : projection(ax.deg, lead);
  let txt: string;
  if (ax.deg != null && pr != null) {
    const dir = polarityLabel(pr);
    txt = `Vetor médio da ${ax.name} em ${normDeg(ax.deg).toFixed(0)}°; ${lead} está em ${LIMB_LEAD_ANGLES[lead]}°. Projeção = cos(${Math.abs(normDeg(ax.deg - LIMB_LEAD_ANGLES[lead])).toFixed(0)}°) = ${pr.toFixed(2)} → deflexão ${dir}` +
      (dir === "positiva" ? " (o vetor se aproxima do polo positivo da derivação)." : dir === "negativa" ? " (o vetor se afasta do polo positivo)." : " (vetor quase perpendicular à derivação).");
  } else if (lead.startsWith("V")) {
    const n = Number(lead.slice(1));
    if (ax.name === "onda P") txt = n === 1 ? "V1 vê primeiro o átrio direito (vetor se aproxima) e depois o esquerdo (posterior, se afasta): P tipicamente bifásica (+/−)." : "O vetor atrial vai para a esquerda/baixo e se aproxima das precordiais esquerdas: P positiva.";
    else if (ax.name === "onda T") txt = n <= 1 ? "Em V1 a T pode ser negativa, isoelétrica ou positiva (variante normal): o vetor de repolarização aponta para trás/esquerda." : "A repolarização (epicárdio→endocárdio) gera vetor para frente/esquerda/baixo, na direção das precordiais: T positiva.";
    else txt = n <= 2 ? `${lead} fica à direita/frente do septo: o vetor dominante do VE (para trás e à esquerda) se afasta → S profundo, r pequeno (septal inicial se aproxima).`
      : n <= 4 ? `${lead} está na zona de transição: forças anteriores (VD/septo) e posteriores (VE) se equilibram → QRS bifásico (R ≈ S).`
      : `${lead} olha a parede livre do VE: o vetor dominante se aproxima → R alto, q septal pequeno e s discreto.`;
  } else txt = "Eixo não disponível para calcular a projeção.";
  if (lm) {
    const o: string[] = [];
    if (ax.name === "complexo QRS") { if (lm.r_amplitude_mv != null) o.push(`R ${lm.r_amplitude_mv.toFixed(2)} mV`); if (lm.s_amplitude_mv != null) o.push(`S ${lm.s_amplitude_mv.toFixed(2)} mV`); }
    if (ax.name === "onda P" && lm.p_amplitude_mv != null) o.push(`P ${lm.p_amplitude_mv.toFixed(2)} mV`);
    if (ax.name === "onda T" && lm.t_amplitude_mv != null) o.push(`T ${lm.t_amplitude_mv.toFixed(2)} mV`);
    if (o.length) txt += ` Medido: ${o.join(", ")}.`;
  }
  return txt;
}
export const isSmallTissue = (s: ConductionStructure) => SMALL_TISSUE.includes(s);

/* ------------------------------------------------------------------ achados */
const LEAD_RE = /\b(aVR|aVL|aVF|V[1-6])\b|\bD(III|II|I|[123])\b|(?:deriva[cç][oõ]es?|leads?)\s+(III|II|I)\b/gi;
export function inferEvidence(f: Finding): { leads: string[]; keys: OverlayKey[] } {
  const text = [f.label, f.code, ...f.evidence].join(" ; ");
  const leads = new Set<string>();
  for (const m of text.matchAll(LEAD_RE)) {
    let l = m[1] ?? (m[2] ? `D${m[2]}` : m[3]);
    if (!l) continue;
    if (/^D/i.test(l)) l = { "1": "I", "2": "II", "3": "III" }[l.slice(1)] ?? l.slice(1).toUpperCase();
    const std = LEAD_ORDER.find((x) => x.toLowerCase() === l.toLowerCase());
    if (std) leads.add(std);
  }
  const keys = new Set<OverlayKey>();
  if (/\bQRS\b|bloqueio|ramo|BRD|BRE|hipertrofia|onda Q|Q patol/i.test(text)) keys.add("QRS");
  if (/\bQTc?\b/.test(text)) keys.add("QT");
  if (/\bPR\b|\bBAV\b|AV/.test(text)) keys.add("PR");
  if (/\bST\b|infra|supra|isquemi|IAM/i.test(text)) keys.add("ST");
  if (/onda T|\bT\b/.test(text)) keys.add("T");
  if (/onda P|\bP\b|sobrecarga atrial/.test(text)) keys.add("P");
  return { leads: [...leads], keys: [...keys] };
}
