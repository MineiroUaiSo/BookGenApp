import { useMemo, useState } from "react";
import type { AIReport, Finding, Reference } from "../../types/api";

export const DEFAULT_DISCLAIMER =
  "Ferramenta de apoio à decisão e ensino. Não é dispositivo médico certificado. Todo laudo é um rascunho e exige revisão por médico.";

const SEV_LABEL: Record<Finding["severity"], string> = {
  normal: "Normal", borderline: "Limítrofe", abnormal: "Alterado", critical: "Crítico",
};
const ORIGIN_LABEL: Record<Finding["origin"], string> = { rules: "regras", model: "modelo", llm: "IA" };

export function dedupRefs(lists: Reference[][]): Reference[] {
  const m = new Map<string, Reference>();
  for (const l of lists) for (const r of l) if (!m.has(r.id)) m.set(r.id, r);
  return [...m.values()];
}

export function collectRefs(findings: Finding[], ai?: AIReport | null): Reference[] {
  return dedupRefs([
    ...findings.map((f) => f.references),
    ...(ai?.findings ?? []).map((f) => f.references),
    ...(ai?.differentials ?? []).map((d) => d.references),
  ]);
}

export function reportToText(title: string, findings: Finding[], ai?: AIReport | null): string {
  const L: string[] = [title, ""];
  const fl = (f: Finding) => `- [${SEV_LABEL[f.severity]}] ${f.label}${f.evidence.length ? ` (${f.evidence.join("; ")})` : ""}`;
  if (findings.length) { L.push("ACHADOS (REGRAS)", ...findings.map(fl), ""); }
  if (ai?.available) {
    if (ai.description) L.push("DESCRIÇÃO MINUCIOSA", ai.description, "");
    if (ai.findings.length) L.push("ACHADOS", ...ai.findings.map(fl), "");
    if (ai.differentials.length) {
      L.push("ANÁLISE CRÍTICA");
      for (const d of ai.differentials) {
        L.push(`- ${d.diagnosis} (confiança ${Math.round(d.confidence * 100)}%)`, `  ${d.rationale}`);
        if (d.supporting.length) L.push(`  A favor: ${d.supporting.join("; ")}`);
        if (d.against.length) L.push(`  Contra: ${d.against.join("; ")}`);
      }
      L.push("");
    }
    if (ai.disagreements_with_measurements.length)
      L.push("DISCORDÂNCIAS COM AS MEDIDAS", ...ai.disagreements_with_measurements.map((x) => `- ${x}`), "");
    if (ai.limitations.length) L.push("LIMITAÇÕES", ...ai.limitations.map((x) => `- ${x}`), "");
  }
  const refs = collectRefs(findings, ai);
  if (refs.length) L.push("REFERÊNCIAS", ...refs.map((r, i) => `[${i + 1}] ${r.source}${r.note ? ` — ${r.note}` : ""}`), "");
  L.push("AVISO", ai?.disclaimer || DEFAULT_DISCLAIMER);
  return L.join("\n");
}

function FindingItem({ f }: { f: Finding }) {
  return (
    <div className={`finding sev-${f.severity}`}>
      <strong>{f.label}</strong>{" "}
      <span className={`badge ${f.severity}`}>{SEV_LABEL[f.severity]}</span>{" "}
      <span className="badge">{ORIGIN_LABEL[f.origin]}</span>{" "}
      <span className="hint">{Math.round(f.confidence * 100)}%</span>
      {f.evidence.length > 0 && <ul>{f.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>}
    </div>
  );
}

interface Props { title?: string; findings: Finding[]; ai?: AIReport | null; aiRequested?: boolean }

export default function ReportPanel({ title = "Laudo", findings, ai, aiRequested = true }: Props) {
  const [copied, setCopied] = useState(false);
  const refs = useMemo(() => collectRefs(findings, ai), [findings, ai]);
  const text = useMemo(() => reportToText(title, findings, ai), [title, findings, ai]);

  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { window.prompt("Copie o laudo:", text); }
  };

  return (
    <article className="card report-panel" aria-label="Laudo">
      <div className="btn-row no-print" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <div className="btn-row">
          <button className="btn small" onClick={copy}>{copied ? "Copiado!" : "Copiar como texto"}</button>
          <button className="btn small" onClick={() => window.print()}>Imprimir / PDF</button>
        </div>
      </div>
      

      <h3>Achados por regras e medidas</h3>
      {findings.length ? findings.map((f) => <FindingItem key={f.code + f.label} f={f} />)
        : <p className="hint">Nenhum achado automático.</p>}

      {ai?.available ? (
        <>
          {ai.model && <p className="hint">Gerado por IA ({ai.model})</p>}
          <h3>Descrição minuciosa</h3>
          <p className="desc">{ai.description || "—"}</p>

          <h3>Achados</h3>
          {ai.findings.length ? ai.findings.map((f) => <FindingItem key={f.code + f.label} f={f} />)
            : <p className="hint">Sem achados adicionais.</p>}

          <h3>Análise crítica</h3>
          {ai.differentials.length ? ai.differentials.map((d) => (
            <div className="diff" key={d.diagnosis}>
              <strong>{d.diagnosis}</strong>{" "}
              <span className="conf" role="img" aria-label={`Confiança ${Math.round(d.confidence * 100)}%`}>
                <i style={{ width: `${Math.round(d.confidence * 100)}%` }} />
              </span>{" "}
              <span className="hint">{Math.round(d.confidence * 100)}%</span>
              <p>{d.rationale}</p>
              <div className="cols">
                <div><h4>A favor</h4>{d.supporting.length ? <ul>{d.supporting.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="hint">—</p>}</div>
                <div><h4>Contra</h4>{d.against.length ? <ul>{d.against.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="hint">—</p>}</div>
              </div>
            </div>
          )) : <p className="hint">Sem diferenciais.</p>}

          <h3>Discordâncias com as medidas</h3>
          {ai.disagreements_with_measurements.length
            ? <ul>{ai.disagreements_with_measurements.map((x, i) => <li key={i}>{x}</li>)}</ul>
            : <p className="hint">Nenhuma discordância identificada.</p>}

          <h3>Limitações</h3>
          {ai.limitations.length ? <ul>{ai.limitations.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="hint">—</p>}
        </>
      ) : (
        <p className="hint" role="status">
          {aiRequested ? "Análise por IA indisponível (sem chave de API ou desativada). Exibindo apenas medidas e regras." : "Análise por IA não solicitada."}
        </p>
      )}

      <h3>Referências</h3>
      {refs.length ? (
        <ol className="refs">{refs.map((r) => <li key={r.id}>{r.source}{r.note ? ` — ${r.note}` : ""}</li>)}</ol>
      ) : <p className="hint">—</p>}

      <p className="disclaimer" role="note"><strong>Aviso: </strong>{ai?.disclaimer || DEFAULT_DISCLAIMER}</p>
    </article>
  );
}
