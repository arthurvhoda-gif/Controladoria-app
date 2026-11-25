# -*- coding: utf-8 -*-
"""Executor diário de homologação Windows. Nenhum envio ou acesso à produção."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import date
import getpass
import importlib.util
import os
from pathlib import Path
import sys
from urllib.parse import quote

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_agendamento_v80 import executar_diario, registrar_log, atomico, pasta_segura, exigir, ErroAgendamento

HOST='ep-royal-union-acmuwc5a.sa-east-1.aws.neon.tech'
BANCO='neondb'
ROLE='haize_intelligence_v80_ro'
FICTICIOS={'Condominio Ficticio Alfa','Condominio Ficticio Beta'}


def carregar_script(nome,alias):
    spec=importlib.util.spec_from_file_location(alias,REPO/'sincronizador'/nome)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def dpapi(dados,proteger):
    exigir(os.name=='nt','WINDOWS_OBRIGATORIO')
    exigir(isinstance(dados,bytes) and 0<len(dados)<=65536,'CREDENCIAL_INVALIDA')
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    def blob(b):
        buf=(ctypes.c_ubyte*len(b)).from_buffer_copy(b)
        return Blob(len(b),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte))),buf
    entrada,b1=blob(dados); ent,b2=blob(b'HAIZE-INTELLIGENCE-V80-NEON-HOMOLOGACAO'); saida=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    P=ctypes.POINTER(Blob)
    crypt.CryptProtectData.argtypes=[P,wintypes.LPCWSTR,P,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,P]
    crypt.CryptProtectData.restype=wintypes.BOOL
    crypt.CryptUnprotectData.argtypes=[P,ctypes.c_void_p,P,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,P]
    crypt.CryptUnprotectData.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
    try:
        f=crypt.CryptProtectData if proteger else crypt.CryptUnprotectData
        desc='HAIZE Neon homologacao' if proteger else None
        exigir(bool(f(ctypes.byref(entrada),desc,ctypes.byref(ent),None,None,1,ctypes.byref(saida))),'DPAPI_FALHOU')
        return ctypes.string_at(saida.pbData,saida.cbData)
    finally:
        ctypes.memset(ctypes.addressof(b1),0,len(b1))
        if saida.pbData:
            ctypes.memset(saida.pbData,0,saida.cbData); kernel.LocalFree(ctypes.cast(saida.pbData,ctypes.c_void_p))


def arquivo_credencial():
    base=Path(os.environ['LOCALAPPDATA']).resolve(strict=True)
    exigir(base.is_dir(),'LOCALAPPDATA_INVALIDA')
    return pasta_segura(base/'HaizeIntelligenceV80')/'neon-homologacao.dpapi'


def snapshot(senha):
    import certifi
    from intelligence_fonte_app_v80 import carregar_app_v80, ROLE as role_codigo
    exigir(role_codigo==ROLE,'CONECTOR_DESATUALIZADO')
    dsn='postgresql://'+ROLE+':'+quote(senha,safe='')+'@'+HOST+'/'+BANCO
    try: s=carregar_app_v80(dsn=dsn,host=HOST,banco=BANCO,ca=certifi.where())
    finally: del dsn
    exigir(len(s['condominios'])==2 and set(s['condominios'].values())==FICTICIOS,'CADASTRO_NAO_FICTICIO')
    return s


def configurar():
    p=arquivo_credencial(); senha=getpass.getpass('Senha exclusiva da Intelligence: ')
    exigir(bool(senha),'CREDENCIAL_VAZIA')
    try:
        snapshot(senha)  # Valida TLS, papel e dados fictícios antes de persistir.
        atomico(p,dpapi(senha.encode('utf-8'),True))
    finally: del senha
    print('CREDENCIAL DPAPI CONFIGURADA - USUARIO WINDOWS ATUAL - HOMOLOGACAO')


def executar(competencia):
    pasta=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve()
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve()
    exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(pasta) and not pasta.is_relative_to(raiz),'PASTA_PRIVADA_INVALIDA')
    raiz.mkdir(parents=True,exist_ok=True)
    etapa='inicializacao'
    try:
        cli=carregar_script('intelligence_executor_v80.py','_haize_cli_executor')
        mem=carregar_script('intelligence_memoria_integrada_v80.py','_haize_cli_memoria')
        exigir(cli.HOST==HOST and cli.BANCO==BANCO and cli.ROLE==ROLE,'DESTINO_DIVERGENTE')
        dia=date.today()
        def produzir(stage):
            nonlocal etapa
            etapa='extracao_local'; dados,agenda,nomes,sem_aba,manifesto=cli.extrair_local(pasta.resolve(strict=True))
            etapa='credencial'; p=arquivo_credencial()
            exigir(p.is_file() and not p.is_symlink() and p.stat().st_size<=65536,'CREDENCIAL_INDISPONIVEL')
            senha=dpapi(p.read_bytes(),False).decode('utf-8')
            try:
                etapa='extracao_neon'; s=snapshot(senha)
            finally: del senha
            exigir(s['data_referencia']==dia.isoformat(),'DIA_WINDOWS_DIVERGENTE_DO_NEON')
            etapa='auditorias'; r=cli.executar_ciclo_v80(registros=dados,agenda=agenda,nomes=nomes,sem_aba=sem_aba,competencia=competencia,snapshot=s)
            etapa='publicacao_staging'; return cli.publicar(stage,r,s,manifesto)
        def memorizar(raiz,run):
            nonlocal etapa
            etapa='memoria'; return mem.registrar_pasta(raiz,run)
        res=executar_diario(raiz,dia,competencia,produzir,memorizar)
        registrar_log(raiz,res['estado'],'OK')
        print(res['estado']+' - HOMOLOGACAO - SEM ENVIO'); print('Ciclo:',res['run']); return 0
    except Exception as e:
        # Nunca incluir mensagens de bibliotecas, DSNs ou dados de origem.
        codigo=e.args[0] if isinstance(e,ErroAgendamento) else type(e).__name__
        try: registrar_log(raiz,'FALHA',etapa+':'+codigo)
        except Exception: pass
        print('AGENDAMENTO BLOQUEADO:',etapa,codigo,file=sys.stderr); return 1


def main():
    p=argparse.ArgumentParser(description=__doc__); g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--configurar',action='store_true'); g.add_argument('--executar',action='store_true')
    p.add_argument('--competencia',default='2026-06'); a=p.parse_args()
    try:
        exigir(os.name=='nt','WINDOWS_OBRIGATORIO')
        if a.configurar: configurar(); return 0
        return executar(a.competencia)
    except Exception as e:
        print('AGENDAMENTO BLOQUEADO:',e.args[0] if isinstance(e,ErroAgendamento) else type(e).__name__,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
