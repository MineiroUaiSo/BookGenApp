import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import LaudoEstruturado from "../features/rx/LaudoEstruturado";
import type { LaudoRX } from "../types/api";

const laudo: LaudoRX = {
  versao: "rx_laudo/v1", status: "rascunho",
  secoes: [
    { id: "achados", titulo: "Achados por região", frases: [
      { secao: "achados", texto: "Índice cardiotorácico medido 0,46 (limite clássico 0,50 em PA).", fatos: ["F1"], fontes: ["S6"], nivel: "MEDIDO" },
      { secao: "achados", texto: "Pleura: não avaliado nesta análise automática.", fatos: [], fontes: [], nivel: "NAO_AVALIADO" },
    ] },
    { id: "sinais_modelo", titulo: "Sinais do modelo auxiliar", frases: [
      { secao: "sinais_modelo", texto: "Modelo auxiliar: possível derrame pleural (probabilidade calibrada ≈ 0,70); escore de modelo; não confirma nem afasta.", fatos: ["F2"], fontes: ["S5"], nivel: "SUGERIDO_MODELO" },
    ] },
    { id: "impressao", titulo: "Impressão", frases: [
      { secao: "impressao", texto: "Pneumotórax, pneumoperitônio e posição de tubos/cateteres NÃO são avaliados por esta análise: revisar a imagem.", fatos: [], fontes: [], nivel: "NAO_AVALIADO" },
    ] },
  ],
};

describe("LaudoEstruturado", () => {
  it("mostra rascunho, nível por frase e fontes", () => {
    render(<LaudoEstruturado laudo={laudo} />);
    expect(screen.getByText(/rascunho/i)).toBeTruthy();
    expect(screen.getByText("MEDIDO")).toBeTruthy();
    expect(screen.getAllByText("NAO AVALIADO").length).toBe(2);
    expect(screen.getByTitle("Fonte S6")).toBeTruthy();
  });
  it("sinais do modelo ficam em caixa separada da Impressão", () => {
    render(<LaudoEstruturado laudo={laudo} />);
    const caixa = screen.getByRole("region", { name: "Sinais do modelo auxiliar" });
    expect(caixa.textContent).toMatch(/possível derrame pleural/);
    expect(screen.getByRole("region", { name: "Impressão" }).textContent).not.toMatch(/derrame/);
  });
  it("tem Concordo/Discordo por seção e comentário só para frase não avaliada", () => {
    render(<LaudoEstruturado laudo={laudo} />);
    expect(screen.getAllByRole("button", { name: /Concordo/ })).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: /Discordo/ })).toHaveLength(3);
    const campo = screen.getAllByLabelText(/Comentário do médico/)[0] as HTMLTextAreaElement;
    fireEvent.change(campo, { target: { value: "campos sem alteração visual" } });
    expect(campo.value).toMatch(/campos/);
  });
  it("nota de IA e campo local de comunicação não rotineira", () => {
    render(<LaudoEstruturado laudo={laudo} />);
    expect(screen.getByText(/decisão final é do médico/i)).toBeTruthy();
    expect(screen.getByLabelText(/Comunicação não rotineira/)).toBeTruthy();
    expect(screen.getByText(/somente neste navegador/i)).toBeTruthy();
  });
  it("sem laudo não renderiza nada", () => {
    const { container } = render(<LaudoEstruturado laudo={null} />);
    expect(container.textContent).toBe("");
  });

  describe("voto e cópia", () => {
    const orig = globalThis.fetch;
    // Node 26 + jsdom: localStorage global pode faltar; usa armazenamento em memória isolado por teste.
    beforeEach(() => {
      const m = new Map<string, string>();
      vi.stubGlobal("localStorage", {
        getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); },
        removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
      });
    });
    afterEach(() => { globalThis.fetch = orig; vi.unstubAllGlobals(); });

    it("voto persiste ao remontar, por estudo e seção", () => {
      const a = render(<LaudoEstruturado laudo={laudo} studyId="s1" />);
      fireEvent.click(screen.getAllByRole("button", { name: /Discordo/ })[0]);
      a.unmount();
      render(<LaudoEstruturado laudo={laudo} studyId="s1" />);
      expect(screen.getAllByRole("button", { name: /Discordo/ })[0].getAttribute("aria-pressed")).toBe("true");
      expect(screen.getAllByRole("button", { name: /Concordo/ })[0].getAttribute("aria-pressed")).toBe("false");
      expect(screen.getAllByRole("button", { name: /Discordo/ })[1].getAttribute("aria-pressed")).toBe("false");
    });
    it("voto de outro estudo não vaza", () => {
      const a = render(<LaudoEstruturado laudo={laudo} studyId="s1" />);
      fireEvent.click(screen.getAllByRole("button", { name: /Concordo/ })[0]);
      a.unmount();
      render(<LaudoEstruturado laudo={laudo} studyId="s2" />);
      expect(screen.getAllByRole("button", { name: /Concordo/ })[0].getAttribute("aria-pressed")).toBe("false");
    });
    it("por padrão o voto não é enviado ao servidor (decisão D2 pendente)", () => {
      const f = vi.fn(); globalThis.fetch = f as unknown as typeof fetch;
      render(<LaudoEstruturado laudo={laudo} studyId="s1" />);
      fireEvent.click(screen.getAllByRole("button", { name: /Concordo/ })[0]);
      expect(f).not.toHaveBeenCalled();
    });
    it("com envio ligado, o corpo é exatamente kind/code/verdict", async () => {
      const f = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
      globalThis.fetch = f as unknown as typeof fetch;
      render(<LaudoEstruturado laudo={laudo} studyId="s1" enviarVoto />);
      fireEvent.click(screen.getAllByRole("button", { name: /Discordo/ })[0]);
      await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
      const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
      expect(url).toMatch(/\/feedback\/s1$/);
      expect(JSON.parse(String(init.body))).toEqual({ kind: "rx", code: "rx.laudo.achados", verdict: "disagree" });
    });
    it("falha de rede no envio não quebra a UI nem desfaz o voto local", async () => {
      globalThis.fetch = vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))) as unknown as typeof fetch;
      render(<LaudoEstruturado laudo={laudo} studyId="s1" enviarVoto />);
      fireEvent.click(screen.getAllByRole("button", { name: /Concordo/ })[0]);
      await new Promise((r) => setTimeout(r, 0));
      expect(screen.getAllByRole("button", { name: /Concordo/ })[0].getAttribute("aria-pressed")).toBe("true");
    });
    it("Copiar laudo copia o markdown e acrescenta os comentários do médico", async () => {
      const writeText = vi.fn(async () => {});
      Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
      render(<LaudoEstruturado laudo={laudo} studyId="s1" markdown={"# Laudo RX\n\nTexto."} />);
      fireEvent.change(screen.getAllByLabelText(/Comentário do médico/)[0], { target: { value: "campos sem alteração visual" } });
      fireEvent.click(screen.getByRole("button", { name: /Copiar laudo/ }));
      await waitFor(() => expect(writeText).toHaveBeenCalled());
      const texto = (writeText.mock.calls[0] as unknown as [string])[0];
      expect(texto).toContain("# Laudo RX");
      expect(texto).toContain("Comentário do médico");
      expect(texto).toContain("campos sem alteração visual");
    });
  });
});
