#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventário somente leitura de anexos e fotos de checklist.

Executar no MESMO host onde a API acessa os arquivos e com DATABASE_URL
já definido no ambiente; jamais colar credenciais em argumentos/comentários.
Não altera dados nem lê conteúdo dos documentos; informa apenas CONTAGENS.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, text


def resumir(caminhos, existe=None):
    existe = existe or (lambda caminho: Path(caminho).is_file())
    resultado = {"total": 0, "presentes": 0, "ausentes": 0, "sem_caminho": 0}
    for caminho in caminhos:
        resultado["total"] += 1
        if not isinstance(caminho, str) or not caminho.strip():
            resultado["sem_caminho"] += 1
        else:
            try:
                if existe(caminho):
                    resultado["presentes"] += 1
                else:
                    resultado["ausentes"] += 1
            except (OSError, ValueError):
                resultado["ausentes"] += 1
    return resultado


def executar():
    p = argparse.ArgumentParser(description="Inventário agregado de arquivos da Haize sem alterações")
    p.add_argument("--somente-leitura", required=True, action="store_true")
    args = p.parse_args()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL ausente. Nada foi alterado.")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text("SET TRANSACTION READ ONLY"))
            anexos = conn.execute(text("SELECT caminho FROM anexos")).scalars().all()
            fotos = conn.execute(text("SELECT caminho_foto FROM checklist_execucoes WHERE caminho_foto IS NOT NULL")).scalars().all()
        saida = {
            "anexos_compras": resumir(anexos),
            "fotos_checklist": resumir(fotos),
            "observacao": "Contagens feitas no host atual. Não garante preservação se os arquivos estão em outra instância."
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    executar()
