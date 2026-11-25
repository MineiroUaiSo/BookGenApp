export const DEV_API_BASE = "http://localhost:8000/api";

export interface ApiBaseInput {
  /** VITE_API_BASE, se definido (vazio é ignorado). */
  override?: string;
  /** import.meta.env.DEV: true só sob `vite` (porta 5173). */
  dev: boolean;
  origin?: string;
}

/**
 * Base da API: override explícito > localhost:8000 no dev server do vite >
 * '/api' relativo (frontend servido pelo próprio backend, em qualquer porta).
 */
export function resolveApiBase({ override, dev }: ApiBaseInput): string {
  if (override) return override;
  return dev ? DEV_API_BASE : "/api";
}

export function connectionErrorMessage(base: string, origin?: string): string {
  const full = base.startsWith("/") && origin ? `${origin}${base}` : base;
  return `Não foi possível conectar a ${full}; o backend está rodando?`;
}
