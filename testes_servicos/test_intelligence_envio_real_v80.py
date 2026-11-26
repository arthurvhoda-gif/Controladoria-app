import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from datetime import date
from email.message import EmailMessage
from email.policy import SMTP
from tempfile import TemporaryDirectory
import sqlite3

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_envio_real_v80 import (DESTINO, validar_mensagem, enviar_uma_vez_real, enviar_gmail_real, ErroEmail, NaoEnviado)

DIA=date(2026,11,26); RUN='a'*32

def mensagem(dia=DIA,run=RUN,body='Parecer privado',alterar=None):
    m=EmailMessage(policy=SMTP); m['From']='HAIZE Intelligence <'+DESTINO+'>'; m['To']=DESTINO; m['Subject']='HAIZE INTELLIGENCE | Prévia local '+dia.isoformat(); m['Message-ID']='<haize-v80-local-'+dia.isoformat()+'-'+run+'@gmail.com>'; m.set_content(body)
    if alterar: alterar(m)
    return m.as_bytes()

class TestEnvioReal(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.db=Path(self.tmp.name).resolve()/'real.sqlite3'; self.raw=mensagem(); self.send=Mock(return_value=True)
    def enviar(self,raw=None,run=RUN,dia=DIA):
        return enviar_uma_vez_real(self.db,dia,run,self.raw if raw is None else raw,self.send)
    def test_mensagem(self): self.assertEqual(len(validar_mensagem(DIA,RUN,self.raw)),64)
    def test_destino(self):
        with self.assertRaises(ErroEmail): validar_mensagem(DIA,RUN,mensagem(alterar=lambda m:m.replace_header('To','outro@example.org')))
    def test_cc(self):
        with self.assertRaises(ErroEmail): validar_mensagem(DIA,RUN,mensagem(alterar=lambda m:m.__setitem__('Cc','outro@example.org')))
    def test_data(self):
        with self.assertRaises(ErroEmail): validar_mensagem(date(2026,11,27),RUN,self.raw)
    def test_id(self):
        with self.assertRaises(ErroEmail): validar_mensagem(DIA,'b'*32,self.raw)
    def test_aceito(self):
        self.assertEqual(self.enviar(),'ACEITO'); self.assertEqual(self.enviar(),'JA_ACEITO'); self.send.assert_called_once_with(DIA,RUN,self.raw)
    def test_conteudo_divergente(self):
        self.enviar()
        with self.assertRaises(ErroEmail): self.enviar(mensagem(body='outro conteúdo'))
        self.send.assert_called_once()
    def test_ciclo_divergente(self):
        self.enviar()
        with self.assertRaises(ErroEmail): self.enviar(mensagem(run='b'*32),run='b'*32)
        self.send.assert_called_once()
    def test_falha_antes_data(self):
        self.send.side_effect=NaoEnviado('falha')
        with self.assertRaises(NaoEnviado): self.enviar()
        self.send.side_effect=None; self.assertEqual(self.enviar(),'ACEITO'); self.assertEqual(self.send.call_count,2)
    def test_incerteza_bloqueia(self):
        self.send.side_effect=ErroEmail('incerto')
        with self.assertRaises(ErroEmail): self.enviar()
        self.send.side_effect=None
        with self.assertRaisesRegex(ErroEmail,'RECONCILIACAO'): self.enviar()
        with self.assertRaisesRegex(ErroEmail,'RECONCILIACAO'): self.enviar(mensagem(dia=date(2026,11,28)),dia=date(2026,11,28))
        self.send.assert_called_once()
    def test_banco_incompativel(self):
        db=sqlite3.connect(self.db)
        try: db.execute('CREATE TABLE outro(x)'); db.commit()
        finally: db.close()
        with self.assertRaisesRegex(ErroEmail,'INCOMPATIVEL'): self.enviar()
        self.send.assert_not_called()
    @patch('intelligence_envio_real_v80.smtplib.SMTP_SSL')
    def test_smtp_aceito(self,smtp):
        c=smtp.return_value; c.mail.return_value=(250,b''); c.rcpt.return_value=(250,b''); c.data.return_value=(250,b'')
        self.assertTrue(enviar_gmail_real('a'*16,DIA,RUN,self.raw)); c.rcpt.assert_called_once_with(DESTINO); c.data.assert_called_once_with(self.raw); c.close.assert_called_once()
    @patch('intelligence_envio_real_v80.smtplib.SMTP_SSL')
    def test_smtp_recusa(self,smtp):
        c=smtp.return_value; c.mail.return_value=(250,b''); c.rcpt.return_value=(550,b'')
        with self.assertRaises(NaoEnviado): enviar_gmail_real('a'*16,DIA,RUN,self.raw)
        c.data.assert_not_called()
    @patch('intelligence_envio_real_v80.smtplib.SMTP_SSL')
    def test_smtp_incerteza(self,smtp):
        c=smtp.return_value; c.mail.return_value=(250,b''); c.rcpt.return_value=(250,b''); c.data.side_effect=TimeoutError()
        with self.assertRaises(ErroEmail) as e: enviar_gmail_real('a'*16,DIA,RUN,self.raw)
        self.assertNotIsInstance(e.exception,NaoEnviado)

if __name__=='__main__': unittest.main()
