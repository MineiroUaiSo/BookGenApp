import { describe, expect, it } from "vitest";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import {
  advanceTime, buildGeometry, mmToMs, mmToPx, msToMm, msToPx, mvToMm, phasesAt, pxToMs, rrToBpm,
  inRange, projection, polarityLabel, snapToNearest, GLOBAL_ROWS, PX_PER_MM_BASE,
} from "../ecgMath";
import { useConductionPlayer } from "../useConductionPlayer";
import { sampleAnalysis } from "../__fixtures__/sampleAnalysis";
import ECGWorkspace from "../ECGWorkspace";

describe("ecgMath", () => {
  it("converte ms <-> mm <-> px", () => {
    expect(msToMm(1000, 25)).toBe(25);
    expect(msToMm(200, 25)).toBe(5);
    expect(mmToMs(5, 25)).toBe(200);
    expect(msToMm(200, 50)).toBe(10);
    expect(mvToMm(1, 10)).toBe(10);
    expect(mmToPx(5, 4)).toBe(20);
    expect(msToPx(200, 25, 4)).toBe(20);
    expect(pxToMs(20, 25, 4)).toBeCloseTo(200);
    expect(rrToBpm(1000)).toBe(60);
    expect(rrToBpm(800)).toBeCloseTo(75);
  });
  it("geometria: 10 s a 25 mm/s = 250 mm", () => {
    const g = buildGeometry({ layout: "3x4+1", durationMs: 10000, speed: 25, gain: 10, pxPerMm: 4 });
    expect(g.panels).toHaveLength(13);
    expect(g.panels[12].rhythm).toBe(true);
    expect(g.panels[12].w).toBeCloseTo(1000);
    expect(g.panels[0].w).toBeCloseTo(250);
    expect(buildGeometry({ layout: "12x1", durationMs: 10000, speed: 25, gain: 10, pxPerMm: 4 }).panels).toHaveLength(12);
    expect(buildGeometry({ layout: "6x2", durationMs: 10000, speed: 25, gain: 10, pxPerMm: 4 }).panels[6].t0).toBe(5000);
  });
  it("faixas, projeção e snap", () => {
    expect(inRange(300, { max: 450, label: "" })).toBe(true);
    expect(inRange(500, { max: 450, label: "" })).toBe(false);
    expect(projection(60, "II")).toBeCloseTo(1);
    expect(polarityLabel(projection(60, "aVR")!)).toBe("negativa");
    expect(polarityLabel(projection(60, "aVL")!)).toBe("isobifásica");
    expect(snapToNearest(103, [100, 200], 5)).toEqual({ value: 100, snapped: true });
    expect(snapToNearest(150, [100, 200], 5).snapped).toBe(false);
  });
});

describe("condução", () => {
  const ph = sampleAnalysis.conduction;
  it("fase ativa no tempo t", () => {
    expect(phasesAt(ph, 10).map((p) => p.structure)).toEqual(["SA"]);
    expect(phasesAt(ph, 60).map((p) => p.structure)).toEqual(["atria"]);
    expect(phasesAt(ph, 120).map((p) => p.structure)).toEqual(["AV_node"]);
    expect(phasesAt(ph, 155).map((p) => p.structure)).toEqual(["RBB", "LBB"]);
    expect(phasesAt(ph, 200).map((p) => p.structure)).toEqual(["ventricles_depol"]);
    expect(phasesAt(ph, 400).map((p) => p.structure)).toEqual(["ventricles_repol"]);
    expect(phasesAt(ph, 900)).toEqual([]);
  });
  it("advanceTime respeita velocidade e loop", () => {
    expect(advanceTime(0, 100, 0.5, 0, 500, true).t).toBe(50);
    expect(advanceTime(480, 100, 1, 0, 500, true).t).toBe(80);
    expect(advanceTime(480, 100, 1, 0, 500, false)).toEqual({ t: 500, ended: true });
  });
  it("hook: seek altera fase ativa", () => {
    const { result } = renderHook(() => useConductionPlayer(ph));
    expect(result.current.total).toBe(515);
    act(() => result.current.seek(60));
    expect(result.current.active[0].structure).toBe("atria");
    act(() => result.current.seek(10000));
    expect(result.current.t).toBe(515);
  });
});

describe("ECGWorkspace", () => {
  it("toggles mostram/escondem sobreposições de onda", () => {
    const { container } = render(<ECGWorkspace analysis={sampleAnalysis} />);
    expect(container.querySelectorAll("rect.wave-P").length).toBe(0);
    fireEvent.click(screen.getByLabelText("destacar P"));
    expect(container.querySelectorAll("rect.wave-P").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("rect.wave-T").length).toBe(0);
    fireEvent.click(screen.getByLabelText("destacar P"));
    expect(container.querySelectorAll("rect.wave-P").length).toBe(0);
    fireEvent.click(screen.getByText("Todos"));
    expect(container.querySelectorAll("rect.wave-T").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".interval-PR").length).toBeGreaterThan(0);
  });
  it("grade em escala verdadeira e pulso de calibração", () => {
    const { getByTestId, getAllByTestId } = render(<ECGWorkspace analysis={sampleAnalysis} />);
    expect(getByTestId("ecg-grid")).toBeTruthy();
    expect(getAllByTestId("calibration").length).toBe(4);
    expect(PX_PER_MM_BASE).toBeCloseTo(3.78, 1);
  });
  it("tabela global marca valores fora da faixa", () => {
    const a = { ...sampleAnalysis, global_measurements: { ...sampleAnalysis.global_measurements, qrs_ms: 150 } };
    render(<ECGWorkspace analysis={a} />);
    fireEvent.click(screen.getByRole("tab", { name: "Medidas" }));
    expect(document.querySelector('tr[data-key="qrs_ms"] td[data-out="1"]')).toBeTruthy();
    expect(document.querySelector('tr[data-key="pr_ms"] td[data-out="1"]')).toBeNull();
    expect(GLOBAL_ROWS.length).toBeGreaterThan(10);
  });
  it("painel de condução ilumina a estrutura ativa", () => {
    render(<ECGWorkspace analysis={sampleAnalysis} />);
    fireEvent.click(screen.getByRole("tab", { name: "Condução cardíaca" }));
    fireEvent.change(screen.getByLabelText("Posição no batimento"), { target: { value: "60" } });
    expect(document.querySelector('[data-structure="atria"][data-active="1"]')).toBeTruthy();
    expect(document.querySelector('[data-structure="His"][data-active="1"]')).toBeNull();
    fireEvent.click(screen.getByText("Isolar estrutura"));
    fireEvent.click(screen.getByRole("button", { name: "Nó AV" }));
    expect(document.querySelector('[data-structure="AV_node"][data-active="1"]')).toBeTruthy();
    expect(document.querySelectorAll('[data-testid="phase-band"]').length).toBe(12);
  });
});
