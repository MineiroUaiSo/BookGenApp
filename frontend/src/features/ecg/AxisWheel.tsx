import { LIMB_LEAD_ANGLES, classifyAxis, normDeg } from "./ecgMath";

interface Props { p?: number | null; qrs?: number | null; t?: number | null; size?: number }
const R = 100, C = 130;
const pt = (deg: number, r = R) => [C + r * Math.cos((deg * Math.PI) / 180), C + r * Math.sin((deg * Math.PI) / 180)] as const;

export default function AxisWheel({ p, qrs, t, size = 260 }: Props) {
  const vecs: { name: string; deg?: number | null; color: string }[] = [
    { name: "P", deg: p, color: "#2f80ed" }, { name: "QRS", deg: qrs, color: "#d62828" }, { name: "T", deg: t, color: "#2e9e5b" },
  ];
  const [nx1, ny1] = pt(-30), [nx2, ny2] = pt(90);
  return (
    <figure style={{ margin: 0 }}>
      <svg width={size} height={size} viewBox="0 0 260 260" role="img" aria-label="Diagrama hexaxial dos eixos" data-testid="axis-wheel">
        <circle cx={C} cy={C} r={R} fill="none" style={{ stroke: "var(--ecg-line)" }} strokeWidth={1.5} />
        <path d={`M${C} ${C}L${nx1} ${ny1}A${R} ${R} 0 0 1 ${nx2} ${ny2}Z`} fill="#2e9e5b" fillOpacity={0.1} />
        {Object.entries(LIMB_LEAD_ANGLES).map(([lead, a]) => {
          const [x1, y1] = pt(a), [x2, y2] = pt(a + 180), [lx, ly] = pt(a, R + 14);
          return (
            <g key={lead}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} style={{ stroke: "var(--ecg-line)" }} strokeDasharray="3 3" />
              <text x={lx} y={ly} fontSize={11} textAnchor="middle" dominantBaseline="middle" style={{ fill: "var(--ecg-fg)" }}>{lead}</text>
            </g>
          );
        })}
        {vecs.map((v) => {
          if (v.deg == null) return null;
          const [x, y] = pt(v.deg, R - 6);
          const [tx, ty] = pt(v.deg, R * 0.55);
          return (
            <g key={v.name} data-vector={v.name}>
              <line x1={C} y1={C} x2={x} y2={y} stroke={v.color} strokeWidth={3} strokeLinecap="round" />
              <circle cx={x} cy={y} r={4} fill={v.color} />
              <text x={tx} y={ty - 5} fontSize={11} fontWeight={700} fill={v.color} textAnchor="middle">{v.name} {normDeg(v.deg).toFixed(0)}°</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="ecg-muted" style={{ fontSize: 12 }}>
        Faixa verde: eixo normal do QRS (−30° a +90°).
        {qrs != null && ` QRS: ${classifyAxis(qrs)}.`}
      </figcaption>
    </figure>
  );
}
