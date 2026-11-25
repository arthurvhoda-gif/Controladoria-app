# -*- coding: utf-8 -*-
"""Registra ciclo já auditado na memória privada, sem senha, rede ou envio."""
import argparse
from pathlib import Path
import re
import sqlite3
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_memoria_integrada_v80 import registrar_ciclo_memoria_v80, MAX_BYTES


def registrar_pasta(raiz,run):
    if not re.fullmatch(r'[0-9a-f]{32}',run): raise ValueError('MEM_ID')
    raiz=raiz.resolve(strict=True); pasta=(raiz/('ciclo_'+run)).resolve(strict=True)
    if pasta.parent!=raiz or raiz.is_relative_to(REPO): raise ValueError('MEM_PASTA')
    arquivos=[]
    for nome in ('CICLO_AUDITADO.json','EVIDENCIAS_CENTRAL.json','SNAPSHOT_APP_FICTICIO.json'):
        p=(pasta/nome).resolve(strict=True)
        if p.parent!=pasta or p.stat().st_size>MAX_BYTES: raise ValueError('MEM_ARQUIVO')
        arquivos.append(p.read_bytes())
    import json
    if json.loads(arquivos[0]).get('execucao')!=run: raise ValueError('MEM_ID_DIVERGENTE')
    banco=raiz/'MEMORIA_INTEGRADA_V80.sqlite3'
    if banco.is_symlink() or banco.resolve().parent!=raiz: raise ValueError('MEM_BANCO')
    db=sqlite3.connect(banco,timeout=15)
    try: return registrar_ciclo_memoria_v80(db,*arquivos)
    finally: db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--ciclo',required=True); a=p.parse_args()
    try:
        raiz=Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'
        r=registrar_pasta(raiz,a.ciclo)
        print('MEMORIA INTEGRADA REGISTRADA - HOMOLOGACAO')
        print('Reprocessamento:', 'SIM' if r['reprocessamento'] else 'NAO')
        for origem,x in r['origens'].items():
            print(origem+':',x['casos_atual']); print('  '+', '.join(f'{k}={v}' for k,v in x['contagem'].items()))
        print('SEM ENVIO - AUSENCIA NAO COMPROVA RESOLUCAO'); return 0
    except Exception as e:
        print('MEMORIA BLOQUEADA:',type(e).__name__,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
