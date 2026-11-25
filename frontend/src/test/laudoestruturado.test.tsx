import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
});
