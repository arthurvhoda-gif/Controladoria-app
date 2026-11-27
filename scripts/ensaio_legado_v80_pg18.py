"""Ensaio de upgrade V8.0 somente em PostgreSQL 18 descartavel, com dados ficticios."""
import os, sys
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
URL = make_url(os.environ['DATABASE_URL'])
if (os.environ.get('CI') != 'true' or URL.host != '127.0.0.1'
        or URL.port != 5432 or URL.username != 'haize_ci'
        or URL.database not in ('haize_v80_upgrade','haize_v80_restore')
        or URL.query or URL.get_backend_name() != 'postgresql'):
    raise SystemExit('BLOQUEADO: somente PostgreSQL descartavel da CI.')
engine = create_engine(URL)
with engine.connect() as c:
    assert int(c.execute(text('SHOW server_version_num')).scalar()) // 10000 == 18
    assert c.execute(text('SELECT current_database()')).scalar() == URL.database

DDL = ROOT / 'testes_migracao' / 'schema_legado_v80.sql'
MIG = ROOT / 'migracoes' / 'candidata_v80_legado.sql'
def executar_sql(c, path):
    c.connection.cursor().execute(path.read_text(encoding='utf-8'))

def verificar_legado():
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM solicitacoes')).scalar() == 2
        assert c.execute(text('SELECT count(*) FROM solicitacoes_compra')).scalar() == 1
        assert c.execute(text('SELECT count(*) FROM checklist_envios_relatorios')).scalar() == 3
        assert c.execute(text("SELECT count(*) FROM checklist_envios_relatorios WHERE status='falhou'")).scalar() == 1
        assert 'solicitante_id' not in {x['name'] for x in inspect(c).get_columns('solicitacoes')}
        for tabela in ('anexos','historico_solicitacoes'):
            assert any(f['referred_table']=='solicitacoes_compra' for f in inspect(c).get_foreign_keys(tabela))
        assert not inspect(c).has_table('servicos_internos')
    print('LEGADO VERIFICADO: dados sinteticos e estrutura original.',flush=True)

def preparar():
    with engine.begin() as c:
        executar_sql(c, DDL)
        c.execute(text("INSERT INTO condominios(nome) VALUES ('Alfa ficticio'),('Beta ficticio')"))
        c.execute(text("INSERT INTO usuarios(nome,email,senha,perfil) VALUES ('Gestora ficticia','gestora@local.test','hash-ficticio','Controladoria'),('Solicitante ficticio','solicitante@local.test','hash-ficticio','Solicitante')"))
        c.execute(text("INSERT INTO solicitacoes(numero,condominio,condominio_id,categoria,fornecedor,descricao,solicitante,status) VALUES ('SOL-0001','Alfa ficticio',1,'Teste','Ficticio','Legado 1','Solicitante ficticio','Aprovação pendente'),('SOL-0002','Alfa ficticio',1,'Teste','Ficticio','Legado 2','Solicitante ficticio','Aprovação pendente')"))
        c.execute(text("INSERT INTO solicitacoes_compra(numero) VALUES ('ANTIGA-1')"))
        c.execute(text("""INSERT INTO checklist_envios_relatorios(execucao_id,dados_json,status,tentativas) VALUES (1,'{}','enviado',1),(2,'{}','enviado',1),(3,'{}','falhou',1)"""))
    verificar_legado()

def migrar():
    assert URL.database == 'haize_v80_upgrade'
    # Provar bloqueio atomico se uma referencia historica nao puder ser conciliada.
    with engine.begin() as c:
        c.execute(text("INSERT INTO historico_solicitacoes(solicitacao_id,acao) VALUES (1,'legado ficticio')"))
    try:
        with engine.begin() as c:
            executar_sql(c,MIG)
    except Exception as e:
        assert 'V8.0 BLOQUEADA' in str(e), str(e)
    else:
        raise AssertionError('Migracao ignorou referencia legada')
    verificar_legado()
    with engine.begin() as c:
        c.execute(text("DELETE FROM historico_solicitacoes WHERE acao='legado ficticio'"))
    # Apenas o fixture foi saneado. Nenhum registro real.
    import models
    for _ in range(2):
        with engine.begin() as c:
            executar_sql(c,MIG)
            models.Base.metadata.create_all(c)
    with engine.connect() as c:
        dbi=inspect(c)
        assert all(dbi.has_table(t) for t in models.Base.metadata.tables)
        for t in models.Base.metadata.tables.values():
            assert set(x.name for x in t.columns) <= {x['name'] for x in dbi.get_columns(t.name)}
        assert c.execute(text('SELECT count(*) FROM solicitacoes WHERE solicitante_id IS NULL')).scalar()==2
        assert c.execute(text('SELECT count(*) FROM checklist_envios_relatorios')).scalar()==3
        assert c.execute(text('SELECT count(*) FROM solicitacoes_compra')).scalar()==1
        for tabela in ('anexos','historico_solicitacoes'):
            assert any(f['referred_table']=='solicitacoes' for f in dbi.get_foreign_keys(tabela))
            assert not any(f['referred_table']=='solicitacoes_compra' for f in dbi.get_foreign_keys(tabela))
    import main as api
    import auth_utils
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from fastapi import BackgroundTasks
    with api.SessionLocal() as db:
        gestor= db.get(models.Usuario,1)
        solicitante=db.get(models.Usuario,2)
        h={'Authorization':'Bearer '+auth_utils.create_token(gestor)}
        hs={'Authorization':'Bearer '+auth_utils.create_token(solicitante)}
    with TestClient(api.app) as client:
        assert client.get('/status').status_code==200
        assert client.get('/solicitacoes',headers=hs).json()==[]
        assert len(client.get('/solicitacoes',headers=h).json())==2
        p=client.post('/solicitacoes',headers=hs,json={'condominio':'Alfa ficticio','condominio_id':1,'categoria':'Teste','fornecedor':'Ficticio','descricao':'Compra nova','valor_produto':100})
        assert p.status_code==200,p.text
        sid=p.json()['id']
        assert sid>2
        hist=client.get(f'/solicitacoes/{sid}/historico',headers=hs)
        assert hist.status_code==200 and len(hist.json())==1,hist.text
        up=client.post(f'/solicitacoes/{sid}/anexos',headers=hs,files={'arquivo':('orcamento.txt',b'Arquivo ficticio','text/plain')},data={'tipo':'Orcamento'})
        # O uploader pode restringir extensoes. Validar com PDF real se TXT rejeitado.
        if up.status_code!=200:
            from io import BytesIO
            from reportlab.pdfgen import canvas
            arq=BytesIO(); pdf=canvas.Canvas(arq); pdf.drawString(20,20,'Ficticio'); pdf.save()
            up=client.post(f'/solicitacoes/{sid}/anexos',headers=hs,files={'arquivo':('orcamento.pdf',arq.getvalue(),'application/pdf')},data={'tipo':'Orcamento'})
        assert up.status_code==200,up.text
        assert client.get(f'/anexos/{up.json()["id"]}/download',headers=hs).status_code==200
        ck=client.post('/checklists',headers=h,json={'condominio':'Alfa ficticio','condominio_id':1,'titulo':'Inspecao ficticia','frequencia':'Diária'})
        assert ck.status_code==200,ck.text
        vi=client.post(f'/checklists/{ck.json()["id"]}/executar',headers=h,data={'responsavel':'Ficticio','status_conformidade':'Conforme'})
        assert vi.status_code==200,vi.text
        assert vi.json()['ultima_execucao']['id']>3
        # Provar que o envio orfao nao entra na fila nem chama provedor.
        with api.SessionLocal() as db, patch.object(api,'ENVIO_AUTOMATICO_CHECKLIST',True):
            tarefas=BackgroundTasks()
            assert api.reprocessar_envios_checklist(tarefas,db)['fila_reprocessamento']==0
        with patch.object(api,'enviar_relatorio_google_apps_script') as enviar:
            api._processar_envio_execucao(3)
            enviar.assert_not_called()
    print('UPGRADE PG18: schema completo, idempotencia, bloqueio legado, compra, historico, anexo, vistoria e fila orfa aprovados.',flush=True)

if __name__=='__main__':
    {'preparar':preparar,'migrar':migrar,'restauracao':verificar_legado}[sys.argv[1]]()
