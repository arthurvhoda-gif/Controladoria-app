# -*- coding: utf-8 -*-
"""Ensaio somente leitura da auditoria operacional em Neon homologação.
Não grava credenciais, não envia relatórios, não usa a conta administrativa.
"""
import argparse
import getpass
import sys
from pathlib import Path
from urllib.parse import quote
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_fonte_app_v80 import carregar_app_v80, ROLE, ErroFonteApp
from intelligence_central_v80 import executar_central_v80
from intelligence_prescritiva_v80 import priorizar_v80
from intelligence_auditoria_v80 import ErroAuditoria, exigir
from intelligence_auditoria_app_v80 import auditar_app_v80

HOST='ep-royal-union-acmuwc5a.sa-east-1.aws.neon.tech'
BANCO='neondb'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--homologar-leitura',action='store_true',required=True)
    p.parse_args()
    try:
        import certifi
        exigir(ROLE=='haize_intelligence_v80_ro','CONECTOR_DESATUALIZADO')
        print('Destino exclusivo de homologacao:',HOST)
        senha=getpass.getpass('Senha exclusiva da Intelligence: ')
        dsn='postgresql://'+ROLE+':'+quote(senha,safe='')+'@'+HOST+'/'+BANCO
        try: s=carregar_app_v80(dsn=dsn,host=HOST,banco=BANCO,ca=certifi.where())
        finally: del senha,dsn
        exigir(set(s['condominios'].values())=={'Condominio Ficticio Alfa','Condominio Ficticio Beta'},'CADASTRO_FICTICIO_DIVERGENTE')
        c=executar_central_v80(data_referencia=s['data_referencia'],competencia=s['data_referencia'][:7],snapshot_app=s)
        carteira=priorizar_v80(c); r=auditar_app_v80(s,c,carteira)
        print(r['estado'])
        for k in ('solicitacoes','lancamentos','servicos','vistorias','decisoes','pago_liquido_centavos'): print(k+':',r[k])
        print('Grupos executivos:',len(carteira['executivo']))
        print('SEM ENVIO - DADOS FICTICIOS')
        return 0
    except (ErroAuditoria,ErroFonteApp) as e:
        print('AUDITORIA BLOQUEADA:',str(e),file=sys.stderr)
    except Exception:
        print('AUDITORIA BLOQUEADA: CONFIGURACAO_OU_ESTRUTURA_INVALIDA',file=sys.stderr)
    return 1

if __name__=='__main__': sys.exit(main())
