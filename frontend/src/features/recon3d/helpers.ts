// Funções puras do visualizador 3D (testáveis sem WebGL).
// Convenção de eixos do modelo: +X = esquerda do paciente, +Y = superior, +Z = anterior.

export type Vec3 = [number, number, number];

export const DEMO_URL = "demo";

/** Resolve a URL do GLB. `apiBase` costuma ser "http://host:8000/api" ou "/api". */
export function resolveGltfUrl(gltfUrl: string, apiBase: string): string {
  if (!gltfUrl || gltfUrl === DEMO_URL) return DEMO_URL;
  if (/^(https?:|blob:|data:)/i.test(gltfUrl)) return gltfUrl;
  if (gltfUrl.startsWith("/")) {
    const origin = (apiBase || "").replace(/\/+$/, "").replace(/\/api$/, "");
    return `${origin}${gltfUrl}`;
  }
  return gltfUrl;
}

/** Deslocamentos de "explodir": cada estrutura se afasta do centróide geral. */
export function explodeOffsets(
  centroids: Record<string, Vec3>,
  amount: number,
): Record<string, Vec3> {
  const keys = Object.keys(centroids);
  const out: Record<string, Vec3> = {};
  if (keys.length === 0) return out;
  const c: Vec3 = [0, 0, 0];
  for (const k of keys) for (let i = 0; i < 3; i++) c[i] += centroids[k][i] / keys.length;
  for (const k of keys) {
    out[k] = [
      (centroids[k][0] - c[0]) * amount + 0,
      (centroids[k][1] - c[1]) * amount + 0,
      (centroids[k][2] - c[2]) * amount + 0,
    ];
  }
  return out;
}

export type PresetId = "anterior" | "lateral_e" | "lateral_d" | "superior";

export interface ViewPreset {
  id: PresetId;
  label: string;
  /** direção da câmera a partir do centro do modelo (unitária) */
  dir: Vec3;
  up: Vec3;
}

// Vista anterior: câmera em +Z olhando para -Z; direita do paciente fica à esquerda do observador.
// Lateral E: câmera no lado esquerdo do paciente (+X). Lateral D: -X.
export const VIEW_PRESETS: ViewPreset[] = [
  { id: "anterior", label: "Anterior (PA)", dir: [0, 0, 1], up: [0, 1, 0] },
  { id: "lateral_e", label: "Lateral E", dir: [1, 0, 0], up: [0, 1, 0] },
  { id: "lateral_d", label: "Lateral D", dir: [-1, 0, 0], up: [0, 1, 0] },
  { id: "superior", label: "Superior", dir: [0, 1, 0], up: [0, 0, -1] },
];

export function getPreset(id: PresetId): ViewPreset {
  return VIEW_PRESETS.find((p) => p.id === id) ?? VIEW_PRESETS[0];
}

export function cameraPositionForPreset(id: PresetId, radius: number, fovDeg = 45): Vec3 {
  const p = getPreset(id);
  const dist = (radius / Math.sin((fovDeg * Math.PI) / 360)) * 1.05;
  return [p.dir[0] * dist, p.dir[1] * dist, p.dir[2] * dist];
}

export type ClipAxis = "axial" | "coronal" | "sagittal";

export const CLIP_AXES: { id: ClipAxis; label: string; normal: Vec3 }[] = [
  { id: "axial", label: "Axial", normal: [0, -1, 0] },
  { id: "coronal", label: "Coronal", normal: [0, 0, -1] },
  { id: "sagittal", label: "Sagital", normal: [-1, 0, 0] },
];

/**
 * Plano de corte (normal, constante) para three.Plane: mantém pontos com
 * normal·p + constante >= 0. `t` em [0,1] percorre min→max do eixo.
 */
export function clipPlaneFor(
  axis: ClipAxis,
  t: number,
  min: Vec3,
  max: Vec3,
): { normal: Vec3; constant: number } {
  const a = CLIP_AXES.find((x) => x.id === axis) ?? CLIP_AXES[0];
  const idx = a.normal[0] !== 0 ? 0 : a.normal[1] !== 0 ? 1 : 2;
  const tt = Math.min(1, Math.max(0, t));
  const pos = min[idx] + (max[idx] - min[idx]) * tt;
  // normal = -e_i  →  -p_i + c >= 0  →  p_i <= c ; c = pos
  return { normal: a.normal, constant: pos };
}

export function isLungKey(key: string): boolean {
  return /lung|pulm/i.test(key);
}

/** Opacidade efetiva = opacidade individual × (transparência global se for pulmão). */
export function effectiveOpacity(key: string, own: number, lungGlobal: number): number {
  return Math.min(1, Math.max(0.02, own * (isLungKey(key) ? lungGlobal : 1)));
}

export function formatVolume(ml?: number | null): string {
  if (ml == null || !isFinite(ml)) return "—";
  return ml >= 1000 ? `${(ml / 1000).toFixed(2).replace(".", ",")} L` : `${Math.round(ml)} mL`;
}

/** Quais chaves ficam visíveis dado o estado de ocultação e solo. */
export function visibleKeys(keys: string[], hidden: Set<string>, solo: string | null): Set<string> {
  if (solo && keys.includes(solo)) return new Set([solo]);
  return new Set(keys.filter((k) => !hidden.has(k)));
}
