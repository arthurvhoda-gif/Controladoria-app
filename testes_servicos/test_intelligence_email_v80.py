import sqlite3
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date,datetime,timezone,timedelta
from email import policy
from email.parser import BytesParser
from unittest.mock import Mock,patch
import smtplib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_email_v80 import payload,enviar_uma_vez,enviar_gmail,senha_app,ErroEmail,NaoEnviado,DESTINO

class TestEmailV80(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name).resolve()/'email.sqlite3'; self.dia=date(2026,11,26); self.run='a'*32
        self.now=datetime(2026,11,26,10,tzinfo=timezone.utc); self.send=Mock(return_value=True)
    def call(self,**kwargs):
        args=dict(banco=self.db,dia=self.dia,run=self.run,enviar=self.send,agora=self.now); args.update(kwargs); return enviar_uma_vez(**args)
    def test_destino_fixo(self):
        m=BytesParser(policy=policy.default).parsebytes(payload(self.dia,self.run)); self.assertEqual(m['To'],DESTINO); self.assertEqual(m['From'].addresses[0].addr_spec,DESTINO); self.assertIsNone(m['Cc']); self.assertIsNone(m['Bcc']); self.assertFalse(m.is_multipart()); self.assertIn('HOMOLOGACAO',m.get_content())
    def test_run_invalido(self):
        with self.assertRaises(ErroEmail): self.call(run='invalido')
        self.send.assert_not_called()
    def test_aceite(self): self.assertEqual(self.call(),'ACEITO'); self.send.assert_called_once()
    def test_duplicidade(self):
        self.call(); self.assertEqual(self.call(),'JA_ACEITO'); self.send.assert_called_once()
    def test_conflito(self):
        self.call()
        with self.assertRaisesRegex(ErroEmail,'CONFLITANTE'): self.call(run='b'*32)
        self.send.assert_called_once()
    def test_retry_falha_segura(self):
        self.send.side_effect=[NaoEnviado('GMAIL_AUTENTICACAO'),True]
        with self.assertRaises(NaoEnviado): self.call()
        self.assertEqual(self.call(agora=self.now+timedelta(minutes=15)),'ACEITO'); self.assertEqual(self.send.call_args_list[0],self.send.call_args_list[1])
    def test_incerto_sem_retry(self):
        self.send.side_effect=ErroEmail('GMAIL_RESULTADO_INCERTO')
        with self.assertRaises(ErroEmail): self.call()
        with self.assertRaisesRegex(ErroEmail,'RECONCILIACAO_MANUAL'): self.call()
        self.send.assert_called_once()
    def test_relogio_retrocede(self):
        self.send.side_effect=NaoEnviado('GMAIL_AUTENTICACAO')
        with self.assertRaises(NaoEnviado): self.call()
        with self.assertRaisesRegex(ErroEmail,'RELOGIO'): self.call(agora=self.now-timedelta(seconds=1))
        self.send.assert_called_once()
    def test_novo_dia(self):
        self.call(); self.assertEqual(self.call(dia=self.dia+timedelta(days=1),run='b'*32,agora=self.now+timedelta(days=1)),'ACEITO'); self.assertEqual(self.send.call_count,2)
    def test_resposta_invalida(self):
        self.send.return_value=False
        with self.assertRaisesRegex(ErroEmail,'INCERTO'): self.call()
        with self.assertRaisesRegex(ErroEmail,'RECONCILIACAO_MANUAL'): self.call()
        self.send.assert_called_once()
    def test_banco_alheio(self):
        with closing(sqlite3.connect(self.db)) as db: db.execute('CREATE TABLE outro(id)'); db.commit()
        with self.assertRaisesRegex(ErroEmail,'INCOMPATIVEL'): self.call()
        self.send.assert_not_called()
    def test_senha_app(self):
        self.assertEqual(senha_app('abcd efgh ijkl mnop'),'abcdefghijklmnop')
        with self.assertRaises(ErroEmail): senha_app('senha')
    @patch('intelligence_email_v80.smtplib.SMTP_SSL')
    def test_smtp_tls_destino(self,con):
        c=con.return_value; c.mail.return_value=(250,b''); c.rcpt.return_value=(250,b''); c.data.return_value=(250,b'')
        self.assertTrue(enviar_gmail('abcdefghijklmnop',self.dia,self.run)); self.assertEqual(con.call_args.args,('smtp.gmail.com',465)); self.assertTrue(con.call_args.kwargs['context'].check_hostname); c.login.assert_called_once_with(DESTINO,'abcdefghijklmnop'); c.mail.assert_called_once_with(DESTINO); c.rcpt.assert_called_once_with(DESTINO); c.data.assert_called_once_with(payload(self.dia,self.run)); c.close.assert_called_once()
    @patch('intelligence_email_v80.smtplib.SMTP_SSL')
    def test_smtp_auth_recusada(self,con):
        c=con.return_value; c.login.side_effect=smtplib.SMTPAuthenticationError(535,b'secret')
        with self.assertRaisesRegex(NaoEnviado,'^GMAIL_AUTENTICACAO$'): enviar_gmail('abcdefghijklmnop',self.dia,self.run)
        c.data.assert_not_called(); c.close.assert_called_once()
    @patch('intelligence_email_v80.smtplib.SMTP_SSL')
    def test_smtp_timeout_data(self,con):
        c=con.return_value; c.mail.return_value=(250,b''); c.rcpt.return_value=(250,b''); c.data.side_effect=TimeoutError('secret')
        with self.assertRaisesRegex(ErroEmail,'^GMAIL_RESULTADO_INCERTO$'): enviar_gmail('abcdefghijklmnop',self.dia,self.run)
        c.close.assert_called_once()
    def test_reserva_concorrente(self):
        def enviar(*args):
            with self.assertRaisesRegex(ErroEmail,'RECONCILIACAO_MANUAL'): self.call()
            return True
        self.assertEqual(self.call(enviar=enviar),'ACEITO')

if __name__=='__main__': unittest.main()
