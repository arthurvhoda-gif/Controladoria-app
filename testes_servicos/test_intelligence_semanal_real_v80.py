from datetime import date
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_semanal_real_v80 import executar, OUTBOX_ID, APP_ID

RUN='a'*32
OTHER='b'*32
SAB=date(2026,11,28)

class Semanal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name).resolve()
        self.produzir=Mock(return_value=RUN); self.preparar=Mock(return_value=b'parecer'); self.transmitir=Mock(return_value='ACEITO')
    def rodar(self,dia=SAB):
        return executar(self.raiz,dia,self.produzir,self.preparar,self.transmitir)
    def fila(self,estado='aceito',run=RUN,dia=SAB,aid=OUTBOX_ID):
        with closing(sqlite3.connect(self.raiz/'EMAIL_LOCAL_REAL_V80.sqlite3')) as db, db:
            db.execute(f'PRAGMA application_id={aid}'); db.execute('PRAGMA user_version=1')
            db.execute('CREATE TABLE IF NOT EXISTS envios(dia TEXT PRIMARY KEY,run TEXT,estado TEXT)')
            db.execute('INSERT INTO envios VALUES(?,?,?)',(dia.isoformat(),run,estado))
    def test_fora_sabado(self):
        self.assertEqual(self.rodar(date(2026,11,29)),('FORA_DO_SABADO',None)); self.produzir.assert_not_called(); self.transmitir.assert_not_called(); self.assertFalse(list(self.raiz.iterdir()))
    def test_primeiro(self):
        self.assertEqual(self.rodar(),('ACEITO',RUN)); self.preparar.assert_called_once_with(RUN); self.transmitir.assert_called_once_with(SAB,RUN,b'parecer')
    def test_reutiliza_slot(self):
        self.rodar(); self.rodar(); self.produzir.assert_called_once()
    def test_falha_preparacao(self):
        self.preparar.side_effect=ValueError('falha')
        with self.assertRaises(ValueError): self.rodar()
        self.transmitir.assert_not_called(); self.preparar.side_effect=None; self.rodar(); self.produzir.assert_called_once()
    def test_falha_producao(self):
        self.produzir.side_effect=ValueError('falha')
        with self.assertRaises(ValueError): self.rodar()
        self.preparar.assert_not_called(); self.transmitir.assert_not_called()
        self.produzir.side_effect=None; self.assertEqual(self.rodar(),('ACEITO',RUN))
    def test_aceito_manual(self):
        self.fila(); self.assertEqual(self.rodar(),('JA_ACEITO',RUN)); self.produzir.assert_not_called(); self.transmitir.assert_not_called()
    def test_nao_enviado_manual(self):
        self.fila('nao_enviado',OTHER); self.assertEqual(self.rodar(),('ACEITO',OTHER)); self.produzir.assert_not_called(); self.preparar.assert_called_once_with(OTHER)
    def test_incerteza_anterior(self):
        self.fila('pendente',dia=date(2026,11,26))
        with self.assertRaisesRegex(ValueError,'RECONCILIACAO'): self.rodar()
        self.produzir.assert_not_called(); self.transmitir.assert_not_called()
    def test_conflito(self):
        self.rodar(); self.fila('aceito',OTHER); self.transmitir.reset_mock()
        with self.assertRaisesRegex(ValueError,'CONFLITANTE'): self.rodar()
        self.transmitir.assert_not_called()
    def test_fila_incompativel(self):
        self.fila(aid=0)
        with self.assertRaisesRegex(ValueError,'INCOMPATIVEL'): self.rodar()
        self.produzir.assert_not_called()
    def test_outro_sabado(self):
        self.rodar(); self.fila(); self.produzir.return_value=OTHER
        self.assertEqual(self.rodar(date(2026,12,5)),('ACEITO',OTHER)); self.assertEqual(self.produzir.call_count,2)
    def test_falha_transmissao_reutiliza(self):
        self.transmitir.side_effect=ValueError('falha')
        with self.assertRaises(ValueError): self.rodar()
        self.transmitir.side_effect=None; self.rodar(); self.produzir.assert_called_once()
