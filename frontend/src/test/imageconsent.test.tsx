import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ImageConsent from "../components/ImageConsent";
import { fetchAI } from "../api/client";

describe("ImageConsent (opt-in de envio da imagem à IA na nuvem)", () => {
  it("vem DESMARCADO e mostra aviso curto de LGPD", () => {
    render(<ImageConsent checked={false} onChange={() => {}} />);
    const box = screen.getByRole("checkbox", { name: /Enviar imagem à IA na nuvem/ }) as HTMLInputElement;
    expect(box.checked).toBe(false);
    expect(screen.getByRole("note").textContent).toMatch(/LGPD/);
    expect(screen.getByRole("note").textContent).toMatch(/medidas e regras/);
  });
  it("avisa o pai ao marcar", () => {
    const onChange = vi.fn();
    render(<ImageConsent checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Enviar imagem à IA na nuvem/ }));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("fetchAI envia o consentimento só para RX", () => {
  const corpo = async (kind: "ecg" | "rx", opts?: { sendImages?: boolean }) => {
    const calls: { url: string; body: string }[] = [];
    const orig = globalThis.fetch;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: String(init?.body) });
      return new Response(JSON.stringify({ available: true }), { status: 200 });
    }) as typeof fetch;
    try { await fetchAI(kind, "s1", "http://x/api", opts); } finally { globalThis.fetch = orig; }
    return calls[0];
  };
  it("RX sem consentimento manda send_images_to_ai=false", async () => {
    const c = await corpo("rx");
    expect(c.url).toBe("http://x/api/rx/s1/ai");
    expect(JSON.parse(c.body)).toEqual({ send_images_to_ai: false });
  });
  it("RX com consentimento manda true", async () => {
    expect(JSON.parse((await corpo("rx", { sendImages: true })).body)).toEqual({ send_images_to_ai: true });
  });
  it("ECG nunca leva o campo", async () => {
    expect(JSON.parse((await corpo("ecg", { sendImages: true })).body)).toEqual({});
  });
});
