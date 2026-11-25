import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import css from "../styles/global.css?raw";
import ReliabilityAlert, { isLowReliability } from "../components/ReliabilityAlert";

describe("ReliabilityAlert", () => {
  it("renders a visible role=alert with icon for low-reliability messages", () => {
    render(<ReliabilityAlert messages={["confiabilidade: baixa confiança (heurística)"]} />);
    const a = screen.getByRole("alert");
    expect(a.className).toContain("warning");
    expect(a.textContent).toMatch(/Baixa confiabilidade/);
  });
  it("is critical for out-of-scope images", () => {
    render(<ReliabilityAlert messages={["Fora de escopo: não é radiografia de tórax"]} />);
    expect(screen.getByRole("alert").className).toContain("critical");
  });
  it("renders nothing without messages and classifies texts", () => {
    const { container } = render(<ReliabilityAlert messages={[]} />);
    expect(container.firstChild).toBeNull();
    expect(isLowReliability("segmentação: PSPNet")).toBe(false);
    expect(isLowReliability("confiabilidade: baixa confiabilidade")).toBe(true);
  });
});

describe("touch targets (WCAG 2.5.5)", () => {
  const minHeight = (sel: string) => {
    const m = css.match(new RegExp(`^${sel.replace(/[.\\[\]]/g, "\\$&")}\\s*\\{[^}]*min-height:\\s*(\\d+)px`, "m"));
    return m ? Number(m[1]) : 0;
  };
  it(".btn.small and .tab have min-height >= 44px", () => {
    expect(minHeight(".btn.small")).toBeGreaterThanOrEqual(44);
    expect(minHeight(".tab")).toBeGreaterThanOrEqual(44);
  });
});
