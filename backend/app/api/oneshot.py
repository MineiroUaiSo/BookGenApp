"""POST /api/oneshot/{ecg|rx}: análise sem estado, em modo pediátrico, sem IA.

Fluxo: autentica (Bearer, tempo constante) -> valida corpo/arquivo/idade -> grava a imagem num
TemporaryDirectory com nome FIXO -> analisa -> aplica o filtro pediátrico -> apaga o diretório (finally) -> JSON.

Garantias (cobertas por tests/test_oneshot.py):
  * nada vai ao Store nem ao usage_log; nada persiste além do TemporaryDirectory;
  * nenhum nome de arquivo, byte de imagem, mensagem de exceção do motor ou resultado vai a log ou à resposta de erro;
  * nenhuma chamada a LLM/rede: este módulo nem importa app.llm, e o motor roda com use_model=False.
"""
from __future__ import annotations

import hmac
import io
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from PIL import Image

from app import pediatric

log = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_BYTES = 4 * 1024 * 1024            # teto do arquivo (o proxy do Pediatria já limita a 4 MB)
MAX_BODY_BYTES = int(4.5 * 1024 * 1024)     # limite de corpo de uma Vercel Function
MAX_PIXELS = 40_000_000                     # protege contra imagem minúscula em bytes e gigante em pixels
TIPOS = ("ecg", "rx")
LAYOUTS = ("auto", "strips", "3x4", "3x4+1", "6x2", "12x1")
SEXOS = ("M", "F")
# extensão -> (formato PIL, assinatura de bytes). Extensão e conteúdo precisam concordar.
_FORMATOS = {"png": ("PNG", b"\x89PNG\r\n\x1a\n"), "jpg": ("JPEG", b"\xff\xd8\xff"), "jpeg": ("JPEG", b"\xff\xd8\xff")}
_NOME_FIXO = "entrada"
_RE_INT = re.compile(r"-?\d+")


def _erro(status: int, codigo: str, mensagem: str) -> HTTPException:
    return HTTPException(status, {"codigo": codigo, "mensagem": mensagem})


def _autenticar(request: Request) -> None:
    """Falha fechada: sem MEDLENS_API_TOKEN no ambiente o serviço não atende (503); token errado dá 401."""
    token = os.environ.get("MEDLENS_API_TOKEN", "")
    if not token:
        raise _erro(503, "nao_configurado", "Serviço sem token configurado.")
    esquema, _, dado = request.headers.get("authorization", "").partition(" ")
    if esquema.lower() != "bearer" or not hmac.compare_digest(dado.strip().encode(), token.encode()):
        raise HTTPException(401, {"codigo": "nao_autenticado", "mensagem": "Token inválido."},
                            headers={"WWW-Authenticate": "Bearer"})


def _checar_corpo(request: Request) -> None:
    bruto = request.headers.get("content-length", "")
    if not bruto.isdigit():
        raise _erro(411, "content_length_obrigatorio", "Informe o Content-Length.")
    if int(bruto) > MAX_BODY_BYTES:
        raise _erro(413, "corpo_grande", "Corpo da requisição acima de 4,5 MB.")


def _parse_idade(bruto: Any) -> Optional[int]:
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return None
    if not isinstance(bruto, str) or not _RE_INT.fullmatch(bruto.strip()):
        raise _erro(400, "idade_invalida", "idade_meses deve ser um número inteiro de meses.")
    meses = int(bruto.strip())
    if not 0 <= meses <= pediatric.IDADE_MAX_MESES:
        raise _erro(400, "idade_fora_da_faixa", "Faixa pediátrica: 0 a 215 meses (até 17 anos e 11 meses).")
    return meses


def _declaracao(form: Any, campo: str, permitidos: dict[str, str]) -> Optional[str]:
    valor = form.get(campo)
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str) or valor not in permitidos:
        raise _erro(400, f"{campo}_invalida", f"{campo} deve ser um de: {', '.join(permitidos)}.")
    return valor


def _validar_campos(form: Any) -> tuple[Optional[int], str, dict[str, Optional[str]]]:
    modo = form.get("modo")
    if modo not in (None, "", "pediatrico"):
        raise _erro(400, "modo_invalido", "Este serviço atende apenas o modo pediátrico.")
    sexo = form.get("sexo")
    if sexo not in (None, "") and sexo not in SEXOS:
        raise _erro(400, "sexo_invalido", "sexo deve ser M ou F.")
    layout = form.get("layout") or "auto"
    if layout not in LAYOUTS:
        raise _erro(400, "layout_invalido", "layout desconhecido.")
    declaradas = {
        "regiao_declarada": _declaracao(form, "regiao_declarada", pediatric.REGIOES_DECLARADAS),
        "incidencia_declarada": _declaracao(form, "incidencia_declarada", pediatric.INCIDENCIAS_DECLARADAS),
    }
    return _parse_idade(form.get("idade_meses")), layout, declaradas


async def _ler_arquivo(form: Any) -> tuple[bytes, str]:
    """Devolve (bytes, extensão normalizada). O nome enviado pelo cliente só serve para a extensão."""
    itens = form.getlist("file")
    if len(itens) != 1 or not hasattr(itens[0], "read"):
        raise _erro(400, "um_arquivo", "Envie exatamente um arquivo no campo 'file'.")
    up = itens[0]
    ext = Path((up.filename or "").replace("\\", "/")).suffix.lower().lstrip(".")
    if ext not in _FORMATOS:
        raise _erro(415, "tipo_nao_permitido", "Formatos aceitos: PNG, JPG e JPEG.")
    dados = await up.read(MAX_FILE_BYTES + 1)
    if len(dados) > MAX_FILE_BYTES:
        raise _erro(413, "arquivo_grande", "Arquivo acima de 4 MB.")
    if not dados:
        raise _erro(400, "arquivo_vazio", "Arquivo vazio.")
    if not dados.startswith(_FORMATOS[ext][1]):
        raise _erro(415, "tipo_nao_permitido", "O conteúdo não confere com a extensão.")
    return dados, ext


def _validar_imagem(dados: bytes, ext: str) -> None:
    try:
        with Image.open(io.BytesIO(dados)) as im:
            formato, (w, h) = im.format, im.size
            if formato != _FORMATOS[ext][0]:
                raise _erro(415, "tipo_nao_permitido", "O conteúdo não confere com a extensão.")
            if w * h > MAX_PIXELS:
                raise _erro(413, "imagem_grande", "Imagem com pixels demais.")
            im.verify()
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - qualquer falha de decodificação vira erro genérico, sem texto do PIL
        raise _erro(422, "imagem_invalida", "Não foi possível ler a imagem.") from None


def _analisar(tipo: str, caminho: Path, layout: str = "auto"):
    """Motor de análise (sem modelo, sem IA). Importações pesadas ficam aqui dentro."""
    from app.dicom.render import open_image

    if tipo == "ecg":
        from app.ecg.analysis import analyze_signal
        from app.ecg.digitize import digitize_image

        return analyze_signal(digitize_image(open_image(caminho, gray=False), layout), "oneshot")
    from app.rx import analyze_image
    from app.schemas import RXAnalysis

    img = analyze_image(open_image(caminho, gray=True), "oneshot", None, use_model=False)
    return RXAnalysis(study_id="oneshot", images=[img])


def _processar(tipo: str, dados: bytes, ext: str, idade: Optional[int], layout: str,
               declaradas: Optional[dict[str, Optional[str]]] = None) -> dict[str, Any]:
    """Tudo o que toca disco acontece aqui, dentro do TemporaryDirectory (apagado mesmo com exceção)."""
    with tempfile.TemporaryDirectory(prefix="medlens-oneshot-") as d:
        caminho = Path(d) / f"{_NOME_FIXO}.{ext}"
        caminho.write_bytes(dados)
        try:
            analise = _analisar(tipo, caminho) if layout == "auto" else _analisar(tipo, caminho, layout)
        except ValueError:
            raise _erro(422, "imagem_nao_analisavel",
                        "A imagem não pôde ser analisada com segurança. Envie outra foto ou arquivo.") from None
        except Exception as e:  # noqa: BLE001 - só o TIPO da exceção vai ao log (a mensagem pode ter dado pessoal)
            log.warning("oneshot: análise falhou (%s)", type(e).__name__)
            raise _erro(500, "analise_falhou", "Falha interna na análise.") from None
        try:
            extras = declaradas if tipo == "rx" and declaradas else {}
            return pediatric.aplicar_modo_pediatrico(tipo, analise, idade, **extras)
        except ValueError:
            raise _erro(502, "resultado_bloqueado", "Resultado indisponível com segurança.") from None
    # o diretório e o arquivo já foram apagados ao sair do with


@router.post("/oneshot/{tipo}")
async def oneshot(tipo: str, request: Request) -> JSONResponse:
    _autenticar(request)
    if tipo not in TIPOS:
        raise _erro(404, "tipo_desconhecido", "Tipo de exame desconhecido.")
    _checar_corpo(request)
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001 - multipart malformado
        raise _erro(400, "corpo_invalido", "Corpo multipart inválido.") from None
    try:
        idade, layout, declaradas = _validar_campos(form)
        dados, ext = await _ler_arquivo(form)
        _validar_imagem(dados, ext)
        resultado = await run_in_threadpool(_processar, tipo, dados, ext, idade, layout, declaradas)
    finally:
        await form.close()
    return JSONResponse(resultado, headers={"Cache-Control": "no-store"})
