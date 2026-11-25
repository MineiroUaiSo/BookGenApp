export interface Bounds { left: number; top: number; right: number; bottom: number }

export interface LabelPlacement {
  lines: string[];
  /** borda esquerda do texto (textAlign = "left"), em unidades de imagem */
  x: number;
  /** centro vertical da primeira linha (textBaseline = "middle") */
  y: number;
  lineHeight: number;
}

const PAD = 4;       // folga até a borda, em px de tela
const OFFSET_X = 5;  // distância horizontal do âncora
const OFFSET_Y = 6;  // elevação do texto sobre o âncora
const LINE_H = 14;   // altura de linha, em px de tela

function wrap(text: string, measure: (s: string) => number, maxW: number): string[] {
  const lines: string[] = [];
  let cur = "";
  for (const word of text.split(" ")) {
    const next = cur ? `${cur} ${word}` : word;
    if (cur && measure(next) > maxW) { lines.push(cur); cur = word; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

/** limita v a [lo, hi]; se o intervalo for inválido (hi < lo), vale lo. */
const clamp = (v: number, lo: number, hi: number) => (hi < lo ? lo : Math.min(Math.max(v, lo), hi));

/**
 * Posiciona o rótulo de uma medida dentro de `bounds` (viewport visível em
 * coordenadas de imagem). Prefere à direita do âncora; perto da borda direita
 * vai para a esquerda; texto mais largo que o viewport quebra em linhas.
 * `px` = unidades de imagem por pixel de tela (1 / escala).
 */
export function placeLabel(
  text: string, measure: (s: string) => number, anchor: [number, number], bounds: Bounds, px: number,
): LabelPlacement {
  const pad = PAD * px;
  const lineHeight = LINE_H * px;
  const maxW = Math.max(0, bounds.right - bounds.left - 2 * pad);
  const lines = measure(text) > maxW ? wrap(text, measure, maxW) : [text];
  const w = Math.max(...lines.map(measure));

  let x = anchor[0] + OFFSET_X * px;
  if (x + w > bounds.right - pad) x = anchor[0] - OFFSET_X * px - w;
  x = clamp(x, bounds.left + pad, bounds.right - pad - w);

  const blockH = lines.length * lineHeight;
  let y = anchor[1] - OFFSET_Y * px - (lines.length - 1) * lineHeight;
  y = clamp(y, bounds.top + pad + lineHeight / 2, bounds.bottom - pad - blockH + lineHeight / 2);
  return { lines, x, y, lineHeight };
}
