import { useEffect, useState } from "react";
import { health } from "./api/client";
import ThemeToggle from "./components/ThemeToggle";
import StudyView from "./features/StudyView";
import UploadPage from "./features/upload/UploadPage";
import type { AnalysisResult } from "./features/upload/UploadPage";

export default function App() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [ai, setAi] = useState(true);
  const [aiAvailable, setAiAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    health().then((h) => { setAiAvailable(h.ai_available); if (!h.ai_available) setAi(false); })
      .catch(() => setAiAvailable(null));
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
        {result ? <StudyView result={result} ai={ai} onBack={() => setResult(null)} />
          : <UploadPage ai={ai} onResult={setResult} />}
      </main>
    </>
  );
}
