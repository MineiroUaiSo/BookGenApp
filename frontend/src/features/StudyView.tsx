import { Suspense, useState } from "react";
import { analyzeRX, API_BASE, recon3d } from "../api/client";
import type { BodyRegion, RXAnalysis, Recon3DResult } from "../types/api";
import ReportPanel from "./report/ReportPanel";
import RXViewer from "./rx/RXViewer";
import { ECGWorkspace, Recon3DViewer } from "./registry";
import type { AnalysisResult } from "./upload/UploadPage";

export default function StudyView({ result, ai, onBack }: { result: AnalysisResult; ai: boolean; onBack: () => void }) {
  const [recon, setRecon] = useState<Recon3DResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rxOverride, setRxOverride] = useState<RXAnalysis | null>(null);
  const [overrides, setOverrides] = useState<Record<string, BodyRegion>>({});

  const confirmRegion = async (instanceId: string, region: BodyRegion) => {
    const next = { ...overrides, [instanceId]: region };
    setBusy(true); setError(null);
    try {
      setRxOverride(await analyzeRX(result.study.study_id, ai, { region_overrides: next }));
      setOverrides(next);
    } catch (e) { setError(`Falha ao reanalisar: ${(e as Error).message}`); }
    finally { setBusy(false); }
  };

  const run3d = async () => {
    setBusy(true); setError(null);
    try { setRecon(await recon3d(result.study.study_id)); }
    catch (e) { setError(`Falha na reconstrução 3D: ${(e as Error).message}`); }
    finally { setBusy(false); }
  };

  const rx = result.kind === "RX" ? (rxOverride ?? result.rx) : null;
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
            <RXViewer analysis={rx ?? result.rx} apiBase={API_BASE} onRegionConfirm={confirmRegion}
              dicom={result.study.series.some((s) => !!s.dicom_modality)} />
            <ReportPanel title="Laudo de RX" findings={(rx ?? result.rx).findings} ai={(rx ?? result.rx).ai} aiRequested={ai} />
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
