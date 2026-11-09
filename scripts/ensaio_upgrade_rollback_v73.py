#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensaio V7.3: upgrade e rollback de uma COPIA sintética com PostgreSQL real.

Nenhuma conexão remota é permitida. Criamos bancos descartáveis no runner da
CI, geramos pg_dump completo FORA do repositório, comprovamos o bloqueio de
duplicatas, saneamos apenas o cenário fictício, migramos e restauramos o
backup pré-migração em outro banco para verificar reversibilidade real.

Esse rollback é do BANCO INTEIRO restaurado; não finge desfazer uma migração
em produção com git revert. NÃO ACESSA NEON, RENDER OU ARQUIVOS REAIS.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'backend'))
import models
import preflight_migracao_whatsapp_v73 as preflight

ORIGEM = 'haize_v70_testes'
UPGRADE = 'haize_v73_upgrade_ci'
RESTAURACAO = 'haize_v73_reversao_ci'
TABELAS = ('condominios', 'usuarios', 'solicitacoes',
           'whatsapp_preferencias', 'whatsapp_auditoria_contatos',
           'whatsapp_auditoria_consentimentos')
SQL_MIGRACAO = (RAIZ / 'migracoes' / 'v73_whatsapp_telefone_unico.sql'
                ).read_text(encoding='utf-8')


def guarda():
    try:
        u = make_url(os.environ.get('DATABASE_URL', ''))
    except Exception as exc:
        raise SystemExit('BLOQUEADO: URL CI inválida.') from exc
    if (os.environ.get('CI') != 'true'
            or u.get_backend_name() != 'postgresql'
            or u.host != '127.0.0.1'
            or u.port != 5432
            or u.username != 'haize_ci'
            or u.database != ORIGEM
            or u.query):
        raise SystemExit('BLOQUEADO: somente GitHub CI e PostgreSQL descartável local.')
    if (os.environ.get('PGHOST') != '127.0.0.1'
            or os.environ.get('PGPORT') != '5432'
            or os.environ.get('PGUSER') != 'haize_ci'
            or not os.environ.get('PGPASSWORD')):
        raise SystemExit('BLOQUEADO: cliente pg_dump não usa o banco CI local.')
    return u


def comando(*args):
    # Não capturar nem publicar registros de banco nos logs da CI.
    subprocess.run(args, check=True, capture_output=True)


def usar(nome, u):
    return str(u.set(database=nome))


def criar_db(nome):
    if nome not in (UPGRADE, RESTAURACAO):
        raise RuntimeError('Nome de banco descartável não autorizado.')
    comando('createdb', '-h', '127.0.0.1', '-p', '5432',
            '-U', 'haize_ci', nome)


def conectar(nome, u):
    return psycopg2.connect(usar(nome, u), connect_timeout=5)


def coletar_snapshot(nome, u):
    conn = conectar(nome, u)
    conn.set_session(readonly=True, autocommit=False)
    try:
        with conn.cursor() as c:
            hash_registros = {}
            for tabela in TABELAS:
                c.execute('SELECT * FROM ' + tabela + ' ORDER BY 1')
                # Hash dos registros fictícios, nunca valores em logs.
                payload = json.dumps(c.fetchall(), default=str,
                                     ensure_ascii=False).encode('utf-8')
                hash_registros[tabela] = hashlib.sha256(payload).hexdigest()
        conn.rollback()
        return hash_registros
    finally:
        conn.close()


def diagnostico(nome, u):
    conn = conectar(nome, u)
    conn.set_session(readonly=True, autocommit=False)
    try:
        with conn.cursor() as c:
            resultado = preflight.inspecionar(c)
        conn.rollback()
        return resultado
    finally:
        conn.close()


def executar_migracao(nome, u):
    conn = conectar(nome, u)
    try:
        # SQL já tem BEGIN/COMMIT e é transacional em PostgreSQL.
        with conn.cursor() as c:
            c.execute(SQL_MIGRACAO)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def preparar_legado(u):
    e = create_engine(usar(UPGRADE, u))
    try:
        models.Base.metadata.create_all(e)
        with e.begin() as c:
            # Simula schema pré-V7.3, que ainda não impunha telefone único.
            c.execute(text('ALTER TABLE whatsapp_preferencias '
                           'DROP CONSTRAINT uq_whatsapp_preferencias_telefone'))
            c.execute(text("INSERT INTO condominios (id, nome) "
                           "VALUES (1, 'Condominio Ficticio de Upgrade')"))
            c.execute(text("INSERT INTO usuarios (id,nome,email,senha,perfil,condominio_id) VALUES "
                           "(1,'Gestora Teste','gestora.upgrade@local.test','hash-ficticio','Controladoria',NULL),"
                           "(2,'Zelador A','a.upgrade@local.test','hash-ficticio','Checklist',1),"
                           "(3,'Zelador B','b.upgrade@local.test','hash-ficticio','Checklist',1)"))
            c.execute(text("INSERT INTO solicitacoes "
                           "(numero,condominio,categoria,fornecedor,descricao,solicitante,status) VALUES "
                           "('SOL-V73-UPGRADE','Condominio Ficticio de Upgrade','Teste','Ficticio',"
                           "'Solicitacao anterior a migracao','Gestora Teste','Aprovação pendente')"))
            c.execute(text("INSERT INTO whatsapp_preferencias "
                           "(usuario_id,telefone,consentimento,atualizado_em) VALUES "
                           "(2,'+5543999991111',1,CURRENT_TIMESTAMP),"
                           "(3,'+5543999991111',0,CURRENT_TIMESTAMP)"))
    finally:
        e.dispose()


def corrigir_copia_ficticia(u):
    e = create_engine(usar(UPGRADE, u))
    try:
        with e.begin() as c:
            c.execute(text("UPDATE whatsapp_preferencias SET telefone = '+5543999992222' "
                           'WHERE usuario_id = 3'))
    finally:
        e.dispose()


def main():
    u = guarda()
    criar_db(UPGRADE)
    preparar_legado(u)
    original = coletar_snapshot(UPGRADE, u)
    d = diagnostico(UPGRADE, u)
    assert d['situacao'] == 'bloqueado' and d['grupos_duplicados'] == 1
    assert d['contas_afetadas'] == 2 and not d['indice_unico_valido']

    with tempfile.TemporaryDirectory(prefix='haize_upgrade_rollback_ci_') as pasta:
        arquivo = Path(pasta) / 'pre_v73.dump'
        comando('pg_dump', '-h', '127.0.0.1', '-p', '5432', '-U', 'haize_ci',
                '-d', UPGRADE, '-Fc', '-f', str(arquivo))
        assert arquivo.is_file() and arquivo.stat().st_size > 1024
        dump_hash = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        print('V7.3 rollback 1/4: backup pre-migracao em pasta temporaria, '
              'SHA256 calculado, sem publicar dump.', flush=True)

        try:
            executar_migracao(UPGRADE, u)
        except psycopg2.Error as e:
            assert 'V7.3 BLOQUEADA' in str(e), 'Falha diferente do bloqueio esperado.'
        else:
            raise AssertionError('Migração ignorou telefones legados duplicados!')
        assert original == coletar_snapshot(UPGRADE, u)
        assert diagnostico(UPGRADE, u)['situacao'] == 'bloqueado'
        print('V7.3 rollback 2/4: duplicados bloqueados; nenhum dado alterado.', flush=True)

        # Saneamento MANUAL somente no fixture fictício; nunca no banco real.
        corrigir_copia_ficticia(u)
        snapshot_saneado = coletar_snapshot(UPGRADE, u)
        assert diagnostico(UPGRADE, u)['situacao'] == 'pronto_para_migracao_na_copia'
        executar_migracao(UPGRADE, u)
        executar_migracao(UPGRADE, u)
        assert diagnostico(UPGRADE, u)['situacao'] == 'migracao_ja_aplicada_na_copia'
        assert coletar_snapshot(UPGRADE, u) == snapshot_saneado
        print('V7.3 rollback 3/4: saneamento fictício e migração idempotente '
              'preservaram os dados.', flush=True)

        # Restaura a IMAGEM DE ANTES DA MIGRAÇÃO num banco totalmente novo.
        criar_db(RESTAURACAO)
        comando('pg_restore', '--exit-on-error', '--no-owner', '--no-acl',
                '-h', '127.0.0.1', '-p', '5432', '-U', 'haize_ci',
                '-d', RESTAURACAO, str(arquivo))
        assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == dump_hash
        assert coletar_snapshot(RESTAURACAO, u) == original
        restaurado = diagnostico(RESTAURACAO, u)
        assert restaurado['situacao'] == 'bloqueado'
        assert restaurado['grupos_duplicados'] == 1
        assert not restaurado['indice_unico_valido']
        print('V7.3 rollback 4/4: restore independente reproduziu dados '
              'e schema anterior; dump íntegro.', flush=True)
    print('V7.3: 4/4 ensaios de upgrade/rollback aprovados — '
          'PostgreSQL descartável, sem serviços externos.', flush=True)


if __name__ == '__main__':
    main()
