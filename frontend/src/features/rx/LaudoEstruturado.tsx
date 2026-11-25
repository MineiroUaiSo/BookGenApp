import { useState } from "react";
import { sendFeedback } from "../../api/client";
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

/** Markdown do laudo + comentários do médico (nunca persistidos nem enviados). */
function textoParaCopia(markdown: string, laudo: LaudoRX, comentarios: Record<string, string>): string {
  const extras = laudo.secoes
    .filter((s) => (comentarios[s.id] ?? "").trim())
    .map((s) => `- ${s.titulo}: ${comentarios[s.id].trim()}`);
  return extras.length ? `${markdown.trimEnd()}\n\nComentário do médico:\n${extras.join("\n")}\n` : markdown;
}

interface LaudoProps { laudo?: LaudoRX | null; studyId?: string; markdown?: string; enviarVoto?: boolean }

export default function LaudoEstruturado({ laudo, studyId, markdown = "", enviarVoto = ENVIAR_VOTO_PADRAO }: LaudoProps) {
  const [comunicacao, setComunicacao] = useState(() => ler(ARMAZENAMENTO));
  const [comentarios, setComentarios] = useState<Record<string, string>>({});
  const [copiado, setCopiado] = useState(false);
  if (!laudo) return null;
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
