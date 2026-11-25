"""Baixa casos-ouro de RX de tórax do Wikimedia Commons (spec RX-LAUDO-CONFIAVEL §4.2) para `data/gold_rx/` (fora do git).
Só baixa arquivo cuja licença, lida na API do Commons, seja CC0 ou domínio público. Sem dado de paciente.
Uso: python -m bench.rx_gold_fetch [--dest data/gold_rx]"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
TITULOS = (
    "File:Cardiothoracic ratio.jpg",
    "File:Chest radiograph of a lung with Kerley B lines.jpg",
    "File:Chest radiograph with signs of congestive heart failure - annotated.jpg",
    "File:Chest Xray PA 3-8-2010 inverted.png",
    "File:Air crescent sign.jpg",
    "File:6077 lores.jpg",
)
_LIVRE = re.compile(r"^(cc0\b.*|cc[- ]?zero.*|public domain.*|pd\b.*|pdm\b.*)$", re.IGNORECASE)
_UA = {"User-Agent": "gold-rx-fetch/1.0 (research; contact via repository)"}


def licenca_livre(nome_licenca: str | None) -> bool:
    """True só para CC0 / domínio público (a licença vem da API; vazio ou CC-BY etc. = False)."""
    return bool(nome_licenca and _LIVRE.match(nome_licenca.strip()))


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=60) as r:
        return r.read()


def consultar(titulo: str) -> dict:
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
         "titles": titulo}
    pagina = next(iter(json.loads(_get(API + "?" + urllib.parse.urlencode(q)))["query"]["pages"].values()))
    info = (pagina.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    return {"titulo": titulo, "url": info.get("url"), "mime": info.get("mime"),
            "licenca": (meta.get("LicenseShortName") or {}).get("value"),
            "autor": re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", ""))[:120],
            "pagina": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(titulo.replace(" ", "_"))}


def baixar(dest: Path, titulos=TITULOS) -> list[dict]:
    dest.mkdir(parents=True, exist_ok=True)
    manifesto = []
    for t in titulos:
        try:
            m = consultar(t)
        except Exception as e:  # rede/API: registra e segue
            manifesto.append({"titulo": t, "baixado": False, "motivo": f"consulta falhou: {e}"})
            continue
        if not m["url"] or not licenca_livre(m["licenca"]):
            manifesto.append({**m, "baixado": False, "motivo": f"licença não livre: {m['licenca']}"})
            continue
        arq = dest / re.sub(r"[^A-Za-z0-9._-]+", "_", t.removeprefix("File:"))
        arq.write_bytes(_get(m["url"]))
        manifesto.append({**m, "baixado": True, "arquivo": arq.name})
    (dest / "manifest.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(Path(__file__).resolve().parents[2] / "data" / "gold_rx"))
    a = ap.parse_args(argv)
    for m in baixar(Path(a.dest)):
        print(("OK  " if m.get("baixado") else "PULA"), m["titulo"], "|", m.get("licenca"), m.get("motivo", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
