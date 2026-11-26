import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Recon3DViewer from "../Recon3DViewer";
import type { Recon3DResult } from "../../../types/api";

const result: Recon3DResult = {
  study_id: "s",
  gltf_url: "demo",
  meshes: [
    { key: "left_lung", label: "pulmão esquerdo", color: "#88f", volume_ml: 2000 },
    { key: "heart", label: "coração (estimativa, 1 incidência: ausente no perfil)", color: "#f44", volume_ml: 600 },
    { key: "spine", label: "coluna (estimativa, 1 incidência: ausente no perfil)", color: "#eee", volume_ml: 90 },
  ],
  method: "m",
  disclaimer: "d",
};

describe("Recon3DViewer: estruturas ausentes no perfil", () => {
  it("avisa quais estruturas são estimativa e marca cada uma", () => {
    render(<Recon3DViewer result={result} apiBase="/api" />);
    const aviso = screen.getByRole("status");
    expect(aviso.textContent).toContain("Estruturas ausentes no perfil: coração, coluna");
    expect(aviso.textContent).toContain("estimativa");
    expect(screen.getAllByText("estimativa")).toHaveLength(2);
    expect(screen.getByLabelText("Mostrar coração")).toBeTruthy();
  });
  it("sem estimativas não mostra o aviso", () => {
    render(<Recon3DViewer result={{ ...result, meshes: [result.meshes[0]] }} apiBase="/api" />);
    expect(screen.queryByRole("status")).toBeNull();
  });
  it("esconder e solo funcionam na lista", () => {
    render(<Recon3DViewer result={result} apiBase="/api" />);
    const cb = screen.getByLabelText("Mostrar pulmão esquerdo") as HTMLInputElement;
    fireEvent.click(cb);
    expect(cb.checked).toBe(false);
    const solo = screen.getAllByText("Solo")[1];
    fireEvent.click(solo);
    expect(solo.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Mostrar todas")).toBeTruthy();
  });
});

describe("Recon3DViewer: Destaque x Imagem real", () => {
  it("alternador visível, padrão destaque, e a escolha persiste na sessão", () => {
    sessionStorage.clear();
    const { unmount } = render(<Recon3DViewer result={result} apiBase="/api" />);
    expect(screen.getByRole("button", { name: "Destaque das estruturas" }).getAttribute("aria-pressed")).toBe("true");
    const real = screen.getByRole("button", { name: "Imagem real" }) as HTMLButtonElement;
    expect(real.disabled).toBe(true); // GLB demo não traz radiografia
    unmount();
    sessionStorage.setItem("medlens.recon3d.texmode", "real");
    render(<Recon3DViewer result={result} apiBase="/api" />);
    expect(screen.getByRole("button", { name: "Imagem real" }).getAttribute("aria-pressed")).toBe("true");
    sessionStorage.clear();
  });
});
