"""Testes de múltiplos executores, fiscalização e isolamento de tarefas.
SQLite em memória: nenhum acesso ao Neon, Render ou produção.
"""
import unittest
from datetime import date, timedelta
from fastapi import HTTPException
import test_servicos as fixture
api = fixture.api
models = fixture.models


class MultiplosParticipantesTeste(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add(models.Condominio(id=1, nome='Condomínio A'))
        self.db.add(models.Condominio(id=2, nome='Condomínio B'))
        self.db.add(models.Usuario(id=1, nome='Gestora', email='gestora@teste.local', senha='x', perfil='Controladoria'))
        self.db.add(models.Usuario(id=2, nome='Zelador A', email='a@teste.local', senha='x', perfil='Checklist', condominio_id=1))
        self.db.add(models.Usuario(id=3, nome='Zelador B', email='b@teste.local', senha='x', perfil='Checklist', condominio_id=2))
        self.db.add(models.Usuario(id=4, nome='Interno', email='interno@teste.local', senha='x', perfil='Solicitante'))
        self.db.add(models.Usuario(id=5, nome='Zelador extra A', email='a2@teste.local', senha='x', perfil='Checklist', condominio_id=1))
        self.db.add(models.Usuario(id=6, nome='Fiscalizador interno', email='f@teste.local', senha='x', perfil='Solicitante'))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def novo(self, execs=[2, 5], fisc=[6]):
        return api.criar(api.ServicoNovo(
            condominio_id=1, executores_ids=execs, fiscalizadores_ids=fisc,
            titulo='Teste de manutenção', descricao='Execução em equipe com fiscalização interna',
            prazo=date.today() + timedelta(days=2),
        ), self.req(1), self.db)

    def req(self, uid):
        from types import SimpleNamespace
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))

    def acao(self, servico, uid, action, obs=''):
        return api.atualizar(servico['id'], api.ServicoAcao(acao=action, observacao=obs), self.req(uid), self.db)

    def test_criar_dois_executores_e_fiscalizador(self):
        s = self.novo()
        self.assertEqual(len(s['executores']), 2)
        self.assertEqual(len(s['fiscalizadores']), 1)
        for uid in (2, 5, 6):
            self.assertEqual(len(api.listar(self.req(uid), self.db)), 1)
            self.assertEqual(len(api.notificacoes(self.req(uid), self.db)), 1)
        self.assertEqual(api.listar(self.req(3), self.db), [])
        self.assertIn('confirmar', api.detalhes(s['id'], self.req(6), self.db)['acoes_disponiveis'])
        self.assertNotIn('iniciar', api.detalhes(s['id'], self.req(6), self.db)['acoes_disponiveis'])

    def test_execucoes_individuais_e_fiscalizacao(self):
        s = self.novo()
        self.acao(s, 2, 'confirmar')
        self.acao(s, 5, 'confirmar')
        self.acao(s, 6, 'confirmar')
        self.assertEqual(api.detalhes(s['id'], self.req(1), self.db)['status'], 'Recebido')
        self.acao(s, 2, 'iniciar')
        # Exigência de iniciar e concluir por pessoa; um executor não finaliza o trabalho do outro.
        a = self.acao(s, 2, 'concluir', 'Minha parte foi executada e verificada.')
        self.assertEqual(a['status'], 'Em andamento')
        self.assertEqual(next(p for p in a['executores'] if p['usuario_id'] == 5)['status'], 'Recebido')
        self.acao(s, 5, 'iniciar')
        a = self.acao(s, 5, 'concluir', 'Minha etapa da manutenção foi concluída.')
        self.assertEqual(a['status'], 'Aguardando fiscalização')
        self.assertIn('validar', api.detalhes(s['id'], self.req(6), self.db)['acoes_disponiveis'])
        with self.assertRaises(HTTPException) as cm:
            self.acao(s, 1, 'validar')
        self.assertEqual(cm.exception.status_code, 403)
        a = self.acao(s, 6, 'validar', 'Fiscalização presencial aprovada.')
        self.assertEqual(a['status'], 'Aguardando validação')
        a = self.acao(s, 1, 'validar')
        self.assertEqual(a['status'], 'Concluído')
        self.assertEqual(len(api.historico(s['id'], self.req(1), self.db)), 10)

    def test_fiscalizador_pode_devolver_mas_nao_executar(self):
        s = self.novo(execs=[2], fisc=[6])
        self.acao(s, 6, 'confirmar')
        with self.assertRaises(HTTPException) as cm:
            self.acao(s, 6, 'iniciar')
        self.assertEqual(cm.exception.status_code, 403)
        self.acao(s, 2, 'confirmar')
        self.acao(s, 2, 'iniciar')
        self.acao(s, 2, 'concluir', 'Manutenção efetuada no condomínio.')
        a = self.acao(s, 6, 'devolver', 'Faltou corrigir um problema identificado na vistoria.')
        self.assertEqual(a['status'], 'Em andamento')
        self.assertEqual(a['executores'][0]['status'], 'Em andamento')
        self.assertTrue(any('devolvido' in n['mensagem'].lower() for n in api.notificacoes(self.req(2), self.db)))

    def test_fiscalizador_nao_pode_validar_antes_de_todos_concluirem(self):
        s = self.novo()
        self.acao(s, 6, 'confirmar')
        self.acao(s, 2, 'confirmar')
        self.acao(s, 2, 'iniciar')
        self.acao(s, 2, 'concluir', 'Etapa de reparo executada.')
        with self.assertRaises(HTTPException) as cm:
            self.acao(s, 6, 'validar')
        self.assertEqual(cm.exception.status_code, 409)

    def test_duplicidade_e_autofiscalizacao_rejeitadas(self):
        for ex, fi in [([2, 2], [6]), ([2], [2]), ([], [6]), ([2, 3], [])]:
            with self.subTest(ex=ex, fi=fi), self.assertRaises(HTTPException) as cm:
                self.novo(execs=ex, fisc=fi)
            self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(self.db.query(models.ServicoInterno).count(), 0)

    def test_outro_condominio_nao_acessa_nem_recebe_aviso(self):
        s = self.novo()
        self.assertEqual(api.listar(self.req(3), self.db), [])
        with self.assertRaises(HTTPException) as cm:
            api.detalhes(s['id'], self.req(3), self.db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(api.notificacoes(self.req(3), self.db), [])

    def test_dois_fiscalizadores_ambos_precisam_validar(self):
        s = self.novo(execs=[2], fisc=[4, 6])
        for u in (2, 4, 6):
            self.acao(s, u, 'confirmar')
        self.acao(s, 2, 'iniciar')
        self.acao(s, 2, 'concluir', 'Execução integral concluída e documentada.')
        a = self.acao(s, 4, 'validar')
        self.assertEqual(a['status'], 'Aguardando fiscalização')
        a = self.acao(s, 6, 'validar')
        self.assertEqual(a['status'], 'Aguardando validação')

    def test_fiscalizador_zelador_de_outro_condominio_rejeitado(self):
        with self.assertRaises(HTTPException) as cm:
            self.novo(execs=[2], fisc=[3])
        self.assertEqual(cm.exception.status_code, 400)

    def test_servico_v1_legado_continua_operavel(self):
        s = api.criar(api.ServicoNovo(condominio_id=1, responsavel_id=2,
            titulo="Verificar portão", descricao="Inspeção simples de portão",
            prazo=date.today() + timedelta(days=2)), self.req(1), self.db)
        self.assertEqual(s['executores'][0]['usuario_id'], 2)
        self.assertEqual(self.acao(s, 2, 'confirmar')['status'], 'Recebido')
        self.acao(s, 2, 'iniciar')
        self.assertEqual(self.acao(s, 2, 'concluir', 'Trabalho finalizado pela pessoa designada.')['status'], 'Aguardando validação')
        self.assertEqual(self.acao(s, 1, 'validar')['status'], 'Concluído')


if __name__ == '__main__':
    unittest.main()
