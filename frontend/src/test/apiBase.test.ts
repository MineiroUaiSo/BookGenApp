import { describe, expect, it } from "vitest";
import { resolveApiBase, connectionErrorMessage } from "../api/apiBase";

describe("resolveApiBase", () => {
  it("override VITE_API_BASE vence tudo", () => {
    expect(resolveApiBase({ override: "http://x:1/api", dev: true, origin: "http://localhost:5173" })).toBe("http://x:1/api");
  });
  it("desenvolvimento (vite): mantém localhost:8000", () => {
    expect(resolveApiBase({ dev: true, origin: "http://localhost:5173" })).toBe("http://localhost:8000/api");
  });
  it("servido pelo backend (build): '/api' relativo, qualquer porta", () => {
    expect(resolveApiBase({ dev: false, origin: "http://localhost:8010" })).toBe("/api");
    expect(resolveApiBase({ dev: false, origin: "http://localhost:8000" })).toBe("/api");
  });
  it("override vazio é ignorado", () => {
    expect(resolveApiBase({ override: "", dev: false })).toBe("/api");
  });
});

describe("connectionErrorMessage", () => {
  it("cita a base e pergunta se o backend está rodando", () => {
    const m = connectionErrorMessage("http://localhost:8000/api");
    expect(m).toContain("http://localhost:8000/api");
    expect(m).toMatch(/backend está rodando/);
  });
  it("base relativa é resolvida contra a origem", () => {
    expect(connectionErrorMessage("/api", "http://localhost:8010")).toContain("http://localhost:8010/api");
  });
});
