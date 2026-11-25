# -*- coding: utf-8 -*-
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_fonte_app_v80 import extrair_snapshot_v80, validar_conexao, ErroFonteApp, ROLE, PROJECOES

class TestFonteAppV80(unittest.TestCase):
    def fake(self,session=None,role=(True,True),priv=(False,False),rows=None):
        c=Mock(); cur=c.cursor.return_value
        cur.fetchone.side_effect=[session or (ROLE,ROLE,'teste','on','repeatable read',date(2026,11,25)),role]+[priv]*len(PROJECOES)
        cur.fetchall.side_effect=rows if rows is not None else [[(1,'Alfa')],[],[],[(2,1,'Recebido',date(2026,11,25),'Normal')],[],[],[]]
        return c,cur
    def test_snapshot(self):
        c,cur=self.fake(); s=extrair_snapshot_v80(c,'teste')
        self.assertEqual(s['condominios'],{1:'Alfa'}); self.assertEqual(s['servicos'][0]['prazo'],'2026-11-25'); self.assertEqual(s['lancamentos'],[])
        c.set_session.assert_called_once_with(isolation_level='REPEATABLE READ',readonly=True,autocommit=False)
        c.rollback.assert_called_once(); cur.close.assert_called_once(); c.commit.assert_not_called()
    def test_projecoes_minimas(self):
        c,cur=self.fake(); extrair_snapshot_v80(c,'teste')
        sql=[a.args[0] for a in cur.execute.call_args_list]
        self.assertTrue(all(x.startswith('SELECT ') for x in sql)); self.assertFalse(any('SELECT *' in x or 'senha' in x or 'usuarios' in x or 'imagem' in x for x in sql))
    def test_usuario_errado(self):
        c,_=self.fake(session=('admin','admin','teste','on','repeatable read',date.today()))
        with self.assertRaisesRegex(ErroFonteApp,'SESSAO'): extrair_snapshot_v80(c,'teste')
        c.rollback.assert_called_once()
    def test_transacao_escrita(self):
        c,_=self.fake(session=(ROLE,ROLE,'teste','off','repeatable read',date.today()))
        with self.assertRaisesRegex(ErroFonteApp,'SESSAO'): extrair_snapshot_v80(c,'teste')
    def test_isolamento_errado(self):
        c,_=self.fake(session=(ROLE,ROLE,'teste','on','read committed',date.today()))
        with self.assertRaisesRegex(ErroFonteApp,'SESSAO'): extrair_snapshot_v80(c,'teste')
    def test_banco_errado(self):
        c,_=self.fake()
        with self.assertRaisesRegex(ErroFonteApp,'SESSAO'): extrair_snapshot_v80(c,'outro')
    def test_role_privilegiada(self):
        c,_=self.fake(role=(False,True))
        with self.assertRaisesRegex(ErroFonteApp,'PRIVILEGIADO'): extrair_snapshot_v80(c,'teste')
    def test_role_membro(self):
        c,_=self.fake(role=(True,False))
        with self.assertRaisesRegex(ErroFonteApp,'PRIVILEGIADO'): extrair_snapshot_v80(c,'teste')
    def test_escrita_tabela(self):
        c,_=self.fake(priv=(True,False))
        with self.assertRaisesRegex(ErroFonteApp,'ESCRITA'): extrair_snapshot_v80(c,'teste')
    def test_escrita_coluna(self):
        c,_=self.fake(priv=(False,True))
        with self.assertRaisesRegex(ErroFonteApp,'ESCRITA'): extrair_snapshot_v80(c,'teste')
    def test_truncamento(self):
        c,_=self.fake(rows=[[(i,'x') for i in range(1,1002)]])
        with self.assertRaisesRegex(ErroFonteApp,'LIMITE'): extrair_snapshot_v80(c,'teste')
    def test_duplicidade(self):
        c,_=self.fake(rows=[[(1,'A'),(1,'B')]])
        with self.assertRaisesRegex(ErroFonteApp,'REGISTRO'): extrair_snapshot_v80(c,'teste')
    def test_cadastro_vazio(self):
        c,_=self.fake(rows=[[]])
        with self.assertRaisesRegex(ErroFonteApp,'CADASTRO'): extrair_snapshot_v80(c,'teste')
    def test_falha_sem_dados_sensiveis(self):
        c,cur=self.fake(); cur.execute.side_effect=RuntimeError('segredo ficticio')
        with self.assertRaisesRegex(ErroFonteApp,'^EXTRACAO_FALHOU$'): extrair_snapshot_v80(c,'teste')
        c.rollback.assert_called_once(); cur.close.assert_called_once()
    def test_configuracao_tls(self):
        with tempfile.TemporaryDirectory() as d:
            ca=Path(d)/'ca.crt'; ca.touch()
            cfg=validar_conexao('postgresql://haize_intelligence_ro:fake@ep-teste.neon.tech/teste','ep-teste.neon.tech','teste',ca)
            self.assertEqual(cfg['sslmode'],'verify-full'); self.assertEqual(cfg['sslrootcert'],str(ca.resolve()))
    def test_uri_admin_ou_parametros(self):
        for url in ('postgresql://admin:fake@ep-teste.neon.tech/teste','postgresql://haize_intelligence_ro:fake@ep-teste.neon.tech/teste?sslmode=disable','postgresql://haize_intelligence_ro:fake@outro.neon.tech/teste'):
            with self.subTest(url=url), self.assertRaisesRegex(ErroFonteApp,'CONFIGURACAO'): validar_conexao(url,'ep-teste.neon.tech','teste','ca')

if __name__=='__main__': unittest.main()
