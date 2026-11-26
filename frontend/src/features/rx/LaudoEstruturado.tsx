import { useEffect, useState } from "react";
import { API_BASE, fetchDescricaoIA, sendFeedback } from "../../api/client";
import type { FraseLaudo, LaudoRX, NivelLaudo, SecaoLaudo } from "../../types/api";

const ROTULO_NIVEL: Record<NivelLaudo, string> = {
  MEDIDO: "MEDIDO", REGRA: "REGRA", SUGERIDO_MODELO: "SUGERIDO MODELO", NAO_AVALIADO: "NAO AVALIADO", QUALIDADE: "QUALIDADE",
};
/** Alvo de toque mínimo de 44 px (global.css é do lote U1; sem edição de estilo global aqui). */
const ALVO_TOQUE = { minHeight: 44 } as const;
const ARMAZENAMENTO = "medlens.laudo_rx.comunicacao";

function guardar(chave: string, valor: string): void {
  try { localStorage.setItem(chave, valor); } catch { /* armazenamento indisponível: segue sem persistir */ }
}
function ler(chave: string): string {
  try { return localStorage.getItem(chave) ?? ""; } catch { return ""; }
}

function Frase({ f }: { f: FraseLaudo }) {
  return (
    <li className={`laudo-frase nivel-${f.nivel.toLowerCase()}`}>
      <span className="laudo-nivel" data-nivel={f.nivel}>{ROTULO_NIVEL[f.nivel]}</span>{" "}
      <span>{f.texto}</span>{" "}
      {f.fontes.map((s) => <sup key={s} className="laudo-fonte" title={`Fonte ${s}`}>{s}</sup>)}
    </li>
  );
}

type Voto = "agree" | "disagree";

const chaveVoto = (studyId: string | undefined, secaoId: string): string => `medlens.laudo_rx.voto.${studyId ?? "-"}.${secaoId}`;

/** Envio do voto ao servidor fica desligado até a decisão D2 do dono (VITE_ENVIAR_VOTO_LAUDO=1 liga). */
const ENVIAR_VOTO_PADRAO: boolean = import.meta.env?.VITE_ENVIAR_VOTO_LAUDO === "1";

function Parecer({ secao, studyId, enviarVoto }: { secao: SecaoLaudo; studyId?: string; enviarVoto: boolean }) {
  const [voto, setVoto] = useState<Voto | null>(() => {
    const v = ler(chaveVoto(studyId, secao.id));
    return v === "agree" || v === "disagree" ? v : null;
  });
  const votar = (v: Voto) => {
    setVoto(v);
    guardar(chaveVoto(studyId, secao.id), v);
    if (enviarVoto && studyId) {
      // Só hash do estudo, código da seção e voto; falha de rede não afeta a UI.
      sendFeedback(studyId, { kind: "rx", code: `rx.laudo.${secao.id}`, verdict: v }).catch(() => undefined);
    }
  };
  return (
    <span className="feedback no-print" role="group" aria-label={`Parecer sobre ${secao.titulo}`}>
      <button type="button" className="btn small" style={ALVO_TOQUE} aria-pressed={voto === "agree"} onClick={() => votar("agree")}>Concordo</button>{" "}
      <button type="button" className="btn small" style={ALVO_TOQUE} aria-pressed={voto === "disagree"} onClick={() => votar("disagree")}>Discordo</button>
    </span>
  );
}

function Comentario({ id, valor, onChange }: { id: string; valor: string; onChange: (v: string) => void }) {
  return (
    <label className="laudo-comentario no-print">
      <span className="dim">Comentário do médico (região não avaliada)</span>
      <textarea value={valor} rows={2} aria-label={`Comentário do médico ${id}`} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

interface SecaoProps {
  secao: SecaoLaudo; studyId?: string; enviarVoto: boolean;
  comentario: string; onComentario: (v: string) => void;
}

function Secao({ secao, studyId, enviarVoto, comentario, onComentario }: SecaoProps) {
  const modelo = secao.id === "sinais_modelo";
  const naoAvaliadas = secao.frases.filter((f) => f.nivel === "NAO_AVALIADO" && secao.id === "achados");
  return (
    <section aria-label={secao.titulo} className={`laudo-secao${modelo ? " laudo-modelo" : ""}`}>
      <h3>{secao.titulo}</h3>
      <ul>{secao.frases.map((f, i) => <Frase key={i} f={f} />)}</ul>
      {naoAvaliadas.length > 0 && <Comentario id={secao.id} valor={comentario} onChange={onComentario} />}
      <Parecer secao={secao} studyId={studyId} enviarVoto={enviarVoto} />
    </section>
  );
}

function rotuloOrigem(laudo: LaudoRX, carregando: boolean): string {
  if (laudo.descricao_origem !== "ia") {
    return `Montado automaticamente a partir das frases do laudo.${carregando ? " Redação por IA em andamento…" : ""}`;
  }
  const n = laudo.descricao_validacao?.removidas ?? 0;
  return `Redigido por IA, verificado${n > 0 ? ` (${n} ${n === 1 ? "frase sem lastro removida" : "frases sem lastro removidas"})` : ""}.`;
}

function Descricao({ laudo, texto, carregando }: { laudo: LaudoRX; texto: string; carregando: boolean }) {
  const [copiada, setCopiada] = useState(false);
  const copiar = async () => {
    try { await navigator.clipboard.writeText(texto); setCopiada(true); setTimeout(() => setCopiada(false), 2000); }
    catch { window.prompt("Copie a descrição:", texto); }
  };
  return (
    <section aria-label="Descrição completa" className="laudo-secao laudo-descricao">
      <h3>Descrição completa</h3>
      <p className="laudo-descricao-texto">{texto}</p>
      <p className="dim laudo-descricao-origem" role="status" data-origem={laudo.descricao_origem ?? "deterministico"}>{rotuloOrigem(laudo, carregando)}</p>
      <button type="button" className="btn small no-print" style={ALVO_TOQUE} onClick={copiar}>{copiada ? "Copiada" : "Copiar descrição"}</button>
    </section>
  );
}

/** Markdown do laudo (+ descrição, se o servidor não a incluiu) + comentários do médico (nunca persistidos nem enviados). */
function textoParaCopia(markdown: string, laudo: LaudoRX, comentarios: Record<string, string>): string {
  const desc = (laudo.descricao_completa ?? "").trim();
  if (desc && !markdown.includes(desc)) markdown = `${markdown.trimEnd()}\n\n## Descrição completa\n${desc}\n`;
  const extras = laudo.secoes
    .filter((s) => (comentarios[s.id] ?? "").trim())
    .map((s) => `- ${s.titulo}: ${comentarios[s.id].trim()}`);
  return extras.length ? `${markdown.trimEnd()}\n\nComentário do médico:\n${extras.join("\n")}\n` : markdown;
}

interface LaudoProps { laudo?: LaudoRX | null; studyId?: string; markdown?: string; enviarVoto?: boolean; ai?: boolean }

export default function LaudoEstruturado({ laudo: laudoBase, studyId, markdown: markdownBase = "", enviarVoto = ENVIAR_VOTO_PADRAO, ai = false }: LaudoProps) {
  const [comunicacao, setComunicacao] = useState(() => ler(ARMAZENAMENTO));
  const [comentarios, setComentarios] = useState<Record<string, string>>({});
  const [copiado, setCopiado] = useState(false);
  // Descrição redigida por IA (só fatos, verificada) chega à parte; falha ou recusa = fica a determinística.
  const [ia, setIa] = useState<{ laudo: LaudoRX; markdown: string } | null>(null);
  const [iaBusy, setIaBusy] = useState(false);
  const temDescricao = Boolean(laudoBase?.descricao_completa);
  useEffect(() => {
    setIa(null);
    if (!ai || !studyId || !temDescricao) { setIaBusy(false); return; }
    const ctl = new AbortController();
    setIaBusy(true);
    fetchDescricaoIA(studyId, API_BASE, { signal: ctl.signal })
      .then((r) => { if (!ctl.signal.aborted && r.laudo_rx) setIa({ laudo: r.laudo_rx, markdown: r.laudo_rx_markdown }); })
      .catch(() => undefined)
      .finally(() => { if (!ctl.signal.aborted) setIaBusy(false); });
    return () => ctl.abort();
  }, [ai, studyId, temDescricao]);
  if (!laudoBase) return null;
  const laudo: LaudoRX = ia?.laudo.descricao_completa
    ? { ...laudoBase, descricao_completa: ia.laudo.descricao_completa, descricao_origem: ia.laudo.descricao_origem,
        descricao_validacao: ia.laudo.descricao_validacao }
    : laudoBase;
  const markdown = ia?.laudo.descricao_completa ? ia.markdown : markdownBase;
  const descricao = (laudo.descricao_completa ?? "").trim();
  const copiar = async () => {
    const texto = textoParaCopia(markdown, laudo, comentarios);
    try { await navigator.clipboard.writeText(texto); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }
    catch { window.prompt("Copie o laudo:", texto); }
  };
  return (
    <div className="card laudo-estruturado" aria-label="Laudo estruturado">
      <h2>Laudo estruturado <span className="laudo-status">({laudo.status})</span></h2>
      {laudo.secoes.map((s) => (
        <Secao key={s.id} secao={s} studyId={studyId} enviarVoto={enviarVoto}
          comentario={comentarios[s.id] ?? ""} onComentario={(v) => setComentarios((c) => ({ ...c, [s.id]: v }))} />
      ))}
      {descricao && <Descricao laudo={laudo} texto={descricao} carregando={iaBusy} />}
      {markdown && (
        <button type="button" className="btn small no-print" style={ALVO_TOQUE} onClick={copiar}>{copiado ? "Copiado" : "Copiar laudo"}</button>
      )}
      <label className="laudo-comunicacao no-print">
        <span>Comunicação não rotineira</span>
        <textarea rows={2} value={comunicacao} aria-label="Comunicação não rotineira"
          onChange={(e) => { setComunicacao(e.target.value); guardar(ARMAZENAMENTO, e.target.value); }} />
        <small className="dim">Guardado somente neste navegador; não é enviado ao servidor.</small>
      </label>
      <p role="note" className="dim">Análise computacional: a decisão final é do médico.</p>
    </div>
  );
}
