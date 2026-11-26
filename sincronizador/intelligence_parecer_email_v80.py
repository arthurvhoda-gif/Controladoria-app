# -*- coding: utf-8 -*-
"""Gera rascunho EML de uma prévia registrada. Não envia e-mail."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend'))
from intelligence_parecer_email_v80 import preparar,conferir_memoria,exigir,DESTINO
from intelligence_memoria_real_v80 import preparar as validar_memoria
from intelligence_agendamento_v80 import atomico

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--preparar',required=True); a=p.parse_args()
    try:
        exigir(re.fullmatch('[0-9a-f]{32}',a.preparar) is not None,'PARECER_ID')
        raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA'/'PREVIAS_DEFINITIVAS').resolve(strict=True)
        pasta=raiz/('previa_'+a.preparar); exigir(pasta.is_dir() and pasta.resolve()==pasta,'PARECER_PASTA')
        def ler(nome):
            f=pasta/nome; exigir(f.is_file() and not f.is_symlink() and f.stat().st_size<=64*1024*1024,'PARECER_ARQUIVO'); return json.loads(f.read_text(encoding='utf-8'))
        doc=ler('PREVIA_AUDITADA.json'); mem=ler('MEMORIA_INVESTIGACOES.json'); exigir(doc['execucao']==a.preparar,'PARECER_ID')
        validar_memoria(doc); conferir_memoria(raiz/'MEMORIA_LOCAL_REAL_V80.sqlite3',doc,mem)
        raw=preparar(doc,mem,date.today()); dest=pasta/'PARECER_EMAIL.eml'; exigir(not dest.is_symlink(),'PARECER_SAIDA'); atomico(dest,raw)
        print('PARECER_EMAIL_PREPARADO - SEM ENVIO'); print('Destinatario:',DESTINO); print('Candidatos:',doc['carteira']['total_casos']); print('Arquivo privado:',dest); return 0
    except Exception as e:
        print('PARECER BLOQUEADO:',type(e).__name__,str(e) if isinstance(e,ValueError) and str(e).startswith('PARECER_') else '',file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
