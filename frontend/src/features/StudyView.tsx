import { Suspense, useState } from "react";
import { API_BASE, recon3d } from "../api/client";
import type { Recon3DResult } from "../types/api";
import ReportPanel from "./report/ReportPanel";
import RXViewer from "./rx/RXViewer";
import { ECGWorkspace, Recon3DViewer } from "./registry";
import type { AnalysisResult } from "./upload/UploadPage";

export default function StudyView({ result, ai, onBack }: { result: AnalysisResult; ai: boolean; onBack: () => void }) {
  const [recon, setRecon] = useState<Recon3DResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run3d = async () => {
    setBusy(true); setError(null);
    try { setRecon(await recon3d(result.study.study_id)); }
    catch (e) { setError(`Falha na reconstrução 3D: ${(e as Error).message}`); }
    finally { setBusy(false); }
  };

  const fallback = <p className="hint" role="status">Carregando…</p>;

  return (
    <div>
      <button className="btn small no-print" onClick={onBack} style={{ marginBottom: ".75rem" }}>← Novo estudo</button>
      {result.kind === "ECG" ? (
        <div className="study-layout">
          <Suspense fallback={fallback}><div className="no-print"><ECGWorkspace analysis={result.ecg} /></div></Suspense>
          <ReportPanel title="Laudo de ECG" findings={result.ecg.findings} ai={result.ecg.ai} aiRequested={ai} />
        </div>
      ) : (
        <>
          <div className="study-layout">
            <RXViewer analysis={result.rx} apiBase={API_BASE}
              dicom={result.study.series.some((s) => !!s.dicom_modality)} />
            <ReportPanel title="Laudo de RX" findings={result.rx.findings} ai={result.rx.ai} aiRequested={ai} />
          </div>
          {result.rx.recon3d_available && (
            <section className="card no-print" aria-label="Reconstrução 3D">
              <button className="btn primary" onClick={run3d} disabled={busy}>
                {busy ? "Reconstruindo…" : "Reconstrução 3D (PA + Perfil)"}
              </button>
              {error && <div className="error" role="alert">{error}</div>}
              {recon && <Suspense fallback={fallback}><Recon3DViewer result={recon} apiBase={API_BASE} /></Suspense>}
            </section>
          )}
        </>
      )}
    </div>
  );
}
