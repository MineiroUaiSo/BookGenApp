import { useEffect, useMemo, useState } from "react";
import { fetchRulePpv, sendFeedback } from "../../api/client";
import type { RulePpvEntry } from "../../api/client";
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

type Verdict = "agree" | "disagree";
type FeedbackFn = (code: string, verdict: Verdict) => void;

function FeedbackButtons({ code, vote, onVote }: { code: string; vote?: Verdict; onVote: FeedbackFn }) {
  return (
    <span className="feedback no-print" role="group" aria-label={`Feedback sobre o achado ${code}`}>
      <button type="button" className="btn small" aria-pressed={vote === "agree"} onClick={() => onVote(code, "agree")}>Concordo</button>{" "}
      <button type="button" className="btn small" aria-pressed={vote === "disagree"} onClick={() => onVote(code, "disagree")}>Discordo</button>
    </span>
  );
}

const nf = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "VPP 0,80 [0,74–0,85] (PTB-XL dev, N=123)" or "VPP não medido". */
export function ppvLabel(e?: RulePpvEntry): string {
  if (!e) return "VPP não medido";
  return `VPP ${nf.format(e.ppv)} [${nf.format(e.ic_inf)}–${nf.format(e.ic_sup)}] (${e.fonte}, N=${e.n})`;
}

let ppvCache: Promise<Record<string, RulePpvEntry>> | null = null;
function loadPpv(): Promise<Record<string, RulePpvEntry>> {
  ppvCache ??= fetchRulePpv().then((r) => r.codes).catch(() => ({}));
  return ppvCache;
}

function useRulePpv(): Record<string, RulePpvEntry> {
  const [m, setM] = useState<Record<string, RulePpvEntry>>({});
  useEffect(() => { let on = true; loadPpv().then((x) => { if (on) setM(x); }); return () => { on = false; }; }, []);
  return m;
}

function FindingItem({ f, vote, onVote, ppv }: { f: Finding; vote?: Verdict; onVote?: FeedbackFn; ppv?: Record<string, RulePpvEntry> }) {
  return (
    <div className={`finding sev-${f.severity}`}>
      <strong>{f.label}</strong>{" "}
      <span className={`badge ${f.severity}`}>{SEV_LABEL[f.severity]}</span>{" "}
      <span className="badge">{ORIGIN_LABEL[f.origin]}</span>{" "}
      {f.origin === "rules" && ppv
        ? <span className="hint" data-testid="ppv">{ppvLabel(ppv[f.code])}</span>
        : <span className="hint">{Math.round(f.confidence * 100)}%</span>}
      {f.evidence.length > 0 && <ul>{f.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>}
      {onVote && <FeedbackButtons code={f.code} vote={vote} onVote={onVote} />}
    </div>
  );
}

interface Props {
  title?: string; findings: Finding[]; ai?: AIReport | null; aiRequested?: boolean;
  aiLoading?: boolean; aiError?: string | null;
  /** when both are set, rules findings get concordo/discordo buttons (stored locally, no PHI) */
  feedback?: { studyId: string; kind: "ecg" | "rx" };
}

export default function ReportPanel({ title = "Laudo", findings, ai, aiRequested = true, aiLoading = false, aiError = null, feedback }: Props) {
  const [copied, setCopied] = useState(false);
  const [votes, setVotes] = useState<Record<string, Verdict>>({});
  const [fbError, setFbError] = useState<string | null>(null);
  const ppv = useRulePpv();
  const vote: FeedbackFn | undefined = feedback ? (code, verdict) => {
    setFbError(null);
    setVotes((v) => ({ ...v, [code]: verdict }));
    sendFeedback(feedback.studyId, { kind: feedback.kind, code, verdict })
      .catch((e: Error) => { setVotes((v) => { const { [code]: _drop, ...rest } = v; return rest; }); setFbError(e.message); });
  } : undefined;
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
      {fbError && <p className="error" role="alert">Feedback não gravado: {fbError}</p>}
      {findings.length ? findings.map((f) => <FindingItem key={f.code + f.label} f={f} vote={votes[f.code]} onVote={vote} ppv={ppv} />)
        : <p className="hint">Nenhum achado automático.</p>}

      {ai?.available ? (
        <>
          {ai.model && <p className="hint">Gerado por IA ({ai.model})</p>}
          {ai.laudo_markdown ? (
            <>
              <h3>Laudo estruturado (rascunho)</h3>
              <pre className="desc" style={{ whiteSpace: "pre-wrap" }}>{ai.laudo_markdown}</pre>
              {ai.laudo_curto && (
                <>
                  <h4>Versão curta para prontuário</h4>
                  <p className="desc">{ai.laudo_curto}</p>
                </>
              )}
              <div className="btn-row no-print">
                <button className="btn small" onClick={() => navigator.clipboard?.writeText(ai.laudo_markdown ?? "")}>Copiar laudo (markdown)</button>
                {ai.laudo_curto && <button className="btn small" onClick={() => navigator.clipboard?.writeText(ai.laudo_curto ?? "")}>Copiar versão curta</button>}
              </div>
            </>
          ) : null}
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
      ) : aiLoading ? (
        <p className="hint" role="status" data-testid="ai-loading">Gerando texto da IA… o laudo por regras acima já está disponível.</p>
      ) : aiError ? (
        <p className="hint" role="status">Texto da IA indisponível ({aiError}). Exibindo apenas medidas e regras.</p>
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
