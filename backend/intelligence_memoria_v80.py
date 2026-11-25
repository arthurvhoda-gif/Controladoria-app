# -*- coding: utf-8 -*-
"""Memória local, transacional, de investigações das planilhas V8.0.
Não confirma resolução ou economia; não altera fontes nem acessa rede.
"""
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from intelligence_prescritiva_v80 import priorizar_v80

APP_ID = 0x48414938
MAX_BYTES = 100_000_000


def _json(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _utc(s):
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        raise ValueError('Execução sem fuso horário.')
    return t.astimezone(timezone.utc).isoformat(timespec='microseconds')


def _preparar(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Arquivo inválido ou acima do limite.')
    def pares(ps):
        d = {}
        for k, v in ps:
            if k in d: raise ValueError('Chave JSON duplicada.')
            d[k] = v
        return d
    c = json.loads(raw, object_pairs_hook=pares)
    priorizar_v80(c)
    run = c.get('execucao')
    if not isinstance(run, str) or not re.fullmatch(r'[0-9a-f]{32}', run):
        raise ValueError('Identificador de execução inválido.')
    utc = _utc(c['utc'])
    dia = date.fromisoformat(c['data_referencia'])
    mes = date.fromisoformat(c['competencia']+'-01')
    if dia.isoformat()!=c['data_referencia'] or mes.strftime('%Y-%m')!=c['competencia'] or mes>dia.replace(day=1):
        raise ValueError('Referência inválida.')
    if type(c.get('simulacao')) is not bool:
        raise ValueError('Modo inválido.')
    if any(c['fontes'][f]!='indisponivel' for f in ('financeiro','operacional','compras')):
        raise ValueError('Memória desta etapa aceita apenas ensaio local; integração app ainda não homologada.')
    nomes=c.get('nomes_locais'); arquivos=c.get('arquivos')
    if not isinstance(nomes,dict) or not nomes or any(not re.fullmatch(r'[1-9][0-9]*',k) or not isinstance(v,str) or not v.strip() for k,v in nomes.items()) or len({v.casefold().strip() for v in nomes.values()})!=len(nomes):
        raise ValueError('Cadastro local inválido.')
    if not isinstance(arquivos,list) or len(arquivos)!=len(nomes):
        raise ValueError('Manifesto de fontes ausente.')
    manifesto={}
    for a in arquivos:
        i=str(a['condominio_id']); nome=a['arquivo']; h=a['sha256']
        if i not in nomes or i in manifesto or not isinstance(nome,str) or not nome or not isinstance(h,str) or not re.fullmatch(r'[0-9a-f]{64}',h):
            raise ValueError('Manifesto inválido.')
        manifesto[i]=nome
    # Escopo conservador: não compara mudança de competência, modo, IDs, nomes
    # ou arquivos. Hash dos conteúdos pode variar sem mudar o escopo.
    scope=_hash(_json([c['competencia'],c['simulacao'],nomes,manifesto]))
    r=c.get('resultados',{}); detalhes={}
    def inserir(k,v):
        if k in detalhes: raise ValueError('Evidência duplicada.')
        detalhes[k]=v
    for x in r.get('historico',{}).get('casos',[]):
        inserir(f"historico:{x['condominio_id']}:{x['categoria']}",x)
    for x in r.get('manutencao',{}).get('agenda',[]):
        inserir(f"agenda:{x['condominio_id']}:{x['evidencia']['linha']}",x)
    for x in r.get('manutencao',{}).get('recorrencias',[]):
        inserir(f"recorrencia:{x['condominio_id']}:{x['categoria']}:{x['descricao']}",x)
    casos={}
    for d in c['decisoes']:
        k=d['chave']
        if d['origem']!='planilhas' or str(d['condominio_id']) not in nomes or k not in detalhes:
            raise ValueError('Caso sem evidência local correspondente.')
        if detalhes[k]['condominio_id'] != d['condominio_id']:
            raise ValueError('Condomínio divergente da evidência.')
        body=_json({'decisao':d,'evidencia':detalhes[k]})
        casos[k]=(_hash(body),body)
    return c,run,utc,scope,casos


def registrar_memoria_v80(db, raw):
    """Recebe conexão dedicada e bytes do relatório central. Commit atômico.
    Ausência de caso nunca significa solução. Reaparecimento não é caso novo.
    """
    c,run,utc,scope,casos=_preparar(raw)
    sha=hashlib.sha256(raw).hexdigest()
    if not isinstance(db,sqlite3.Connection) or db.in_transaction:
        raise ValueError('Conexão dedicada sem transação pendente obrigatória.')
    if len(db.execute('PRAGMA database_list').fetchall())!=1:
        raise ValueError('Banco com anexos não permitido.')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('BEGIN IMMEDIATE')
    try:
        aid=db.execute('PRAGMA application_id').fetchone()[0]
        versao=db.execute('PRAGMA user_version').fetchone()[0]
        objetos={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        if aid==0 and versao==0 and not objetos:
            db.execute('CREATE TABLE runs(seq INTEGER PRIMARY KEY, run TEXT NOT NULL UNIQUE, sha TEXT NOT NULL, scope TEXT NOT NULL, utc TEXT NOT NULL, fontes TEXT NOT NULL, resumo TEXT NOT NULL)')
            db.execute('CREATE TABLE casos(seq INTEGER NOT NULL REFERENCES runs(seq), chave TEXT NOT NULL, sha TEXT NOT NULL, corpo TEXT NOT NULL, PRIMARY KEY(seq,chave))')
            db.execute('CREATE INDEX idx_runs_scope ON runs(scope,seq)')
            db.execute(f'PRAGMA application_id={APP_ID}')
            db.execute('PRAGMA user_version=1')
        elif aid!=APP_ID or versao!=1 or objetos!={'runs','casos','idx_runs_scope'}:
            raise ValueError('Banco não pertence à memória V8.0 ou schema incompatível.')
        existente=db.execute('SELECT sha,resumo FROM runs WHERE run=?',(run,)).fetchone()
        if existente:
            if existente[0]!=sha: raise ValueError('Mesmo ID com conteúdo diferente.')
            res=json.loads(existente[1]); res['reprocessamento']=True
            db.commit(); return res
        anterior=db.execute('SELECT seq,run,utc FROM runs WHERE scope=? ORDER BY seq DESC LIMIT 1',(scope,)).fetchone()
        if anterior and utc<=anterior[2]:
            raise ValueError('Execução fora da ordem cronológica do escopo.')
        prev={}; ultimos={}
        # Última observação de cada chave, inclusive antes de uma ausência.
        for k,h,b,s in db.execute('SELECT c.chave,c.sha,c.corpo,c.seq FROM casos c JOIN runs r ON r.seq=c.seq JOIN (SELECT c2.chave,MAX(c2.seq) AS ultima FROM casos c2 JOIN runs r2 ON r2.seq=c2.seq WHERE r2.scope=? GROUP BY c2.chave) u ON u.chave=c.chave AND u.ultima=c.seq WHERE r.scope=?',(scope,scope)):
            if _hash(b)!=h: raise ValueError('Falha de integridade em memória anterior.')
            ultimos[k]=(h,b,s)
            if anterior and s==anterior[0]: prev[k]=(h,b,s)
        eventos=[]
        for k,(h,b) in sorted(casos.items()):
            old=ultimos.get(k)
            estado='novo' if old is None else 'reaparecido' if k not in prev else 'persistente' if old[0]==h else 'alterado'
            eventos.append({'chave':k,'estado':estado,'sha_atual':h,'sha_anterior':old[0] if old else None})
        for k,(h,b,s) in sorted(prev.items()):
            if k in casos: continue
            prefixo=k.split(':',1)[0]
            fs={'historico':('historico',),'agenda':('agenda',),'recorrencia':('agenda','historico')}[prefixo]
            indisponivel=any(c['fontes'][f]=='indisponivel' for f in fs)
            eventos.append({'chave':k,'estado':'fonte_indisponivel' if indisponivel else 'nao_observado','sha_atual':None,'sha_anterior':h})
        contagem={s:sum(e['estado']==s for e in eventos) for s in ('novo','persistente','alterado','reaparecido','nao_observado','fonte_indisponivel')}
        res={'versao':'8.0-memoria-1','execucao':run,'sha256_origem':sha,'escopo':scope,'competencia':c['competencia'],'data_referencia':c['data_referencia'],'execucao_anterior':anterior[1] if anterior else None,'fontes':c['fontes'],'contagem':contagem,'casos_atual':len(casos),'eventos':eventos,'reprocessamento':False,'economia_comprovada_centavos':None,'limites':['Comparação somente dentro do mesmo cadastro, arquivos, competência e modo.','Mudança indica diferença em decisão ou evidência registrada, não necessariamente agravamento.','Não observado ou fonte indisponível não confirma resolução.','Não mede eficácia causal nem altera parâmetros automaticamente.']}
        seq=db.execute('INSERT INTO runs(run,sha,scope,utc,fontes,resumo) VALUES(?,?,?,?,?,?)',(run,sha,scope,utc,_json(c['fontes']),_json(res))).lastrowid
        db.executemany('INSERT INTO casos VALUES(?,?,?,?)',((seq,k,h,b) for k,(h,b) in sorted(casos.items())))
        db.commit(); return res
    except BaseException:
        db.rollback(); raise
