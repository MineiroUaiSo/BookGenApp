export type AlertLevel = "warning" | "critical";

const LOW_RE = /baixa confiabilidade|baixa confian|confiabilidade|fora de escopo|incerta|ruído|ruido|indisponível|não avaliad/i;

/** True when a quality/warning text signals that the result must not be trusted as-is. */
export function isLowReliability(text: string): boolean { return LOW_RE.test(text); }

export function alertLevel(text: string): AlertLevel {
  return /fora de escopo|incerta|em branco/i.test(text) ? "critical" : "warning";
}

interface Props { messages: string[]; title?: string }

/** Visible alert (colour + icon + role="alert") for low-reliability / out-of-scope messages. */
export default function ReliabilityAlert({ messages, title = "Baixa confiabilidade" }: Props) {
  if (!messages.length) return null;
  const level: AlertLevel = messages.some((m) => alertLevel(m) === "critical") ? "critical" : "warning";
  return (
    <div className={`reliability-alert ${level}`} role="alert" data-testid="reliability-alert">
      <span className="ra-icon" aria-hidden="true">{level === "critical" ? "⛔" : "⚠"}</span>
      <div>
        <strong>{level === "critical" ? "Atenção — resultado não confiável" : title}</strong>
        <ul>{messages.map((m, i) => <li key={i}>{m}</li>)}</ul>
      </div>
    </div>
  );
}
