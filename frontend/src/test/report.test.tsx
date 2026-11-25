import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportPanel, { collectRefs, ppvLabel, reportToText } from "../features/report/ReportPanel";
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
  it("formats measured PPV with CI and source, or 'não medido'", () => {
    expect(ppvLabel({ ppv: 0.8, ic_inf: 0.74, ic_sup: 0.85, n: 123, fonte: "PTB-XL dev", prevalencia: 0.11 }))
      .toBe("VPP 0,80 [0,74–0,85] (PTB-XL dev, N=123; em base com 11% de prevalência)");
    expect(ppvLabel(undefined)).toBe("VPP não medido");
  });
  it("never shows a VPP without saying it depends on the base prevalence", () => {
    const sem = ppvLabel({ ppv: 0.847, ic_inf: 0.82, ic_sup: 0.87, n: 1002, fonte: "PTB-XL dev" });
    expect(sem).toMatch(/prevalência/);
    expect(sem).toMatch(/não informada/);
    expect(ppvLabel({ ppv: 0.5, ic_inf: 0.4, ic_sup: 0.6, n: 10, fonte: "x", prevalencia: 0.016 })).toMatch(/1,6% de prevalência/);
    expect(ppvLabel(undefined)).not.toMatch(/\d/);
  });
  it("shows the real reason when AI is unavailable (LGPD/refusal/provider error), not the generic no-key text", () => {
    const off = { ...ai, available: false, findings: [], differentials: [], disagreements_with_measurements: [],
      limitations: ["Envio à IA bloqueado pela barreira LGPD (CPF no payload); nada foi enviado."] };
    render(<ReportPanel findings={findings} ai={off} />);
    expect(screen.getByRole("status").textContent).toMatch(/Envio à IA bloqueado pela barreira LGPD/);
    expect(screen.queryByText(/sem chave de API/)).toBeNull();
  });
  it("keeps the generic text only when there is no limitation reason", () => {
    render(<ReportPanel findings={findings} ai={{ ...ai, available: false, limitations: [] }} />);
    expect(screen.getByRole("status").textContent).toMatch(/sem chave de API/);
  });
  it("differentials use confidence_display instead of a fake 0%", () => {
    const d = { ...ai.differentials[0], confidence: 0, confidence_display: "não quantificada" };
    render(<ReportPanel findings={[]} ai={{ ...ai, differentials: [d] }} />);
    expect(screen.getByText("não quantificada")).toBeTruthy();
    expect(screen.queryByText("0%")).toBeNull();
    expect(screen.getByRole("img", { name: /não quantificada/ })).toBeTruthy();
    expect(reportToText("L", [], { ...ai, differentials: [d] })).toContain("(confiança não quantificada)");
  });
  it("replaces 'Nenhuma discordância' by the automatic check wording and shows removed claims", () => {
    const a = { ...ai, disagreements_with_measurements: [], validation: { afirmacoes_removidas: 3 } };
    render(<ReportPanel findings={[]} ai={a} />);
    expect(screen.queryByText(/Nenhuma discordância identificada/)).toBeNull();
    expect(screen.getByText(/Conferência automática: números e tópicos verificados; não substitui leitura do traçado\./)).toBeTruthy();
    expect(screen.getByText(/3 frase\(s\) removida\(s\) pela barreira/)).toBeTruthy();
  });
  it("lists rx.model.* findings in a separate 'Escore do modelo (não medido)' block", () => {
    const m = { code: "rx.model.derrame", label: "Sugestivo de derrame (escore do modelo)", severity: "borderline" as const,
      evidence: [], references: [], confidence: 0.4, origin: "model" as const };
    render(<ReportPanel findings={[...findings, m]} ai={null} />);
    const h = screen.getByRole("heading", { name: "Escore do modelo (não medido)" });
    const box = h.parentElement as HTMLElement;
    expect(box.textContent).toContain("Sugestivo de derrame");
    expect(box.textContent).not.toContain("QRS alargado");
  });
  it("dedups refs and builds text", () => {
    expect(collectRefs(findings, ai).map((r) => r.id)).toEqual(["ref-1", "ref-2"]);
    const t = reportToText("Laudo", findings, ai);
    expect(t).toContain("ANÁLISE CRÍTICA");
    expect(t).toContain("BRE (confiança 70%)");
  });
});
