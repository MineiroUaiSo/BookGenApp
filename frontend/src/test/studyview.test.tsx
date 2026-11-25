import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ai as aiFixture } from "./fixtures";
import type { RXAnalysis } from "../types/api";
import type { AnalysisResult } from "../features/upload/UploadPage";

const api = vi.hoisted(() => ({
  analyzeRX: vi.fn(), fetchAI: vi.fn(), recon3d: vi.fn(), sendFeedback: vi.fn(), fetchRulePpv: vi.fn(),
}));
vi.mock("../api/client", () => ({ ...api, API_BASE: "/api", modelUrl: () => "", renderUrl: () => "" }));
vi.mock("../features/rx/RXViewer", () => ({
  default: (p: { onRegionConfirm: (id: string, r: string) => void; analysis: RXAnalysis }) => {
    if ((p.analysis as { boom?: boolean }).boom) throw new Error("falha simulada do visualizador");
    return <button onClick={() => p.onRegionConfirm("i1", "chest")}>confirmar região</button>;
  },
}));

import StudyView from "../features/StudyView";

const rxBase = (extra: Partial<RXAnalysis> = {}): RXAnalysis => ({
  study_id: "s1", images: [], findings: [], recon3d_available: false, warnings: [], ...extra,
});
const result = (rx: RXAnalysis): AnalysisResult => ({
  kind: "RX", rx, study: { study_id: "s1", series: [], created_at: "2026-01-01" },
} as unknown as AnalysisResult);

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  api.fetchAI.mockResolvedValue({ available: false, limitations: [] });
  api.fetchRulePpv.mockResolvedValue({ _meta: {}, codes: {} });
});

describe("StudyView", () => {
  it("erro de reanálise aparece com role=alert mesmo sem 3D disponível", async () => {
    api.analyzeRX.mockRejectedValue(new Error("1 incidência apenas"));
    render(<StudyView result={result(rxBase())} ai={false} onBack={() => {}} />);
    fireEvent.click(screen.getByText("confirmar região"));
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/Falha ao reanalisar: 1 incidência apenas/);
  });

  it("botão 3D usa a análise reanalisada", async () => {
    api.analyzeRX.mockResolvedValue(rxBase({ recon3d_available: true }));
    render(<StudyView result={result(rxBase({ recon3d_available: false }))} ai={false} onBack={() => {}} />);
    expect(screen.queryByRole("button", { name: /Reconstrução 3D/ })).toBeNull();
    fireEvent.click(screen.getByText("confirmar região"));
    expect(await screen.findByRole("button", { name: /Reconstrução 3D/ })).toBeTruthy();
  });

  it("aborta a chamada /ai anterior; em StrictMode só a última conclui", async () => {
    const sinais: AbortSignal[] = [];
    api.fetchAI.mockImplementation((_k: string, _id: string, _b: string, o: { signal?: AbortSignal }) => {
      if (o.signal) sinais.push(o.signal);
      return Promise.resolve(aiFixture);
    });
    render(<StrictMode><StudyView result={result(rxBase())} ai onBack={() => {}} /></StrictMode>);
    await waitFor(() => expect(api.fetchAI).toHaveBeenCalledTimes(2));
    expect(sinais).toHaveLength(2);
    expect(sinais[0].aborted).toBe(true);
    expect(sinais[1].aborted).toBe(false);
  });

  it("falha do visualizador não derruba a página (ErrorBoundary)", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<StudyView result={result({ ...rxBase(), boom: true } as RXAnalysis)} ai={false} onBack={() => {}} />);
    expect((await screen.findAllByRole("alert")).some((a) => /Não foi possível exibir/.test(a.textContent ?? ""))).toBe(true);
    expect(screen.getByRole("button", { name: /Novo estudo/ })).toBeTruthy();
    spy.mockRestore();
  });
});
