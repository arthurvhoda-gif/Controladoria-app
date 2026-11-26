# -*- coding: utf-8 -*-
"""Memoria isolada de previas locais auditadas. Sem rede ou envio."""
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime
from collections import Counter

APP_ID = 0x4841493A
ESTADOS = ('novo','persistente','alterado','reaparecido','nao_observado')


def exigir(ok, codigo):
    if not ok:
        raise ValueError(codigo)


def serial(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',',':'))


def hash_texto(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def preparar(r):
    exigir(r['versao']=='8.0-previa-local-1' and r['estado']=='PREVIA_LOCAL_AUDITADA' and r['envio_autorizado'] is False and r['economia_comprovada_centavos'] is None and r['app_definitivo']=='indisponivel_nao_publicado','MEM_REAL_ESCOPO')
    run=r['execucao']; exigir(isinstance(run,str) and re.fullmatch('[0-9a-f]{32}',run),'MEM_REAL_ID')
    dia=r['referencia']; exigir(date.fromisoformat(dia).isoformat()==dia,'MEM_REAL_DATA')
    utc=datetime.fromisoformat(r['utc']); exigir(utc.utcoffset() is not None and utc.utcoffset().total_seconds()==0,'MEM_REAL_UTC')
    utc=utc.isoformat(timespec='microseconds')
    s=r['selecao']; c=r['central']; a=r['auditoria']; p=r['carteira']; nomes=r['nomes']; m=r['manifesto']
    exigir(s['fechamento_confirmado'] is False and c['simulacao'] is True and c['competencia']==s['competencia'] and c['data_referencia']==dia and c['economia_comprovada_centavos'] is None and not c['contextos'],'MEM_REAL_REFERENCIA')
    exigir(c['fontes']['historico']=='simulacao_cobertura_nao_confirmada' and all(c['fontes'][k]=='indisponivel' for k in ('financeiro','operacional','compras')),'MEM_REAL_FONTES')
    exigir(a['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and a['decisoes']==p['total_casos']==len(c['decisoes']) and a['economia_comprovada_centavos'] is None,'MEM_REAL_AUDITORIA')
    from intelligence_auditoria_v80 import auditar_carteira_v80
    exigir(auditar_carteira_v80(c,p) is True,'MEM_REAL_CARTEIRA')
    # IDs locais dependem da ordem do cadastro. Alteracao de cadastro/arquivo
    # cria escopo distinto, mas mudanca de conteudo nao cria novo escopo.
    arquivos={str(x['condominio_id']):x['arquivo'] for x in m['arquivos']}
    exigir(len(nomes)==10 and set(arquivos)==set(map(str,nomes)) and len(set(nomes.values()))==10,'MEM_REAL_CADASTRO')
    cadastro=[[str(k),v,arquivos[str(k)]] for k,v in sorted(nomes.items(),key=lambda x:int(x[0]))]
    escopos={}
    for tipo in ('historico','recorrencia','agenda'):
        if tipo in ('agenda','recorrencia') and c['fontes']['agenda']=='indisponivel': continue
        esc=[tipo,cadastro]
        if tipo!='agenda': esc.append(s['janela'])
        if tipo!='historico': esc.append(sorted(m['sem_aba_prazos']))
        escopos[tipo]=(hash_texto(serial(esc)),{})
    chaves=set()
    for d in c['decisoes']:
        k=d['chave']; tipo=k.split(':',1)[0]; cid=d['condominio_id']
        exigir(k not in chaves and d['origem']=='planilhas' and tipo in escopos and str(cid) in arquivos and d['economia_comprovada_centavos'] is None,'MEM_REAL_DECISAO')
        chaves.add(k)
        # Agenda: inclui nome para que linha reutilizada por outra atividade
        # nao herde identidade. Mudanca de linha pode gerar nova ocorrencia.
        if tipo=='agenda': k=serial([k,d['referencias']['nome']])
        corpo=serial(d); escopos[tipo][1][k]=(hash_texto(corpo),corpo)
    return run,dia,utc,hash_texto(serial(r)),escopos


def registrar(db,r):
    run,dia,utc,sha,escopos=preparar(r)
    exigir(isinstance(db,sqlite3.Connection) and not db.in_transaction and len(db.execute('PRAGMA database_list').fetchall())==1,'MEM_REAL_CONEXAO')
    db.execute('PRAGMA foreign_keys=ON'); db.execute('BEGIN IMMEDIATE')
    try:
        aid=db.execute('PRAGMA application_id').fetchone()[0]; ver=db.execute('PRAGMA user_version').fetchone()[0]
        objs={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        if aid==ver==0 and not objs:
            db.execute('CREATE TABLE ciclos(run TEXT PRIMARY KEY,dia TEXT NOT NULL,utc TEXT NOT NULL,sha TEXT NOT NULL,resumo TEXT NOT NULL)')
            db.execute('CREATE TABLE escopos(run TEXT REFERENCES ciclos(run),tipo TEXT,scope TEXT NOT NULL,PRIMARY KEY(run,tipo))')
            db.execute('CREATE TABLE casos(run TEXT,tipo TEXT,chave TEXT,sha TEXT NOT NULL,corpo TEXT NOT NULL,PRIMARY KEY(run,tipo,chave),FOREIGN KEY(run,tipo) REFERENCES escopos(run,tipo))')
            db.execute(f'PRAGMA application_id={APP_ID}'); db.execute('PRAGMA user_version=1')
        else: exigir(aid==APP_ID and ver==1 and objs=={'ciclos','escopos','casos'},'MEM_REAL_BANCO')
        old=db.execute('SELECT sha,resumo FROM ciclos WHERE run=?',(run,)).fetchone()
        if old:
            exigir(old[0]==sha,'MEM_REAL_CICLO_ALTERADO'); out=json.loads(old[1]); out['reprocessamento']=True; db.commit(); return out
        ultimo=db.execute('SELECT dia,utc FROM ciclos ORDER BY utc DESC LIMIT 1').fetchone()
        exigir(not ultimo or (dia>=ultimo[0] and utc>ultimo[1]),'MEM_REAL_ORDEM')
        out=dict(versao='8.0-memoria-real-1',execucao=run,referencia=dia,sha256_previa=sha,reprocessamento=False,escopos={},economia_comprovada_centavos=None,limites=['Ausencia nao confirma resolucao.','Alterado indica mudanca na decisao registrada, nao agravamento comprovado.','Mudanca de janela ou cadastro impede comparacao; linha de agenda movida pode mudar identidade.','Memoria de triagem local exploratoria; sem fechamento confirmado.','Cobertura financeira e candidatos a duplicidade ainda nao tem memoria propria.'])
        for tipo,(scope,casos) in escopos.items():
            prev=db.execute('SELECT c.run FROM ciclos c JOIN escopos e ON e.run=c.run WHERE e.tipo=? AND e.scope=? ORDER BY c.utc DESC LIMIT 1',(tipo,scope)).fetchone()
            ult={}
            for k,h,b,rr in db.execute('SELECT a.chave,a.sha,a.corpo,a.run FROM casos a JOIN escopos e ON e.run=a.run AND e.tipo=a.tipo JOIN ciclos c ON c.run=a.run WHERE a.tipo=? AND e.scope=? ORDER BY c.utc DESC',(tipo,scope)):
                if k not in ult:
                    exigir(hash_texto(b)==h,'MEM_REAL_CORPO'); ult[k]=(h,rr)
            ev=[]
            for k,(h,b) in sorted(casos.items()):
                u=ult.get(k); estado='novo' if u is None else 'reaparecido' if u[1]!=prev[0] else 'persistente' if u[0]==h else 'alterado'
                ev.append(dict(chave=k,estado=estado,sha_atual=h,sha_anterior=u[0] if u else None))
            if prev:
                for k,(h,rr) in sorted(ult.items()):
                    if rr==prev[0] and k not in casos: ev.append(dict(chave=k,estado='nao_observado',sha_atual=None,sha_anterior=h))
            counts=Counter(x['estado'] for x in ev)
            out['escopos'][tipo]=dict(escopo=scope,execucao_anterior=prev[0] if prev else None,casos_atual=len(casos),contagem={k:counts[k] for k in ESTADOS},eventos=ev)
        db.execute('INSERT INTO ciclos VALUES(?,?,?,?,?)',(run,dia,utc,sha,serial(out)))
        for tipo,(scope,casos) in escopos.items():
            db.execute('INSERT INTO escopos VALUES(?,?,?)',(run,tipo,scope)); db.executemany('INSERT INTO casos VALUES(?,?,?,?,?)',((run,tipo,k,h,b) for k,(h,b) in sorted(casos.items())))
        db.commit(); return out
    except BaseException:
        db.rollback(); raise
