import { describe, expect, it } from "vitest";
import { placeLabel } from "../features/rx/labelLayout";

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
