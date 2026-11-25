import { describe, expect, it } from "vitest";
import css from "../styles/global.css?raw";

describe("alvo de toque do consentimento de imagem (R4, validado no Playwright)", () => {
  it("label do checkbox de consentimento tem altura mínima de 44px", () => {
    const m = css.match(/\.image-consent\s+\.switch\s*\{([^}]*)\}/);
    expect(m, "regra .image-consent .switch ausente").not.toBeNull();
    const h = m![1].match(/min-height:\s*(\d+)px/);
    expect(h, "min-height em px ausente").not.toBeNull();
    expect(Number(h![1])).toBeGreaterThanOrEqual(44);
  });

  it("switch 'Usar IA (Claude)' do cabeçalho tem altura mínima de 44px", () => {
    const m = css.match(/\.app-header\s+\.switch\s*\{([^}]*)\}/);
    expect(m, "regra .app-header .switch ausente").not.toBeNull();
    const h = m![1].match(/min-height:\s*(\d+)px/);
    expect(h, "min-height em px ausente").not.toBeNull();
    expect(Number(h![1])).toBeGreaterThanOrEqual(44);
  });
});
