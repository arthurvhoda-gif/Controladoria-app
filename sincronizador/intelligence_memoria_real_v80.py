# -*- coding: utf-8 -*-
"""Gera nova previa auditada e registra memoria separada. Sem envio."""
import argparse
from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))


def carregar(nome,p):
    spec=importlib.util.spec_from_file_location(nome,p)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--registrar-nova-previa',action='store_true',required=True); p.parse_args()
    etapa='configuracao'
    try:
        mem=carregar('_mem_real_motor',REPO/'backend'/'intelligence_memoria_real_v80.py')
        previa=carregar('_mem_real_previa',REPO/'sincronizador'/'intelligence_previa_definitiva_v80.py')
        extrator=carregar('_mem_real_extrator',REPO/'sincronizador'/'intelligence_executor_v80.py')
        pasta=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve(strict=True)
        raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'/'PREVIAS_DEFINITIVAS').resolve()
        mem.exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(pasta) and not pasta.is_relative_to(raiz),'MEM_REAL_PASTA')
        etapa='extracao'; d,a,n,s,m,c=extrator.extrair_local_com_cobertura(pasta)
        etapa='auditoria'; r=previa.motor.gerar_previa(registros=d,agenda=a,nomes=n,sem_aba=s,manifesto=m,cobertura=c,hoje=date.today())
        etapa='publicacao'; destino=previa.publicar(raiz,r)
        if r['estado']!='PREVIA_LOCAL_AUDITADA':
            print('MEMORIA NAO REGISTRADA - SEM BASE AUDITADA'); print('Pasta privada:',destino); return 0
        etapa='memoria'; doc=json.loads((destino/'PREVIA_AUDITADA.json').read_text(encoding='utf-8'))
        from intelligence_agendamento_v80 import atomico
        db=sqlite3.connect(raiz/'MEMORIA_LOCAL_REAL_V80.sqlite3',timeout=30)
        try: res=mem.registrar(db,doc)
        finally: db.close()
        atomico(destino/'MEMORIA_INVESTIGACOES.json',json.dumps(res,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8'))
        print('MEMORIA_LOCAL_REAL_REGISTRADA'); print('Competencia:',r['selecao']['competencia'])
        for tipo,g in res['escopos'].items(): print(tipo, '| casos:',g['casos_atual'],'|',g['contagem'])
        print('SEM ENVIO'); print('Pasta privada:',destino); return 0
    except Exception as e:
        print('MEMORIA BLOQUEADA:',etapa,type(e).__name__,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
