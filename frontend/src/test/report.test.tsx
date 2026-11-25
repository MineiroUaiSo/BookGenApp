import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportPanel, { collectRefs, reportToText } from "../features/report/ReportPanel";
import { ai, findings } from "./fixtures";

describe("ReportPanel", () => {
  it("renders all AI sections, dedups references and shows disclaimer", () => {
    render(<ReportPanel findings={findings} ai={ai} />);
    for (const h of ["Descrição minuciosa", "Achados", "Análise crítica", "Discordâncias com as medidas", "Limitações", "Referências"])
      expect(screen.getByRole("heading", { name: h })).toBeTruthy();
    expect(screen.getByText("QRS alargado")).toBeTruthy();
    expect(screen.getByText(/Visual sugere eixo normal/)).toBeTruthy();
    expect(screen.getByText("Rascunho — revisar por médico.")).toBeTruthy();
    expect(screen.getAllByText(/Goldberger/)).toHaveLength(1);
  });
  it("shows disclaimer and notice without AI", () => {
    render(<ReportPanel findings={findings} ai={null} />);
    expect(screen.getByRole("status").textContent).toMatch(/indisponível/);
    expect(screen.getByRole("note").textContent).toMatch(/revisão por médico/);
  });
  it("shows rules immediately and a loading notice while the AI text is generated", () => {
    render(<ReportPanel findings={findings} ai={null} aiLoading />);
    expect(screen.getByTestId("ai-loading").textContent).toMatch(/Gerando texto da IA/);
    expect(screen.getByText("QRS alargado")).toBeTruthy();
  });
  it("sends concordo/discordo feedback per rules finding", async () => {
    const calls: { url: string; body: string }[] = [];
    const orig = globalThis.fetch;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: String(init?.body) });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as typeof fetch;
    try {
      render(<ReportPanel findings={findings} ai={null} feedback={{ studyId: "s1", kind: "ecg" }} />);
      const btn = screen.getAllByRole("button", { name: "Discordo" })[0];
      btn.click();
      await new Promise((r) => setTimeout(r, 10));
      expect(calls[0].url).toMatch(/\/feedback\/s1$/);
      expect(JSON.parse(calls[0].body)).toMatchObject({ kind: "ecg", verdict: "disagree" });
    } finally { globalThis.fetch = orig; }
  });
  it("dedups refs and builds text", () => {
    expect(collectRefs(findings, ai).map((r) => r.id)).toEqual(["ref-1", "ref-2"]);
    const t = reportToText("Laudo", findings, ai);
    expect(t).toContain("ANÁLISE CRÍTICA");
    expect(t).toContain("BRE (confiança 70%)");
  });
});
