import { describe, expect, it } from "vitest";
import { labelBox, placeLabel, type Bounds } from "../features/rx/labelLayout";

// medida fake: 6 unidades por caractere
const measure = (s: string) => s.length * 6;
const bounds = { left: 0, top: 0, right: 600, bottom: 600 };
const TEXT = "Diferença de altura das cúpulas (D − E, + = direita mais alta): 12.3%"; // 70 chars = 420

function box(p: ReturnType<typeof placeLabel>) {
  const w = Math.max(...p.lines.map(measure));
  return { l: p.x, r: p.x + w, t: p.y - p.lineHeight / 2, b: p.y + (p.lines.length - 1) * p.lineHeight + p.lineHeight / 2 };
}

describe("placeLabel (rótulo de medida dentro do viewport)", () => {
  it("mantém à direita do âncora quando cabe", () => {
    const p = placeLabel("curto: 5%", measure, [100, 300], bounds, 1);
    expect(p.lines).toEqual(["curto: 5%"]);
    expect(p.x).toBeCloseTo(105);
  });

  it("perto da borda direita: alinha o fim do texto ao âncora (vai para a esquerda)", () => {
    const p = placeLabel(TEXT, measure, [550, 300], bounds, 1);
    const b = box(p);
    expect(b.r).toBeLessThanOrEqual(600);
    expect(b.l).toBeGreaterThanOrEqual(0);
    expect(p.x).toBeLessThan(550);
  });

  it("perto da borda esquerda: não sai pela esquerda", () => {
    const p = placeLabel(TEXT, measure, [2, 300], bounds, 1);
    const b = box(p);
    expect(b.l).toBeGreaterThanOrEqual(0);
    expect(b.r).toBeLessThanOrEqual(600);
  });

  it("texto mais largo que o viewport quebra em linhas que cabem", () => {
    const narrow = { left: 0, top: 0, right: 200, bottom: 600 };
    const p = placeLabel(TEXT, measure, [100, 300], narrow, 1);
    expect(p.lines.length).toBeGreaterThan(1);
    expect(p.lines.join(" ")).toBe(TEXT);
    const b = box(p);
    expect(b.l).toBeGreaterThanOrEqual(0);
    expect(b.r).toBeLessThanOrEqual(200);
  });

  it("clampa verticalmente no topo e na base", () => {
    const top = box(placeLabel("x: 1", measure, [100, 0], bounds, 1));
    expect(top.t).toBeGreaterThanOrEqual(0);
    const bottom = box(placeLabel("x: 1", measure, [100, 600], bounds, 1));
    expect(bottom.b).toBeLessThanOrEqual(600);
  });

  it("respeita viewport recortado (zoom/pan): bounds não começam em 0", () => {
    const b2 = { left: 300, top: 100, right: 500, bottom: 400 };
    const p = placeLabel(TEXT, measure, [310, 200], b2, 1);
    const b = box(p);
    expect(b.l).toBeGreaterThanOrEqual(300);
    expect(b.r).toBeLessThanOrEqual(500);
  });

  it("escala com px (unidades de imagem): px=2 dobra margens", () => {
    const p = placeLabel("curto: 5%", (s) => s.length * 12, [100, 300], bounds, 2);
    expect(p.x).toBeCloseTo(110);
    expect(p.lineHeight).toBeCloseTo(2 * 14);
  });
});

const overlaps = (a: Bounds, b: Bounds) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

describe("placeLabel anti-colisão (ocupados)", () => {
  const vp390 = { left: 0, top: 0, right: 390, bottom: 600 };
  const ICT = "Índice cardiotorácico: 0.52";
  const DOMES = "Diferença de altura das cúpulas: 12.3%";

  it("duas âncoras a 4 px em 390 px: caixas sem interseção e dentro dos limites", () => {
    const first = placeLabel(DOMES, measure, [120, 300], vp390, 1);
    const occupied = [labelBox(first)];
    const second = placeLabel(ICT, measure, [120, 304], vp390, 1, occupied);
    const b2 = labelBox(second);
    expect(overlaps(b2, occupied[0])).toBe(false);
    expect(b2.left).toBeGreaterThanOrEqual(vp390.left);
    expect(b2.right).toBeLessThanOrEqual(vp390.right);
    expect(b2.top).toBeGreaterThanOrEqual(vp390.top);
    expect(b2.bottom).toBeLessThanOrEqual(vp390.bottom);
  });

  it("sem ocupados o resultado é idêntico ao comportamento anterior", () => {
    expect(placeLabel(ICT, measure, [120, 304], vp390, 1, [])).toEqual(placeLabel(ICT, measure, [120, 304], vp390, 1));
  });

  it("encadeia 3 rótulos na mesma âncora sem nenhuma interseção", () => {
    const occ: Bounds[] = [];
    for (const t of [DOMES, ICT, "Outra medida: 3%"]) {
      const p = placeLabel(t, measure, [120, 300], vp390, 1, occ);
      const b = labelBox(p);
      occ.forEach((o) => expect(overlaps(b, o)).toBe(false));
      occ.push(b);
    }
  });

  it("perto do topo desloca para baixo (não sai do viewport)", () => {
    const first = placeLabel("a: 1", measure, [100, 0], vp390, 1);
    const second = placeLabel("b: 2", measure, [100, 0], vp390, 1, [labelBox(first)]);
    const b = labelBox(second);
    expect(overlaps(b, labelBox(first))).toBe(false);
    expect(b.top).toBeGreaterThanOrEqual(0);
  });

  it("escala com px: deslocamento em múltiplos de lineHeight", () => {
    const first = placeLabel("a: 1", measure, [100, 300], vp390, 2);
    const second = placeLabel("b: 2", measure, [100, 300], vp390, 2, [labelBox(first)]);
    expect(Math.abs(second.y - first.y) % first.lineHeight).toBeCloseTo(0);
    expect(second.y).not.toBeCloseTo(first.y);
  });

  it("rótulo quebrado em várias linhas (viewport estreito) também não colide", () => {
    const narrow = { left: 0, top: 0, right: 200, bottom: 600 };
    const long = "Diferença de altura das cúpulas (D − E, + = direita mais alta): 12.3%";
    const first = placeLabel(long, measure, [100, 300], narrow, 1);
    expect(first.lines.length).toBeGreaterThan(2);
    const second = placeLabel("Índice cardiotorácico: 0.52", measure, [100, 302], narrow, 1, [labelBox(first)]);
    expect(overlaps(labelBox(second), labelBox(first))).toBe(false);
  });
});
