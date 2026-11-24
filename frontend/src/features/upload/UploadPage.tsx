import { useRef, useState } from "react";
import { analyzeECG, analyzeRX, ingest } from "../../api/client";
import type { UploadItem } from "../../api/client";
import type { ECGAnalysis, RXAnalysis, StudyInfo } from "../../types/api";
import { collectFromDataTransfer, fromFileList } from "./collect";

export type AnalysisResult =
  | { kind: "ECG"; study: StudyInfo; ecg: ECGAnalysis }
  | { kind: "RX"; study: StudyInfo; rx: RXAnalysis };

interface Props { ai: boolean; onResult: (r: AnalysisResult) => void }

function studyKind(s: StudyInfo): "ECG" | "RX" | "UNKNOWN" {
  if (s.series.some((x) => x.modality === "ECG")) return "ECG";
  if (s.series.some((x) => x.modality === "RX")) return "RX";
  return "UNKNOWN";
}

export default function UploadPage({ ai, onResult }: Props) {
  const [over, setOver] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [studies, setStudies] = useState<StudyInfo[]>([]);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const upload = async (items: UploadItem[]) => {
    if (!items.length) return;
    setError(null); setProgress(0);
    try {
      const res = await ingest(items, setProgress);
      setStudies(res.studies); setSkipped(res.skipped_files); setWarnings(res.warnings);
    } catch (e) { setError((e as Error).message); }
    finally { setProgress(null); }
  };

  const analyze = async (study: StudyInfo, kind: "ECG" | "RX") => {
    setBusy(study.study_id); setError(null);
    try {
      if (kind === "ECG") onResult({ kind, study, ecg: await analyzeECG(study.study_id, ai) });
      else onResult({ kind, study, rx: await analyzeRX(study.study_id, ai) });
    } catch (e) { setError(`Falha na análise: ${(e as Error).message}`); }
    finally { setBusy(null); }
  };

  return (
    <div>
      <section className="card" aria-label="Envio de arquivos">
        <div className={`dropzone${over ? " over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={async (e) => { e.preventDefault(); setOver(false); upload(await collectFromDataTransfer(e.dataTransfer)); }}>
          <p><strong>Arraste arquivos ou uma pasta DICOM inteira aqui</strong></p>
          <p className="hint">DICOM, imagens (PNG/JPG), XML aECG, CSV, WFDB</p>
          <div className="btn-row" style={{ justifyContent: "center" }}>
            <label className="btn primary">
              Selecionar arquivos
              <input type="file" multiple className="sr-only" onChange={(e) => { upload(fromFileList(e.target.files)); e.target.value = ""; }} />
            </label>
            <button className="btn" onClick={() => folderRef.current?.click()}>Selecionar pasta DICOM</button>
            <input ref={folderRef} type="file" className="sr-only" tabIndex={-1} aria-label="Selecionar pasta DICOM"
              {...({ webkitdirectory: "", directory: "" } as Record<string, string>)} multiple
              onChange={(e) => { upload(fromFileList(e.target.files)); e.target.value = ""; }} />
            <label className="btn">
              Foto do ECG
              <input type="file" accept="image/*" capture="environment" className="sr-only"
                onChange={(e) => { upload(fromFileList(e.target.files)); e.target.value = ""; }} />
            </label>
          </div>
        </div>
        {progress !== null && (
          <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} aria-label="Progresso do envio" className="progress">
            <div style={{ width: `${progress * 100}%` }} />
          </div>
        )}
        {error && <div className="error" role="alert">{error}</div>}
      </section>

      {studies.length > 0 && (
        <section className="card" aria-label="Estudos encontrados">
          <h2>Estudos encontrados</h2>
          <ul className="study-list">
            {studies.map((s) => {
              const kind = studyKind(s);
              const disabled = busy === s.study_id;
              return (
                <li key={s.study_id}>
                  <strong>Estudo {s.study_id.slice(0, 8)}</strong>{" "}
                  <span className="badge">{kind === "UNKNOWN" ? "Imagem não classificada" : kind}</span>
                  {s.patient_age && <span className="hint"> · {s.patient_age}</span>}
                  {s.patient_sex && <span className="hint"> · {s.patient_sex}</span>}
                  <ul className="series-list">
                    {s.series.map((se) => (
                      <li key={se.series_uid} style={{ border: 0, padding: 0, margin: 0, background: "none" }}>
                        {se.modality}{se.dicom_modality ? ` (${se.dicom_modality})` : ""} — {se.description || "série"}
                        {se.view_position ? ` · ${se.view_position}` : ""} · {se.n_instances} imagem(ns)
                      </li>
                    ))}
                  </ul>
                  {kind === "UNKNOWN" ? (
                    <div role="group" aria-label="Tipo de imagem">
                      <p>Isto é um ECG ou um RX?</p>
                      <div className="btn-row">
                        <button className="btn primary" disabled={disabled} onClick={() => analyze(s, "ECG")}>É um ECG</button>
                        <button className="btn primary" disabled={disabled} onClick={() => analyze(s, "RX")}>É um RX</button>
                      </div>
                    </div>
                  ) : (
                    <button className="btn primary" disabled={disabled} onClick={() => analyze(s, kind)}>
                      {disabled ? "Analisando…" : `Analisar ${kind}`}
                    </button>
                  )}
                  {disabled && <p className="hint" role="status">Analisando, isto pode levar alguns instantes…</p>}
                </li>
              );
            })}
          </ul>
          {skipped.length > 0 && <details><summary>{skipped.length} arquivo(s) ignorado(s)</summary><ul>{skipped.slice(0, 50).map((f) => <li key={f}>{f}</li>)}</ul></details>}
          {warnings.length > 0 && <ul className="hint">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
        </section>
      )}
    </div>
  );
}
