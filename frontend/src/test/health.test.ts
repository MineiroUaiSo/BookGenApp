import { describe, expect, it } from "vitest";
import { healthWarnings } from "../App";

describe("healthWarnings", () => {
  it("is empty when every analysis component is ok", () => {
    expect(healthWarnings({ modelo_rx: "ok", analisador_rx: "ok", analisador_ecg: "ok" })).toEqual([]);
  });

  it("warns in Portuguese when the RX model is missing or broken", () => {
    expect(healthWarnings({ modelo_rx: "ausente" })[0]).toContain("Modelo de RX indisponível");
    expect(healthWarnings({ modelo_rx: "erro: ImportError: x" })).toHaveLength(1);
  });
});
