# -*- coding: utf-8 -*-
"""Gera carteira local a partir de EVIDENCIAS_CENTRAL.json. Sem rede/envio."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil
import uuid

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_prescritiva_v80 import priorizar_v80


def executar(arquivo,limite):
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve(strict=True)
    origem=arquivo.resolve(strict=True)
    if not origem.is_relative_to(raiz) or origem.is_relative_to(REPO) or origem.name!='EVIDENCIAS_CENTRAL.json':
        raise ValueError('Origem fora da pasta privada ou nome inválido.')
    if origem.stat().st_size>100_000_000: raise ValueError('Arquivo muito grande.')
    dados=origem.read_bytes(); central=json.loads(dados)
    r=priorizar_v80(central,limite)
    r['sha256_origem']=hashlib.sha256(dados).hexdigest(); r['execucao_central']=central.get('execucao'); r['data_referencia']=central.get('data_referencia'); r['competencia']=central.get('competencia')
    nomes=central.get('nomes_locais',{})
    linhas=['HAIZE INTELLIGENCE | CARTEIRA EXECUTIVA PRIVADA',
            'ENSAIO - sem execução de ações e sem envio.',
            f'Referência da extração: {r["data_referencia"]}; competência histórica: {r["competencia"]}. Não constitui atualização das fontes.',
            'Fontes: '+', '.join(f'{k}={v}' for k,v in r['fontes'].items()),
            f'{r["total_casos"]} casos em {r["total_grupos"]} grupos; {r["total_p1"]} casos P1.',
            f'Grupos executivos: {len(r["executivo"])}; fila: {len(r["fila"])}.', '', 'PRIORIDADES EXECUTIVAS']
    for g in r['executivo']:
        nome=nomes.get(str(g['condominio_id']),str(g['condominio_id'])) if g['origem']=='planilhas' else str(g['condominio_id'])
        linhas.append(f'P{g["prioridade"]} | {g["origem"]} | {nome} | {g["tema"]} | {g["quantidade_casos"]} casos')
        for a in g['acoes']:
            linhas.append(f'  P{a["prioridade"]} {a["chave"]}: {a["acao"]}')
        linhas.append('')
    linhas+=['Fila integral preservada no JSON.','Sem premissas documentadas para simulação de benefícios; não estimar economia.',*r['limites'],'CONFIDENCIAL']
    tmp=Path(tempfile.mkdtemp(prefix='.prescritiva-',dir=raiz)); destino=raiz/('prescritiva_'+uuid.uuid4().hex)
    try:
        (tmp/'CARTEIRA_EXECUTIVA.txt').write_text('\n'.join(linhas),encoding='utf-8')
        (tmp/'CARTEIRA_COMPLETA.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.rename(destino)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise
    print('ENSAIO PRESCRITIVO V8.0 - SEM ENVIO')
    print('Casos originais:',r['total_casos']); print('Grupos consolidados:',r['total_grupos'])
    print('Casos P1 preservados:',r['total_p1']); print('Grupos executivos:',len(r['executivo'])); print('Grupos na fila:',len(r['fila']))
    print('Pasta privada:',destino)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--evidencias',required=True,type=Path); p.add_argument('--limite',type=int,default=5)
    a=p.parse_args()
    try: executar(a.evidencias,a.limite)
    except Exception as e:
        print('EXECUCAO BLOQUEADA:',type(e).__name__,file=sys.stderr); sys.exit(1)
