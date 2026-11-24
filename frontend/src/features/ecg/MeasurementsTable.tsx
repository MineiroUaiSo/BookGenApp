import type { GlobalMeasurements, LeadMeasurements } from "../../types/api";
import { GLOBAL_ROWS, LEAD_COLS, classifyAxis, inRange } from "./ecgMath";

export function GlobalTable({ g }: { g: GlobalMeasurements }) {
  return (
    <div className="ecg-table-scroll">
      <table className="ecg-table" aria-label="Medidas globais">
        <thead><tr><th>Medida</th><th>Valor</th><th>Normal</th></tr></thead>
        <tbody>
          {GLOBAL_ROWS.map((r) => {
            const v = g[r.key];
            const num = typeof v === "number" ? v : null;
            const out = num != null && !inRange(num, r.range);
            const extra = num != null && r.key.endsWith("axis_deg") && r.key === "qrs_axis_deg" ? ` (${classifyAxis(num)})` : "";
            return (
              <tr key={r.key} data-key={r.key}>
                <td>{r.label}</td>
                <td className={out ? "out" : undefined} data-out={out ? "1" : "0"}>
                  {v == null ? "–" : num != null ? `${num.toFixed(r.decimals)} ${r.unit}${extra}` : String(v)}
                </td>
                <td className="ecg-muted">{r.range?.label ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function LeadTable({ rows, highlight = [] }: { rows: LeadMeasurements[]; highlight?: string[] }) {
  return (
    <div className="ecg-table-scroll">
      <table className="ecg-table" aria-label="Medidas por derivação">
        <thead>
          <tr><th>Deriv.</th>{LEAD_COLS.map((c) => <th key={c.key}>{c.label}</th>)}<th>Morfologia</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.lead} style={highlight.includes(r.lead) ? { background: "color-mix(in srgb, #ffd23f 25%, transparent)" } : undefined}>
              <td><strong>{r.lead}</strong></td>
              {LEAD_COLS.map((c) => {
                const v = r[c.key];
                const num = typeof v === "number" ? v : null;
                const out = num != null && !inRange(num, c.range);
                return <td key={c.key} className={out ? "out" : undefined}>{num == null ? "–" : num.toFixed(c.decimals)}</td>;
              })}
              <td>{r.morphology ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
