# -*- coding: utf-8 -*-
"""SMTP de homologacao: destinatario fixo, sem dados reais. Sem rede ao importar."""
import hashlib
import re
import sqlite3
import ssl
import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

DESTINO='app1haize@gmail.com'
REMETENTE='HAIZE Intelligence <'+DESTINO+'>'
APP_ID=1212237111

class ErroEmail(ValueError): pass
class NaoEnviado(ErroEmail):
    """Falha comprovadamente anterior a entrega do corpo SMTP."""


def exigir(ok,codigo):
    if not ok: raise ErroEmail(codigo)


def senha_app(s):
    exigir(isinstance(s,str),'EMAIL_SENHA_INVALIDA')
    s=''.join(s.split())
    exigir(re.fullmatch(r'[A-Za-z0-9]{16}',s) is not None,'EMAIL_SENHA_INVALIDA')
    return s


def payload(dia,run):
    exigir(type(dia) is date and isinstance(run,str) and re.fullmatch(r'[0-9a-f]{32}',run),'EMAIL_CICLO_INVALIDO')
    msg=EmailMessage(policy=SMTP)
    msg['From']=REMETENTE; msg['To']=DESTINO
    msg['Subject']='HAIZE INTELLIGENCE V8.0 | Teste privado '+dia.isoformat()
    msg['Message-ID']='<haize-v80-teste-'+dia.isoformat()+'-'+run+'@gmail.com>'
    msg.set_content('HOMOLOGACAO - TESTE DE ENTREGA\nCiclo '+run+'\nAuditorias e registro na memoria confirmados. Nenhuma informacao financeira ou operacional real foi enviada. Nao e um parecer de producao.\n')
    return msg.as_bytes()


def enviar_gmail(senha,dia,run):
    senha=senha_app(senha); body=payload(dia,run)
    conn=None
    try:
        try:
            import certifi
            ctx=ssl.create_default_context(cafile=certifi.where())
            conn=smtplib.SMTP_SSL('smtp.gmail.com',465,timeout=30,context=ctx)
            conn.login(DESTINO,senha)
            code,_=conn.mail(DESTINO)
            if code!=250: raise NaoEnviado('GMAIL_REMETENTE_RECUSADO')
            code,_=conn.rcpt(DESTINO)
            if code not in (250,251): raise NaoEnviado('GMAIL_DESTINO_RECUSADO')
        except NaoEnviado: raise
        except smtplib.SMTPAuthenticationError: raise NaoEnviado('GMAIL_AUTENTICACAO') from None
        except Exception: raise NaoEnviado('GMAIL_CONEXAO_ANTES_DO_ENVIO') from None
        # Qualquer falha nesta fase pode ocorrer depois da aceitacao remota.
        try: code,_=conn.data(body)
        except Exception: raise ErroEmail('GMAIL_RESULTADO_INCERTO') from None
        exigir(code==250,'GMAIL_RESULTADO_INCERTO')
        return True
    finally:
        if conn is not None:
            try: conn.close()
            except Exception: pass


def enviar_uma_vez(banco,dia,run,enviar,agora=None):
    """Reserva duravel antes da rede. Incerteza bloqueia novas tentativas.
    Nenhuma garantia de entrega ou idempotencia do servidor SMTP.
    """
    sha=hashlib.sha256(payload(dia,run)).hexdigest(); slot=dia.isoformat()
    now=agora if agora is not None else datetime.now(timezone.utc)
    exigir(isinstance(now,datetime) and now.tzinfo is not None,'EMAIL_RELOGIO')
    stamp=now.astimezone(timezone.utc).isoformat()
    p=Path(banco); exigir(p.is_absolute() and not p.is_symlink() and p.resolve()==p,'EMAIL_BANCO_INVALIDO')
    db=sqlite3.connect(p,timeout=40)
    try:
        db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
        objs={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        aid=db.execute('PRAGMA application_id').fetchone()[0]
        if not objs and aid==0:
            db.execute("CREATE TABLE envios(dia TEXT PRIMARY KEY,run TEXT NOT NULL,sha TEXT NOT NULL,utc TEXT NOT NULL,estado TEXT NOT NULL CHECK(estado IN ('pendente','aceito','nao_enviado')))")
            db.execute(f'PRAGMA application_id={APP_ID}')
        else: exigir(objs=={'envios'} and aid==APP_ID,'EMAIL_BANCO_INCOMPATIVEL')
        row=db.execute('SELECT run,sha,utc,estado FROM envios WHERE dia=?',(slot,)).fetchone()
        if row:
            exigir(row[:2]==(run,sha),'EMAIL_CICLO_CONFLITANTE')
            if row[3]=='aceito': db.commit(); return 'JA_ACEITO'
            exigir(row[3]=='nao_enviado','EMAIL_RECONCILIACAO_MANUAL')
            exigir(stamp>=row[2],'EMAIL_RELOGIO')
            db.execute("UPDATE envios SET utc=?,estado='pendente' WHERE dia=?",(stamp,slot))
        else: db.execute("INSERT INTO envios VALUES(?,?,?,?,'pendente')",(slot,run,sha,stamp))
        db.commit() # Reserva persiste inclusive se processo morrer.
        try: resultado=enviar(dia,run)
        except NaoEnviado:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE envios SET estado='nao_enviado' WHERE dia=? AND estado='pendente'",(slot,)); db.commit(); raise
        exigir(resultado is True,'GMAIL_RESULTADO_INCERTO')
        db.execute('BEGIN IMMEDIATE')
        cur=db.execute("UPDATE envios SET estado='aceito' WHERE dia=? AND estado='pendente'",(slot,))
        exigir(cur.rowcount==1,'GMAIL_RESULTADO_INCERTO'); db.commit()
        return 'ACEITO'
    except BaseException:
        db.rollback(); raise
    finally: db.close()
