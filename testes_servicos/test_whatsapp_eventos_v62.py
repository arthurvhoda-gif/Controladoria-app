"""Regressoes offline da fila WhatsApp para eventos da Central de Servicos (V6.2).

Usa o banco SQLite em memoria dos testes existentes. Nao abre conexoes com
PostgreSQL, Neon, Render, nem executa envio de mensagens.

Execute a partir da raiz do projeto:
  py -m unittest discover -s testes_servicos -p "test_whatsapp_eventos_v62.py" -v
"""
import unittest

from fastapi import HTTPException

import test_multiplos_participantes as base
import whatsapp_alertas as wa

models = base.models


class FilaWhatsAppEventosV62Teste(unittest.TestCase):
    def setUp(self):
        # Reutiliza a fixture ja validada: SQLite em memoria e usuarios ficticios.
        self.cenario = base.MultiplosParticipantesTeste()
        self.cenario.setUp()
        self.db = self.cenario.db

    def tearDown(self):
        self.cenario.tearDown()

    def autorizar(self, *usuarios):
        for uid in usuarios:
            # Numero ficticio, diferente por usuario; nunca sera enviado.
            numero = f'4399999{uid:04d}'
            wa.salvar_numero_admin(
                uid, wa.NumeroAdministrado(numero=numero),
                self.cenario.req(1), self.db,
            )
            wa.salvar_preferencias(
                wa.PreferenciaEntrada(receber_alertas=True),
                self.cenario.req(uid), self.db,
            )

    def itens(self, servico_id):
        return (self.db.query(models.FilaWhatsApp)
                .filter(models.FilaWhatsApp.servico_id == servico_id)
                .order_by(models.FilaWhatsApp.id).all())

    def destinatarios(self, servico_id):
        return [item.usuario_id for item in self.itens(servico_id)]

    def test_criacao_prepara_um_aviso_por_participante_autorizado(self):
        self.autorizar(2, 5, 6)
        servico = self.cenario.novo()
        itens = self.itens(servico['id'])
        self.assertEqual(sorted(item.usuario_id for item in itens), [2, 5, 6])
        self.assertTrue(all(item.status == 'preparada' for item in itens))
        self.assertEqual(len({item.aviso_id for item in itens}), 3)
        self.assertFalse(any(item.usuario_id == 3 for item in itens))
        for uid in (2, 5, 6):
            self.assertEqual(len(base.api.notificacoes(self.cenario.req(uid), self.db)), 1)

    def test_sem_autorizacao_gera_aviso_interno_mas_nao_fila(self):
        self.autorizar(2, 6)
        servico = self.cenario.novo()
        self.assertEqual(sorted(self.destinatarios(servico['id'])), [2, 6])
        # O executor 5 recebeu o aviso interno mesmo sem autorizar WhatsApp.
        self.assertEqual(len(base.api.notificacoes(self.cenario.req(5), self.db)), 1)

    def test_fiscalizacao_validacao_final_e_encerramento(self):
        self.autorizar(1, 2, 5, 6)
        servico = self.cenario.novo()
        self.assertEqual(sorted(self.destinatarios(servico['id'])), [2, 5, 6])
        for uid in (2, 5, 6):
            self.cenario.acao(servico, uid, 'confirmar')
        for uid in (2, 5):
            self.cenario.acao(servico, uid, 'iniciar')
            self.cenario.acao(servico, uid, 'concluir', 'Concluido em teste.')
        # Finalizada a execucao, apenas o fiscalizador deve ser avisado.
        self.assertEqual(self.destinatarios(servico['id'])[-1:], [6])
        self.cenario.acao(servico, 6, 'validar', 'Fiscalizacao aprovada.')
        # Fiscalizacao aprovada: pedido de validacao final ao criador.
        self.assertEqual(self.destinatarios(servico['id'])[-1:], [1])
        self.cenario.acao(servico, 1, 'validar', 'Validacao final.')
        # Encerramento: aviso aos participantes, excluindo o autor (Controladoria).
        self.assertEqual(sorted(self.destinatarios(servico['id'])[-3:]), [2, 5, 6])
        self.assertEqual(len(self.itens(servico['id'])), 8)
        self.assertEqual(len({item.aviso_id for item in self.itens(servico['id'])}), 8)

    def test_devolucao_avisa_executor_e_nao_outro_condominio(self):
        self.autorizar(2, 3, 6)
        servico = self.cenario.novo(execs=[2], fisc=[6])
        self.cenario.acao(servico, 2, 'confirmar')
        self.cenario.acao(servico, 6, 'confirmar')
        self.cenario.acao(servico, 2, 'iniciar')
        self.cenario.acao(servico, 2, 'concluir', 'Etapa de teste concluida.')
        antes = len(self.itens(servico['id']))
        self.cenario.acao(servico, 6, 'devolver', 'Necessita ajuste.')
        novos = self.itens(servico['id'])[antes:]
        self.assertEqual([item.usuario_id for item in novos], [2])
        self.assertNotIn(3, self.destinatarios(servico['id']))

    def test_acao_nao_autorizada_nao_adiciona_fila(self):
        self.autorizar(2, 3, 6)
        servico = self.cenario.novo(execs=[2], fisc=[6])
        quantidade = len(self.itens(servico['id']))
        with self.assertRaises(HTTPException):
            self.cenario.acao(servico, 3, 'validar')
        self.assertEqual(len(self.itens(servico['id'])), quantidade)


if __name__ == '__main__':
    unittest.main()
