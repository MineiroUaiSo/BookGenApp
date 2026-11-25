import { describe, expect, it, vi } from "vitest";
import { cutoutMask, maskLayerPlan } from "../features/rx/maskUtils";

const S = (key: string, category: string) => ({ key, category });

describe("maskLayerPlan", () => {
  it("desenha o coração por cima e recorta o coração dos pulmões", () => {
    const plan = maskLayerPlan([S("heart", "heart_vessels"), S("right_lung", "lung"), S("left_lung", "lung"), S("spine", "bone")]);
    expect(plan.map((l) => l.key)).toEqual(["right_lung", "left_lung", "spine", "heart"]);
    expect(plan.find((l) => l.key === "right_lung")?.cutBy).toEqual(["heart"]);
    expect(plan.find((l) => l.key === "left_lung")?.cutBy).toEqual(["heart"]);
    expect(plan.find((l) => l.key === "heart")?.cutBy).toEqual([]);
    expect(plan.find((l) => l.key === "spine")?.cutBy).toEqual([]);
  });

  it("sem coração, nada é recortado e a ordem se mantém", () => {
    const plan = maskLayerPlan([S("right_lung", "lung"), S("left_lung", "lung")]);
    expect(plan).toEqual([{ key: "right_lung", cutBy: [] }, { key: "left_lung", cutBy: [] }]);
  });
});

describe("cutoutMask", () => {
  it("copia a máscara e remove os recortadores com destination-out, sem alterar a original", () => {
    const calls: string[] = [];
    const ctx = {
      globalCompositeOperation: "source-over",
      drawImage: vi.fn(function (this: { globalCompositeOperation: string }) { calls.push(this.globalCompositeOperation); }),
    };
    const fake = { width: 0, height: 0, getContext: () => ctx } as unknown as HTMLCanvasElement;
    vi.spyOn(document, "createElement").mockReturnValueOnce(fake);
    const lung = { width: 10, height: 8 } as HTMLCanvasElement;
    const heart = { width: 10, height: 8 } as HTMLCanvasElement;
    const out = cutoutMask(lung, [heart]);
    expect(out).toBe(fake);
    expect(out).not.toBe(lung);
    expect(calls).toEqual(["source-over", "destination-out"]);
    expect(ctx.drawImage).toHaveBeenNthCalledWith(1, lung, 0, 0);
    expect(ctx.drawImage).toHaveBeenNthCalledWith(2, heart, 0, 0);
    expect(ctx.globalCompositeOperation).toBe("source-over");
  });

  it("sem recortadores devolve a própria máscara", () => {
    const lung = { width: 1, height: 1 } as HTMLCanvasElement;
    expect(cutoutMask(lung, [])).toBe(lung);
  });
});
