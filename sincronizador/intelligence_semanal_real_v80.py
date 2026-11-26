# -*- coding: utf-8 -*-
"""Parecer semanal local. Modo de teste nunca transmite e não reserva sábado."""
import argparse
from datetime import date, datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_semanal_real_v80 import executar, exigir, id_valido
from intelligence_agendamento_v80 import atomico
from intelligence_parecer_email_v80 import preparar, conferir_memoria
from intelligence_memoria_real_v80 import registrar
from intelligence_envio_real_v80 import enviar_uma_vez_real


def cli(nome):
    spec=importlib.util.spec_from_file_location('_semanal_'+nome, REPO/'sincronizador'/(nome+'.py'))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def gerar(raiz, pasta, dia):
    ext=cli('intelligence_executor_v80'); previa=cli('intelligence_previa_definitiva_v80')
    d,a,n,s,m,c=ext.extrair_local_com_cobertura(pasta)
    r=previa.motor.gerar_previa(registros=d,agenda=a,nomes=n,sem_aba=s,manifesto=m,cobertura=c,hoje=dia)
    dest=previa.publicar(raiz,r)
    exigir(r['estado']=='PREVIA_LOCAL_AUDITADA','SEMANAL_SEM_BASE_AUDITADA')
    return id_valido(dest.name.removeprefix('previa_'))


def preparar_ciclo(raiz,run,dia):
    pasta=raiz/('previa_'+id_valido(run)); exigir(pasta.is_dir() and pasta.resolve()==pasta,'SEMANAL_PREVIA')
    f=pasta/'PREVIA_AUDITADA.json'; exigir(f.is_file() and not f.is_symlink() and f.stat().st_size<=64*1024*1024,'SEMANAL_ARQUIVO')
    doc=json.loads(f.read_bytes()); exigir(doc['execucao']==run and doc['referencia']==dia.isoformat(),'SEMANAL_REFERENCIA')
    mp=pasta/'MEMORIA_INVESTIGACOES.json'; ep=pasta/'PARECER_EMAIL.eml'; banco=raiz/'MEMORIA_LOCAL_REAL_V80.sqlite3'
    exigir(not any(x.is_symlink() for x in (mp,ep,banco)),'SEMANAL_ARQUIVO')
    if mp.exists():
        exigir(mp.is_file() and mp.stat().st_size<=64*1024*1024,'SEMANAL_MEMORIA'); mem=json.loads(mp.read_bytes()); conferir_memoria(banco,doc,mem)
    else:
        db=sqlite3.connect(banco,timeout=30)
        try: mem=registrar(db,doc)
        finally: db.close()
        atomico(mp,json.dumps(mem,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8'))
    raw=preparar(doc,mem,dia)
    if ep.exists():
        exigir(ep.is_file() and ep.stat().st_size<=1024*1024 and ep.read_bytes()==raw,'SEMANAL_RASCUNHO_DIVERGENTE')
    else: atomico(ep,raw)
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__); g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--validar-sem-envio',action='store_true'); g.add_argument('--executar-semanal',action='store_true'); a=p.parse_args()
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'/'PREVIAS_DEFINITIVAS').resolve()
    log_autorizado=False
    def log(s):
        print(s)
        if not log_autorizado: return
        exigir(not (raiz/'SEMANAL_REAL_V80.log').is_symlink(),'SEMANAL_LOG')
        with (raiz/'SEMANAL_REAL_V80.log').open('a',encoding='utf-8') as f: f.write(datetime.now().isoformat(timespec='seconds')+' '+s+'\n')
    try:
        origem=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve()
        exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(origem) and not origem.is_relative_to(raiz),'SEMANAL_PASTA')
        raiz.mkdir(parents=True,exist_ok=True); log_autorizado=True; dia=date.today()
        def produzir(): return gerar(raiz,origem.resolve(strict=True),dia)
        def preparar_run(run): return preparar_ciclo(raiz,run,dia)
        if a.validar_sem_envio:
            run=produzir(); preparar_run(run); log('SEMANAL_VALIDADO_SEM_ENVIO '+run); return 0
        def enviar(d,r,raw):
            exigir(date.today()==d,'SEMANAL_DIA_ALTERADO')
            m=cli('intelligence_envio_real_v80'); exigir(m.carregar_parecer(raiz,r,d)==raw,'SEMANAL_PARECER_DIVERGENTE')
            return enviar_uma_vez_real(raiz/'EMAIL_LOCAL_REAL_V80.sqlite3',d,r,raw,m.transmitir)
        estado,run=executar(raiz,dia,produzir,preparar_run,enviar)
        log('SEMANAL_'+estado+(' '+run if run else '')); return 0
    except Exception as e:
        codigo=str(e) if isinstance(e,ValueError) and str(e).startswith(('SEMANAL_','ENVIO_REAL_','PARECER_','MEM_REAL_')) else type(e).__name__
        try: log('SEMANAL_BLOQUEADO '+codigo)
        except Exception: print('SEMANAL_BLOQUEADO '+codigo,file=sys.stderr)
        return 1

if __name__=='__main__': sys.exit(main())
