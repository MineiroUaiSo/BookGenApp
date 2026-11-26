import { Component, Suspense, useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Recon3DResult } from "../../types/api";
import {
  CLIP_AXES,
  absentInProfile,
  baseLabel,
  isEstimated,
  VIEW_PRESETS,
  formatVolume,
  resolveGltfUrl,
  visibleKeys,
  type ClipAxis,
  type PresetId,
} from "./helpers";
import { Capture, CameraRig, Gizmo, ModelLoader, type Bounds, type SceneState } from "./Scene";

const CSS = `
.r3d{display:flex;flex-direction:column;gap:8px;font-family:system-ui,sans-serif;color:#e8eaed;background:#12161c;border-radius:10px;padding:10px;box-sizing:border-box}
.r3d *{box-sizing:border-box}
.r3d-disclaimer{background:#4a3b12;border:1px solid #b8912a;color:#ffe9a8;padding:8px 10px;border-radius:6px;font-size:13px}
.r3d-estimate{background:#1d2d3f;border:1px solid #3f78b0;color:#cfe4fb;padding:8px 10px;border-radius:6px;font-size:13px}
.r3d-badge{font-size:10px;line-height:1;padding:2px 5px;border-radius:8px;border:1px dashed #d6a93a;color:#ffe9a8;flex:none}
.r3d-main{display:flex;gap:10px;flex-wrap:wrap}
.r3d-canvas{position:relative;flex:1 1 420px;min-height:460px;height:60vh;background:#0b0e13;border-radius:8px;overflow:hidden}
.r3d-side{flex:0 1 310px;min-width:260px;display:flex;flex-direction:column;gap:8px;max-height:60vh;overflow:auto}
.r3d-card{background:#1b212b;border:1px solid #2a3340;border-radius:8px;padding:8px 10px;font-size:13px}
.r3d-card h4{margin:0 0 6px;font-size:13px;color:#9fb3c8}
.r3d-row{display:flex;align-items:center;gap:6px;margin:4px 0}
.r3d-row .grow{flex:1;min-width:0}
.r3d-sw{width:14px;height:14px;border-radius:3px;border:1px solid #fff4;flex:none}
.r3d button{background:#2a3340;color:#e8eaed;border:1px solid #3a4658;border-radius:5px;padding:4px 8px;font-size:12px;cursor:pointer}
.r3d button:hover{background:#364253}
.r3d button.on{background:#2f6fb5;border-color:#5aa0e8}
.r3d button:focus-visible,.r3d input:focus-visible{outline:2px solid #5aa0e8}
.r3d input[type=range]{width:100%}
.r3d-mini{width:70px!important}
.r3d-label3d{background:rgba(15,18,24,.85);color:#fff;border:1px solid #fff3;border-radius:4px;padding:1px 6px;font-size:11px;white-space:nowrap;transform:translate(4px,-50%)}
.r3d-msg{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:20px;text-align:center;color:#ffb4a8;font-size:14px}
.r3d-load{color:#9fb3c8;font-size:13px;white-space:nowrap}
.r3d-btns{display:flex;gap:6px;flex-wrap:wrap}
.r3d details{font-size:12px;color:#b6c2d0}
`;

const TEX_KEY = "medlens.recon3d.texmode";

function readTexMode(): "highlight" | "real" {
  try {
    return sessionStorage.getItem(TEX_KEY) === "real" ? "real" : "highlight";
  } catch {
    return "highlight";
  }
}

function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

class Boundary extends Component<
  { children: ReactNode; onRetry: () => void },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="r3d-msg" role="alert">
          <div>
            Não foi possível carregar o modelo 3D.
            <br />
            <small>{String(this.state.error.message || this.state.error).slice(0, 200)}</small>
          </div>
          <button
            onClick={() => {
              this.setState({ error: null });
              this.props.onRetry();
            }}
          >
            Tentar novamente
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function Recon3DViewer(props: { result: Recon3DResult; apiBase: string }) {
  const { result, apiBase } = props;
  const url = useMemo(() => resolveGltfUrl(result.gltf_url, apiBase), [result.gltf_url, apiBase]);
  const keys = useMemo(() => result.meshes.map((m) => m.key), [result.meshes]);

  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [solo, setSolo] = useState<string | null>(null);
  const [opacity, setOpacity] = useState<Record<string, number>>({});
  const [lungTransp, setLungTransp] = useState(45);
  const [selected, setSelected] = useState<string | null>(null);
  const [labels, setLabels] = useState(false);
  const [explode, setExplode] = useState(0);
  const [preset, setPreset] = useState<PresetId>("anterior");
  const [nonce, setNonce] = useState(0);
  const [clipOn, setClipOn] = useState(false);
  const [clipAxis, setClipAxis] = useState<ClipAxis>("axial");
  const [clipT, setClipT] = useState(0.5);
  const [bounds, setBounds] = useState<Bounds>({ radius: 3, min: [-3, -3, -3], max: [3, 3, 3] });
  const [retry, setRetry] = useState(0);
  const [texMode, setTexModeState] = useState<"highlight" | "real">(readTexMode);
  const [tex, setTex] = useState({ available: false, onlyPA: false });
  const setTexMode = (m: "highlight" | "real") => {
    setTexModeState(m);
    try {
      sessionStorage.setItem(TEX_KEY, m);
    } catch {
      /* sessionStorage indisponível: vale só nesta tela */
    }
  };
  const onTexture = useCallback((i: { available: boolean; onlyPA: boolean }) => setTex(i), []);
  const [webgl] = useState(hasWebGL);
  const shot = useRef<(() => string) | null>(null);

  const visible = useMemo(() => visibleKeys(keys, hidden, solo), [keys, hidden, solo]);
  const sceneState: SceneState = {
    visible,
    opacity,
    lungGlobal: 1 - lungTransp / 100,
    selected,
    explode,
    labels,
    texMode,
    clip: { enabled: clipOn, axis: clipAxis, t: clipT },
  };

  const onBounds = useCallback((b: Bounds) => setBounds(b), []);
  const toggle = (k: string) =>
    setHidden((h) => {
      const n = new Set(h);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  const goPreset = (p: PresetId) => {
    setPreset(p);
    setNonce((n) => n + 1);
  };
  const screenshot = () => {
    const data = shot.current?.();
    if (!data) return;
    const a = document.createElement("a");
    a.href = data;
    a.download = `medlens-3d-${result.study_id}.png`;
    a.click();
  };

  const sel = result.meshes.find((m) => m.key === selected) ?? null;
  const absent = useMemo(() => absentInProfile(result.meshes), [result.meshes]);
  const totalVol = result.meshes.reduce((s, m) => s + (m.volume_ml ?? 0), 0);

  return (
    <section className="r3d" aria-label="Reconstrução 3D">
      <style>{CSS}</style>
      <div className="r3d-disclaimer" role="note">
        <strong>Aviso:</strong> {result.disclaimer}
      </div>

      {absent.length > 0 && (
        <div className="r3d-estimate" role="status">
          <strong>Estruturas ausentes no perfil: {absent.join(", ")}.</strong> Não há máscara real delas no
          perfil; aparecem translúcidas, desenhadas só a partir da PA, como estimativa (não medida).
        </div>
      )}

      <div className="r3d-btns" role="group" aria-label="Aparência das estruturas">
        <button
          className={texMode === "highlight" ? "on" : ""}
          aria-pressed={texMode === "highlight"}
          onClick={() => setTexMode("highlight")}
        >
          Destaque das estruturas
        </button>
        <button
          className={texMode === "real" ? "on" : ""}
          aria-pressed={texMode === "real"}
          disabled={!tex.available}
          title={tex.available ? "Projeta a radiografia real nas estruturas" : "Este modelo não traz a imagem da radiografia"}
          onClick={() => setTexMode("real")}
        >
          Imagem real
        </button>
      </div>
      {texMode === "real" && tex.available && tex.onlyPA && (
        <div className="r3d-estimate" role="status">
          Imagem real só da PA: sem imagem do perfil, as faces laterais mostram a PA esticada e escurecida.
        </div>
      )}
      {texMode === "real" && tex.available && !tex.onlyPA && (
        <div className="r3d-estimate" role="note">
          Imagem real: PA projetada de frente e perfil de lado, só sobre as estruturas reconstruídas; faces
          opostas à projeção ficam escurecidas. Não é uma tomografia.
        </div>
      )}

      <div className="r3d-btns" role="toolbar" aria-label="Vistas">
        {VIEW_PRESETS.map((p) => (
          <button key={p.id} className={preset === p.id ? "on" : ""} onClick={() => goPreset(p.id)}>
            {p.label}
          </button>
        ))}
        <button className={explode > 0 ? "on" : ""} onClick={() => setExplode(explode > 0 ? 0 : 1)}>
          Explodir
        </button>
        <button className={labels ? "on" : ""} aria-pressed={labels} onClick={() => setLabels(!labels)}>
          Legendas
        </button>
        <button onClick={screenshot} disabled={!webgl}>
          Captura de tela
        </button>
      </div>

      <div className="r3d-main">
        <div className="r3d-canvas">
          {!webgl ? (
            <div className="r3d-msg" role="alert">
              WebGL não está disponível neste navegador/dispositivo. Ative a aceleração de hardware ou
              use outro navegador para ver o modelo 3D.
            </div>
          ) : (
            <Boundary key={retry} onRetry={() => setRetry((r) => r + 1)}>
              <Canvas
                camera={{ fov: 45, position: [0, 0, 10] }}
                gl={{ preserveDrawingBuffer: true, antialias: true }}
                dpr={[1, 2]}
                onPointerMissed={() => setSelected(null)}
              >
                <color attach="background" args={["#0b0e13"]} />
                <ambientLight intensity={0.7} />
                <directionalLight position={[5, 8, 10]} intensity={1.4} />
                <directionalLight position={[-6, -3, -8]} intensity={0.5} />
                <Suspense
                  fallback={
                    <Html center>
                      <span className="r3d-load">Carregando modelo 3D…</span>
                    </Html>
                  }
                >
                  <ModelLoader
                    url={url}
                    meshes={result.meshes}
                    state={sceneState}
                    onSelect={setSelected}
                    onBounds={onBounds}
                    onTexture={onTexture}
                  />
                </Suspense>
                <CameraRig preset={preset} nonce={nonce} radius={bounds.radius} />
                <Gizmo />
                <Capture shot={shot} />
              </Canvas>
            </Boundary>
          )}
        </div>

        <aside className="r3d-side">
          <div className="r3d-card">
            <h4>Estruturas</h4>
            {result.meshes.map((m) => (
              <div key={m.key}>
                <div className="r3d-row">
                  <input
                    type="checkbox"
                    aria-label={`Mostrar ${baseLabel(m.label)}`}
                    checked={!hidden.has(m.key)}
                    onChange={() => toggle(m.key)}
                  />
                  <span className="r3d-sw" style={{ background: m.color }} />
                  <button
                    className="grow"
                    style={{ textAlign: "left", background: selected === m.key ? "#2f6fb5" : undefined }}
                    onClick={() => setSelected(selected === m.key ? null : m.key)}
                  >
                    {baseLabel(m.label)}
                  </button>
                  {isEstimated(m.label) && <span className="r3d-badge" title={m.label}>estimativa</span>}
                  <span style={{ fontSize: 11, color: "#9fb3c8" }}>{formatVolume(m.volume_ml)}</span>
                  <button
                    className={solo === m.key ? "on" : ""}
                    title="Isolar estrutura"
                    aria-pressed={solo === m.key}
                    onClick={() => setSolo(solo === m.key ? null : m.key)}
                  >
                    Solo
                  </button>
                </div>
                <div className="r3d-row" style={{ paddingLeft: 26 }}>
                  <small style={{ width: 62 }}>Opacidade</small>
                  <input
                    type="range"
                    min={5}
                    max={100}
                    aria-label={`Opacidade de ${baseLabel(m.label)}`}
                    value={Math.round((opacity[m.key] ?? 1) * 100)}
                    onChange={(e) => setOpacity((o) => ({ ...o, [m.key]: +e.target.value / 100 }))}
                  />
                </div>
              </div>
            ))}
            {solo && (
              <div className="r3d-row">
                <button onClick={() => setSolo(null)}>Mostrar todas</button>
              </div>
            )}
          </div>

          <div className="r3d-card">
            <h4>Ajustes</h4>
            <label>
              Transparência dos pulmões: {lungTransp}%
              <input type="range" min={0} max={90} value={lungTransp} onChange={(e) => setLungTransp(+e.target.value)} />
            </label>
            <label>
              Explodir: {Math.round(explode * 100)}%
              <input
                type="range"
                min={0}
                max={200}
                value={Math.round(explode * 100)}
                onChange={(e) => setExplode(+e.target.value / 100)}
              />
            </label>
          </div>

          <div className="r3d-card">
            <h4>Plano de corte</h4>
            <div className="r3d-row">
              <label>
                <input type="checkbox" checked={clipOn} onChange={(e) => setClipOn(e.target.checked)} /> Ativar corte
              </label>
            </div>
            <div className="r3d-btns">
              {CLIP_AXES.map((a) => (
                <button key={a.id} className={clipAxis === a.id ? "on" : ""} onClick={() => setClipAxis(a.id)}>
                  {a.label}
                </button>
              ))}
            </div>
            <input
              type="range"
              min={0}
              max={100}
              aria-label="Posição do plano de corte"
              disabled={!clipOn}
              value={Math.round(clipT * 100)}
              onChange={(e) => setClipT(+e.target.value / 100)}
            />
          </div>

          {sel && (
            <div className="r3d-card" aria-live="polite">
              <h4>{baseLabel(sel.label)}</h4>
              <div className="r3d-row">
                <span className="r3d-sw" style={{ background: sel.color }} />
                <span>Volume estimado: {formatVolume(sel.volume_ml)}</span>
              </div>
              {isEstimated(sel.label) && (
                <div style={{ fontSize: 12, color: "#ffe9a8" }}>{sel.label.slice(baseLabel(sel.label).length).trim()}</div>
              )}
              {sel.volume_ml != null && totalVol > 0 && (
                <div style={{ fontSize: 12, color: "#9fb3c8" }}>
                  {((sel.volume_ml / totalVol) * 100).toFixed(0)}% do volume total reconstruído
                </div>
              )}
              <div style={{ fontSize: 11, color: "#7d8ea3", marginTop: 4 }}>
                Valores aproximados a partir de imagens 2D.
              </div>
            </div>
          )}
        </aside>
      </div>

      <details className="r3d-card">
        <summary>Método</summary>
        <p style={{ margin: "6px 0 0" }}>{result.method}</p>
      </details>
    </section>
  );
}
