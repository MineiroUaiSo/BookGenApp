import type {
  AIReport, BodyRegion, ECGAnalysis, IngestResponse, RXAnalysis, Recon3DResult, StudyInfo,
} from "../types/api";

export const API_BASE: string =
  (import.meta.env?.VITE_API_BASE as string | undefined) ?? "http://localhost:8000/api";

export interface Health { status: string; ai_available: boolean; models: Record<string, string>; degraded?: string[] }
export interface UploadItem { file: File; path?: string }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}),
});

export function buildIngestFormData(items: UploadItem[]): FormData {
  const fd = new FormData();
  for (const it of items) {
    fd.append("files", it.file, it.file.name);
  }
  for (const it of items) {
    fd.append("relative_paths", it.path || (it.file as File & { webkitRelativePath?: string }).webkitRelativePath || it.file.name);
  }
  return fd;
}

export function ingest(items: UploadItem[], onProgress?: (frac: number) => void, base = API_BASE): Promise<IngestResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base}/ingest`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { onProgress?.(1); resolve(xhr.response as IngestResponse); }
      else {
        const d = xhr.response?.detail;
        reject(new ApiError(xhr.status, typeof d === "string" ? d : xhr.statusText || "Falha no envio"));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Não foi possível conectar ao servidor"));
    xhr.send(buildIngestFormData(items));
  });
}

export const health = (base = API_BASE) => fetch(`${base}/health`).then(parse<Health>);
export const listStudies = (base = API_BASE) => fetch(`${base}/studies`).then(parse<StudyInfo[]>);
export const getStudy = (id: string, base = API_BASE) => fetch(`${base}/studies/${id}`).then(parse<StudyInfo>);

export function renderUrl(instanceId: string, wc?: number, ww?: number, base = API_BASE): string {
  const q = new URLSearchParams();
  if (wc != null) q.set("wc", String(wc));
  if (ww != null) q.set("ww", String(ww));
  const s = q.toString();
  return `${base}/instances/${instanceId}/render.png${s ? `?${s}` : ""}`;
}

export const analyzeECG = (
  studyId: string, ai: boolean,
  body: { instance_id?: string; layout?: "3x4+1" | "6x2" | "12x1" | "auto" } = {}, base = API_BASE,
) => fetch(`${base}/ecg/${studyId}/analyze?ai=${ai}`, json(body)).then(parse<ECGAnalysis>);

export const analyzeRX = (
  studyId: string, ai: boolean, body: { instance_ids?: string[]; region_overrides?: Record<string, BodyRegion> } = {}, base = API_BASE,
) => fetch(`${base}/rx/${studyId}/analyze?ai=${ai}`, json(body)).then(parse<RXAnalysis>);

export const fetchAI = (kind: "ecg" | "rx", studyId: string, base = API_BASE) =>
  fetch(`${base}/${kind}/${studyId}/ai`, json({})).then(parse<AIReport>);

export interface RulePpvEntry { ppv: number; ic_inf: number; ic_sup: number; n: number; fonte: string }
export interface RulePpv { _meta: Record<string, unknown>; codes: Record<string, RulePpvEntry> }
export const fetchRulePpv = (base = API_BASE) => fetch(`${base}/rule-ppv`).then(parse<RulePpv>);

export const sendFeedback = (
  studyId: string, body: { kind: "ecg" | "rx"; code: string; verdict: "agree" | "disagree" }, base = API_BASE,
) => fetch(`${base}/feedback/${studyId}`, json(body)).then(parse<{ ok: boolean }>);

export const recon3d = (
  studyId: string, body: { frontal_id?: string; lateral_id?: string } = {}, base = API_BASE,
) => fetch(`${base}/rx/${studyId}/recon3d`, json(body)).then(parse<Recon3DResult>);

export const modelUrl = (studyId: string, base = API_BASE) => `${base}/recon3d/${studyId}/model.glb`;
