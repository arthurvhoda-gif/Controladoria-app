"""Integracao de diagnostico SOMENTE LEITURA na previa V6.4 (SQLite em memoria)."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException

import test_multiplos_participantes as base
import whatsapp_alertas as wa

models = base.models


class DiagnosticoPreviaV64Teste(unittest.TestCase):
    def setUp(self):
        self.cenario = base.MultiplosParticipantesTeste()
        self.cenario.setUp()
        self.db = self.cenario.db

    def tearDown(self):
        self.cenario.tearDown()

    def autorizar(self, *usuarios):
        for uid in usuarios:
            wa.salvar_numero_admin(
                uid, wa.NumeroAdministrado(numero=f'4399999{uid:04d}'),
                self.cenario.req(1), self.db,
            )
            wa.salvar_preferencias(
                wa.PreferenciaEntrada(receber_alertas=True),
                self.cenario.req(uid), self.db,
            )

    def previas(self, usuario_id=1):
        with patch.dict(os.environ, {'FRONTEND_PUBLIC_URL': 'http://127.0.0.1:5173'}):
            return wa.listar_previas_fila(self.cenario.req(usuario_id), self.db)

    def test_novos_avisos_tem_diagnostico_coerente(self):
        self.autorizar(2, 6)
        servico = self.cenario.novo(execs=[2], fisc=[6])
        result = self.previas()
        self.assertFalse(result['envios_ativos'])
        registros = [p for p in result['previa'] if p['servico_id'] == servico['id']]
        self.assertEqual(len(registros), 2)
        self.assertEqual({p['diagnostico']['situacao'] for p in registros}, {'coerente'})
        self.assertTrue(all(p['diagnostico']['motivo'] for p in registros))
        self.assertTrue(all(p['status'] == 'preparada' for p in registros))

    def test_apos_ciencia_aviso_antigo_sinalizado_sem_cancelar(self):
        self.autorizar(2, 6)
        servico = self.cenario.novo(execs=[2], fisc=[6])
        self.cenario.acao(servico, 2, 'confirmar')
        result = self.previas()
        executor = next(p for p in result['previa'] if p['servico_id'] == servico['id']
                        and p['evento'] == 'nova_tarefa')
        self.assertEqual(executor['diagnostico']['situacao'], 'possivelmente_desatualizado')
        filas = self.db.query(models.FilaWhatsApp).filter(
            models.FilaWhatsApp.servico_id == servico['id']).all()
        self.assertEqual(len(filas), 2)
        self.assertTrue(all(f.status == 'preparada' for f in filas))

    def test_usuario_nao_controladoria_recebe_403(self):
        self.autorizar(2)
        self.cenario.novo(execs=[2], fisc=[6])
        with self.assertRaises(HTTPException) as contexto:
            self.previas(usuario_id=2)
        self.assertEqual(contexto.exception.status_code, 403)

    def test_sem_avisos_retorna_lista_vazia(self):
        result = self.previas()
        self.assertEqual(result['previa'], [])
        self.assertFalse(result['envios_ativos'])

    def test_encerramento_preserva_avisos_informativos(self):
        self.autorizar(1, 2, 6)
        servico = self.cenario.novo(execs=[2], fisc=[6])
        self.cenario.acao(servico, 2, 'confirmar')
        self.cenario.acao(servico, 6, 'confirmar')
        self.cenario.acao(servico, 2, 'iniciar')
        self.cenario.acao(servico, 2, 'concluir', 'Concluido em teste.')
        self.cenario.acao(servico, 6, 'validar', 'Fiscalizacao aprovada.')
        self.cenario.acao(servico, 1, 'validar', 'Validacao final.')
        result = self.previas()
        encerramentos = [p for p in result['previa'] if p['servico_id'] == servico['id']
                         and p['evento'] == 'servico_validado']
        self.assertTrue(encerramentos)
        self.assertTrue(all(p['diagnostico']['situacao'] == 'informativo'
                            for p in encerramentos))
        self.assertTrue(all(f.status == 'preparada' for f in
                            self.db.query(models.FilaWhatsApp).filter(
                                models.FilaWhatsApp.servico_id == servico['id']).all()))


if __name__ == '__main__':
    unittest.main()
