"""Testes independentes com SQLite em memória. Não toca Neon/Render."""
import sys
import types
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BASE = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BASE))
stub = types.ModuleType('database')
stub.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
stub.SessionLocal = sessionmaker(bind=stub.engine)
from sqlalchemy.orm import declarative_base
stub.Base = declarative_base()
sys.modules['database'] = stub

import models
import servicos_api as api
models.Base.metadata.create_all(stub.engine)
api.SessionLocal = stub.SessionLocal


class ServicosTeste(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(stub.engine)
        models.Base.metadata.create_all(stub.engine)
        self.db = stub.SessionLocal()
        self.db.add(models.Condominio(id=1, nome='Condomínio A'))
        self.db.add(models.Condominio(id=2, nome='Condomínio B'))
        self.db.add(models.Usuario(id=1, nome='Gestora', email='gestora@teste.local', senha='x', perfil='Controladoria'))
        self.db.add(models.Usuario(id=2, nome='Zelador A', email='a@teste.local', senha='x', perfil='Checklist', condominio_id=1))
        self.db.add(models.Usuario(id=3, nome='Zelador B', email='b@teste.local', senha='x', perfil='Checklist', condominio_id=2))
        self.db.add(models.Usuario(id=4, nome='Interno', email='interno@teste.local', senha='x', perfil='Solicitante'))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def req(self, id):
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=id))

    def criar(self):
        return api.criar(api.ServicoNovo(condominio_id=1, responsavel_id=2,
            titulo='Conferir portão', descricao='Verificar problema no portão',
            prazo=date.today()+timedelta(days=3)), self.req(1), self.db)

    def test_fluxo_completo_e_historico(self):
        s = self.criar()
        self.assertEqual(s['status'], 'Aguardando ciência')
        self.assertEqual(len(api.listar(self.req(2), self.db)), 1)
        self.assertEqual(api.listar(self.req(3), self.db), [])
        self.assertEqual(len(api.notificacoes(self.req(2), self.db)), 1)
        for usuario, acao, observacao, status in [
            (2, 'confirmar', '', 'Recebido'),
            (2, 'iniciar', '', 'Em andamento'),
            (2, 'concluir', 'Finalizado com revisão visual.', 'Aguardando validação'),
            (1, 'validar', 'Verificação presencial concluída.', 'Concluído'),
        ]:
            res = api.atualizar(s['id'], api.ServicoAcao(acao=acao, observacao=observacao), self.req(usuario), self.db)
            self.assertEqual(res['status'], status)
        self.assertEqual(len(api.historico(s['id'], self.req(1), self.db)), 5)
        self.assertEqual(len(api.notificacoes(self.req(1), self.db)), 1)

    def test_restricoes_por_condominio_e_perfil(self):
        with self.assertRaises(HTTPException) as cm:
            api.criar(api.ServicoNovo(condominio_id=2, responsavel_id=2,
                titulo='Verificar garagem', descricao='Teste com condomínio errado',
                prazo=date.today()+timedelta(days=1)), self.req(1), self.db)
        self.assertEqual(cm.exception.status_code, 400)
        s = self.criar()
        for usuario in (3, 4):
            with self.assertRaises(HTTPException) as cm:
                api.detalhes(s['id'], self.req(usuario), self.db)
            self.assertEqual(cm.exception.status_code, 404)
        with self.assertRaises(HTTPException) as cm:
            api.atualizar(s['id'], api.ServicoAcao(acao='confirmar'), self.req(1), self.db)
        self.assertEqual(cm.exception.status_code, 403)
        with self.assertRaises(HTTPException) as cm:
            api.criar(api.ServicoNovo(condominio_id=1, responsavel_id=2,
                titulo='Teste não autorizado', descricao='Não pode abrir tarefa',
                prazo=date.today()+timedelta(days=2)), self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 403)

    def test_nao_permite_atualizacao_fora_de_sequencia(self):
        s = self.criar()
        with self.assertRaises(HTTPException) as cm:
            api.atualizar(s['id'], api.ServicoAcao(acao='concluir', observacao='Tentativa indevida de encerramento'), self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 409)
        api.atualizar(s['id'], api.ServicoAcao(acao='confirmar'), self.req(2), self.db)
        with self.assertRaises(HTTPException) as cm:
            api.atualizar(s['id'], api.ServicoAcao(acao='confirmar'), self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertEqual(len(api.historico(s['id'], self.req(1), self.db)), 2)

    def test_somente_destinatario_marca_notificacao(self):
        s = self.criar()
        n = api.notificacoes(self.req(2), self.db)[0]
        with self.assertRaises(HTTPException) as cm:
            api.ler_aviso(n['id'], self.req(3), self.db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(api.ler_aviso(n['id'], self.req(2), self.db), {'ok': True})
        self.assertTrue(api.notificacoes(self.req(2), self.db)[0]['lida'])


if __name__ == '__main__':
    unittest.main()
