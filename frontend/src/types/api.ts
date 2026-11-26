// Mirror of backend/app/schemas.py — keep in sync. Units: ms, mV, mm, px.

export type Modality = "ECG" | "RX" | "UNKNOWN";
export type SourceKind = "dicom" | "image" | "aecg_xml" | "csv" | "wfdb";

export interface Reference { id: string; source: string; note?: string | null }

export interface Finding {
  code: string;
  label: string;
  severity: "normal" | "borderline" | "abnormal" | "critical";
  evidence: string[];
  references: Reference[];
  confidence: number;
  origin: "rules" | "model" | "llm";
}

export interface Differential {
  diagnosis: string;
  rationale: string;
  supporting: string[];
  against: string[];
  references: Reference[];
  confidence: number;
}

export interface AIReport {
  available: boolean;
  model?: string | null;
  description: string;
  findings: Finding[];
  differentials: Differential[];
  disagreements_with_measurements: string[];
  limitations: string[];
  disclaimer: string;
  laudo?: Record<string, unknown> | null;
  laudo_markdown?: string;
  laudo_curto?: string;
  /** ECG: descrição completa em parágrafo único; origem "ia" (redigida e verificada) ou "deterministico". */
  descricao_completa?: string;
  descricao_origem?: "ia" | "deterministico" | "";
  descricao_validacao?: number;
}

export interface SeriesInfo {
  series_uid: string;
  modality: Modality;
  dicom_modality?: string | null;
  description?: string | null;
  view_position?: string | null;
  body_part?: string | null;
  n_instances: number;
  instance_ids: string[];
}

export interface StudyInfo {
  study_id: string;
  study_uid?: string | null;
  patient_age?: string | null;
  patient_sex?: string | null;
  series: SeriesInfo[];
  created_at: string;
}

export interface IngestResponse { studies: StudyInfo[]; skipped_files: string[]; warnings: string[] }

// ---------------- ECG
export const LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"] as const;
export type LeadName = (typeof LEADS)[number];

export interface ECGSignal {
  fs: number;
  leads: Record<string, number[]>;
  duration_s: number;
  source: SourceKind;
  quality: Record<string, number>;
  calibration: Record<string, number>;
}

export type WaveKind = "P" | "Q" | "R" | "S" | "R'" | "T" | "U" | "QRS";

export interface Wave {
  kind: WaveKind;
  lead: string;
  beat_index: number;
  onset_ms: number;
  peak_ms?: number | null;
  offset_ms?: number | null;
  amplitude_mv?: number | null;
  duration_ms?: number | null;
  morphology?: string | null;
}

export interface LeadMeasurements {
  lead: string;
  p_duration_ms?: number | null;
  p_amplitude_mv?: number | null;
  pr_ms?: number | null;
  qrs_ms?: number | null;
  q_amplitude_mv?: number | null;
  q_duration_ms?: number | null;
  r_amplitude_mv?: number | null;
  s_amplitude_mv?: number | null;
  t_amplitude_mv?: number | null;
  qt_ms?: number | null;
  st_j_mv?: number | null;
  st_j60_mv?: number | null;
  st_j80_mv?: number | null;
  intrinsicoid_deflection_ms?: number | null;
  morphology?: string | null;
}

export interface GlobalMeasurements {
  heart_rate_bpm?: number | null;
  rr_mean_ms?: number | null;
  rr_sd_ms?: number | null;
  p_duration_ms?: number | null;
  pr_ms?: number | null;
  qrs_ms?: number | null;
  qt_ms?: number | null;
  qtc_bazett_ms?: number | null;
  qtc_fridericia_ms?: number | null;
  qtc_framingham_ms?: number | null;
  qtc_hodges_ms?: number | null;
  p_axis_deg?: number | null;
  qrs_axis_deg?: number | null;
  t_axis_deg?: number | null;
  sokolow_lyon_mv?: number | null;
  cornell_mv?: number | null;
  precordial_transition?: string | null;
  rhythm?: string | null;
}

export type ConductionStructure =
  | "SA" | "atria" | "AV_node" | "His" | "LBB" | "RBB"
  | "purkinje" | "ventricles_depol" | "ventricles_repol";

export interface ConductionPhase {
  structure: ConductionStructure;
  start_ms: number;
  end_ms: number;
  ecg_correlate: string;
  note?: string | null;
  abnormal?: boolean;
}

export interface ECGAnalysis {
  study_id: string;
  signal: ECGSignal;
  r_peaks_ms: number[];
  waves: Wave[];
  median_beats: Record<string, number[]>;
  /** fiducials of the median beat (beat_index -1, ms from first median sample) */
  median_waves?: Wave[];
  /** R sample index inside median_beats (= round(0.3*fs)) */
  median_beat_r_index?: number | null;
  lead_measurements: LeadMeasurements[];
  global_measurements: GlobalMeasurements;
  conduction: ConductionPhase[];
  findings: Finding[];
  ai?: AIReport | null;
  warnings: string[];
}

// ---------------- RX
export type RXView = "PA" | "AP" | "LATERAL" | "OTHER";
export type BodyRegion = "chest" | "abdomen" | "extremity" | "spine" | "skull" | "pelvis" | "other";
export type StructureCategory =
  | "bone" | "lung" | "heart_vessels" | "airway" | "mediastinum"
  | "diaphragm" | "abdomen" | "soft_tissue" | "device" | "other";

export interface Structure {
  key: string;
  label: string;
  category: StructureCategory;
  color: string;
  mask_png_b64?: string | null;
  polygon: number[][];
  bbox?: number[] | null;
  area_mm2?: number | null;
  confidence: number;
  origin: "model" | "heuristic" | "llm" | "cxas";
}

export interface RXMeasurement {
  key: string;
  label: string;
  value?: number | null;
  unit?: string | null;
  normal_range?: string | null;
  drawing: number[][];
}

export interface RXImageAnalysis {
  instance_id: string;
  view: RXView;
  region: BodyRegion;
  image_png_b64: string;
  width: number;
  height: number;
  pixel_spacing_mm?: number[] | null;
  structures: Structure[];
  measurements: RXMeasurement[];
  model_scores: Record<string, number>;
  quality: Record<string, string>;
  region_uncertain?: boolean;
  region_conflict?: boolean;
  tag_region?: BodyRegion | null;
  out_of_scope?: boolean;
  scope_reason?: string | null;
}

export type NivelLaudo = "MEDIDO" | "REGRA" | "SUGERIDO_MODELO" | "NAO_AVALIADO" | "QUALIDADE";
export interface FraseLaudo { secao: string; texto: string; fatos: string[]; fontes: string[]; nivel: NivelLaudo }
export interface SecaoLaudo { id: string; titulo: string; frases: FraseLaudo[] }
export type DescricaoOrigem = "ia" | "deterministico";
export interface LaudoRX {
  versao: string; status: string; secoes: SecaoLaudo[];
  /** Parágrafo único (aditivo): vazio/ausente = sem descrição. */
  descricao_completa?: string;
  descricao_origem?: DescricaoOrigem;
  descricao_validacao?: { frases?: number; removidas?: number };
}

export interface RXAnalysis {
  study_id: string;
  images: RXImageAnalysis[];
  findings: Finding[];
  ai?: AIReport | null;
  recon3d_available: boolean;
  warnings: string[];
  laudo_rx?: LaudoRX | null;
  laudo_rx_markdown?: string;
}

// ---------------- 3D
export interface Recon3DMesh { key: string; label: string; color: string; volume_ml?: number | null }
export interface Recon3DResult {
  study_id: string;
  gltf_url: string;
  meshes: Recon3DMesh[];
  method: string;
  disclaimer: string;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  message?: string | null;
  result_url?: string | null;
}
