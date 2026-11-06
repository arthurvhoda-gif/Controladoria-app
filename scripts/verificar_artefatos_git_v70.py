#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V7.0 - Impede NOVOS artefatos locais sensiveis no Git.

Nao abre nem altera arquivos, nao acessa bancos e nao apaga historico.
Os artefatos antigos sao sinalizados; sua remocao exige auditoria e plano.
"""
from __future__ import annotations

import subprocess
from pathlib import PurePosixPath

LEGADOS_PARA_AUDITAR = {
    "backend/controladoria.db",
    "backend/__pycache__/database.cpython-314.pyc",
    "backend/__pycache__/empresas.cpython-314.pyc",
    "backend/__pycache__/main.cpython-314.pyc",
    "backend/__pycache__/models.cpython-314.pyc",
    "backend/__pycache__/schemas.cpython-314.pyc",
}
EXTENSOES_PROIBIDAS = (
    ".db", ".sqlite", ".sqlite3", ".pyc", ".pyo", ".pem", ".p12", ".pfx",
)


def sensivel(caminho: str) -> bool:
    partes = PurePosixPath(caminho).parts
    nome = partes[-1].lower()
    if nome == ".env.example":
        return False
    return (
        nome == ".env"
        or nome.startswith(".env.")
        or nome.endswith(EXTENSOES_PROIBIDAS)
        or nome.endswith(".key")
        or "__pycache__" in partes
    )


def main() -> int:
    resultado = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    caminhos = sorted(
        s for s in resultado.stdout.decode("utf-8").split("\0") if s
    )
    candidatos = {s for s in caminhos if sensivel(s)}
    legados = sorted(candidatos & LEGADOS_PARA_AUDITAR)
    novos = sorted(candidatos - LEGADOS_PARA_AUDITAR)

    for caminho in legados:
        print(
            f"::warning file={caminho}::Artefato legado versionado; "
            "avaliar dados e historico antes de remocao."
        )
    for caminho in novos:
        print(
            f"::error file={caminho}::Novo artefato local/sensivel "
            "versionado; retire-o do commit sem excluir seus dados locais."
        )
    print(
        f"Auditoria Git V7.0: {len(caminhos)} arquivos rastreados, "
        f"{len(legados)} legados pendentes, {len(novos)} novos proibidos."
    )
    if novos:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
