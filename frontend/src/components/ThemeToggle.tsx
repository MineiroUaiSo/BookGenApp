import { useEffect, useState } from "react";

type Theme = "dark" | "light";
function initial(): Theme {
  try {
    const s = localStorage.getItem("medlens-theme");
    if (s === "dark" || s === "light") return s;
  } catch { /* ignore */ }
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("medlens-theme", theme); } catch { /* ignore */ }
  }, [theme]);
  return (
    <button className="btn small" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}>
      {theme === "dark" ? "Tema claro" : "Tema escuro"}
    </button>
  );
}
