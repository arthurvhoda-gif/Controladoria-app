# -*- coding: utf-8 -*-
"""Envia explicitamente uma prévia local do dia já auditada e registrada."""
import argparse
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_envio_real_v80 import enviar_uma_vez_real, enviar_gmail_real, validar_mensagem, exigir, DESTINO, NaoEnviado, ErroEmail
from intelligence_parecer_email_v80 import preparar, conferir_memoria
from intelligence_memoria_real_v80 import preparar as validar_memoria
from intelligence_email_v80 import senha_app


def carregar_agendado():
    spec = importlib.util.spec_from_file_location('_haize_envio_real_dpapi', REPO/'sincronizador'/'intelligence_agendado_v80.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def carregar_parecer(raiz, run, dia):
    exigir(isinstance(run,str) and re.fullmatch('[0-9a-f]{32}',run), 'ENVIO_REAL_ID')
    pasta = raiz/('previa_'+run)
    exigir(pasta.is_dir() and pasta.resolve()==pasta, 'ENVIO_REAL_PASTA')
    def ler(nome,limite):
        f = pasta/nome
        exigir(f.is_file() and not f.is_symlink() and f.stat().st_size<=limite, 'ENVIO_REAL_ARQUIVO')
        raw=f.read_bytes()
        exigir(0<len(raw)<=limite,'ENVIO_REAL_ARQUIVO')
        return raw
    doc=json.loads(ler('PREVIA_AUDITADA.json',64*1024*1024))
    mem=json.loads(ler('MEMORIA_INVESTIGACOES.json',64*1024*1024))
    exigir(doc['execucao']==run,'ENVIO_REAL_ID')
    validar_memoria(doc)
    conferir_memoria(raiz/'MEMORIA_LOCAL_REAL_V80.sqlite3',doc,mem)
    raw=ler('PARECER_EMAIL.eml',1024*1024)
    exigir(raw==preparar(doc,mem,dia),'ENVIO_REAL_RASCUNHO_DIVERGENTE')
    validar_mensagem(dia,run,raw)
    return raw


def transmitir(dia,run,raw):
    # Reutiliza apenas a credencial Gmail do mesmo remetente/destinatário.
    # Não usa credenciais do Neon nem invoca o ciclo de homologação.
    try:
        h=carregar_agendado(); p=h.arquivo_credencial().with_name('gmail-homologacao.dpapi')
        exigir(p.is_file() and not p.is_symlink() and p.stat().st_size<=65536,'ENVIO_REAL_CREDENCIAL')
        dados=h.dpapi(p.read_bytes(),False); prefixo=b'HAIZE-GMAIL-HOMOLOGACAO:'
        exigir(dados.startswith(prefixo),'ENVIO_REAL_CREDENCIAL')
        chave=senha_app(dados[len(prefixo):].decode('ascii'))
    except Exception:
        raise NaoEnviado('ENVIO_REAL_CREDENCIAL_INDISPONIVEL') from None
    try: return enviar_gmail_real(chave,dia,run,raw)
    finally: del chave,dados


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--enviar',required=True,metavar='ID_PREVIA'); p.add_argument('--confirmar-envio-real',required=True,action='store_true'); a=p.parse_args()
    etapa='configuracao'
    try:
        exigir(os.name=='nt','ENVIO_REAL_WINDOWS')
        raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'/'PREVIAS_DEFINITIVAS').resolve(strict=True)
        origem=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve()
        exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(origem) and not origem.is_relative_to(raiz),'ENVIO_REAL_PASTA')
        dia=date.today(); etapa='validacao'; raw=carregar_parecer(raiz,a.enviar,dia)
        etapa='transmissao'; res=enviar_uma_vez_real(raiz/'EMAIL_LOCAL_REAL_V80.sqlite3',dia,a.enviar,raw,transmitir)
        print('EMAIL_REAL_'+res); print('Destinatario:',DESTINO); print('Ciclo:',a.enviar); print('Aceitacao SMTP nao confirma chegada na caixa de entrada.'); return 0
    except Exception as e:
        codigo=str(e) if isinstance(e,ErroEmail) and str(e).startswith('ENVIO_REAL_') else type(e).__name__
        print('ENVIO REAL BLOQUEADO:',etapa,codigo,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
