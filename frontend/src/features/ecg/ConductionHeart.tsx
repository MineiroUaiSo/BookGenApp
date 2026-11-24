import type { ConductionStructure } from "../../types/api";
import { STRUCTURE_COLORS, STRUCTURE_LABELS } from "./ecgMath";

interface Props {
  active: ConductionStructure[];
  onPick?: (s: ConductionStructure) => void;
}

// ramificações de Purkinje determinísticas a partir de pontos terminais
const TERMINALS: [number, number, number][] = [
  [170, 372, -90], [262, 255, -20], [255, 345, 40], [172, 330, 180],
];
const PURKINJE = TERMINALS.flatMap(([x, y, a], k) =>
  [-50, -25, 0, 25, 50].map((d, i) => {
    const r = ((a + d) * Math.PI) / 180, len = 16 + ((i + k) % 3) * 5;
    const x2 = x + len * Math.cos(r), y2 = y - len * Math.sin(r);
    return `M${x} ${y}L${x2.toFixed(1)} ${y2.toFixed(1)}`;
  }),
).join("");

export default function ConductionHeart({ active, onPick }: Props) {
  const on = new Set(active);
  const cls = (s: ConductionStructure) => (on.has(s) ? "lit" : "dim");
  const g = (s: ConductionStructure) => ({
    className: cls(s), "data-structure": s, "data-active": on.has(s) ? "1" : "0",
    filter: on.has(s) ? "url(#glow)" : undefined, onClick: () => onPick?.(s), style: { cursor: onPick ? "pointer" : "default" },
  });
  const col = STRUCTURE_COLORS;
  const wall = "var(--ecg-line)";
  return (
    <svg viewBox="0 0 380 420" role="img" aria-label="Diagrama anatômico do sistema de condução cardíaco" className="ecg-heart" style={{ width: "100%", maxWidth: 420 }} data-testid="heart">
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {/* ventrículos (parede) */}
      <g {...g("ventricles_depol")}>
        <path d="M62 205 C58 285 100 360 180 392 L180 205 Z" fill={on.has("ventricles_depol") ? col.ventricles_depol : "#c78c8c"} fillOpacity={on.has("ventricles_depol") ? 0.55 : 0.35} stroke={wall} strokeWidth={2} />
        <path d="M184 205 L184 392 C275 368 322 300 306 205 Z" fill={on.has("ventricles_depol") ? col.ventricles_depol : "#c78c8c"} fillOpacity={on.has("ventricles_depol") ? 0.55 : 0.35} stroke={wall} strokeWidth={2} />
      </g>
      <g {...g("ventricles_repol")} filter={on.has("ventricles_repol") ? "url(#glow)" : undefined} style={{ pointerEvents: "none" }}>
        <path d="M62 205 C58 285 100 360 180 392 L180 205 Z" fill={col.ventricles_repol} fillOpacity={on.has("ventricles_repol") ? 0.5 : 0} />
        <path d="M184 205 L184 392 C275 368 322 300 306 205 Z" fill={col.ventricles_repol} fillOpacity={on.has("ventricles_repol") ? 0.5 : 0} />
      </g>
      {/* átrios */}
      <g {...g("atria")}>
        <path d="M65 85 C60 130 75 175 125 195 L178 195 L178 88 C150 60 90 55 65 85 Z" fill={on.has("atria") ? col.atria : "#8aa7d6"} fillOpacity={on.has("atria") ? 0.6 : 0.35} stroke={wall} strokeWidth={2} />
        <path d="M182 88 L182 195 L250 195 C300 170 300 120 280 90 C255 60 215 62 182 88 Z" fill={on.has("atria") ? col.atria : "#8aa7d6"} fillOpacity={on.has("atria") ? 0.6 : 0.35} stroke={wall} strokeWidth={2} />
        <path d="M105 85 C125 110 135 150 150 182 M100 86 C112 130 125 160 152 184 M112 82 C150 120 150 150 156 182 M110 78 C150 62 200 62 250 80" fill="none" stroke={col.atria} strokeWidth={1.6} strokeDasharray="4 2" />
      </g>
      {/* Purkinje */}
      <g {...g("purkinje")}><path d={PURKINJE} stroke={col.purkinje} strokeWidth={2} fill="none" strokeLinecap="round" /></g>
      {/* ramos */}
      <g {...g("RBB")}><path d="M178 245 C172 290 164 330 170 372" stroke={col.RBB} strokeWidth={4} fill="none" strokeLinecap="round" /></g>
      <g {...g("LBB")}>
        <path d="M182 245 L188 270 M188 270 C215 300 250 295 262 255 M188 270 C200 320 230 350 255 345" stroke={col.LBB} strokeWidth={4} fill="none" strokeLinecap="round" />
        <text x={268} y={252} fontSize={9} fill="currentColor" style={{ fill: "var(--ecg-fg)" }}>fascículo anterior</text>
        <text x={226} y={366} fontSize={9} style={{ fill: "var(--ecg-fg)" }}>fascículo posterior</text>
      </g>
      <g {...g("His")}><path d="M158 196 L178 215 L180 245" stroke={col.His} strokeWidth={5} fill="none" strokeLinecap="round" strokeLinejoin="round" /></g>
      <g {...g("AV_node")}><ellipse cx={155} cy={190} rx={12} ry={7} fill={col.AV_node} stroke={wall} /></g>
      <g {...g("SA")}><ellipse cx={100} cy={80} rx={13} ry={7} fill={col.SA} stroke={wall} transform="rotate(-20 100 80)" /></g>
      {([
        ["SA", 70, 62], ["AV_node", 100, 212], ["His", 190, 212], ["RBB", 100, 330], ["LBB", 270, 300],
        ["purkinje", 70, 392],
      ] as [ConductionStructure, number, number][]).map(([s, x, y]) => (
        <text key={s} x={x} y={y} fontSize={11} fontWeight={on.has(s) ? 700 : 500} style={{ fill: "var(--ecg-fg)" }} pointerEvents="none">{STRUCTURE_LABELS[s]}</text>
      ))}
      <text x={96} y={140} fontSize={11} style={{ fill: "var(--ecg-fg)" }} pointerEvents="none">AD</text>
      <text x={232} y={140} fontSize={11} style={{ fill: "var(--ecg-fg)" }} pointerEvents="none">AE</text>
      <text x={110} y={290} fontSize={11} style={{ fill: "var(--ecg-fg)" }} pointerEvents="none">VD</text>
      <text x={250} y={272} fontSize={11} style={{ fill: "var(--ecg-fg)" }} pointerEvents="none">VE</text>
    </svg>
  );
}
