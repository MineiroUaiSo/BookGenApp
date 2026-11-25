import { useEffect, useMemo, useState } from "react";
import type { BodyRegion, RXAnalysis, RXImageAnalysis, RXView } from "../../types/api";
import ReliabilityAlert, { isLowReliability } from "../../components/ReliabilityAlert";
import Legend from "./Legend";
import ViewerPane from "./ViewerPane";

const VIEW_LABEL: Record<RXView, string> = { PA: "PA", AP: "AP", LATERAL: "Perfil", OTHER: "Outra" };

export function imageLabel(img: RXImageAnalysis, idx: number): string {
  const base = VIEW_LABEL[img.view] ?? "Imagem";
  return img.view === "OTHER" ? `${base} ${idx + 1}` : base;
}

const REGION_OPTIONS: [BodyRegion, string][] = [
  ["chest", "Tórax"], ["abdomen", "Abdome"], ["pelvis", "Pelve"], ["spine", "Coluna"], ["extremity", "Extremidade"],
  ["skull", "Crânio"], ["other", "Outra"],
];

interface Props {
  analysis: RXAnalysis; apiBase: string; dicom?: boolean;
  /** re-runs the analysis with the region chosen by the human (used when the DICOM tag and image disagree) */
  onRegionConfirm?: (instanceId: string, region: BodyRegion) => void;
}

function RegionNotice({ img, onConfirm }: { img: RXImageAnalysis; onConfirm?: Props["onRegionConfirm"] }) {
  const [sel, setSel] = useState<BodyRegion>(img.region);
  if (!img.region_uncertain && !img.region_conflict) return null;
  return (
    <div className="error" role="alert" style={{ margin: ".5rem 0" }}>
      {img.region_uncertain
        ? "Região incerta: a tag DICOM e a imagem divergem. Achados suspensos até você confirmar a região."
        : `Atenção: a tag DICOM diz ${img.tag_region ?? "?"}, mas a imagem parece ${img.region}. Região corrigida pela imagem.`}
      {onConfirm && (
        <label style={{ marginLeft: ".5rem" }}>Região do exame{" "}
          <select value={sel} onChange={(e) => setSel(e.target.value as BodyRegion)} aria-label="Região do exame">
            {REGION_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>{" "}
          <button className="btn small" onClick={() => onConfirm(img.instance_id, sel)}>Reanalisar</button>
        </label>
      )}
    </div>
  );
}

export default function RXViewer({ analysis, apiBase, dicom = false, onRegionConfirm }: Props) {
  const images = analysis.images;
  const [tab, setTab] = useState<string>(images[0]?.instance_id ?? "");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [opacity, setOpacity] = useState(0.45);
  const [outlines, setOutlines] = useState(true);
  const [labels, setLabels] = useState(false);
  const [showMeas, setShowMeas] = useState(true);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [hlMeas, setHlMeas] = useState<string | null>(null);
  const [wlOn, setWlOn] = useState(false);
  const [wl, setWl] = useState({ wc: 2048, ww: 4096 });
  const [wlCommitted, setWlCommitted] = useState<{ wc: number; ww: number } | null>(null);

  useEffect(() => {
    if (!wlOn) { setWlCommitted(null); return; }
    const t = setTimeout(() => setWlCommitted(wl), 250);
    return () => clearTimeout(t);
  }, [wlOn, wl]);

  const sideBySide = tab === "__side";
  const canSide = images.length >= 2;
  const shown: RXImageAnalysis[] = useMemo(() => {
    if (sideBySide) {
      const f = images.find((i) => i.view === "PA" || i.view === "AP") ?? images[0];
      const l = images.find((i) => i.view === "LATERAL" && i !== f) ?? images.find((i) => i !== f);
      return [f, l].filter(Boolean) as RXImageAnalysis[];
    }
    const cur = images.find((i) => i.instance_id === tab) ?? images[0];
    return cur ? [cur] : [];
  }, [images, tab, sideBySide]);

  const structures = useMemo(() => shown.flatMap((i) => i.structures), [shown]);

  const toggle = (k: string) => setHidden((h) => { const n = new Set(h); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const setMany = (keys: string[], visible: boolean) =>
    setHidden((h) => { const n = new Set(h); keys.forEach((k) => (visible ? n.delete(k) : n.add(k))); return n; });

  if (!images.length) return <div className="card">Nenhuma imagem analisada.</div>;

  return (
    <section className="card rx-viewer" aria-label="Visualizador de radiografia">
      <div className="tabs no-print" role="tablist" aria-label="Incidências">
        {images.map((img, i) => (
          <button key={img.instance_id} role="tab" className="tab" aria-selected={tab === img.instance_id}
            onClick={() => setTab(img.instance_id)}>{imageLabel(img, i)}</button>
        ))}
        {canSide && (
          <button role="tab" className="tab" aria-selected={sideBySide} onClick={() => setTab("__side")}>Lado a lado</button>
        )}
      </div>

      <div className={`panes${sideBySide ? " side" : ""}`}>
        {shown.map((img) => (
          <ViewerPane key={img.instance_id} image={img} label={imageLabel(img, images.indexOf(img))}
            hidden={hidden} opacity={opacity} outlines={outlines} labels={labels} measurements={showMeas}
            hoverKey={hoverKey} onHover={setHoverKey} highlightMeas={hlMeas} wl={wlCommitted} apiBase={apiBase} />
        ))}
      </div>
      <p className="hint no-print">Roda do mouse ou botões +/− para zoom; arraste para mover.</p>

      <div className="viewer-tools no-print">
        <label>Opacidade
          <input type="range" min={0} max={1} step={0.05} value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))} aria-label="Opacidade das máscaras" />
        </label>
        <label><input type="checkbox" checked={outlines} onChange={(e) => setOutlines(e.target.checked)} /> Contornos</label>
        <label><input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} /> Rótulos</label>
        <label><input type="checkbox" checked={showMeas} onChange={(e) => setShowMeas(e.target.checked)} /> Medidas</label>
        {dicom && (
          <label><input type="checkbox" checked={wlOn} onChange={(e) => setWlOn(e.target.checked)} /> Janela/nível (DICOM)</label>
        )}
      </div>
      {dicom && wlOn && (
        <div className="viewer-tools no-print">
          <label>Nível (WC) {wl.wc}
            <input type="range" min={-1024} max={4095} step={8} value={wl.wc}
              onChange={(e) => setWl({ ...wl, wc: Number(e.target.value) })} aria-label="Nível da janela" />
          </label>
          <label>Largura (WW) {wl.ww}
            <input type="range" min={1} max={8192} step={8} value={wl.ww}
              onChange={(e) => setWl({ ...wl, ww: Number(e.target.value) })} aria-label="Largura da janela" />
          </label>
          <button className="btn small" onClick={() => setWl({ wc: 2048, ww: 4096 })}>Restaurar</button>
        </div>
      )}

      <div className="no-print">
        <Legend structures={structures} hidden={hidden} onToggle={toggle} onSetMany={setMany}
          hoverKey={hoverKey} onHover={setHoverKey} />
      </div>

      {shown.map((img) => (
        <div key={img.instance_id}>
          <h3 style={{ marginTop: "1rem" }}>Medidas — {imageLabel(img, images.indexOf(img))}</h3>
          <RegionNotice img={img} onConfirm={onRegionConfirm} />
          <ReliabilityAlert messages={[
            ...(img.out_of_scope && img.scope_reason ? [`Fora de escopo: ${img.scope_reason}`] : []),
            ...Object.entries(img.quality).filter(([k, v]) => k !== "escopo" && k !== "região" && isLowReliability(`${k}: ${v}`))
              .map(([k, v]) => `${k}: ${v}`),
          ]} />
          {Object.keys(img.quality).length > 0 && (
            <p>{Object.entries(img.quality).filter(([k, v]) => k === "escopo" || k === "região" || !isLowReliability(`${k}: ${v}`)).map(([k, v]) => (
              <span key={k} className="badge" style={{ marginRight: 4 }} title={k}>{k}: {v}</span>
            ))}</p>
          )}
          {img.measurements.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="meas">
                <caption className="sr-only">Medidas da imagem</caption>
                <thead><tr><th>Medida</th><th>Valor</th><th>Normal</th></tr></thead>
                <tbody>
                  {img.measurements.map((m) => (
                    <tr key={m.key} className={hlMeas === m.key ? "hl" : undefined}
                      onMouseEnter={() => setHlMeas(m.key)} onMouseLeave={() => setHlMeas(null)}>
                      <td>{m.label}</td>
                      <td>{m.value != null ? `${m.value}${m.unit ? ` ${m.unit}` : ""}` : "—"}</td>
                      <td>{m.normal_range ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="hint">Sem medidas para esta imagem.</p>}
        </div>
      ))}
      <ReliabilityAlert title="Avisos da análise" messages={analysis.warnings} />
    </section>
  );
}
