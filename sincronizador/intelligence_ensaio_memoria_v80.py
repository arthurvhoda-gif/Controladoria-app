# -*- coding: utf-8 -*-
"""Memória privada local: sem banco do aplicativo, rede ou envio."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import os

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_memoria_v80 import registrar_memoria_v80, MAX_BYTES


def executar(arquivo):
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve(strict=True)
    origem=arquivo.resolve(strict=True)
    if raiz.is_relative_to(REPO) or not origem.is_relative_to(raiz) or origem.name!='EVIDENCIAS_CENTRAL.json':
        raise ValueError('Origem deve estar na pasta privada, fora do repositório.')
    if origem.stat().st_size>MAX_BYTES: raise ValueError('Arquivo muito grande.')
    with origem.open('rb') as f: raw=f.read(MAX_BYTES+1)
    destino=raiz/'MEMORIA_V80.sqlite3'
    if destino.is_symlink() or destino.resolve().parent!=raiz:
        raise ValueError('Destino de memória inválido.')
    db=sqlite3.connect(destino,timeout=30)
    try: r=registrar_memoria_v80(db,raw)
    finally: db.close()
    # Relatório derivado; se a escrita falhar, reprocessar o mesmo ID é seguro.
    saida=raiz/('MEMORIA_RESUMO_'+r['execucao']+'.json')
    fd,tmp=tempfile.mkstemp(prefix='.memoria-',dir=raiz)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,indent=2)
        os.replace(tmp,saida)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    print('MEMORIA V8.0 - SEM ENVIO')
    print('Reprocessamento:', 'SIM' if r['reprocessamento'] else 'NAO')
    print('Casos atuais:',r['casos_atual'])
    for k,v in r['contagem'].items(): print(k+':',v)
    print('Banco privado:',destino)
    print('Resumo privado:',saida)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--evidencias',type=Path,required=True)
    try: executar(p.parse_args().evidencias)
    except Exception as e:
        print('EXECUCAO BLOQUEADA:',type(e).__name__,str(e),file=sys.stderr); sys.exit(1)
