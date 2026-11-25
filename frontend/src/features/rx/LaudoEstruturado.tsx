import { useState } from "react";
import type { FraseLaudo, LaudoRX, NivelLaudo, SecaoLaudo } from "../../types/api";

const ROTULO_NIVEL: Record<NivelLaudo, string> = {
  MEDIDO: "MEDIDO", REGRA: "REGRA", SUGERIDO_MODELO: "SUGERIDO MODELO", NAO_AVALIADO: "NAO AVALIADO", QUALIDADE: "QUALIDADE",
};
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

function Parecer({ secao }: { secao: SecaoLaudo }) {
  const [voto, setVoto] = useState<"agree" | "disagree" | null>(null);
  return (
    <span className="feedback no-print" role="group" aria-label={`Parecer sobre ${secao.titulo}`}>
      <button type="button" className="btn small" aria-pressed={voto === "agree"} onClick={() => setVoto("agree")}>Concordo</button>{" "}
      <button type="button" className="btn small" aria-pressed={voto === "disagree"} onClick={() => setVoto("disagree")}>Discordo</button>
    </span>
  );
}

function Comentario({ id }: { id: string }) {
  const [v, setV] = useState("");
  return (
    <label className="laudo-comentario no-print">
      <span className="dim">Comentário do médico (região não avaliada)</span>
      <textarea value={v} rows={2} aria-label={`Comentário do médico ${id}`} onChange={(e) => setV(e.target.value)} />
    </label>
  );
}

function Secao({ secao }: { secao: SecaoLaudo }) {
  const modelo = secao.id === "sinais_modelo";
  const naoAvaliadas = secao.frases.filter((f) => f.nivel === "NAO_AVALIADO" && secao.id === "achados");
  return (
    <section aria-label={secao.titulo} className={`laudo-secao${modelo ? " laudo-modelo" : ""}`}>
      <h3>{secao.titulo}</h3>
      <ul>{secao.frases.map((f, i) => <Frase key={i} f={f} />)}</ul>
      {naoAvaliadas.length > 0 && <Comentario id={secao.id} />}
      <Parecer secao={secao} />
    </section>
  );
}

export default function LaudoEstruturado({ laudo }: { laudo?: LaudoRX | null }) {
  const [comunicacao, setComunicacao] = useState(() => ler(ARMAZENAMENTO));
  if (!laudo) return null;
  return (
    <div className="card laudo-estruturado" aria-label="Laudo estruturado">
      <h2>Laudo estruturado <span className="laudo-status">({laudo.status})</span></h2>
      {laudo.secoes.map((s) => <Secao key={s.id} secao={s} />)}
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
