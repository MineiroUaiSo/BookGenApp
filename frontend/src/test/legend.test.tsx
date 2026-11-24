import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import Legend from "../features/rx/Legend";
import { structures } from "./fixtures";

function Host() {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  return (
    <Legend structures={structures} hidden={hidden} hoverKey={null} onHover={() => {}}
      onToggle={(k) => setHidden((h) => { const n = new Set(h); n.has(k) ? n.delete(k) : n.add(k); return n; })}
      onSetMany={(keys, v) => setHidden((h) => { const n = new Set(h); keys.forEach((k) => (v ? n.delete(k) : n.add(k))); return n; })} />
  );
}

describe("Legend", () => {
  it("groups by category and toggles", () => {
    render(<Host />);
    expect(screen.getByRole("group", { name: "Pulmões" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Ossos" })).toBeTruthy();
    const btn = screen.getByRole("button", { name: /Coração/ });
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(screen.getByText("Ocultar todas"));
    expect(screen.getByRole("button", { name: /Pulmão direito/ }).getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(screen.getByText("Mostrar todas"));
    expect(screen.getByRole("button", { name: /Pulmão direito/ }).getAttribute("aria-pressed")).toBe("true");
  });
});
