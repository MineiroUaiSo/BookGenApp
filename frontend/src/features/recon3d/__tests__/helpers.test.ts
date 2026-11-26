import { describe, it, expect } from "vitest";
import {
  resolveGltfUrl,
  explodeOffsets,
  getPreset,
  cameraPositionForPreset,
  clipPlaneFor,
  effectiveOpacity,
  visibleKeys,
  formatVolume,
  VIEW_PRESETS,
  isEstimated,
  baseLabel,
  absentInProfile,
  ESTIMATE_OPACITY,
  readTextureMeta,
  planarUV,
  atlasLayout,
  type TexView,
} from "../helpers";

describe("resolveGltfUrl", () => {
  it("resolve caminho relativo removendo /api da base", () => {
    expect(resolveGltfUrl("/api/recon3d/x/model.glb", "http://h:8000/api")).toBe(
      "http://h:8000/api/recon3d/x/model.glb",
    );
    expect(resolveGltfUrl("/api/recon3d/x/model.glb", "/api")).toBe("/api/recon3d/x/model.glb");
    expect(resolveGltfUrl("/api/a.glb", "http://h/api/")).toBe("http://h/api/a.glb");
  });
  it("mantém URLs absolutas e demo", () => {
    expect(resolveGltfUrl("https://cdn/x.glb", "/api")).toBe("https://cdn/x.glb");
    expect(resolveGltfUrl("demo", "/api")).toBe("demo");
  });
});

describe("explodeOffsets", () => {
  it("afasta do centróide proporcionalmente", () => {
    const o = explodeOffsets({ a: [-1, 0, 0], b: [1, 0, 0] }, 2);
    expect(o.a).toEqual([-2, 0, 0]);
    expect(o.b).toEqual([2, 0, 0]);
  });
  it("amount 0 => sem deslocamento; vazio ok", () => {
    expect(explodeOffsets({ a: [1, 2, 3], b: [3, 2, 1] }, 0).a).toEqual([0, 0, 0]);
    expect(explodeOffsets({}, 1)).toEqual({});
  });
});

describe("presets", () => {
  it("anterior em +Z, lateral E em +X, lateral D em -X, superior em +Y", () => {
    expect(getPreset("anterior").dir).toEqual([0, 0, 1]);
    expect(getPreset("lateral_e").dir).toEqual([1, 0, 0]);
    expect(getPreset("lateral_d").dir).toEqual([-1, 0, 0]);
    expect(getPreset("superior").dir).toEqual([0, 1, 0]);
    expect(VIEW_PRESETS).toHaveLength(4);
  });
  it("distância da câmera escala com o raio", () => {
    const a = cameraPositionForPreset("anterior", 1);
    const b = cameraPositionForPreset("anterior", 2);
    expect(b[2]).toBeCloseTo(a[2] * 2);
    expect(a[0]).toBe(0);
  });
});

describe("clipPlaneFor", () => {
  const min: [number, number, number] = [-2, -4, -1];
  const max: [number, number, number] = [2, 4, 1];
  it("axial usa eixo Y", () => {
    const p = clipPlaneFor("axial", 0.5, min, max);
    expect(p.normal).toEqual([0, -1, 0]);
    expect(p.constant).toBeCloseTo(0);
    expect(clipPlaneFor("axial", 1, min, max).constant).toBe(4);
  });
  it("sagital usa X e limita t", () => {
    expect(clipPlaneFor("sagittal", 5, min, max).constant).toBe(2);
    expect(clipPlaneFor("coronal", -1, min, max).constant).toBe(-1);
  });
});

describe("opacidade e visibilidade", () => {
  it("transparência global só afeta pulmões", () => {
    expect(effectiveOpacity("lung_left", 1, 0.4)).toBeCloseTo(0.4);
    expect(effectiveOpacity("heart", 1, 0.4)).toBe(1);
  });
  it("solo isola; ocultos removidos", () => {
    const keys = ["a", "b", "c"];
    expect([...visibleKeys(keys, new Set(["b"]), null)]).toEqual(["a", "c"]);
    expect([...visibleKeys(keys, new Set(), "b")]).toEqual(["b"]);
  });
  it("formata volume", () => {
    expect(formatVolume(null)).toBe("—");
    expect(formatVolume(620)).toBe("620 mL");
    expect(formatVolume(2450)).toBe("2,45 L");
  });
});

describe("estruturas estimadas (1 incidência)", () => {
  const meshes = [
    { key: "heart", label: "coração (estimativa, 1 incidência: ausente no perfil)", color: "#f00", volume_ml: 600 },
    { key: "spine", label: "coluna (estimativa, 1 incidência: ausente no perfil)", color: "#fff", volume_ml: 90 },
    { key: "sternum", label: "esterno (estimativa, 1 incidência: ausente na PA)", color: "#fff", volume_ml: 20 },
    { key: "lung_left", label: "pulmão esquerdo", color: "#88f", volume_ml: 2000 },
  ];
  it("detecta estimativa e remove o sufixo do rótulo", () => {
    expect(isEstimated(meshes[0].label)).toBe(true);
    expect(isEstimated("pulmão esquerdo")).toBe(false);
    expect(baseLabel(meshes[0].label)).toBe("coração");
    expect(baseLabel("pulmão esquerdo")).toBe("pulmão esquerdo");
  });
  it("lista só as ausentes no perfil", () => {
    expect(absentInProfile(meshes)).toEqual(["coração", "coluna"]);
    expect(absentInProfile([meshes[3]])).toEqual([]);
  });
  it("estimada nunca fica opaca; pulmão estimado combina com a transparência global", () => {
    expect(effectiveOpacity("heart", 1, 1, true)).toBeCloseTo(ESTIMATE_OPACITY);
    expect(effectiveOpacity("heart", 1, 1, false)).toBe(1);
    expect(effectiveOpacity("lung_left", 1, 0.5, true)).toBeCloseTo(0.5 * ESTIMATE_OPACITY);
  });
});

describe("modo imagem real: projeção planar", () => {
  const frontal: TexView = { png_b64: "x", w: 100, h: 200, col: [50, 2], row: [100, -2] }; // col=50+2X, row=100-2Y
  const lateral: TexView = { png_b64: "y", w: 80, h: 200, col: [40, -2], row: [100, -2] }; // col=40-2Z (coluna à direita)
  const meta = { frontal, lateral };

  it("lê os metadados do GLB e rejeita lixo", () => {
    expect(readTextureMeta({ medlens_texture: meta })?.lateral?.w).toBe(80);
    expect(readTextureMeta({ medlens_texture: { frontal } })?.lateral).toBeUndefined();
    expect(readTextureMeta({})).toBeNull();
    expect(readTextureMeta(undefined)).toBeNull();
    expect(readTextureMeta({ medlens_texture: { frontal: { w: 1 } } })).toBeNull();
  });
  it("com perfil: atlas dividido ao meio; sem perfil: só a PA ocupa tudo", () => {
    expect(atlasLayout(meta)).toEqual({ frontal: [0, 0.5], lateral: [0.5, 1] });
    expect(atlasLayout({ frontal })).toEqual({ frontal: [0, 1], lateral: null });
  });
  it("normal em Z usa a PA: UV a partir de (X,Y), centro do pixel, v invertido", () => {
    // X=0,Y=0 -> col 50,row 100 -> u=(50.5)/100 -> metade do atlas; v=1-(100.5/200)
    const r = planarUV([0, 0, 0], [0, 0, 1], meta);
    expect(r.uv[0]).toBeCloseTo((50.5 / 100) * 0.5);
    expect(r.uv[1]).toBeCloseTo(1 - 100.5 / 200);
    expect(r.shade[0]).toBeCloseTo(1);
  });
  it("normal em X usa o perfil: UV a partir de (Z,Y) na metade direita do atlas", () => {
    const r = planarUV([0, 10, 5], [1, 0, 0], meta);
    // col = 40 - 2*5 = 30 ; row = 100 - 2*10 = 80
    expect(r.uv[0]).toBeCloseTo(0.5 + (30.5 / 80) * 0.5);
    expect(r.uv[1]).toBeCloseTo(1 - 80.5 / 200);
    expect(r.shade[0]).toBeCloseTo(1); // col[1]<0: lado +X é o voltado à imagem
  });
  it("face oposta à fonte da projeção e faces rasantes escurecem (nunca mostram a imagem como se fosse ali)", () => {
    const back = planarUV([0, 0, 0], [0, 0, -1], meta).shade[0];
    const graz = planarUV([0, 0, 0], [0.7, 0, 0.714], meta).shade[0];
    expect(back).toBeLessThan(0.5);
    expect(graz).toBeGreaterThan(back);
    expect(graz).toBeLessThan(0.7);
  });
  it("sem perfil, normais laterais também usam a PA e ficam escuras", () => {
    const r = planarUV([0, 0, 0], [1, 0, 0], { frontal });
    expect(r.uv[0]).toBeCloseTo(50.5 / 100);
    expect(r.shade[0]).toBeLessThan(0.4);
  });
  it("UV fica entre 0 e 1 para pontos dentro da imagem e vários vértices em lote", () => {
    const pos = [0, 0, 0, 10, 20, 0];
    const nrm = [0, 0, 1, 0, 0, 1];
    const r = planarUV(pos, nrm, meta);
    expect(r.uv).toHaveLength(4);
    expect(r.shade).toHaveLength(2);
    for (const u of r.uv) expect(u >= 0 && u <= 1).toBe(true);
  });
});
