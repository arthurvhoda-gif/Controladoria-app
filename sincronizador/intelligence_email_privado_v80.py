# -*- coding: utf-8 -*-
"""Teste privado via Gmail. Sem dados reais, sem anexos, sem producao."""
import argparse
from datetime import date
import getpass
import json
import os
from pathlib import Path
import re
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_email_v80 import enviar_uma_vez,enviar_gmail,senha_app,exigir,ErroEmail,NaoEnviado,DESTINO
from intelligence_agendado_v80 import dpapi,arquivo_credencial,executar,carregar_script
from intelligence_agendamento_v80 import atomico,ciclo_id,registrar_log

PREFIXO=b'HAIZE-GMAIL-HOMOLOGACAO:'

def credencial():
    return arquivo_credencial().with_name('gmail-homologacao.dpapi')

def configurar():
    chave=senha_app(getpass.getpass('Senha de app do Gmail: '))
    try: atomico(credencial(),dpapi(PREFIXO+chave.encode('ascii'),True))
    finally: del chave
    print('CREDENCIAL GMAIL DPAPI CONFIGURADA - AINDA SEM ENVIO')

def enviar_hoje(raiz):
    dia=date.today(); slot=raiz/'AGENDAMENTO_V80'/dia.isoformat()/'estado.json'
    exigir(slot.is_file() and not slot.is_symlink(),'EMAIL_SEM_CICLO_HOJE')
    estado=json.loads(slot.read_bytes()); run=estado.get('run')
    exigir(estado.get('estado')=='concluido' and isinstance(run,str) and re.fullmatch(r'[0-9a-f]{32}',run),'EMAIL_CICLO_NAO_CONCLUIDO')
    pasta=raiz/('ciclo_'+run); exigir(ciclo_id(pasta)==run,'EMAIL_CICLO_INVALIDO')
    doc=json.loads((pasta/'CICLO_AUDITADO.json').read_bytes())
    exigir(doc['execucao']==run and doc['estado']=='APROVADO_HOMOLOGACAO_MISTA' and doc['central']['data_referencia']==dia.isoformat() and doc['central']['competencia']==estado['competencia'],'EMAIL_CICLO_DIVERGENTE')
    exigir(doc['auditoria_local']['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and doc['auditoria_app']['estado']=='APROVADO_ESCOPO_SNAPSHOT_APP','EMAIL_AUDITORIA')
    mem=carregar_script('intelligence_memoria_integrada_v80.py','_haize_email_memoria')
    r=mem.registrar_pasta(raiz,run)
    exigir(r.get('execucao')==run and r.get('reprocessamento') is True,'EMAIL_MEMORIA_NAO_CONFIRMADA')
    def enviar(dia,run):
        try:
            p=credencial(); exigir(p.is_file() and not p.is_symlink() and p.stat().st_size<=65536,'EMAIL_CREDENCIAL_AUSENTE')
            dados=dpapi(p.read_bytes(),False); exigir(dados.startswith(PREFIXO),'EMAIL_CREDENCIAL_INVALIDA')
            chave=senha_app(dados[len(PREFIXO):].decode('ascii'))
        except Exception: raise NaoEnviado('EMAIL_CREDENCIAL_INDISPONIVEL') from None
        try: return enviar_gmail(chave,dia,run)
        finally: del dados,chave
    res=enviar_uma_vez(raiz/'EMAIL_GMAIL_HOMOLOGACAO_V80.sqlite3',dia,run,enviar)
    registrar_log(raiz,'EMAIL_'+res,'OK')
    print('EMAIL_'+res+' - '+DESTINO+' - SOMENTE TESTE'); return 0

def main():
    p=argparse.ArgumentParser(description=__doc__); g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--configurar',action='store_true'); g.add_argument('--testar',action='store_true'); g.add_argument('--executar',action='store_true')
    p.add_argument('--competencia',default='2026-06'); a=p.parse_args()
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve()
    try:
        exigir(os.name=='nt','WINDOWS_OBRIGATORIO')
        if a.configurar: configurar(); return 0
        if a.executar:
            rc=executar(a.competencia)
            if rc: return rc
        return enviar_hoje(raiz)
    except Exception as e:
        codigo=str(e) if isinstance(e,ErroEmail) else type(e).__name__
        try: registrar_log(raiz,'EMAIL_FALHA',codigo)
        except Exception: pass
        print('EMAIL BLOQUEADO:',codigo,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
