# -*- coding: utf-8 -*-
"""Ensaio explícito de leitura do app. Só contagens no CMD. Sem envio ou escrita."""
import argparse
import os
import sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_fonte_app_v80 import carregar_app_v80, ErroFonteApp
from intelligence_central_v80 import executar_central_v80
from intelligence_prescritiva_v80 import priorizar_v80
from intelligence_auditoria_v80 import auditar_carteira_v80


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--homologar-leitura',required=True,action='store_true')
    p.parse_args()
    try:
        s=carregar_app_v80(dsn=os.environ.get('HAIZE_INTELLIGENCE_READONLY_DSN',''),host=os.environ.get('HAIZE_INTELLIGENCE_DB_HOST',''),banco=os.environ.get('HAIZE_INTELLIGENCE_DB_NAME',''),ca=os.environ.get('HAIZE_INTELLIGENCE_CA_FILE',''))
        r=executar_central_v80(data_referencia=s['data_referencia'],competencia=s['data_referencia'][:7],snapshot_app=s)
        carteira=priorizar_v80(r); auditar_carteira_v80(r,carteira)
        print('ENSAIO FONTE APP V8.0 - SOMENTE LEITURA - SEM ENVIO')
        for k,v in s.items():
            if k!='data_referencia': print(k+':',len(v))
        print('Decisoes/candidatos:',len(r['decisoes']))
        print('Grupos executivos:',len(carteira['executivo']))
        print('Auditoria da carteira: OK (nao auditoria independente dos dados do app)')
        return 0
    except ErroFonteApp as e:
        print('ENSAIO BLOQUEADO:',str(e),file=sys.stderr)
    except Exception:
        print('ENSAIO BLOQUEADO: VALIDACAO_ANALITICA_OU_CONFIGURACAO',file=sys.stderr)
    return 1

if __name__=='__main__': sys.exit(main())
