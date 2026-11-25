# -*- coding: utf-8 -*-
"""Coordenador diário privado. Sem rede ou credenciais. Recuperação por staging.
Callbacks: produzir(staging) publica um ciclo completo; memorizar(raiz,run) é idempotente.
"""
import json
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

class ErroAgendamento(ValueError):
    pass


def exigir(ok, codigo):
    if not ok:
        raise ErroAgendamento(codigo)


def atomico(p, dados):
    p = Path(p)
    exigir(not p.is_symlink(), 'ARQUIVO_SIMBOLICO')
    fd, tmp = tempfile.mkstemp(prefix='.gravacao-', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(dados); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def gravar(p, x):
    atomico(p, json.dumps(x, sort_keys=True, allow_nan=False).encode('utf-8'))


def pasta_segura(p):
    exigir(not p.is_symlink(), 'PASTA_SIMBOLICA')
    p.mkdir(exist_ok=True)
    exigir(p.is_dir() and p.resolve() == p, 'PASTA_INVALIDA')
    return p


def ciclo_id(p):
    exigir(re.fullmatch(r'ciclo_[0-9a-f]{32}', p.name) is not None and p.is_dir() and not p.is_symlink() and p.resolve()==p, 'CICLO_INVALIDO')
    for nome in ('CICLO_AUDITADO.json','EVIDENCIAS_CENTRAL.json','SNAPSHOT_APP_FICTICIO.json','PARECER_EXECUTIVO.txt'):
        ar=p/nome
        exigir(ar.is_file() and not ar.is_symlink(), 'CICLO_INCOMPLETO')
    return p.name[6:]


def _estado(slot):
    p=slot/'estado.json'
    exigir(not p.is_symlink(), 'ESTADO_INVALIDO')
    if not p.exists(): return None
    x=json.loads(p.read_text(encoding='utf-8'))
    exigir(isinstance(x,dict) and set(x)=={'run','competencia','estado'} and isinstance(x['run'],str) and re.fullmatch(r'[0-9a-f]{32}',x['run']) and x['estado'] in ('memoria_pendente','concluido') and isinstance(x['competencia'],str) and re.fullmatch(r'\d{4}-\d{2}',x['competencia']), 'ESTADO_INVALIDO')
    return x


def _staged(slot):
    stage=pasta_segura(slot/'staging')
    ciclos=list(stage.glob('ciclo_*'))
    exigir(len(ciclos)<=1,'STAGING_AMBIGUO')
    if ciclos: ciclo_id(ciclos[0])
    return stage,ciclos


def _processar(raiz,slot,competencia,produzir,memorizar,antigo=False):
    estado=_estado(slot); stage,ciclos=_staged(slot)
    if estado and estado['estado']=='concluido':
        exigir(not ciclos and ciclo_id(raiz/('ciclo_'+estado['run']))==estado['run'],'CICLO_CONCLUIDO_AUSENTE')
        if not antigo: exigir(estado['competencia']==competencia,'COMPETENCIA_JA_REGISTRADA')
        return {'estado':'JA_CONCLUIDO','run':estado['run']}
    if not estado and not ciclos:
        if antigo: return None  # não fabricar snapshot para dia passado
        p=produzir(stage)
        exigir(isinstance(p,Path) and p.parent==stage,'DESTINO_INVALIDO')
        stage,ciclos=_staged(slot)
        exigir(len(ciclos)==1 and ciclos[0]==p,'PUBLICACAO_INCOMPLETA')
    if not estado:
        p=ciclos[0]; run=ciclo_id(p)
        doc=json.loads((p/'CICLO_AUDITADO.json').read_bytes())
        exigir(doc['execucao']==run and doc['estado']=='APROVADO_HOMOLOGACAO_MISTA' and doc['central']['data_referencia']==slot.name,'CICLO_REFERENCIA_INVALIDA')
        comp=doc['central']['competencia']
        exigir(isinstance(comp,str) and re.fullmatch(r'\d{4}-\d{2}',comp) and (antigo or comp==competencia),'CICLO_COMPETENCIA_INVALIDA')
        estado={'run':run,'competencia':comp,'estado':'memoria_pendente'}
        gravar(slot/'estado.json',estado)
    elif not antigo:
        exigir(estado['competencia']==competencia,'COMPETENCIA_PENDENTE_DIVERGENTE')
    run=estado['run']; destino=raiz/('ciclo_'+run)
    if ciclos:
        exigir(ciclo_id(ciclos[0])==run and not destino.exists() and not destino.is_symlink(),'CICLO_CONFLITANTE')
        ciclos[0].rename(destino)
    exigir(ciclo_id(destino)==run,'CICLO_AUSENTE')
    # Se o processo falhar depois do commit da memória, o mesmo run será reimportado.
    res=memorizar(raiz,run)
    exigir(isinstance(res,dict) and res.get('execucao')==run and isinstance(res.get('origens'),dict),'MEMORIA_NAO_CONFIRMADA')
    gravar(slot/'estado.json',dict(estado,estado='concluido'))
    return {'estado':'CONCLUIDO','run':run}


def executar_diario(raiz,dia,competencia,produzir,memorizar):
    raiz=Path(raiz)
    exigir(raiz.is_absolute() and raiz.resolve()==raiz and raiz.is_dir(),'RAIZ_INVALIDA')
    exigir(type(dia) is date and isinstance(competencia,str),'DATA_INVALIDA')
    try: mes=date.fromisoformat(competencia+'-01')
    except ValueError: raise ErroAgendamento('COMPETENCIA_INVALIDA') from None
    exigir(mes.strftime('%Y-%m')==competencia and mes<dia.replace(day=1),'COMPETENCIA_INVALIDA')
    agenda=pasta_segura(raiz/'AGENDAMENTO_V80'); lock=agenda/'exclusao.sqlite3'
    exigir(not lock.is_symlink(),'LOCK_INVALIDO')
    db=sqlite3.connect(lock,timeout=0)
    try:
        try: db.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError: raise ErroAgendamento('EXECUCAO_SIMULTANEA_OU_LOCK_INDISPONIVEL') from None
        # Recuperar publicação/memória pendente de dias anteriores antes do novo ciclo.
        for p in sorted(agenda.iterdir()):
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p.name): continue
            exigir(p.is_dir() and not p.is_symlink() and p.resolve()==p,'SLOT_INVALIDO')
            if p.name<dia.isoformat(): _processar(raiz,p,competencia,produzir,memorizar,antigo=True)
        slot=pasta_segura(agenda/dia.isoformat())
        return _processar(raiz,slot,competencia,produzir,memorizar)
    finally:
        db.rollback(); db.close()


def registrar_log(raiz,estado,codigo):
    # Só status/códigos conhecidos pelo chamador, sem mensagens de drivers.
    p=raiz/'AGENDAMENTO_V80.log'
    exigir(not p.is_symlink(),'LOG_INVALIDO')
    with p.open('a',encoding='utf-8') as f:
        f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),estado=estado,codigo=codigo),ensure_ascii=True)+'\n')
