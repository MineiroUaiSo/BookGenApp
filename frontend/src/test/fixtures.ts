import type { AIReport, Finding, Structure } from "../types/api";

const ref = { id: "ref-1", source: "Goldberger. Clinical Electrocardiography, 9a ed." };
export const findings: Finding[] = [
  { code: "qrs_wide", label: "QRS alargado", severity: "abnormal", evidence: ["QRS 140 ms"], references: [ref], confidence: 0.9, origin: "rules" },
  { code: "hr_ok", label: "FC normal", severity: "normal", evidence: [], references: [], confidence: 0.8, origin: "rules" },
];
export const ai: AIReport = {
  available: true, model: "claude-test",
  description: "Ritmo regular com ondas P presentes.",
  findings: [{ code: "x", label: "Achado IA", severity: "borderline", evidence: ["e1"], references: [ref, { id: "ref-2", source: "Diretriz SBC" }], confidence: 0.5, origin: "llm" }],
  differentials: [{ diagnosis: "BRE", rationale: "QRS largo", supporting: ["QRS > 120"], against: ["sem R monofásico"], references: [ref], confidence: 0.7 }],
  disagreements_with_measurements: ["Visual sugere eixo normal; medido -40°"],
  limitations: ["Foto com baixa resolução"],
  disclaimer: "Rascunho — revisar por médico.",
};
export const structures: Structure[] = [
  { key: "lung_r", label: "Pulmão direito", category: "lung", color: "#3b82f6", polygon: [], confidence: 0.9, origin: "model" },
  { key: "lung_l", label: "Pulmão esquerdo", category: "lung", color: "#06b6d4", polygon: [], confidence: 0.9, origin: "model" },
  { key: "heart", label: "Coração", category: "heart_vessels", color: "#ef4444", polygon: [], confidence: 0.9, origin: "model" },
  { key: "clav_r", label: "Clavícula direita", category: "bone", color: "#eab308", polygon: [], confidence: 0.9, origin: "model" },
];
