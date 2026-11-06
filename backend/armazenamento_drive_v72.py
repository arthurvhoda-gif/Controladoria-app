"""Ponte Drive V7.2 (homologacao). Nunca acessada diretamente pelo navegador.

Arquivos antigos seguem nos caminhos locais; novos uploads passam ao Drive
somente com HAIZE_STORAGE_MODE=drive_v72. Nenhum fallback silencioso.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import time
import uuid
from urllib import error as urlerror, parse as urlparse, request as urlrequest

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
from arquivos_seguros import nome_exibicao_seguro, salvar_upload_local

PREFIXO = "drive-v72:"
LIMITE_PONTE = 20 * 1024 * 1024
LIMITE_RESPOSTA = 29 * 1024 * 1024


def modo_armazenamento() -> str:
    modo = os.environ.get("HAIZE_STORAGE_MODE", "local").strip().lower()
    if modo not in ("local", "drive_v72"):
        raise HTTPException(503, detail="Modo de armazenamento invalido.")
    return modo


def eh_arquivo_drive(caminho: str | None) -> bool:
    return isinstance(caminho, str) and caminho.startswith(PREFIXO)


def _config() -> tuple[str, str]:
    url = os.environ.get("HAIZE_STORAGE_URL", "").strip()
    segredo = os.environ.get("HAIZE_STORAGE_SECRET", "").strip()
    url_partes = urlparse.urlsplit(url)
    if (url_partes.scheme != "https" or url_partes.netloc != "script.google.com"
            or not re.fullmatch(r"/macros/s/[A-Za-z0-9_-]+/exec", url_partes.path)
            or url_partes.query or url_partes.fragment
            or not re.fullmatch(r"[a-f0-9]{64}", segredo)):
        raise HTTPException(503, detail="Ponte de armazenamento nao configurada.")
    return url, segredo


class _RedirectGoogle(urlrequest.HTTPRedirectHandler):
    """Permite apenas o redirecionamento HTTPS oficial do Apps Script."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destino = urlparse.urlsplit(newurl)
        if destino.scheme != "https" or destino.hostname not in (
            "script.googleusercontent.com", "script.google.com"
        ) or destino.username or destino.password:
            raise urlerror.HTTPError(newurl, 503, "Redirecionamento nao permitido", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _enviar(dados: dict) -> dict:
    url, segredo = _config()
    payload = json.dumps({"version": 1, "ts": int(time.time()), **dados},
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    assinatura = hmac.new(segredo.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    corpo = json.dumps({"payload": payload, "signature": assinatura},
                       separators=(",", ":")).encode("utf-8")
    requisicao = urlrequest.Request(
        url, data=corpo, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlrequest.build_opener(_RedirectGoogle()).open(requisicao, timeout=60) as resposta:
            recebido = resposta.read(LIMITE_RESPOSTA + 1)
    except (urlerror.HTTPError, urlerror.URLError, TimeoutError, OSError):
        raise HTTPException(503, detail="Servico de armazenamento indisponivel.") from None
    if len(recebido) > LIMITE_RESPOSTA:
        raise HTTPException(503, detail="Resposta de armazenamento fora do limite.")
    try:
        resultado = json.loads(recebido.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise HTTPException(503, detail="Resposta invalida do armazenamento.") from None
    if not isinstance(resultado, dict) or resultado.get("ok") is not True:
        if isinstance(resultado, dict) and resultado.get("error") == "NAO_ENCONTRADO":
            raise HTTPException(404, detail="Arquivo nao encontrado.")
        raise HTTPException(503, detail="Operacao de armazenamento nao confirmada.")
    return resultado


def salvar_upload_haize(arquivo: UploadFile, diretorio: str, prefixo: str,
                         limite_bytes: int) -> tuple[str, str]:
    if modo_armazenamento() == "local":
        return salvar_upload_local(arquivo, diretorio, prefixo, limite_bytes)
    # Os limites particulares de compra/checklist continuam em vigor.
    limite = min(limite_bytes, LIMITE_PONTE)
    nome = nome_exibicao_seguro(arquivo.filename)
    dados = arquivo.file.read(limite + 1)
    if not dados:
        raise HTTPException(400, detail="Arquivo vazio.")
    if len(dados) > limite:
        raise HTTPException(413, detail="Arquivo excede o limite permitido.")
    chave = uuid.uuid4().hex
    hash_esperado = hashlib.sha256(dados).hexdigest()
    retorno = _enviar({
        "op": "put", "key": chave, "size": len(dados),
        "sha256": hash_esperado, "data": base64.b64encode(dados).decode("ascii"),
    })
    if (retorno.get("key") != chave or retorno.get("size") != len(dados)
            or retorno.get("sha256") != hash_esperado
            or retorno.get("repeated") is not False):
        raise HTTPException(503, detail="Gravacao nao confirmada pelo armazenamento.")
    return nome, PREFIXO + chave


def _baixar_drive(caminho: str) -> bytes:
    if not eh_arquivo_drive(caminho):
        raise HTTPException(404, detail="Referencia de arquivo invalida.")
    chave = caminho[len(PREFIXO):]
    if not re.fullmatch(r"[a-f0-9]{32}", chave):
        raise HTTPException(404, detail="Referencia de arquivo invalida.")
    retorno = _enviar({"op": "get", "key": chave})
    if (retorno.get("key") != chave or not isinstance(retorno.get("size"), int)
            or isinstance(retorno.get("size"), bool)
            or not 0 < retorno["size"] <= LIMITE_PONTE
            or not isinstance(retorno.get("data"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", str(retorno.get("sha256", "")))):
        raise HTTPException(503, detail="Metadados inconsistentes no armazenamento.")
    try:
        bytes_salvos = base64.b64decode(retorno["data"], validate=True)
    except (ValueError, base64.binascii.Error):
        raise HTTPException(503, detail="Arquivo corrompido no armazenamento.") from None
    if (len(bytes_salvos) != retorno["size"]
            or hashlib.sha256(bytes_salvos).hexdigest() != retorno["sha256"]
            or base64.b64encode(bytes_salvos).decode("ascii") != retorno["data"]):
        raise HTTPException(503, detail="Integridade do arquivo nao confirmada.")
    return bytes_salvos


def resposta_arquivo_drive(caminho: str, nome: str, *, inline: bool = False) -> Response:
    dados = _baixar_drive(caminho)
    nome_seguro = nome_exibicao_seguro(nome)
    tipo = "application/octet-stream"
    if inline:
        candidato = mimetypes.guess_type(nome_seguro)[0]
        if candidato in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            tipo = candidato
    disposicao = "inline" if inline else "attachment"
    cabecalhos = {
        "Content-Disposition": f"{disposicao}; filename*=UTF-8''{urlparse.quote(nome_seguro, safe='')}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return Response(content=dados, media_type=tipo, headers=cabecalhos)
