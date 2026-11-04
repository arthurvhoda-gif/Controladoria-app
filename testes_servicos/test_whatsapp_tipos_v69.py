"""Tipos de avisos: SQLite em memoria, sem envio."""
import unittest
import test_multiplos_participantes as base

class TiposV69Teste(unittest.TestCase):
    def setUp(self):
        self.c = base.MultiplosParticipantesTeste()
        self.c.setUp()
    def tearDown(self):
        self.c.tearDown()
    def tipos(self):
        return [a.tipo_evento for a in self.c.db.query(base.models.ServicoAviso).order_by(base.models.ServicoAviso.id).all()]
    def test_ciclo_com_devolucao(self):
        s = self.c.novo(execs=[2], fisc=[6])
        self.assertEqual(self.tipos(), ['nova_tarefa', 'designacao_fiscal'])
        for uid in (2, 6): self.c.acao(s, uid, 'confirmar')
        self.c.acao(s, 2, 'iniciar')
        self.c.acao(s, 2, 'concluir', 'Etapa concluida em teste.')
        self.assertEqual(self.tipos()[-1], 'pronto_fiscalizacao')
        self.c.acao(s, 6, 'devolver', 'Ajustes necessarios em teste.')
        self.assertEqual(self.tipos()[-1], 'devolucao')
        self.c.acao(s, 2, 'concluir', 'Ajustes concluidos em teste.')
        self.c.acao(s, 6, 'validar')
        self.assertEqual(self.tipos()[-1], 'validacao_final')
        self.c.acao(s, 1, 'validar')
        self.assertEqual(self.tipos()[-2:], ['servico_validado', 'servico_validado'])
        self.assertTrue(all(a.evento_id for a in self.c.db.query(base.models.ServicoAviso).all()))
    def test_legado_sem_tipo_preservado(self):
        s = self.c.novo(execs=[2], fisc=[])
        tarefa = self.c.db.get(base.models.ServicoInterno, s['id'])
        base.api.notificar(self.c.db, 2, tarefa, 'Aviso legado')
        self.c.db.flush()
        self.assertIsNone(self.tipos()[-1])
    def test_tipo_invalido_ou_sem_origem_nao_cria_aviso(self):
        s = self.c.novo(execs=[2], fisc=[])
        tarefa = self.c.db.get(base.models.ServicoInterno, s['id'])
        antes = len(self.tipos())
        for tipo in ('inexistente', 'nova_tarefa'):
            with self.assertRaises(ValueError):
                base.api.notificar(self.c.db, 2, tarefa, 'Teste', tipo_evento=tipo)
        self.assertEqual(len(self.tipos()), antes)

if __name__ == '__main__':
    unittest.main()
