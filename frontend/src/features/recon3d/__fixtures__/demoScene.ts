import * as THREE from "three";
import type { Recon3DResult } from "../../../types/api";

export const DEMO_RESULT: Recon3DResult = {
  study_id: "demo",
  gltf_url: "demo",
  meshes: [
    { key: "lung_right", label: "Pulmão direito", color: "#e8a0a8", volume_ml: 2450 },
    { key: "lung_left", label: "Pulmão esquerdo", color: "#e8a0a8", volume_ml: 2100 },
    { key: "heart", label: "Coração", color: "#c0392b", volume_ml: 620 },
    { key: "trachea", label: "Traqueia", color: "#7fb3d5", volume_ml: 35 },
    { key: "spine", label: "Coluna", color: "#e5e1d0", volume_ml: null },
  ],
  method:
    "Cena de demonstração procedural (elipsoides e cilindros). Não deriva de nenhum exame real.",
  disclaimer:
    "Modelo ilustrativo/aproximado, gerado a partir de radiografias 2D. Não substitui TC e não deve ser usado para decisões clínicas.",
};

function mesh(geo: THREE.BufferGeometry, name: string, color: string): THREE.Mesh {
  const m = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.05 }),
  );
  m.name = name;
  return m;
}

/** +X = esquerda do paciente, +Y = superior, +Z = anterior. Unidade ~ 10 cm. */
export function buildDemoScene(): THREE.Group {
  const g = new THREE.Group();
  g.name = "demo";

  const lungGeo = () => new THREE.SphereGeometry(1, 40, 28);
  const lr = mesh(lungGeo(), "lung_right", "#e8a0a8");
  lr.scale.set(0.9, 1.5, 0.8);
  lr.position.set(-1.05, 0, 0);
  const ll = mesh(lungGeo(), "lung_left", "#e8a0a8");
  ll.scale.set(0.8, 1.45, 0.78);
  ll.position.set(1.05, 0, 0);

  const heart = mesh(new THREE.SphereGeometry(1, 32, 24), "heart", "#c0392b");
  heart.scale.set(0.65, 0.75, 0.6);
  heart.position.set(0.35, -0.25, 0.25);
  heart.rotation.z = -0.4;

  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 2.1, 0.05),
    new THREE.Vector3(0, 1.3, 0),
    new THREE.Vector3(0, 0.7, -0.05),
  ]);
  const trachea = mesh(new THREE.TubeGeometry(curve, 24, 0.12, 12, false), "trachea", "#7fb3d5");

  const spine = mesh(new THREE.CylinderGeometry(0.2, 0.2, 4.2, 20), "spine", "#e5e1d0");
  spine.position.set(0, 0.1, -0.95);

  g.add(lr, ll, heart, trachea, spine);
  return g;
}
