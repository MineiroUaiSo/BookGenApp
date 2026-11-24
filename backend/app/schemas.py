"""Shared API contract. Source of truth for backend <-> frontend.

Mirrored in frontend/src/types/api.ts. Add fields rather than rename/remove.
Units: time in milliseconds (ms) unless suffix says otherwise, amplitude in millivolts (mV),
lengths in millimetres (mm), image coordinates in pixels of the *rendered* image.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- common
class Modality(str, Enum):
    ECG = "ECG"
    RX = "RX"
    UNKNOWN = "UNKNOWN"


class SourceKind(str, Enum):
    DICOM = "dicom"
    IMAGE = "image"          # photo / print / screenshot
    AECG_XML = "aecg_xml"
    CSV = "csv"
    WFDB = "wfdb"


class Reference(BaseModel):
    id: str                                  # key in knowledge/*.yaml
    source: str                              # e.g. "Goldberger's Clinical Electrocardiography, 10th ed., ch. 7"
    note: Optional[str] = None


class Finding(BaseModel):
    code: str                                # stable id, e.g. "ecg.av_block_1"
    label: str                               # pt-BR human label
    severity: Literal["normal", "borderline", "abnormal", "critical"] = "abnormal"
    evidence: list[str] = []                 # measurements / observations backing it
    references: list[Reference] = []
    confidence: float = Field(0.5, ge=0, le=1)
    origin: Literal["rules", "model", "llm"] = "rules"
    # added: pós-validação do texto da IA (app/llm/validate.py)
    confidence_source: Optional[Literal["rules", "n/a"]] = None   # origem do número exibido
    confidence_display: Optional[str] = None                      # ex.: "não aplicável" (confiança autodeclarada pela IA não é exibida)
    validation_flags: list[str] = []                              # ex.: "não corroborado", "valor divergente"


class Differential(BaseModel):
    diagnosis: str
    rationale: str
    supporting: list[str] = []
    against: list[str] = []
    references: list[Reference] = []
    confidence: float = Field(0.5, ge=0, le=1)
    confidence_source: Optional[Literal["rules", "n/a"]] = None
    confidence_display: Optional[str] = None
    validation_flags: list[str] = []


class AIReport(BaseModel):
    available: bool = True
    model: Optional[str] = None
    provider: Optional[str] = None           # added: provedor que respondeu ("anthropic" | "openrouter")
    external_ai_blocked: bool = False        # added: imagem com texto queimado não enviada à IA externa
    validation: dict[str, int] = {}          # added: contagens do validador pós-LLM
    description: str = ""                    # minuciosa, estrutura a estrutura / onda a onda
    findings: list[Finding] = []
    differentials: list[Differential] = []
    disagreements_with_measurements: list[str] = []
    limitations: list[str] = []
    disclaimer: str = (
        "Rascunho gerado por IA para apoio à decisão. Não substitui laudo médico."
    )
    laudo: Optional[dict] = None             # laudo estruturado de ECG (app/llm/laudo.py), campo novo
    laudo_markdown: str = ""                 # laudo completo em markdown copiável
    laudo_curto: str = ""                    # versão de 1 parágrafo para prontuário


# ---------------------------------------------------------------- study / ingest
class SeriesInfo(BaseModel):
    series_uid: str
    modality: Modality
    dicom_modality: Optional[str] = None     # raw tag (CR, DX, ECG...)
    description: Optional[str] = None
    view_position: Optional[str] = None      # PA, AP, LL, RL...
    body_part: Optional[str] = None
    n_instances: int = 0
    instance_ids: list[str] = []


class StudyInfo(BaseModel):
    study_id: str                            # internal id
    study_uid: Optional[str] = None
    patient_age: Optional[str] = None        # never names; anonymised on ingest
    patient_sex: Optional[str] = None
    series: list[SeriesInfo] = []
    created_at: str


class IngestResponse(BaseModel):
    studies: list[StudyInfo]
    skipped_files: list[str] = []
    warnings: list[str] = []


# ---------------------------------------------------------------- ECG
LeadName = Literal["I", "II", "III", "aVR", "aVL", "aVF",
                   "V1", "V2", "V3", "V4", "V5", "V6"]


class ECGSignal(BaseModel):
    fs: float                                # Hz
    leads: dict[str, list[float]]            # lead -> samples in mV
    duration_s: float
    source: SourceKind
    quality: dict[str, float] = {}           # lead -> 0..1
    calibration: dict[str, float] = {}       # paper_speed_mm_s, gain_mm_mv, px_per_mm (digitized)


class WaveKind(str, Enum):
    P = "P"
    Q = "Q"
    R = "R"
    S = "S"
    R_PRIME = "R'"
    T = "T"
    U = "U"
    QRS = "QRS"


class Wave(BaseModel):
    kind: WaveKind
    lead: str
    beat_index: int
    onset_ms: float
    peak_ms: Optional[float] = None
    offset_ms: Optional[float] = None
    amplitude_mv: Optional[float] = None
    duration_ms: Optional[float] = None
    morphology: Optional[str] = None         # e.g. "bífida", "invertida", "rSR'"


class LeadMeasurements(BaseModel):
    lead: str
    p_duration_ms: Optional[float] = None
    p_amplitude_mv: Optional[float] = None
    pr_ms: Optional[float] = None
    qrs_ms: Optional[float] = None
    q_amplitude_mv: Optional[float] = None
    q_duration_ms: Optional[float] = None
    r_amplitude_mv: Optional[float] = None
    s_amplitude_mv: Optional[float] = None
    t_amplitude_mv: Optional[float] = None
    qt_ms: Optional[float] = None
    st_j_mv: Optional[float] = None
    st_j60_mv: Optional[float] = None
    st_j80_mv: Optional[float] = None
    intrinsicoid_deflection_ms: Optional[float] = None
    morphology: Optional[str] = None


class GlobalMeasurements(BaseModel):
    heart_rate_bpm: Optional[float] = None
    rr_mean_ms: Optional[float] = None
    rr_sd_ms: Optional[float] = None
    p_duration_ms: Optional[float] = None
    pr_ms: Optional[float] = None
    qrs_ms: Optional[float] = None
    qt_ms: Optional[float] = None
    qtc_bazett_ms: Optional[float] = None
    qtc_fridericia_ms: Optional[float] = None
    qtc_framingham_ms: Optional[float] = None
    qtc_hodges_ms: Optional[float] = None
    p_axis_deg: Optional[float] = None
    qrs_axis_deg: Optional[float] = None
    t_axis_deg: Optional[float] = None
    sokolow_lyon_mv: Optional[float] = None
    cornell_mv: Optional[float] = None
    precordial_transition: Optional[str] = None
    rhythm: Optional[str] = None             # e.g. "sinusal regular"


class ConductionPhase(BaseModel):
    """One step of cardiac conduction mapped to the ECG timeline of a beat."""
    structure: Literal["SA", "atria", "AV_node", "His", "LBB", "RBB",
                       "purkinje", "ventricles_depol", "ventricles_repol"]
    start_ms: float
    end_ms: float
    ecg_correlate: str                       # "onda P", "segmento PR", "QRS", "ST-T"
    note: Optional[str] = None
    abnormal: bool = False                   # added: phase is delayed/altered (block, bypass, AF...)


class ECGAnalysis(BaseModel):
    study_id: str
    signal: ECGSignal
    r_peaks_ms: list[float] = []
    waves: list[Wave] = []
    median_beats: dict[str, list[float]] = {}   # lead -> samples (mV) of median beat, at signal.fs
    lead_measurements: list[LeadMeasurements] = []
    global_measurements: GlobalMeasurements
    conduction: list[ConductionPhase] = []      # for a representative beat (offset from beat start)
    findings: list[Finding] = []                # rules-based
    ai: Optional[AIReport] = None
    warnings: list[str] = []
    median_waves: list[Wave] = []               # added: fiducials of the median beat (beat_index=-1), ms from median_beats start
    median_beat_r_index: Optional[int] = None   # added: sample index of the R peak inside median_beats arrays


# ---------------------------------------------------------------- RX
class RXView(str, Enum):
    PA = "PA"
    AP = "AP"
    LATERAL = "LATERAL"
    OTHER = "OTHER"


class BodyRegion(str, Enum):
    CHEST = "chest"
    ABDOMEN = "abdomen"
    EXTREMITY = "extremity"
    SPINE = "spine"
    SKULL = "skull"
    PELVIS = "pelvis"
    OTHER = "other"


class Structure(BaseModel):
    key: str                                 # e.g. "left_lung", "heart", "trachea"
    label: str                               # pt-BR legend
    category: Literal["bone", "lung", "heart_vessels", "airway", "mediastinum",
                      "diaphragm", "abdomen", "soft_tissue", "device", "other"]
    color: str                               # hex
    mask_png_b64: Optional[str] = None       # binary mask, same size as rendered image
    polygon: list[list[float]] = []          # optional outline [[x,y],...]
    bbox: Optional[list[float]] = None       # [x0,y0,x1,y1]
    area_mm2: Optional[float] = None
    confidence: float = 0.5
    origin: Literal["model", "heuristic", "llm"] = "model"


class RXMeasurement(BaseModel):
    key: str                                 # "cardiothoracic_ratio", "tracheal_deviation_mm"...
    label: str
    value: Optional[float] = None
    unit: Optional[str] = None
    normal_range: Optional[str] = None
    drawing: list[list[float]] = []          # line segments to overlay [[x0,y0,x1,y1],...]


class RXImageAnalysis(BaseModel):
    instance_id: str
    view: RXView
    region: BodyRegion
    image_png_b64: str                       # rendered 8-bit image used for overlays
    width: int
    height: int
    pixel_spacing_mm: Optional[list[float]] = None
    structures: list[Structure] = []
    measurements: list[RXMeasurement] = []
    model_scores: dict[str, float] = {}      # auxiliary pathology scores (raw TorchXRayVision output, uncalibrated)
    model_probs: dict[str, float] = {}       # isotonic-calibrated probability (only pathologies with a calibration curve)
    model_zones: dict[str, str] = {}         # nao_sugerido | indeterminado | sugestivo (same pathologies as model_probs)
    quality: dict[str, str] = {}             # rotação, inspiração, penetração
    burned_text: Optional[str] = None        # added: resultado do detector de texto queimado (PHI em pixels)
    external_ai_blocked: bool = False        # added: imagem NÃO deve ir a provedor externo de IA


class RXAnalysis(BaseModel):
    study_id: str
    images: list[RXImageAnalysis]
    findings: list[Finding] = []
    ai: Optional[AIReport] = None
    recon3d_available: bool = False          # true when PA/AP + LATERAL present
    warnings: list[str] = []


# ---------------------------------------------------------------- 3D
class Recon3DMesh(BaseModel):
    key: str
    label: str
    color: str
    volume_ml: Optional[float] = None


class Recon3DResult(BaseModel):
    study_id: str
    gltf_url: str                            # GET returns model/gltf-binary (.glb)
    meshes: list[Recon3DMesh]
    method: str                              # textual description of the method
    disclaimer: str = (
        "Reconstrução aproximada a partir de duas projeções. Não equivale a tomografia."
    )


# ---------------------------------------------------------------- jobs
class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    progress: float = 0.0
    message: Optional[str] = None
    result_url: Optional[str] = None
