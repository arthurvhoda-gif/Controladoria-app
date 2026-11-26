# -*- coding: utf-8 -*-
"""Relatório local de cobertura. Não modifica planilhas, não acessa banco ou envia e-mail."""
import argparse
from datetime import date
from pathlib import Path
import importlib.util
import json
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
# Nome distinto para não importar este CLI em vez do módulo de análise.
spec=importlib.util.spec_from_file_location('_haize_cobertura_motor',REPO/'backend'/'intelligence_cobertura_v80.py')
motor=importlib.util.module_from_spec(spec); spec.loader.exec_module(motor)
from intelligence_agendamento_v80 import atomico
from intelligence_ensaio_v80 import assinatura
from auditar_planilhas import extrair_base,LeitorXlsm,texto,canon,data_excel,dinheiro


def extrair(pasta):
    pasta=pasta.resolve(strict=True); base=(pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    if base.parent!=pasta: raise ValueError('COBERTURA_PASTA')
    hb=assinatura(base); mapa,*_=extrair_base(base)
    nomes={i:n for i,(n,a) in enumerate(mapa,1)}
    arquivos=[(pasta/a).resolve(strict=True) for n,a in mapa]
    if len(nomes)!=10 or len({canon(n) for n in nomes.values()})!=10 or len(set(arquivos))!=10 or any(a.parent!=pasta or a==base or a.suffix.lower()!='.xlsm' for a in arquivos): raise ValueError('COBERTURA_MANIFESTO')
    hashes={p:assinatura(p) for p in arquivos}; linhas=[]
    for cid,p in enumerate(arquivos,1):
        l=LeitorXlsm(p)
        try:
            for i,d in l.linhas('GASTOS',{'A','B','C','D'}):
                if i==1 or not texto(d.get('A')) or not any(d.get(k) is not None for k in ('B','C','D')): continue
                linhas.append(dict(condominio_id=cid,linha=i,descricao=texto(d.get('A')),data=data_excel(d.get('B')),valor=dinheiro(d.get('C')),categoria=texto(d.get('D'))))
        finally: l.fechar()
    if assinatura(base)!=hb or any(assinatura(p)!=h for p,h in hashes.items()): raise ValueError('COBERTURA_ORIGEM_ALTERADA')
    r=motor.diagnosticar_cobertura_v80(nomes,linhas,date.today())
    r['manifesto']=dict(hash_cadastro=hb,arquivos=[dict(condominio_id=i,arquivo=p.name,sha256=hashes[p]) for i,p in enumerate(arquivos,1)])
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--diagnosticar',action='store_true',required=True); a=p.parse_args()
    try:
        pasta=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve(strict=True)
        raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve()
        if raiz.is_relative_to(REPO) or raiz.is_relative_to(pasta) or pasta.is_relative_to(raiz): raise ValueError('COBERTURA_SAIDA')
        r=extrair(pasta); raiz.mkdir(parents=True,exist_ok=True)
        destino=raiz/'COBERTURA_FINANCEIRA_V80.json'
        atomico(destino,json.dumps(r,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8'))
        print('DIAGNOSTICO DE COBERTURA - SEM ENVIO')
        for k,g in r['totais'].items(): print(k+':',g['registros'],'| positivos_centavos:',g['positivos_centavos'])
        print('Condominios sem positivo classificado no mes anterior:',sum(c['competencia_anterior_sem_positivo_classificado'] for c in r['cobertura']))
        print('Sinais de concentracao temporal:',len(r['sinais']))
        print('Grupos candidatos a duplicidade:',len(r['candidatos_duplicidade']))
        print('Datas invalidas:',r['datas_invalidas'],'| Datas futuras:',r['datas_futuras'])
        print('Arquivo privado:',destino); return 0
    except Exception as e:
        print('COBERTURA BLOQUEADA:',type(e).__name__,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
