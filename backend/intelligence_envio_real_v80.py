# -*- coding: utf-8 -*-
"""Transmissão explícita de parecer local; fila própria, sem agendamento."""
from datetime import date, datetime, timezone
from email import policy
from email.parser import BytesParser
import hashlib
from pathlib import Path
import re
import smtplib
import sqlite3
import ssl
from intelligence_email_v80 import DESTINO, senha_app, NaoEnviado, ErroEmail

APP_ID = 0x4841493B


def exigir(ok, codigo):
    if not ok:
        raise ErroEmail(codigo)


def validar_mensagem(dia, run, raw):
    exigir(type(dia) is date and isinstance(run, str) and re.fullmatch(r'[0-9a-f]{32}', run), 'ENVIO_REAL_ID')
    exigir(isinstance(raw, bytes) and 0 < len(raw) <= 1024*1024, 'ENVIO_REAL_TAMANHO')
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    exigir(not msg.defects and set(k.lower() for k in msg.keys()) == {'from','to','subject','message-id','content-type','content-transfer-encoding','mime-version'} and len(msg.keys()) == 7, 'ENVIO_REAL_CABECALHO')
    exigir(str(msg['From']) == 'HAIZE Intelligence <'+DESTINO+'>' and str(msg['To']) == DESTINO, 'ENVIO_REAL_DESTINO')
    exigir(str(msg['Subject']) == 'HAIZE INTELLIGENCE | Prévia local '+dia.isoformat() and str(msg['Message-ID']) == '<haize-v80-local-'+dia.isoformat()+'-'+run+'@gmail.com>', 'ENVIO_REAL_REFERENCIA')
    exigir(not msg.is_multipart() and msg.get_content_type() == 'text/plain' and msg.get_content_disposition() is None, 'ENVIO_REAL_FORMATO')
    return hashlib.sha256(raw).hexdigest()


def enviar_gmail_real(chave, dia, run, raw):
    validar_mensagem(dia, run, raw)
    chave = senha_app(chave)
    conn = None
    try:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
            conn = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30, context=ctx)
            conn.login(DESTINO, chave)
            if conn.mail(DESTINO)[0] != 250:
                raise NaoEnviado('ENVIO_REAL_REMETENTE_RECUSADO')
            if conn.rcpt(DESTINO)[0] not in (250,251):
                raise NaoEnviado('ENVIO_REAL_DESTINO_RECUSADO')
        except NaoEnviado:
            raise
        except smtplib.SMTPAuthenticationError:
            raise NaoEnviado('ENVIO_REAL_AUTENTICACAO') from None
        except Exception:
            raise NaoEnviado('ENVIO_REAL_CONEXAO_ANTES_DATA') from None
        try:
            code, _ = conn.data(raw)
        except Exception:
            raise ErroEmail('ENVIO_REAL_RESULTADO_INCERTO') from None
        exigir(code == 250, 'ENVIO_REAL_RESULTADO_INCERTO')
        return True
    finally:
        if conn is not None:
            try: conn.close()
            except Exception: pass


def enviar_uma_vez_real(banco, dia, run, raw, enviar):
    """Reserva persistente antes da rede; não repete após incerteza."""
    sha = validar_mensagem(dia, run, raw)
    p = Path(banco)
    exigir(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.parent.is_dir(), 'ENVIO_REAL_BANCO')
    slot = dia.isoformat()
    stamp = datetime.now(timezone.utc).isoformat()
    db = sqlite3.connect(p, timeout=40)
    try:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        objs = {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        aid = db.execute('PRAGMA application_id').fetchone()[0]
        ver = db.execute('PRAGMA user_version').fetchone()[0]
        if not objs and aid == ver == 0:
            db.execute("CREATE TABLE envios(dia TEXT PRIMARY KEY, run TEXT NOT NULL, sha TEXT NOT NULL, utc TEXT NOT NULL, estado TEXT NOT NULL CHECK(estado IN ('pendente','aceito','nao_enviado')))")
            db.execute(f'PRAGMA application_id={APP_ID}')
            db.execute('PRAGMA user_version=1')
        else:
            exigir(objs == {'envios'} and aid == APP_ID and ver == 1, 'ENVIO_REAL_BANCO_INCOMPATIVEL')
        # Qualquer resultado incerto anterior requer reconciliação humana.
        exigir(db.execute("SELECT 1 FROM envios WHERE estado='pendente' LIMIT 1").fetchone() is None, 'ENVIO_REAL_RECONCILIACAO_MANUAL')
        row = db.execute('SELECT run,sha,utc,estado FROM envios WHERE dia=?', (slot,)).fetchone()
        if row:
            exigir(row[:2] == (run,sha), 'ENVIO_REAL_CICLO_CONFLITANTE')
            if row[3] == 'aceito':
                db.commit(); return 'JA_ACEITO'
            exigir(row[3] == 'nao_enviado' and stamp >= row[2], 'ENVIO_REAL_ESTADO')
            db.execute("UPDATE envios SET estado='pendente',utc=? WHERE dia=?", (stamp,slot))
        else:
            db.execute("INSERT INTO envios VALUES(?,?,?,?,'pendente')", (slot,run,sha,stamp))
        db.commit()
        try:
            result = enviar(dia,run,raw)
        except NaoEnviado:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE envios SET estado='nao_enviado' WHERE dia=? AND estado='pendente'", (slot,))
            db.commit(); raise
        exigir(result is True, 'ENVIO_REAL_RESULTADO_INCERTO')
        db.execute('BEGIN IMMEDIATE')
        cur = db.execute("UPDATE envios SET estado='aceito' WHERE dia=? AND estado='pendente'", (slot,))
        exigir(cur.rowcount == 1, 'ENVIO_REAL_RESULTADO_INCERTO')
        db.commit(); return 'ACEITO'
    except BaseException:
        db.rollback(); raise
    finally:
        db.close()
