# -*- coding: utf-8 -*-
"""Projeção privada do app em uma única transação PostgreSQL somente leitura.
Não importa main/database. Não lê DATABASE_URL. Não envia nem altera dados.
"""
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

ROLE = 'haize_intelligence_ro'
# Consultas fixas: nenhuma interpolação de valores recebidos do usuário.
PROJECOES = (
    ('condominios', 'condominios', ('id','nome'), 1000),
    ('solicitacoes', 'solicitacoes', ('id','condominio_id','status','data','categoria','fornecedor','descricao','valor_aprovado','valor_realizado'), 50000),
    ('lancamentos', 'financeiro_lancamentos', ('id','solicitacao_id','tipo','valor_centavos','estorno_de_id'), 200000),
    ('servicos', 'servicos_internos', ('id','condominio_id','status','prazo','prioridade'), 200000),
    ('participantes', 'servicos_participantes', ('id','servico_id','papel','status'), 200000),
    ('itens', 'checklist_itens', ('id','condominio_id'), 200000),
    ('execucoes', 'checklist_execucoes', ('id','item_id','status_conformidade','data_execucao'), 200000),
)

class ErroFonteApp(ValueError):
    pass


def validar_conexao(dsn, host, banco, ca):
    """Destino explícito, credencial separada e TLS com verificação do servidor."""
    try:
        u=urlsplit(dsn)
        if (u.scheme!='postgresql' or u.username!=ROLE or not u.password or
            not isinstance(host,str) or not host.endswith('.neon.tech') or
            u.hostname!=host or u.port not in (None,5432) or not banco or
            u.path!='/'+banco or u.fragment or u.query):
            raise ValueError()
        # Não aceitar parâmetros arbitrários na URI (incluindo options/sslmode).
        if not Path(ca).is_file(): raise ValueError()
    except (TypeError, ValueError, OSError) as exc:
        raise ErroFonteApp('CONFIGURACAO_DE_LEITURA_INVALIDA') from None
    return dict(sslmode='verify-full',sslrootcert=str(Path(ca).resolve()),connect_timeout=10,
                application_name='haize_intelligence_v80',options='-c statement_timeout=30000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=60000 -c row_security=off')


def extrair_snapshot_v80(conexao, banco):
    """Conexão dedicada recém-aberta. Fecha cursor e desfaz transação sempre.
    Não reconstrói estados passados. Rejeita extrações truncadas ou incompletas.
    """
    if not isinstance(banco,str) or not banco: raise ErroFonteApp('BANCO_INVALIDO')
    cursor=None
    try:
        conexao.set_session(isolation_level='REPEATABLE READ',readonly=True,autocommit=False)
        cursor=conexao.cursor()
        cursor.execute("SELECT current_user, session_user, current_database(), current_setting('transaction_read_only'), current_setting('transaction_isolation'), (transaction_timestamp() AT TIME ZONE 'America/Sao_Paulo')::date")
        usuario,sessao,db,ro,iso,dia=cursor.fetchone()
        if (usuario,sessao,db,ro,iso)!=(ROLE,ROLE,banco,'on','repeatable read') or type(dia) is not date:
            raise ErroFonteApp('SESSAO_NAO_AUTORIZADA')
        cursor.execute("SELECT NOT (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls), NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid) FROM pg_catalog.pg_roles r WHERE r.rolname=current_user")
        if cursor.fetchone()!=(True,True): raise ErroFonteApp('PAPEL_PRIVILEGIADO')
        snapshot={'data_referencia':dia.isoformat()}
        for chave,tabela,campos,limite in PROJECOES:
            nome='public.'+tabela
            cursor.execute("SELECT has_table_privilege(current_user,%s,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), has_any_column_privilege(current_user,%s,'INSERT,UPDATE,REFERENCES')",(nome,nome))
            if cursor.fetchone()!=(False,False): raise ErroFonteApp('PAPEL_COM_ESCRITA')
            cursor.execute('SELECT '+','.join(campos)+' FROM '+nome+' ORDER BY id LIMIT %s',(limite+1,))
            rows=cursor.fetchall()
            if len(rows)>limite: raise ErroFonteApp('LIMITE_DA_FONTE')
            registros=[]; ids=set()
            for row in rows:
                if len(row)!=len(campos) or type(row[0]) is not int or row[0]<=0 or row[0] in ids:
                    raise ErroFonteApp('REGISTRO_DA_FONTE_INVALIDO')
                ids.add(row[0]); r=dict(zip(campos,row))
                if 'prazo' in r:
                    if type(r['prazo']) is not date: raise ErroFonteApp('PRAZO_INVALIDO')
                    r['prazo']=r['prazo'].isoformat()
                registros.append(r)
            if chave=='condominios':
                if not registros: raise ErroFonteApp('CADASTRO_VAZIO')
                snapshot[chave]={r['id']:r['nome'] for r in registros}
            else: snapshot[chave]=registros
        return snapshot
    except ErroFonteApp:
        raise
    except Exception:
        # Mensagens de drivers podem incluir credenciais, nomes ou SQL.
        raise ErroFonteApp('EXTRACAO_FALHOU') from None
    finally:
        try:
            if cursor is not None: cursor.close()
        finally:
            conexao.rollback()


def carregar_app_v80(*,dsn,host,banco,ca):
    opcoes=validar_conexao(dsn,host,banco,ca)
    try:
        import psycopg2
        conexao=psycopg2.connect(dsn,**opcoes)
    except Exception:
        raise ErroFonteApp('CONEXAO_FALHOU') from None
    try: return extrair_snapshot_v80(conexao,banco)
    finally: conexao.close()
