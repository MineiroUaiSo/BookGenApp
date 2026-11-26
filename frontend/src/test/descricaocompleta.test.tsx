import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReportPanel, { reportToText } from "../features/report/ReportPanel";
import type { AIReport } from "../types/api";
import { ai, findings } from "./fixtures";

const TEXTO = "Esta descrição foi montada por regras automáticas. Quanto ao ritmo, o ritmo sinusal regular tem 72 bpm. Impressão: pelas regras automáticas, o traçado está dentro dos limites da normalidade.";
const comDescricao = (over: Partial<AIReport> = {}): AIReport => ({
  ...ai, descricao_completa: TEXTO, descricao_origem: "deterministico", descricao_validacao: 0, ...over,
});

afterEach(() => vi.restoreAllMocks());

describe("Descrição completa do ECG", () => {
  it("mostra o bloco 'Descrição completa' em parágrafo único no fim, antes do aviso", () => {
    render(<ReportPanel title="Laudo de ECG" findings={findings} ai={comDescricao()} />);
    const bloco = screen.getByTestId("descricao-completa");
    expect(screen.getByRole("heading", { name: "Descrição completa" })).toBeTruthy();
    expect(bloco.querySelectorAll("p.desc-par")).toHaveLength(1);
    expect(bloco.textContent).toContain(TEXTO);
    const painel = bloco.closest("article")!;
    const filhos = Array.from(painel.children);
    expect(filhos.indexOf(bloco)).toBeGreaterThan(filhos.findIndex((el) => el.textContent?.startsWith("Referências")));
    expect(filhos.indexOf(bloco)).toBeLessThan(filhos.findIndex((el) => el.getAttribute("role") === "note"));
  });

  it("marca a origem: montado automaticamente x redigido por IA, verificado", () => {
    const { rerender } = render(<ReportPanel title="Laudo de ECG" findings={findings} ai={comDescricao()} />);
    expect(screen.getByTestId("descricao-origem").textContent).toMatch(/Montado automaticamente/);
    rerender(<ReportPanel title="Laudo de ECG" findings={findings} ai={comDescricao({ descricao_origem: "ia", descricao_validacao: 2 })} />);
    expect(screen.getByTestId("descricao-origem").textContent).toMatch(/Redigido por IA, verificado/);
    expect(screen.getByTestId("descricao-origem").textContent).toMatch(/2 frases removidas/);
  });

  it("aparece mesmo com a IA indisponível (a base é determinística)", () => {
    const off: AIReport = { ...comDescricao(), available: false, limitations: ["sem chave"] };
    render(<ReportPanel title="Laudo de ECG" findings={findings} ai={off} />);
    expect(screen.getByTestId("descricao-completa").textContent).toContain("ritmo sinusal regular");
  });

  it("não mostra o bloco sem descrição (RX ou relatório antigo)", () => {
    render(<ReportPanel title="Laudo de RX" findings={findings} ai={ai} />);
    expect(screen.queryByTestId("descricao-completa")).toBeNull();
  });

  it("'Copiar descrição' copia só o parágrafo", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<ReportPanel title="Laudo de ECG" findings={findings} ai={comDescricao()} />);
    fireEvent.click(screen.getByRole("button", { name: "Copiar descrição" }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith(TEXTO);
  });

  it("entra no 'Copiar como texto' e fica fora da impressão só no botão", () => {
    expect(reportToText("Laudo de ECG", findings, comDescricao())).toContain(`DESCRIÇÃO COMPLETA\n${TEXTO}`);
    render(<ReportPanel title="Laudo de ECG" findings={findings} ai={comDescricao()} />);
    expect(screen.getByTestId("descricao-completa").classList.contains("no-print")).toBe(false);
    expect(screen.getByRole("button", { name: "Copiar descrição" }).closest(".no-print")).not.toBeNull();
  });
});
