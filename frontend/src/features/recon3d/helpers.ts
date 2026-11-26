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

/** Estrutura em uma única incidência: nunca opaca, para não parecer medida. */
export const ESTIMATE_OPACITY = 0.6;

const ESTIMATE_RE = /\s*\(estimativa[^)]*\)\s*$/i;

export function isEstimated(label: string): boolean {
  return ESTIMATE_RE.test(label);
}

/** Rótulo sem o sufixo "(estimativa, 1 incidência: ausente no perfil)". */
export function baseLabel(label: string): string {
  return label.replace(ESTIMATE_RE, "");
}

/** Nomes das estruturas desenhadas só a partir da PA (sem máscara real no perfil). */
export function absentInProfile(meshes: { label: string }[]): string[] {
  return meshes.filter((m) => /ausente no perfil/i.test(m.label)).map((m) => baseLabel(m.label));
}

/** Opacidade efetiva = opacidade individual × (transparência global se for pulmão) × (teto se estimada). */
export function effectiveOpacity(
  key: string,
  own: number,
  lungGlobal: number,
  estimated = false,
): number {
  const o = own * (isLungKey(key) ? lungGlobal : 1) * (estimated ? ESTIMATE_OPACITY : 1);
  return Math.min(1, Math.max(0.02, o));
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

// ---------------------------------------------------------------- modo "imagem real"
// O backend grava no GLB (scenes[0].extras.medlens_texture) a radiografia do estudo e os coeficientes
// afins que levam coordenadas do modelo a pixels: PA: col=c0+c1*X, lin=r0+r1*Y; perfil: col=c0+c1*Z, lin=r0+r1*Y.

export interface TexView {
  png_b64: string;
  w: number;
  h: number;
  col: [number, number];
  row: [number, number];
}
export interface TextureMeta {
  frontal: TexView;
  lateral?: TexView;
}

function validView(v: unknown): v is TexView {
  const t = v as TexView | undefined;
  return (
    !!t &&
    typeof t.png_b64 === "string" &&
    t.png_b64.length > 0 &&
    t.w > 0 &&
    t.h > 0 &&
    Array.isArray(t.col) &&
    t.col.length === 2 &&
    Array.isArray(t.row) &&
    t.row.length === 2
  );
}

export function readTextureMeta(userData: unknown): TextureMeta | null {
  const m = (userData as { medlens_texture?: { frontal?: unknown; lateral?: unknown } } | undefined)
    ?.medlens_texture;
  if (!m || !validView(m.frontal)) return null;
  return validView(m.lateral) ? { frontal: m.frontal, lateral: m.lateral } : { frontal: m.frontal };
}

/** Faixas [u0,u1] de cada incidência no atlas: PA à esquerda, perfil à direita; sem perfil a PA ocupa tudo. */
export function atlasLayout(meta: TextureMeta): { frontal: [number, number]; lateral: [number, number] | null } {
  return meta.lateral
    ? { frontal: [0, 0.5], lateral: [0.5, 1] }
    : { frontal: [0, 1], lateral: null };
}

const BACK_SHADE = 0.45;

/**
 * Projeção planar por vértice: normal dominante em Z usa a PA, em X usa o perfil (se existir; senão a PA).
 * `shade` escurece faces rasantes e o lado oposto à fonte da projeção, onde a imagem seria só um artefato.
 */
export function planarUV(
  pos: ArrayLike<number>,
  nrm: ArrayLike<number>,
  meta: TextureMeta,
): { uv: Float32Array; shade: Float32Array } {
  const n = Math.floor(pos.length / 3);
  const uv = new Float32Array(n * 2);
  const shade = new Float32Array(n);
  const lay = atlasLayout(meta);
  const f = meta.frontal;
  const l = meta.lateral;
  for (let i = 0; i < n; i++) {
    const x = pos[3 * i], y = pos[3 * i + 1], z = pos[3 * i + 2];
    const nx = nrm[3 * i], nz = nrm[3 * i + 2];
    const useLat = !!l && Math.abs(nx) > Math.abs(nz);
    let u: number, v: number, d: number, facing: boolean;
    if (useLat && l && lay.lateral) {
      const col = l.col[0] + l.col[1] * z;
      const row = l.row[0] + l.row[1] * y;
      u = lay.lateral[0] + ((col + 0.5) / l.w) * (lay.lateral[1] - lay.lateral[0]);
      v = 1 - (row + 0.5) / l.h;
      d = Math.abs(nx);
      facing = nx * (l.col[1] < 0 ? 1 : -1) > 0;
    } else {
      const col = f.col[0] + f.col[1] * x;
      const row = f.row[0] + f.row[1] * y;
      u = lay.frontal[0] + ((col + 0.5) / f.w) * (lay.frontal[1] - lay.frontal[0]);
      v = 1 - (row + 0.5) / f.h;
      d = Math.abs(nz);
      facing = nz * (f.col[1] > 0 ? 1 : -1) > 0;
    }
    uv[2 * i] = u;
    uv[2 * i + 1] = v;
    shade[i] = (0.2 + 0.8 * d * d) * (facing ? 1 : BACK_SHADE);
  }
  return { uv, shade };
}
