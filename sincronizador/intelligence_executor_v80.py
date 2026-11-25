# -*- coding: utf-8 -*-
"""Homologacao em comando unico. Leitura de planilhas e Neon ficticio. Sem envio."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import quote
import uuid

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_executor_v80 import executar_ciclo_v80
from intelligence_fonte_app_v80 import carregar_app_v80, ROLE, ErroFonteApp
from intelligence_auditoria_v80 import ErroAuditoria, exigir

HOST='ep-royal-union-acmuwc5a.sa-east-1.aws.neon.tech'
BANCO='neondb'

def extrair_local(pasta):
    from intelligence_ensaio_v80 import assinatura
    from auditar_planilhas import extrair_base, extrair_condominio, canon, LeitorXlsm, texto, data_excel
    from custos_importacao_v77 import validar_lote
    base=(pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    exigir(base.parent==pasta,'CADASTRO_FORA_DA_PASTA')
    hb=assinatura(base); mapa,_,_,_=extrair_base(base)
    arquivos=[(pasta/a).resolve(strict=True) for _,a in mapa]
    exigir(len(mapa)==10 and len({canon(n) for n,_ in mapa})==10 and len(set(arquivos))==10 and all(a.parent==pasta and a!=base and a.suffix.lower()=='.xlsm' for a in arquivos),'CADASTRO_LOCAL')
    nomes={i:n for i,(n,_) in enumerate(mapa,1)}
    hashes={a:assinatura(a) for a in arquivos}; registros=[]; agenda=[]; sem_aba=[]; pendentes=0
    for i,a in enumerate(arquivos,1):
        f=extrair_condominio(a,nomes[i]); exigir(not any(f[k] for k in ('sem_id','duplicados','datas_invalidas','valores_invalidos')),'INTEGRIDADE_PLANILHA')
        registros.extend(f['classificadas'].values()); pendentes+=f['pendentes']
        leitor=LeitorXlsm(a)
        try:
            if 'PRAZOS' not in leitor.abas: sem_aba.append(i); continue
            for linha,d in leitor.linhas('PRAZOS',{'A','B','C','D'}):
                if linha<=1 or not texto(d.get('A')): continue
                agenda.append(dict(condominio_id=i,linha=linha,nome=texto(d['A']),periodicidade=texto(d.get('B')),ultima=data_excel(d.get('C')),proxima=data_excel(d.get('D'))))
        finally: leitor.fechar()
    exigir(assinatura(base)==hb and all(assinatura(a)==h for a,h in hashes.items()),'PLANILHAS_ALTERADAS')
    dados=validar_lote(registros,{n:i for i,n in nomes.items()})
    manifesto=dict(hash_cadastro=hb,arquivos=[dict(condominio_id=i,arquivo=a.name,sha256=hashes[a]) for i,a in enumerate(arquivos,1)],sem_aba_prazos=sem_aba,nao_classificados_excluidos=pendentes,lancamentos_validados=len(dados))
    return dados,agenda,nomes,sem_aba,manifesto


def serializar(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2).encode('utf-8')


def publicar(raiz,r,snapshot,manifesto):
    exigir(r['estado']=='APROVADO_HOMOLOGACAO_MISTA','PUBLICACAO_NAO_AUTORIZADA')
    run=uuid.uuid4().hex; utc=datetime.now(timezone.utc).isoformat()
    snap=serializar(snapshot); c=r['central']; p=r['carteira']; a=r['auditoria_local']; b=r['auditoria_app']
    r.update(execucao=run,utc=utc,manifesto_planilhas=manifesto,sha256_snapshot_app=hashlib.sha256(snap).hexdigest())
    local=r['local_para_memoria']; local.update(manifesto,execucao=run,utc=utc,nomes_locais=r['nomes_locais'])
    linhas=['HAIZE INTELLIGENCE V8.0 | HOMOLOGACAO PRIVADA','PLANILHAS REAIS (SIMULACAO); NEON FICTICIO; SEM ENVIO',f'Referencia: {c["data_referencia"]} | Competencia historica: {c["competencia"]}',
            'Fontes: '+', '.join(f'{k}={v}' for k,v in c['fontes'].items()),
            f'Planilhas: {a["decisoes"]} candidatos | App FICTICIO: {b["decisoes"]} candidatos',
            f'Impacto historico em centavos: {a["impacto_historico_centavos"]} (nao economia)',
            f'Grupos executivos: {len(p["executivo"])} | Fila: {len(p["fila"])} | P1: {p["total_p1"]}', '', 'PRIORIDADES EXECUTIVAS']
    for g in p['executivo']:
        origem=g['origem']; nomes=r['nomes_locais'] if origem=='planilhas' else r['nomes_app']
        linhas.append(f'P{g["prioridade"]} | {"PLANILHAS REAIS - SIMULACAO" if origem=="planilhas" else "APP FICTICIO"} | {nomes.get(g["condominio_id"],"Sem vinculo / multiconominio")} | {g["tema"]}')
        for d in g['acoes']: linhas.append(f'  P{d["prioridade"]} {d["chave"]}: {d["fato"]} | {d["acao"]}')
        linhas.append('')
    linhas.extend(['LIMITES',*r['limites'],'Nenhuma economia comprovada. Fila integral no JSON.','CONFIDENCIAL.'])
    raiz.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.ciclo-',dir=raiz)); destino=raiz/('ciclo_'+run)
    try:
        (tmp/'PARECER_EXECUTIVO.txt').write_text('\n'.join(linhas),encoding='utf-8')
        (tmp/'CICLO_AUDITADO.json').write_bytes(serializar(r))
        (tmp/'SNAPSHOT_APP_FICTICIO.json').write_bytes(snap)
        (tmp/'EVIDENCIAS_CENTRAL.json').write_bytes(serializar(local))
        tmp.rename(destino)
    except BaseException:
        shutil.rmtree(tmp,ignore_errors=True); raise
    return destino


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--competencia',required=True); p.add_argument('--homologar',required=True,action='store_true')
    p.add_argument('--planilhas',type=Path,default=Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS')
    a=p.parse_args(); etapa='configuracao'
    try:
        import certifi
        exigir(ROLE=='haize_intelligence_v80_ro','CONECTOR_DESATUALIZADO')
        pasta=a.planilhas.resolve(strict=True); raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve()
        exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(pasta) and not pasta.is_relative_to(raiz),'PASTA_PRIVADA_INVALIDA')
        etapa='extracao_planilhas'; dados,agenda,nomes,sem_aba,manifesto=extrair_local(pasta)
        etapa='extracao_app'; print('Destino exclusivo de homologacao:',HOST)
        senha=getpass.getpass('Senha exclusiva da Intelligence: ')
        dsn='postgresql://'+ROLE+':'+quote(senha,safe='')+'@'+HOST+'/'+BANCO
        try: snapshot=carregar_app_v80(dsn=dsn,host=HOST,banco=BANCO,ca=certifi.where())
        finally: del senha,dsn
        etapa='investigacao_e_auditorias'; r=executar_ciclo_v80(registros=dados,agenda=agenda,nomes=nomes,sem_aba=sem_aba,competencia=a.competencia,snapshot=snapshot)
        etapa='publicacao_local'; destino=publicar(raiz,r,snapshot,manifesto)
        print(r['estado']); print('Lancamentos historicos:',len(dados)); print('Linhas agenda:',len(agenda))
        print('Auditoria local:',r['auditoria_local']['estado']); print('Auditoria app:',r['auditoria_app']['estado'])
        print('Decisoes planilhas:',r['auditoria_local']['decisoes']); print('Decisoes app FICTICIO:',r['auditoria_app']['decisoes'])
        print('Grupos executivos:',len(r['carteira']['executivo'])); print('Grupos na fila:',len(r['carteira']['fila']))
        print('SEM ENVIO - HOMOLOGACAO MISTA'); print('Pasta privada:',destino); return 0
    except (ErroFonteApp,ErroAuditoria) as e:
        print('CICLO BLOQUEADO:',etapa,str(e),file=sys.stderr)
    except Exception as e:
        print('CICLO BLOQUEADO:',etapa,type(e).__name__,file=sys.stderr)
    return 1

if __name__=='__main__': sys.exit(main())
