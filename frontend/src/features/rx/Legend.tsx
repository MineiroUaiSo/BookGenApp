import type { Structure, StructureCategory } from "../../types/api";

export const CATEGORY_ORDER: StructureCategory[] = [
  "bone", "lung", "heart_vessels", "airway", "mediastinum", "diaphragm", "abdomen", "soft_tissue", "device", "other",
];
export const CATEGORY_LABEL: Record<StructureCategory, string> = {
  bone: "Ossos", lung: "Pulmões", heart_vessels: "Coração e vasos", airway: "Vias aéreas",
  mediastinum: "Mediastino", diaphragm: "Diafragma", abdomen: "Abdome", soft_tissue: "Partes moles",
  device: "Dispositivos", other: "Outros",
};

export function groupByCategory(structs: Structure[]): [StructureCategory, Structure[]][] {
  const map = new Map<StructureCategory, Structure[]>();
  const seen = new Set<string>();
  for (const s of structs) {
    if (seen.has(s.key)) continue;
    seen.add(s.key);
    const c = CATEGORY_ORDER.includes(s.category) ? s.category : "other";
    map.set(c, [...(map.get(c) ?? []), s]);
  }
  return CATEGORY_ORDER.filter((c) => map.has(c)).map((c) => [c, map.get(c)!]);
}

interface Props {
  structures: Structure[];
  hidden: Set<string>;
  onToggle: (key: string) => void;
  onSetMany: (keys: string[], visible: boolean) => void;
  hoverKey: string | null;
  onHover: (key: string | null) => void;
}

export default function Legend({ structures, hidden, onToggle, onSetMany, hoverKey, onHover }: Props) {
  const groups = groupByCategory(structures);
  const all = groups.flatMap(([, l]) => l.map((s) => s.key));
  return (
    <section className="legend" aria-label="Legenda das estruturas">
      <div className="btn-row" style={{ marginBottom: ".4rem" }}>
        <button className="btn small" onClick={() => onSetMany(all, true)}>Mostrar todas</button>
        <button className="btn small" onClick={() => onSetMany(all, false)}>Ocultar todas</button>
      </div>
      {groups.map(([cat, list]) => {
        const keys = list.map((s) => s.key);
        const allVisible = keys.every((k) => !hidden.has(k));
        return (
          <div className="legend-group" key={cat} role="group" aria-label={CATEGORY_LABEL[cat]}>
            <header>
              <span>{CATEGORY_LABEL[cat]} ({list.length})</span>
              <button className="btn small" onClick={() => onSetMany(keys, !allVisible)}>
                {allVisible ? "Ocultar grupo" : "Mostrar grupo"}
              </button>
            </header>
            <div className="legend-items">
              {list.map((s) => (
                <button key={s.key} type="button"
                  className={`legend-item${hoverKey === s.key ? " hover" : ""}`}
                  aria-pressed={!hidden.has(s.key)}
                  onClick={() => onToggle(s.key)}
                  onMouseEnter={() => onHover(s.key)} onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(s.key)} onBlur={() => onHover(null)}>
                  <span className="swatch" style={{ background: s.color }} aria-hidden="true" />
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
