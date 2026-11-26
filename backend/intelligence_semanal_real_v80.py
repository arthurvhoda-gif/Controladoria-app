# -*- coding: utf-8 -*-
"""Coordenação semanal local, com reserva de ciclo antes de transmitir."""
from datetime import date
from pathlib import Path
import re
import sqlite3
from contextlib import closing

APP_ID = 0x4841493C
OUTBOX_ID = 0x4841493B


def exigir(ok, codigo):
    if not ok:
        raise ValueError(codigo)


def id_valido(run):
    exigir(isinstance(run, str) and re.fullmatch('[0-9a-f]{32}', run), 'SEMANAL_ID')
    return run


def caminho(p):
    p = Path(p)
    exigir(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.parent.is_dir(), 'SEMANAL_CAMINHO')
    return p


def consultar_envio(p, dia):
    p = caminho(p)
    if not p.exists():
        return None
    with closing(sqlite3.connect(p.as_uri()+'?mode=ro', uri=True, timeout=40)) as db:
        exigir(db.execute('PRAGMA application_id').fetchone()[0] == OUTBOX_ID and db.execute('PRAGMA user_version').fetchone()[0] == 1, 'SEMANAL_FILA_INCOMPATIVEL')
        exigir(db.execute("SELECT 1 FROM envios WHERE estado='pendente' LIMIT 1").fetchone() is None, 'SEMANAL_RECONCILIACAO_MANUAL')
        row = db.execute('SELECT run,estado FROM envios WHERE dia=?', (dia.isoformat(),)).fetchone()
        if row:
            id_valido(row[0]); exigir(row[1] in ('aceito','nao_enviado'), 'SEMANAL_FILA_ESTADO')
        return row


def executar(raiz, dia, produzir, preparar, transmitir):
    """Uma referência por sábado. Não envia relatórios atrasados em outro dia.
    produzir -> run; preparar(run) -> bytes; transmitir(dia,run,raw) -> resultado.
    Transmissão usa a fila SMTP existente, inclusive para tentativas manuais.
    """
    exigir(type(dia) is date, 'SEMANAL_DATA')
    if dia.weekday() != 5:
        return 'FORA_DO_SABADO', None
    raiz = Path(raiz)
    p = caminho(raiz/'SEMANAL_REAL_V80.sqlite3')
    outbox = raiz/'EMAIL_LOCAL_REAL_V80.sqlite3'
    with closing(sqlite3.connect(p, timeout=40)) as db:
        try:
            db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
            objs = {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            aid = db.execute('PRAGMA application_id').fetchone()[0]; ver = db.execute('PRAGMA user_version').fetchone()[0]
            if not objs and aid == ver == 0:
                db.execute('CREATE TABLE slots(dia TEXT PRIMARY KEY, run TEXT NOT NULL)')
                db.execute(f'PRAGMA application_id={APP_ID}'); db.execute('PRAGMA user_version=1')
            else:
                exigir(objs == {'slots'} and aid == APP_ID and ver == 1, 'SEMANAL_BANCO_INCOMPATIVEL')
            existente = consultar_envio(outbox,dia)
            row = db.execute('SELECT run FROM slots WHERE dia=?',(dia.isoformat(),)).fetchone()
            if row:
                run = id_valido(row[0]); exigir(existente is None or existente[0] == run, 'SEMANAL_CICLO_CONFLITANTE')
            else:
                run = id_valido(existente[0] if existente else produzir())
                db.execute('INSERT INTO slots VALUES(?,?)',(dia.isoformat(),run))
            db.commit()
        except BaseException:
            db.rollback(); raise
    if existente and existente[1] == 'aceito':
        return 'JA_ACEITO',run
    raw = preparar(run)
    result = transmitir(dia,run,raw)
    exigir(result in ('ACEITO','JA_ACEITO'),'SEMANAL_ENVIO_ESTADO')
    return result,run
