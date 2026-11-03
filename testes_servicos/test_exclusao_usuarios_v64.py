"""V6.4: exclusao segura de usuarios em tarefas abertas, SQLite em memoria.

Testa o endpoint real (extraido por AST) sem importar main.py, sem conectar
PostgreSQL/Neon, sem enviar mensagens e sem mudar arquivos em producao.
"""
import ast
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session

import test_servicos as fixture
import usuarios_pendencias

models = fixture.models
api = fixture.api
MAIN = Path(__file__).resolve().parents[1] / 'backend' / 'main.py'


def carregar_endpoint_exclusao():
    arvore = ast.parse(MAIN.read_text(encoding='utf-8-sig'))
    metodo = next(n for n in arvore.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'excluir_usuario')
    metodo.decorator_list = []
    namespace = {
        'models': models,
        'HTTPException': HTTPException,
        'Request': Request,
        'Session': Session,
        'Depends': Depends,
        'get_db': lambda: None,
        'contar_servicos_pendentes': usuarios_pendencias.contar_servicos_pendentes,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[metodo], type_ignores=[])),
                 str(MAIN), 'exec'), namespace)
    return namespace['excluir_usuario']


class ExclusaoUsuariosV64Teste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.excluir = staticmethod(carregar_endpoint_exclusao())

    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome='Condominio de testes'),
            models.Usuario(id=1, nome='Gestora', email='gestora@teste.local', senha='x', perfil='Controladoria'),
            models.Usuario(id=2, nome='Executor', email='executor@teste.local', senha='x', perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Fiscalizador', email='fiscal@teste.local', senha='x', perfil='Solicitante'),
            models.Usuario(id=4, nome='Outro gestor', email='gestor2@teste.local', senha='x', perfil='Controladoria'),
            models.Usuario(id=5, nome='Sem tarefas', email='livre@teste.local', senha='x', perfil='Solicitante'),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def req(self, uid=1):
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))

    def criar(self, criador=1):
        return api.criar(api.ServicoNovo(
            condominio_id=1, executores_ids=[2], fiscalizadores_ids=[3],
            titulo='Tarefa em aberto', descricao='Teste de responsabilidade antes de exclusao',
            prazo=date.today() + timedelta(days=3)
        ), self.req(criador), self.db)

    def assert_bloqueado(self, uid):
        with self.assertRaises(HTTPException) as capturado:
            self.excluir(uid, self.req(), self.db)
        self.assertEqual(capturado.exception.status_code, 409)
        self.assertIsNotNone(self.db.get(models.Usuario, uid))
        self.assertIn('em aberto', str(capturado.exception.detail).lower())

    def test_impede_exclusao_do_criador_com_servico_aberto(self):
        self.criar(criador=4)
        self.assert_bloqueado(4)

    def test_impede_exclusao_de_executor_com_servico_aberto(self):
        self.criar()
        self.assert_bloqueado(2)

    def test_impede_exclusao_de_fiscalizador_com_servico_aberto(self):
        self.criar()
        self.assert_bloqueado(3)

    def test_pessoa_sem_servicos_pode_ser_excluida(self):
        retorno = self.excluir(5, self.req(), self.db)
        self.assertIn('mensagem', retorno)
        self.assertIsNone(self.db.get(models.Usuario, 5))

    def test_tarefa_fechada_nao_impede_exclusao_por_si_so(self):
        servico = self.criar()
        registro = self.db.get(models.ServicoInterno, servico['id'])
        registro.status = api.STATUS_FECHADO
        self.db.commit()
        self.assertEqual(usuarios_pendencias.contar_servicos_pendentes(self.db, 2), 0)
        self.excluir(2, self.req(), self.db)
        self.assertIsNone(self.db.get(models.Usuario, 2))

    def test_conta_servico_uma_vez_se_for_criador_e_participante(self):
        servico = self.criar()
        self.db.add(models.ServicoParticipante(
            servico_id=servico['id'], usuario_id=1, usuario_nome='Gestora',
            papel='fiscalizador', status=api.STATUS_NOVO))
        self.db.commit()
        self.assertEqual(usuarios_pendencias.contar_servicos_pendentes(self.db, 1), 1)

    def test_nao_permite_excluir_a_propria_conta(self):
        with self.assertRaises(HTTPException) as capturado:
            self.excluir(1, self.req(1), self.db)
        self.assertEqual(capturado.exception.status_code, 400)

    def test_usuario_inexistente_resulta_404(self):
        with self.assertRaises(HTTPException) as capturado:
            self.excluir(99999, self.req(), self.db)
        self.assertEqual(capturado.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
