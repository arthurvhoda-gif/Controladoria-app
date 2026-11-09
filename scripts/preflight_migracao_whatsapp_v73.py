#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico SOMENTE LEITURA da migração V7.3 em PostgreSQL descartável.

Usa exclusivamente o banco CI local `haize_v73_notificacoes`.
Não mostra números, nomes, e-mails, URLs ou registros individuais.
Não conecta ao Neon nem executa a migração.
"""
import json
import os
from urllib.parse import urlsplit

import psycopg2


INDICE = 'uq_whatsapp_preferencias_telefone'


def validar_destino():
    valor = os.environ.get('DATABASE_URL', '')
    try:
        url = urlsplit(valor)
        porta = url.port
    except ValueError as exc:
        raise SystemExit('BLOQUEADO: endereço de teste inválido.') from exc
    if (url.scheme != 'postgresql'
            or url.hostname != '127.0.0.1'
            or porta != 5432
            or url.username != 'haize_ci'
            or url.path != '/haize_v73_notificacoes'
            or url.query or url.fragment or url.params):
        raise SystemExit(
            'BLOQUEADO: somente PostgreSQL CI em 127.0.0.1:5432/'
            'haize_v73_notificacoes.'
        )
    return valor


def _indice_valido(cursor):
    cursor.execute("""
        SELECT i.indisunique, i.indisvalid, i.indisready,
               i.indnkeyatts, i.indnatts, a.attname,
               pg_get_expr(i.indpred, i.indrelid) AS predicado
          FROM pg_class idx
          JOIN pg_namespace ns ON ns.oid = idx.relnamespace
          JOIN pg_index i ON i.indexrelid = idx.oid
          JOIN pg_class tab ON tab.oid = i.indrelid
          JOIN pg_attribute a ON a.attrelid = tab.oid
            AND a.attnum = i.indkey[0]
         WHERE ns.nspname = 'public'
           AND idx.relname = %s
           AND tab.oid = to_regclass('public.whatsapp_preferencias')
    """, (INDICE,))
    resultado = cursor.fetchone()
    if resultado is None:
        return False
    unico, valido, pronto, chaves, total_atributos, coluna, predicado = resultado
    return (
        unico and valido and pronto
        and chaves == 1 and total_atributos == 1
        and coluna == 'telefone'
        and predicado in (None, '(telefone IS NOT NULL)', 'telefone IS NOT NULL')
    )


def inspecionar(cursor):
    """Recebe cursor de transação READ ONLY: retorna APENAS dados agregados."""
    cursor.execute("SELECT to_regclass('public.whatsapp_preferencias') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return {
            'situacao': 'bloqueado',
            'motivos': ['Tabela de preferências ausente na cópia de homologação.'],
            'grupos_duplicados': 0,
            'contas_afetadas': 0,
            'indice_unico_valido': False,
        }

    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(qtd), 0)
          FROM (
            SELECT COUNT(*) AS qtd
              FROM whatsapp_preferencias
             WHERE telefone IS NOT NULL
             GROUP BY telefone
            HAVING COUNT(*) > 1
          ) grupos
    """)
    grupos, contas = cursor.fetchone()
    cursor.execute("SELECT to_regclass('public.uq_whatsapp_preferencias_telefone') IS NOT NULL")
    indice_existe = bool(cursor.fetchone()[0])
    indice_ok = _indice_valido(cursor) if indice_existe else False

    motivos = []
    if grupos:
        motivos.append('Há telefones compartilhados entre cadastros. Resolver manualmente antes da migração.')
    if indice_existe and not indice_ok:
        motivos.append('O nome do índice já está ocupado por estrutura inválida ou não única.')

    if motivos:
        situacao = 'bloqueado'
    elif indice_ok:
        situacao = 'migracao_ja_aplicada_na_copia'
    else:
        situacao = 'pronto_para_migracao_na_copia'

    return {
        'situacao': situacao,
        'motivos': motivos,
        'grupos_duplicados': int(grupos),
        'contas_afetadas': int(contas),
        'indice_unico_valido': bool(indice_ok),
    }


def avaliar_readonly(conn):
    # PostgreSQL impede QUALQUER escrita mesmo por erro em código futuro.
    conn.set_session(readonly=True, autocommit=False)
    try:
        with conn.cursor() as cursor:
            resultado = inspecionar(cursor)
        conn.rollback()
        return resultado
    finally:
        conn.rollback()


def main():
    url = validar_destino()
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        resultado = avaliar_readonly(conn)
    finally:
        conn.close()
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    # Somente a cópia validada sem duplicidades permite preparar a migração.
    return 2 if resultado['situacao'] == 'bloqueado' else 0


if __name__ == '__main__':
    raise SystemExit(main())
