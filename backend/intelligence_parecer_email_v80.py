# -*- coding: utf-8 -*-
"""Prepara mensagem privada de dados reais, sem rede nem envio."""
from contextlib import closing
import hashlib
import json
import re
import sqlite3
from datetime import date
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

DESTINO='app1haize@gmail.com'
ESTADOS=('novo','persistente','alterado','reaparecido','nao_observado')

def exigir(ok,codigo):
    if not ok: raise ValueError(codigo)

def serial(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))

def sha(x):
    return hashlib.sha256(serial(x).encode('utf-8')).hexdigest()

def moeda(v):
    exigir(type(v) is int,'PARECER_VALOR')
    a,b=divmod(abs(v),100)
    return ('-' if v<0 else '')+'R$ '+f'{a:,}'.replace(',','.')+f',{b:02d}'

def conferir_memoria(banco,doc,mem):
    """Confere registro já existente. Jamais cria ou altera o banco."""
    p=Path(banco)
    exigir(p.is_file() and not p.is_symlink(),'PARECER_MEMORIA_AUSENTE')
    exigir(mem['execucao']==doc['execucao'] and mem['referencia']==doc['referencia'] and mem['sha256_previa']==sha(doc),'PARECER_MEMORIA_DIVERGENTE')
    with closing(sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        exigir(db.execute('PRAGMA application_id').fetchone()[0]==0x4841493A and db.execute('PRAGMA user_version').fetchone()[0]==1,'PARECER_BANCO')
        row=db.execute('SELECT sha,resumo FROM ciclos WHERE run=?',(doc['execucao'],)).fetchone()
        exigir(row is not None and row[0]==sha(doc),'PARECER_CICLO_NAO_REGISTRADO')
        salvo=json.loads(row[1]); a=dict(mem); a.pop('reprocessamento',None); salvo.pop('reprocessamento',None)
        exigir(a==salvo,'PARECER_MEMORIA_DIVERGENTE')
    return True

def preparar(doc,mem,hoje):
    exigir(type(hoje) is date and doc['referencia']==hoje.isoformat(),'PARECER_REFERENCIA')
    run=doc['execucao']; exigir(isinstance(run,str) and re.fullmatch('[0-9a-f]{32}',run),'PARECER_ID')
    exigir(doc['versao']=='8.0-previa-local-1' and doc['estado']=='PREVIA_LOCAL_AUDITADA' and doc['envio_autorizado'] is False and doc['app_definitivo']=='indisponivel_nao_publicado' and doc['economia_comprovada_centavos'] is None,'PARECER_ESCOPO')
    c=doc['central']; a=doc['auditoria']; p=doc['carteira']; s=doc['selecao']; cov=doc['cobertura']; nomes=doc['nomes']
    exigir(s['fechamento_confirmado'] is False and c['simulacao'] is True and c['data_referencia']==doc['referencia'] and c['competencia']==s['competencia'] and c['fontes']['historico']=='simulacao_cobertura_nao_confirmada' and all(c['fontes'][k]=='indisponivel' for k in ('financeiro','operacional','compras')) and not c['contextos'],'PARECER_FONTES')
    exigir(a['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and a['economia_comprovada_centavos'] is None and p['economia_comprovada_centavos'] is None and c['economia_comprovada_centavos'] is None,'PARECER_AUDITORIA')
    exigir(mem['versao']=='8.0-memoria-real-1' and mem['execucao']==run and mem['referencia']==doc['referencia'] and mem['sha256_previa']==sha(doc) and mem['economia_comprovada_centavos'] is None,'PARECER_MEMORIA')
    exigir(cov['referencia']==doc['referencia'] and cov['nomes']==nomes and cov['economia_comprovada_centavos'] is None and cov['manifesto']=={k:doc['manifesto'][k] for k in ('hash_cadastro','arquivos')},'PARECER_COBERTURA')
    ds={d['chave']:d for d in c['decisoes']}; grupos=p['executivo']+p['fila']; ks=[k for g in grupos for k in g['chaves']]
    exigir(len(ds)==len(c['decisoes'])==p['total_casos']==a['decisoes']==len(ks)==len(set(ks)) and set(ks)==set(ds) and all(d['origem']=='planilhas' and str(d['condominio_id']) in nomes and d['economia_comprovada_centavos'] is None for d in ds.values()) and all(g['prioridade']!=1 for g in p['fila']),'PARECER_CARTEIRA')
    exigir(sum(g['casos_atual'] for g in mem['escopos'].values())==len(ds),'PARECER_MEMORIA_CONTAGEM')
    for g in mem['escopos'].values():
        exigir(set(g['contagem'])==set(ESTADOS) and all(type(v) is int and v>=0 for v in g['contagem'].values()) and sum(g['contagem'][k] for k in ESTADOS if k!='nao_observado')==g['casos_atual'],'PARECER_MEMORIA_CONTAGEM')
    cl=cov['totais']['classificado']; nc=cov['totais']['nao_classificado']
    linhas=['HAIZE INTELLIGENCE | Parecer semanal privado (prévia local)','Planilhas reais; investigação exploratória, sem fechamento contábil confirmado.','App definitivo indisponível: compras, pagamentos e serviços do app não avaliados.','Nenhuma informação fictícia do app. Nenhuma economia comprovada.','',f'Referência: {hoje.isoformat()} | janela histórica: {", ".join(s["janela"])}',f'Último mês calendário encerrado: {s["ultimo_mes_calendario_encerrado"]}',f'Condomínios com positivos nos seis meses: {len(s["condominios_com_positivo_em_seis_meses"])}/{len(nomes)}','', 'COBERTURA E QUALIDADE',f'Classificados: {cl["registros"]} | positivos brutos: {moeda(cl["positivos_centavos"])}',f'Não classificados: {nc["registros"]} | positivos brutos: {moeda(nc["positivos_centavos"])}',f'Grupos candidatos a duplicidade: {len(cov["candidatos_duplicidade"])} (não comprovados).',f'Datas inválidas: {cov["datas_invalidas"]} | futuras: {cov["datas_futuras"]}.']
    for x in cov['cobertura']:
        linhas.append(f'{nomes[str(x["condominio_id"])]}: último mês positivo classificado {x["ultimo_mes_classificado_positivo"] or "não observado"}')
    for x in cov['sinais']:
        linhas.append(f'Sinal temporal {x["mes"]}: {moeda(x["positivos_nao_classificados_centavos"])} versus mediana observada {moeda(x["mediana_tres_meses_centavos"])}.')
        gs=[g for g in cov['concentracoes'] if g['mes']==x['mes']]
        if gs:
            g=max(gs,key=lambda y:y['positivos_nao_classificados_centavos']); linhas.append(f'Maior concentração: {nomes[str(g["condominio_id"])]} | {moeda(g["positivos_nao_classificados_centavos"])}')
    linhas.extend(['Valores de linhas, não despesa líquida confirmada. Não somar com pagamentos do app.','Atualizar competências, conferir documentos e classificações.','', 'EVOLUÇÃO DAS INVESTIGAÇÕES'])
    for tipo,g in sorted(mem['escopos'].items()):
        linhas.append(f'{tipo}: '+', '.join(f'{k}={g["contagem"][k]}' for k in ESTADOS))
        if g['execucao_anterior'] is None: linhas.append('  Sem ciclo anterior comparável neste escopo.')
    linhas.extend(['Não observado não significa resolvido. Alterado não comprova agravamento.','',f'PRIORIDADES | {p["total_casos"]} candidatos, {len(p["fila"])} grupos em fila'])
    for g in p['executivo']:
        linhas.append(f'P{g["prioridade"]} | {nomes[str(g["condominio_id"])]} | {g["tema"]}')
        for k in g['chaves']:
            d=ds[k]; linhas.extend([f'  {k}: {d["fato"]}',f'  Ação: {d["acao"]}'])
            if d['valor_centavos'] is not None: linhas.append(f'  {moeda(d["valor_centavos"])} | {d["natureza_valor"]}')
            linhas.append('  Limites: '+' '.join(d['hipoteses_nao_comprovadas']))
    linhas.extend(['','Evidências e fila integral preservadas na pasta privada previa_'+run+'.','Confidencial. Não autoriza intervenções nem confirma economia.'])
    msg=EmailMessage(policy=SMTP); msg['From']='HAIZE Intelligence <'+DESTINO+'>'; msg['To']=DESTINO; msg['Subject']='HAIZE INTELLIGENCE | Prévia local '+hoje.isoformat(); msg['Message-ID']='<haize-v80-local-'+hoje.isoformat()+'-'+run+'@gmail.com>'; msg.set_content('\n'.join(linhas)+'\n')
    raw=msg.as_bytes(); exigir(len(raw)<=1024*1024,'PARECER_TAMANHO'); return raw
