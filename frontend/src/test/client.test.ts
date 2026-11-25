import { describe, expect, it } from "vitest";
import { buildIngestFormData, health, renderUrl } from "../api/client";

describe("api client", () => {
  it("builds FormData with files and relative_paths", () => {
    const a = new File(["a"], "a.dcm"), b = new File(["b"], "b.dcm");
    const fd = buildIngestFormData([{ file: a, path: "pasta/a.dcm" }, { file: b }]);
    expect(fd.getAll("files")).toHaveLength(2);
    expect(fd.getAll("relative_paths")).toEqual(["pasta/a.dcm", "b.dcm"]);
  });
  it("falha de rede vira ApiError com mensagem útil citando a base", async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = (() => Promise.reject(new TypeError("Failed to fetch"))) as typeof fetch;
    try {
      await expect(health("http://localhost:8010/api")).rejects.toMatchObject({
        status: 0, message: expect.stringContaining("http://localhost:8010/api"),
      });
      await expect(health("http://localhost:8010/api")).rejects.toThrow(/backend está rodando/);
    } finally { globalThis.fetch = orig; }
  });
  it("builds render url with window/level", () => {
    expect(renderUrl("i1", 40, 400, "http://x/api")).toBe("http://x/api/instances/i1/render.png?wc=40&ww=400");
    expect(renderUrl("i1", undefined, undefined, "http://x/api")).toBe("http://x/api/instances/i1/render.png");
  });
});
