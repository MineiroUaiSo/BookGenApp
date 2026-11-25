import { useEffect, useState } from "react";
import { health } from "./api/client";
import ImageConsent from "./components/ImageConsent";
import ThemeToggle from "./components/ThemeToggle";
import StudyView from "./features/StudyView";
import UploadPage from "./features/upload/UploadPage";
import type { AnalysisResult } from "./features/upload/UploadPage";

const COMPONENT_WARNINGS: Record<string, string> = {
  modelo_rx: "Modelo de RX indisponível: usando heurística (menor confiabilidade)",
  analisador_rx: "Analisador de RX indisponível: análise de radiografia desativada",
  analisador_ecg: "Analisador de ECG indisponível: análise de ECG desativada",
  neurokit2: "Biblioteca de ECG (neurokit2) indisponível: delineação de ECG reduzida",
  pylibjpeg: "Decodificador JPEG de DICOM indisponível: alguns DICOM podem não abrir",
};

/** Messages (pt-BR) for analysis components whose /health status is 'ausente' or 'erro: ...'. */
export function healthWarnings(models: Record<string, string>): string[] {
  return Object.entries(COMPONENT_WARNINGS)
    .filter(([key]) => models[key] !== undefined && models[key] !== "ok")
    .map(([key]) => COMPONENT_WARNINGS[key]);
}

export default function App() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [ai, setAi] = useState(true);
  const [sendImages, setSendImages] = useState(false);   // opt-in: imagem do RX à IA na nuvem (nunca marcado por padrão)
  const [aiAvailable, setAiAvailable] = useState<boolean | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = (retry: boolean) => health().then((h) => {
      if (cancelled) return;
      setAiAvailable(h.ai_available);
      if (!h.ai_available) setAi(false);
      const w = healthWarnings(h.models);
      setWarnings(w);
      // first /health may still be loading the RX model: look again once
      if (w.length && retry) setTimeout(() => load(false), 15000);
    }).catch(() => { if (!cancelled) setAiAvailable(null); });
    load(true);
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <header className="app-header">
        <div className="brand">Med<span>Lens</span></div>
        <div className="spacer" />
        <label className="switch">
          <input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} disabled={aiAvailable === false} />
          Usar IA (Claude)
        </label>
        {aiAvailable === false && <span className="hint">IA indisponível no servidor</span>}
        <ThemeToggle />
      </header>
      <main className="main">
        <div className="banner" role="note">
          Apoio à decisão e ensino — não é dispositivo médico certificado. Todo laudo é rascunho e exige revisão por médico.
        </div>
        {warnings.length > 0 && (
          <div className="banner" role="alert" data-testid="health-banner">
            {warnings.map((w) => <div key={w}>{w}</div>)}
          </div>
        )}
        {ai && <ImageConsent checked={sendImages} onChange={setSendImages} />}
        {result ? <StudyView result={result} ai={ai} sendImages={sendImages} onBack={() => setResult(null)} />
          : <UploadPage ai={ai} onResult={setResult} />}
      </main>
    </>
  );
}
