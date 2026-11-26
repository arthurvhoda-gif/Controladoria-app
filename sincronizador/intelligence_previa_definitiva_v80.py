# -*- coding: utf-8 -*-
"""Prévia local de dados reais. Nenhuma conexão Neon, envio ou mudança de tarefa."""
import argparse
from datetime import date, datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
# A CLI tem nome semelhante ao motor; carregar o motor de modo explícito.
spec=importlib.util.spec_from_file_location('_haize_previa_motor',REPO/'backend'/'intelligence_previa_definitiva_v80.py')
motor=importlib.util.module_from_spec(spec); spec.loader.exec_module(motor)


def publicar(raiz,r):
    motor.exigir(r['estado'] in ('PREVIA_LOCAL_AUDITADA','PREVIA_COBERTURA_SEM_BASE_HISTORICA') and r['envio_autorizado'] is False,'PREVIA_PUBLICACAO')
    run=uuid.uuid4().hex; r=dict(r,execucao=run,utc=datetime.now(timezone.utc).isoformat())
    raiz.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.previa-',dir=raiz)); destino=raiz/('previa_'+run)
    try:
        (tmp/'PARECER_EXECUTIVO.txt').write_text(motor.parecer(r),encoding='utf-8')
        (tmp/'PREVIA_AUDITADA.json').write_text(json.dumps(r,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
        (tmp/'COBERTURA_FINANCEIRA.json').write_text(json.dumps(r['cobertura'],ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
        tmp.rename(destino)
    except BaseException:
        shutil.rmtree(tmp,ignore_errors=True); raise
    return destino


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--gerar-previa',action='store_true',required=True); p.parse_args()
    etapa='configuracao'
    try:
        pasta=(Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS').resolve(strict=True)
        raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'/'PREVIAS_DEFINITIVAS').resolve()
        motor.exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(pasta) and not pasta.is_relative_to(raiz),'PREVIA_PASTA')
        spec=importlib.util.spec_from_file_location('_haize_previa_extrator',REPO/'sincronizador'/'intelligence_executor_v80.py')
        extrator=importlib.util.module_from_spec(spec); spec.loader.exec_module(extrator)
        etapa='extracao'; d,a,n,s,m,c=extrator.extrair_local_com_cobertura(pasta)
        etapa='auditoria'; r=motor.gerar_previa(registros=d,agenda=a,nomes=n,sem_aba=s,manifesto=m,cobertura=c,hoje=date.today())
        etapa='publicacao'; destino=publicar(raiz,r)
        print(r['estado']); print('Competencia historica:',r['selecao']['competencia']); print('Ultimo mes calendario encerrado:',r['selecao']['ultimo_mes_calendario_encerrado'])
        print('Condominios com positivo nos seis meses:',len(r['selecao']['condominios_com_positivo_em_seis_meses']))
        print('Fechamento confirmado: NAO'); print('App definitivo: INDISPONIVEL'); print('Candidatos:',r['carteira']['total_casos'] if r['carteira'] else 'NAO AVALIADO')
        print('Grupos candidatos a duplicidade:',len(c['candidatos_duplicidade'])); print('SEM ENVIO'); print('Pasta privada:',destino); return 0
    except Exception as e:
        print('PREVIA BLOQUEADA:',etapa,type(e).__name__,file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
