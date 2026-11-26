import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { useGLTF, OrbitControls, Html, GizmoHelper, Line } from "@react-three/drei";
import type { Recon3DMesh } from "../../types/api";
import {
  cameraPositionForPreset,
  clipPlaneFor,
  effectiveOpacity,
  baseLabel,
  explodeOffsets,
  isEstimated,
  atlasLayout,
  planarUV,
  readTextureMeta,
  type TextureMeta,
  type ClipAxis,
  type PresetId,
  type Vec3,
} from "./helpers";
import { buildDemoScene } from "./__fixtures__/demoScene";

export interface Bounds {
  radius: number;
  min: Vec3;
  max: Vec3;
}

export interface SceneState {
  visible: Set<string>;
  opacity: Record<string, number>;
  lungGlobal: number;
  selected: string | null;
  explode: number;
  labels: boolean;
  texMode: "highlight" | "real";
  clip: { enabled: boolean; axis: ClipAxis; t: number };
}

interface ModelProps {
  meshes: Recon3DMesh[];
  state: SceneState;
  onSelect: (key: string | null) => void;
  onBounds: (b: Bounds) => void;
  onTexture?: (info: { available: boolean; onlyPA: boolean }) => void;
}

const ATLAS_CELL_MAX = 1024;

function loadImage(b64: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error("textura ilegível"));
    im.src = `data:image/png;base64,${b64}`;
  });
}

/** Atlas (PA | perfil) em canvas local; nada sai do navegador. */
async function buildAtlas(meta: TextureMeta): Promise<THREE.CanvasTexture> {
  const lay = atlasLayout(meta);
  const imgs = await Promise.all([loadImage(meta.frontal.png_b64), meta.lateral ? loadImage(meta.lateral.png_b64) : null]);
  const cell = Math.min(ATLAS_CELL_MAX, Math.max(meta.frontal.w, meta.frontal.h, meta.lateral?.w ?? 0, meta.lateral?.h ?? 0));
  const cv = document.createElement("canvas");
  cv.width = cell * (lay.lateral ? 2 : 1);
  cv.height = cell;
  const g = cv.getContext("2d")!;
  g.drawImage(imgs[0], 0, 0, cell, cell);
  if (imgs[1]) g.drawImage(imgs[1], cell, 0, cell, cell);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function geometryUV(geo: THREE.BufferGeometry, meta: TextureMeta) {
  if (geo.getAttribute("uv") && geo.userData.realUV) return;
  if (!geo.getAttribute("normal")) geo.computeVertexNormals();
  const pos = geo.getAttribute("position").array;
  const nrm = geo.getAttribute("normal").array;
  const { uv, shade } = planarUV(pos, nrm, meta);
  const col = new Float32Array(shade.length * 3);
  for (let i = 0; i < shade.length; i++) col[3 * i] = col[3 * i + 1] = col[3 * i + 2] = shade[i];
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.userData.realUV = true;
}

function Model({ root, meshes, state, onSelect, onBounds, onTexture }: ModelProps & { root: THREE.Object3D }) {
  const gl = useThree((s) => s.gl);
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, -1, 0), 0), []);
  const keys = useMemo(() => meshes.map((m) => m.key), [meshes]);
  const estimated = useMemo(() => new Set(meshes.filter((m) => isEstimated(m.label)).map((m) => m.key)), [meshes]);

  // Prepara nós, materiais próprios, centróides e limites (uma vez por modelo).
  const prep = useMemo(() => {
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const center = box.getCenter(new THREE.Vector3());
    const nodes: Record<string, THREE.Object3D> = {};
    const mats: Record<string, THREE.Material[]> = {};
    const geoms: Record<string, THREE.BufferGeometry[]> = {};
    const centroids: Record<string, Vec3> = {};
    const origin: Record<string, THREE.Vector3> = {};
    for (const m of meshes) {
      const node = root.getObjectByName(m.key);
      if (!node) continue;
      nodes[m.key] = node;
      origin[m.key] = node.position.clone();
      const list: THREE.Material[] = [];
      const glist: THREE.BufferGeometry[] = [];
      node.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) {
          const mat = (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material).clone();
          if ("color" in mat && m.color) (mat as THREE.MeshStandardMaterial).color.set(m.color);
          mat.side = THREE.DoubleSide;
          mesh.material = mat;
          list.push(mat);
          glist.push(mesh.geometry);
        }
      });
      mats[m.key] = list;
      geoms[m.key] = glist;
      const c = new THREE.Box3().setFromObject(node).getCenter(new THREE.Vector3());
      centroids[m.key] = [c.x - center.x, c.y - center.y, c.z - center.z];
    }
    const min: Vec3 = [box.min.x - center.x, box.min.y - center.y, box.min.z - center.z];
    const max: Vec3 = [box.max.x - center.x, box.max.y - center.y, box.max.z - center.z];
    const radius = box.getBoundingSphere(new THREE.Sphere()).radius;
    const texMeta = readTextureMeta(root.userData);
    return { center, nodes, mats, geoms, centroids, origin, min, max, radius, texMeta };
  }, [root, meshes]);

  useEffect(() => {
    gl.localClippingEnabled = true;
  }, [gl]);

  useEffect(() => {
    onBounds({ radius: prep.radius, min: prep.min, max: prep.max });
  }, [prep, onBounds]);

  useEffect(() => {
    onTexture?.({ available: !!prep.texMeta, onlyPA: !!prep.texMeta && !prep.texMeta.lateral });
  }, [prep, onTexture]);

  const [atlas, setAtlas] = useState<THREE.CanvasTexture | null>(null);
  const wantReal = state.texMode === "real" && !!prep.texMeta;
  useEffect(() => {
    if (!wantReal || !prep.texMeta || atlas) return;
    let alive = true;
    buildAtlas(prep.texMeta)
      .then((t) => alive && setAtlas(t))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [wantReal, prep.texMeta, atlas]);
  const realOn = wantReal && !!atlas;

  useEffect(() => {
    for (const m of meshes) {
      const list = prep.mats[m.key] ?? [];
      list.forEach((mat, i) => {
        const std = mat as THREE.MeshStandardMaterial;
        if (realOn && prep.texMeta) {
          geometryUV(prep.geoms[m.key][i], prep.texMeta);
          std.map = atlas;
          std.vertexColors = true;
          std.color.set("#ffffff");
        } else {
          std.map = null;
          std.vertexColors = false;
          if (m.color) std.color.set(m.color);
        }
        std.needsUpdate = true;
      });
    }
  }, [realOn, atlas, prep, meshes]);

  const offsets = useMemo(() => explodeOffsets(prep.centroids, state.explode), [prep, state.explode]);

  useEffect(() => {
    const p = clipPlaneFor(state.clip.axis, state.clip.t, prep.min, prep.max);
    plane.normal.set(...p.normal);
    plane.constant = p.constant;
  }, [state.clip.axis, state.clip.t, prep, plane]);

  useEffect(() => {
    for (const k of keys) {
      const node = prep.nodes[k];
      if (!node) continue;
      node.visible = state.visible.has(k);
      const o = offsets[k] ?? [0, 0, 0];
      node.position.set(prep.origin[k].x + o[0], prep.origin[k].y + o[1], prep.origin[k].z + o[2]);
      const op = effectiveOpacity(k, state.opacity[k] ?? 1, state.lungGlobal, estimated.has(k));
      for (const mat of prep.mats[k] ?? []) {
        mat.transparent = op < 0.99;
        mat.opacity = op;
        mat.depthWrite = op >= 0.99;
        const wasClipped = (mat.clippingPlanes?.length ?? 0) > 0;
        mat.clippingPlanes = state.clip.enabled ? [plane] : [];
        if (wasClipped !== state.clip.enabled) mat.needsUpdate = true;
        const std = mat as THREE.MeshStandardMaterial;
        if (std.emissive) {
          std.emissive.set(state.selected === k ? "#ffffff" : "#000000");
          std.emissiveIntensity = state.selected === k ? 0.35 : 0;
        }
      }
    }
  }, [keys, prep, offsets, state, plane, estimated]);

  const labelPts = useMemo(() => {
    return keys
      .filter((k) => prep.centroids[k])
      .map((k) => {
        const c = prep.centroids[k];
        const o = offsets[k] ?? [0, 0, 0];
        const a = new THREE.Vector3(c[0] + o[0], c[1] + o[1], c[2] + o[2]);
        // etiqueta empurrada para fora (lateral) para a linha-guia não cobrir o órgão
        const side = c[0] === 0 ? 1 : Math.sign(c[0]);
        const b = a.clone().add(new THREE.Vector3(side * prep.radius * 0.75, prep.radius * 0.1, prep.radius * 0.3));
        return { key: k, a, b };
      });
  }, [keys, prep, offsets]);

  const keySet = useMemo(() => new Set(keys), [keys]);

  return (
    <group position={[-prep.center.x, -prep.center.y, -prep.center.z]}>
      <primitive
        object={root}
        onClick={(e: { stopPropagation: () => void; object: THREE.Object3D }) => {
          e.stopPropagation();
          let o: THREE.Object3D | null = e.object;
          while (o && !keySet.has(o.name)) o = o.parent;
          onSelect(o ? o.name : null);
        }}
        onPointerOver={() => (gl.domElement.style.cursor = "pointer")}
        onPointerOut={() => (gl.domElement.style.cursor = "auto")}
      />
      {state.labels &&
        labelPts
          .filter((l) => state.visible.has(l.key))
          .map((l) => {
            const meta = meshes.find((m) => m.key === l.key)!;
            return (
              <group key={l.key}>
                <Line points={[l.a, l.b]} color={meta.color || "#ffffff"} lineWidth={1.2} />
                <Html position={l.b} style={{ pointerEvents: "none" }}>
                  <div className="r3d-label3d">{baseLabel(meta.label)}{isEstimated(meta.label) ? " (estimativa)" : ""}</div>
                </Html>
              </group>
            );
          })}
    </group>
  );
}

function GlbModel(props: ModelProps & { url: string }) {
  const gltf = useGLTF(props.url);
  const root = useMemo(() => gltf.scene.clone(true), [gltf.scene]);
  return <Model {...props} root={root} />;
}

function DemoModel(props: ModelProps) {
  const root = useMemo(() => buildDemoScene(), []);
  return <Model {...props} root={root} />;
}

export function ModelLoader(props: ModelProps & { url: string }) {
  return props.url === "demo" ? <DemoModel {...props} /> : <GlbModel {...props} />;
}

/** Posiciona a câmera conforme a vista predefinida. */
export function CameraRig({ preset, nonce, radius }: { preset: PresetId; nonce: number; radius: number }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as { update?: () => void; target?: THREE.Vector3 } | null;
  useEffect(() => {
    const fov = (camera as THREE.PerspectiveCamera).fov ?? 45;
    const p = cameraPositionForPreset(preset, radius, fov);
    if (preset === "superior") p[2] = -Math.abs(p[1]) * 0.001; // evita singularidade; anterior para cima
    camera.position.set(...p);
    camera.near = radius / 100;
    camera.far = radius * 50;
    camera.updateProjectionMatrix();
    controls?.target?.set(0, 0, 0);
    camera.lookAt(0, 0, 0);
    controls?.update?.();
  }, [preset, nonce, radius, camera, controls]);
  return <OrbitControls makeDefault enableDamping dampingFactor={0.12} />;
}

/** Expõe função de captura de tela ao componente pai. */
export function Capture({ shot }: { shot: React.MutableRefObject<(() => string) | null> }) {
  const { gl, scene, camera } = useThree();
  useEffect(() => {
    shot.current = () => {
      gl.render(scene, camera);
      return gl.domElement.toDataURL("image/png");
    };
    return () => {
      shot.current = null;
    };
  }, [gl, scene, camera, shot]);
  return null;
}

function labelTexture(text: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 80;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "rgba(20,24,32,0.78)";
  ctx.beginPath();
  ctx.roundRect?.(4, 10, 248, 60, 16);
  if (!ctx.roundRect) ctx.rect(4, 10, 248, 60);
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.font = "bold 36px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 42);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const GIZMO_LABELS: { text: string; pos: Vec3; color: string }[] = [
  { text: "Esquerda", pos: [1, 0, 0], color: "#ef5350" },
  { text: "Direita", pos: [-1, 0, 0], color: "#b71c1c" },
  { text: "Superior", pos: [0, 1, 0], color: "#66bb6a" },
  { text: "Inferior", pos: [0, -1, 0], color: "#1b5e20" },
  { text: "Anterior", pos: [0, 0, 1], color: "#42a5f5" },
  { text: "Posterior", pos: [0, 0, -1], color: "#0d47a1" },
];

function OrientationGizmo() {
  const sprites = useMemo(
    () => GIZMO_LABELS.map((l) => ({ ...l, tex: labelTexture(l.text) })),
    [],
  );
  return (
    <group scale={0.9}>
      {sprites.map((s) => (
        <group key={s.text}>
          <mesh position={s.pos.map((v) => v * 0.55) as Vec3}>
            <sphereGeometry args={[0.1, 12, 12]} />
            <meshBasicMaterial color={s.color} />
          </mesh>
          <sprite position={s.pos.map((v) => v * 1.25) as Vec3} scale={[1.2, 0.375, 1]}>
            <spriteMaterial map={s.tex} depthTest={false} transparent />
          </sprite>
        </group>
      ))}
      {(
        <>
          <Line points={[[-0.55, 0, 0], [0.55, 0, 0]]} color="#888" lineWidth={1} />
          <Line points={[[0, -0.55, 0], [0, 0.55, 0]]} color="#888" lineWidth={1} />
          <Line points={[[0, 0, -0.55], [0, 0, 0.55]]} color="#888" lineWidth={1} />
        </>
      )}
    </group>
  );
}

export function Gizmo() {
  return (
    <GizmoHelper alignment="bottom-right" margin={[80, 70]}>
      <OrientationGizmo />
    </GizmoHelper>
  );
}
