#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensaio de schema/backup exclusivo do PostgreSQL descartável de CI.

Guardas rígidas: nunca conectar a Neon, Render ou hosts remotos.
O workflow cria, popula, faz pg_dump, restaura e compara dados fictícios.
"""
import os
from pathlib import Path
import sys
import argparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))


def validar_url(nome_db):
    valor = os.getenv("DATABASE_URL", "")
    try:
        url = make_url(valor)
    except Exception as exc:
        raise SystemExit("URL de banco de testes inválida.") from exc
    if (url.get_backend_name() != "postgresql" or url.host not in ("127.0.0.1", "localhost")
            or url.database != nome_db or url.port != 5432 or url.username != "haize_ci"):
        raise SystemExit("BLOQUEADO: aceita exclusivamente Postgres CI na máquina local e banco descartável.")
    return url


def esquema_conferido(engine):
    tabelas = set(inspect(engine).get_table_names())
    exigidas = {
        "usuarios", "condominios", "solicitacoes", "anexos",
        "checklist_itens", "checklist_execucoes", "checklist_envios_relatorios",
        "servicos_internos", "servicos_eventos", "servicos_participantes",
        "servicos_fotos", "whatsapp_fila", "whatsapp_preferencias",
        "financeiro_lancamentos", "financeiro_comprovantes",
    }
    ausentes = sorted(exigidas - tabelas)
    if ausentes:
        raise AssertionError("Tabelas ausentes: " + ", ".join(ausentes))
    with engine.connect() as conn:
        cond = conn.execute(text("SELECT COUNT(*) FROM condominios WHERE nome = 'Condominio Ficticio V70'")).scalar_one()
        sol = conn.execute(text("SELECT COUNT(*) FROM solicitacoes WHERE numero = 'SOL-V70-CI'")).scalar_one()
        if cond != 1 or sol != 1:
            raise AssertionError("Restauracao nao preservou registros ficticios.")
    print("PostgreSQL descartavel: schema, registros e integridade do backup conferidos.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=("preparar", "verificar-restauracao"))
    args = parser.parse_args()
    nome = "haize_v70_testes" if args.acao == "preparar" else "haize_v70_restauracao"
    url = validar_url(nome)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        if args.acao == "preparar":
            import models
            models.Base.metadata.create_all(engine)
            # O sistema de migrações precisa ser idempotente no PostgreSQL.
            import main
            main.executar_migracoes_automaticas()
            main.executar_migracoes_automaticas()
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO condominios (nome) VALUES ('Condominio Ficticio V70')"))
                conn.execute(text(
                    "INSERT INTO solicitacoes (numero, condominio, categoria, fornecedor, descricao, solicitante, status) "
                    "VALUES ('SOL-V70-CI', 'Condominio Ficticio V70', 'Teste', 'Ficticio', 'CI', 'Gestora', 'Aprovação pendente')"
                ))
            esquema_conferido(engine)
        else:
            esquema_conferido(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
