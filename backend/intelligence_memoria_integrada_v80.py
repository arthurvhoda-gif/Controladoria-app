# -*- coding: utf-8 -*-
"""Memória da homologação mista V8.0. Sem rede, credenciais ou envio.
Registra apenas artefatos de ciclos aprovados. Não comprova resolução ou economia.
"""
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import date
from intelligence_memoria_v80 import _preparar, _json, _hash, _utc, MAX_BYTES
from intelligence_auditoria_app_v80 import auditar_app_v80
from intelligence_prescritiva_v80 import priorizar_v80
from intelligence_auditoria_v80 import exigir

APP_ID = 0x48414939
FICTICIOS = {'Condominio Ficticio Alfa', 'Condominio Ficticio Beta'}
AMBIENTE = 'homologacao:br-orange-sun-acen1dex'
ESTADOS = ('novo','persistente','alterado','reaparecido','nao_observado')


def _ler(raw):
    exigir(isinstance(raw,bytes) and 0<len(raw)<=MAX_BYTES,'MEM_ARQUIVO')
    def pares(ps):
        d={}
        for k,v in ps:
            exigir(k not in d,'MEM_JSON_DUPLICADO'); d[k]=v
        return d
    def invalido(v): raise ValueError('MEM_JSON_NAO_FINITO')
    return json.loads(raw,object_pairs_hook=pares,parse_constant=invalido)


def _preparar_ciclo(raw,local_raw,snap_raw):
    c=_ler(raw); local=_ler(local_raw); snap=_ler(snap_raw)
    exigir(c['versao']=='8.0-executor-homologacao-1' and c['estado']=='APROVADO_HOMOLOGACAO_MISTA','MEM_CICLO')
    exigir(c['local_para_memoria']==local,'MEM_LOCAL_DIVERGENTE')
    exigir(c['sha256_snapshot_app']==hashlib.sha256(snap_raw).hexdigest(),'MEM_SNAPSHOT_SHA')
    _,run,utc,scope_local,locais=_preparar(local_raw)
    exigir(c['execucao']==run and _utc(c['utc'])==utc,'MEM_IDENTIDADE')
    central=c['central']; carteira=c['carteira']; dia=central['data_referencia']
    exigir(date.fromisoformat(dia).isoformat()==dia and local['data_referencia']==snap['data_referencia']==dia and local['competencia']==central['competencia'] and local['simulacao'] is central['simulacao'] is True,'MEM_REFERENCIA')
    exigir(not central['contextos'] and central['economia_comprovada_centavos'] is None,'MEM_ESCOPO')
    exigir(c['nomes_locais']==local['nomes_locais'] and len(c['nomes_locais'])==10 and not set(c['nomes_locais'].values())&FICTICIOS,'MEM_CADASTRO_LOCAL')
    exigir(c['nomes_app']==snap['condominios'] and len(c['nomes_app'])==2 and set(c['nomes_app'].values())==FICTICIOS,'MEM_APP_FICTICIO')
    exigir(all(re.fullmatch(r'[1-9][0-9]*',k) for k in snap['condominios']),'MEM_IDS_APP')
    manifesto=c['manifesto_planilhas']; exigir(all(local.get(k)==v for k,v in manifesto.items()),'MEM_MANIFESTO')
    exigir([d for d in central['decisoes'] if d['origem']=='planilhas']==local['decisoes'],'MEM_DECISOES_LOCAIS')
    exigir({k:v for k,v in central['resultados'].items() if k not in ('financeiro','operacional','compras')}==local['resultados'],'MEM_RESULTADOS_LOCAIS')
    exigir(all(central['fontes'][k]==local['fontes'][k] for k in ('historico','agenda')),'MEM_FONTES_LOCAIS')
    al=c['auditoria_local']; exigir(al['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and al['decisoes']==len(locais) and al['economia_comprovada_centavos'] is None,'MEM_AUDITORIA_LOCAL')
    # Reaudita o app com o snapshot gravado; a auditoria local registrada não
    # é refeita aqui (os .xlsm originais podem ter mudado desde a execução).
    snap['condominios']={int(k):v for k,v in snap['condominios'].items()}
    aa=auditar_app_v80(snap,central,carteira)
    exigir(aa==c['auditoria_app'],'MEM_AUDITORIA_APP')
    priorizar_v80(central)
    r=central['resultados']; evid={}
    def inserir(k,x):
        exigir(k not in evid,'MEM_EVIDENCIA_DUPLICADA'); evid[k]=x
    for x in r['financeiro']['casos']: inserir(f"solicitacao:{x['solicitacao_id']}",x)
    for x in r['compras']['concentracoes']: inserir(f"concentracao:{x['condominio_id']}:{x['categoria']}",x)
    for x in r['compras']['demandas']: inserir(f"demanda:{x['categoria']}:{x['descricao_chave']}",x)
    for x in r['operacional']['casos']: inserir(f"operacional:{x['tipo']}:{x['id']}",x)
    app={}
    for d in central['decisoes']:
        if d['origem']!='app': continue
        k=d['chave']; exigir(k in evid,'MEM_EVIDENCIA_APP')
        body=_json({'decisao':d,'evidencia':evid[k]}); app[k]=(_hash(body),body)
    exigir(len(app)==aa['decisoes'],'MEM_COBERTURA')
    # Cobertura distinta cria escopo distinto. App atual não depende da
    # competência das planilhas; identidade do ambiente é explícita e fixa.
    scopes={
        'planilhas':(_hash(_json(['local-simulado',scope_local,central['fontes']['agenda'],sorted(manifesto['sem_aba_prazos'])])),locais),
        'app_ficticio':(_hash(_json([AMBIENTE,c['nomes_app']])),app)}
    sha=_hash(_json([hashlib.sha256(x).hexdigest() for x in (raw,local_raw,snap_raw)]))
    return run,utc,dia,central['competencia'],sha,scopes


def registrar_ciclo_memoria_v80(db,raw,local_raw,snap_raw):
    run,utc,dia,mes,sha,scopes=_preparar_ciclo(raw,local_raw,snap_raw)
    exigir(isinstance(db,sqlite3.Connection) and not db.in_transaction and len(db.execute('PRAGMA database_list').fetchall())==1,'MEM_CONEXAO')
    db.execute('PRAGMA foreign_keys=ON'); db.execute('BEGIN IMMEDIATE')
    try:
        aid=db.execute('PRAGMA application_id').fetchone()[0]; ver=db.execute('PRAGMA user_version').fetchone()[0]
        objs={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        if aid==ver==0 and not objs:
            db.execute('CREATE TABLE runs(run TEXT PRIMARY KEY, utc TEXT NOT NULL, dia TEXT NOT NULL, sha TEXT NOT NULL, resumo TEXT NOT NULL)')
            db.execute('CREATE TABLE fontes(run TEXT NOT NULL REFERENCES runs(run), origem TEXT NOT NULL, scope TEXT NOT NULL, PRIMARY KEY(run,origem))')
            db.execute('CREATE TABLE casos(run TEXT NOT NULL, origem TEXT NOT NULL, chave TEXT NOT NULL, sha TEXT NOT NULL, corpo TEXT NOT NULL, PRIMARY KEY(run,origem,chave), FOREIGN KEY(run,origem) REFERENCES fontes(run,origem))')
            db.execute('CREATE INDEX ix_fontes_scope ON fontes(origem,scope,run)')
            db.execute(f'PRAGMA application_id={APP_ID}'); db.execute('PRAGMA user_version=1')
        else: exigir(aid==APP_ID and ver==1 and objs=={'runs','fontes','casos','ix_fontes_scope'},'MEM_BANCO_INCOMPATIVEL')
        old=db.execute('SELECT sha,resumo FROM runs WHERE run=?',(run,)).fetchone()
        if old:
            exigir(old[0]==sha,'MEM_RUN_ALTERADO'); res=json.loads(old[1]); res['reprocessamento']=True; db.commit(); return res
        res=dict(versao='8.0-memoria-integrada-1',execucao=run,utc=utc,data_referencia=dia,competencia=mes,sha256_ciclo=sha,reprocessamento=False,origens={},economia_comprovada_centavos=None,limites=['Ausência não comprova resolução.','Alteração pode refletir passagem do tempo, janela ou evidência, não agravamento.','Mudança de escopo não é comparável.','App fictício nunca representa produção.','Auditoria local registrada, não refeita neste importador.'])
        for origem,(scope,casos) in scopes.items():
            prev=db.execute('SELECT r.run,r.utc,r.dia FROM runs r JOIN fontes f ON f.run=r.run WHERE f.origem=? AND f.scope=? ORDER BY r.utc DESC LIMIT 1',(origem,scope)).fetchone()
            exigir(not prev or (utc>prev[1] and dia>=prev[2]),'MEM_ORDEM')
            # Última observação por chave; não confundir ausência com caso novo.
            ult={}
            for k,h,b,rid in db.execute('SELECT c.chave,c.sha,c.corpo,c.run FROM casos c JOIN fontes f ON f.run=c.run AND f.origem=c.origem JOIN runs r ON r.run=c.run WHERE f.origem=? AND f.scope=? ORDER BY r.utc DESC',(origem,scope)):
                if k not in ult:
                    exigir(_hash(b)==h,'MEM_CORPO_ALTERADO'); ult[k]=(h,rid)
            eventos=[]
            for k,(h,b) in sorted(casos.items()):
                anterior=ult.get(k)
                estado='novo' if anterior is None else 'reaparecido' if anterior[1]!=prev[0] else 'persistente' if anterior[0]==h else 'alterado'
                eventos.append(dict(chave=k,estado=estado,sha_atual=h,sha_anterior=anterior[0] if anterior else None))
            for k,(h,rid) in sorted(ult.items()):
                if prev and rid==prev[0] and k not in casos: eventos.append(dict(chave=k,estado='nao_observado',sha_atual=None,sha_anterior=h))
            cont=Counter(e['estado'] for e in eventos)
            res['origens'][origem]=dict(escopo=scope,execucao_anterior=prev[0] if prev else None,casos_atual=len(casos),contagem={k:cont[k] for k in ESTADOS},eventos=eventos)
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run,utc,dia,sha,_json(res)))
        for origem,(scope,casos) in scopes.items():
            db.execute('INSERT INTO fontes VALUES(?,?,?)',(run,origem,scope))
            db.executemany('INSERT INTO casos VALUES(?,?,?,?,?)',((run,origem,k,h,b) for k,(h,b) in sorted(casos.items())))
        db.commit(); return res
    except BaseException:
        db.rollback(); raise
