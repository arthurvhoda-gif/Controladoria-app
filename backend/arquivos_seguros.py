"""Armazenamento local defensivo para uploads legados da Haize.

Este módulo NÃO migra a persistência: arquivos anteriores continuam nos seus
caminhos originais. Uma migração para armazenamento durável exige inventário,
cópia verificada e mudança separada de esquema/infraestrutura.
"""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata
import uuid

from fastapi import HTTPException, UploadFile


BLOCO_BYTES = 1024 * 1024
MAX_ANEXO_SOLICITACAO = 10 * BLOCO_BYTES
MAX_FOTO_CHECKLIST = 20 * BLOCO_BYTES


def nome_exibicao_seguro(nome: str | None) -> str:
    """Retém nome legível sem diretórios, NUL ou caracteres de controle."""
    nome_base = str(nome or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    nome_base = "".join(
        c for c in nome_base
        if not unicodedata.category(c).startswith("C")
    )[:250].strip()
    if nome_base in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    return nome_base


def salvar_upload_local(
    arquivo: UploadFile, diretorio: str | Path, prefixo: str, limite_bytes: int
) -> tuple[str, str]:
    """Escreve chunks com limite e nome imprevisível; apaga uploads parciais.

    Retorna (nome exibido, caminho absoluto). Não usa o nome informado pelo
    cliente em caminhos. O diretório é controlado pelo servidor, jamais pelo
    usuário. Os caminhos antigos no banco não são modificados.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,70}", prefixo):
        raise ValueError("Prefixo interno de armazenamento inválido.")
    if limite_bytes <= 0:
        raise ValueError("Limite de upload inválido.")

    nome_exibido = nome_exibicao_seguro(arquivo.filename)
    extensao = Path(nome_exibido).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,12}", extensao):
        extensao = ""

    pasta = Path(diretorio).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{prefixo}_{uuid.uuid4().hex}{extensao}"
    total = 0

    try:
        with destino.open("xb") as saida:
            while True:
                trecho = arquivo.file.read(BLOCO_BYTES)
                if not trecho:
                    break
                total += len(trecho)
                if total > limite_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Arquivo excede o limite de {limite_bytes // BLOCO_BYTES} MB."
                    )
                saida.write(trecho)
        if not total:
            raise HTTPException(status_code=400, detail="Arquivo vazio.")
        return nome_exibido, str(destino)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
