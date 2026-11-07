# -*- coding: utf-8 -*-
"""Conferência V7.3, SEM DESPACHO: sessão única e bloqueios conservadores.

Todos os dados são fictícios. SQLite exercita regras de negócio; o ensaio
PostgreSQL separado comprova locks reais.
"""
import unittest
from fastapi import HTTPException

import test_multiplos_participantes as base
import whatsapp_alertas as wa

models = base.models


class VerificacaoTransacionalWhatsAppV73(unittest.TestCase):
    def setUp(self):
        self.c = base.MultiplosParticipantesTeste()
        self.c.setUp()
        self.db = self.c.db

    def tearDown(self):
        self.c.tearDown()

    def autorizar(self, uid=2):
        numero = f'4399999{uid:04d}'
        wa.salvar_numero_admin(
            uid, wa.NumeroAdministrado(numero=numero),
            self.c.req(1), self.db,
        )
        wa.salvar_preferencias(
            wa.PreferenciaEntrada(receber_alertas=True,
                                   numero_confirmado=f'+55{numero}'),
            self.c.req(uid), self.db,
        )

    def preparar(self):
        self.autorizar(2)
        servico = self.c.novo(execs=[2], fisc=[6])
        fila = (self.db.query(models.FilaWhatsApp)
                .filter_by(servico_id=servico['id'], usuario_id=2).one())
        return servico, fila.id

    def conferir(self, fila_id, uid=1):
        return wa.verificar_aviso_preparado(fila_id, self.c.req(uid), self.db)

    def test_conferencia_atual_revisar_sem_envio_nem_escrita(self):
        servico, fila_id = self.preparar()
        antes_filas = [(f.id, f.status) for f in self.db.query(models.FilaWhatsApp).all()]
        antes_auditorias = self.db.query(models.WhatsAppAuditoriaConsentimento).count()
        primeiro = self.conferir(fila_id)
        segundo = self.conferir(fila_id)
        self.assertEqual(primeiro['servico_id'], servico['id'])
        self.assertEqual(primeiro['situacao'], 'revisar')
        self.assertEqual(primeiro['diagnostico_atual'], 'coerente')
        self.assertEqual(primeiro['diagnostico_historico'], 'nao_comprovado')
        self.assertTrue(primeiro['conferencia_transacional'])
        self.assertFalse(primeiro['envio_autorizado'])
        self.assertFalse(primeiro['envios_ativos'])
        self.assertEqual(primeiro['impedimentos'], [])
        self.assertTrue(primeiro['pendencias'])
        self.assertEqual(segundo['situacao'], primeiro['situacao'])
        self.assertEqual(antes_filas,
                         [(f.id, f.status) for f in self.db.query(models.FilaWhatsApp).all()])
        self.assertEqual(antes_auditorias,
                         self.db.query(models.WhatsAppAuditoriaConsentimento).count())
        self.assertNotIn('+5543999990002', str(primeiro))

    def test_escopo_admin_e_nao_existente(self):
        _, fila_id = self.preparar()
        with self.assertRaises(HTTPException) as ex:
            self.conferir(fila_id, uid=2)
        self.assertEqual(ex.exception.status_code, 403)
        with self.assertRaises(HTTPException) as ex:
            self.conferir(99999)
        self.assertEqual(ex.exception.status_code, 404)

    def test_ciencia_apos_origem_impede_aviso_antigo(self):
        servico, fila_id = self.preparar()
        self.c.acao(servico, 2, 'confirmar')
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'impedido')
        self.assertIn('Evento de origem superado', ' '.join(resposta['impedimentos']))
        self.assertFalse(resposta['envio_autorizado'])

    def test_retirada_do_condominio_impede_aviso_preparado(self):
        _, fila_id = self.preparar()
        self.db.get(models.Usuario, 2).condominio_id = 2
        self.db.commit()
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'impedido')
        self.assertIn('perdeu acesso', ' '.join(resposta['impedimentos']))
        self.assertEqual(self.db.get(models.FilaWhatsApp, fila_id).status, 'preparada')

    def test_troca_numero_cancela_fila_e_conferencia_recusa(self):
        _, fila_id = self.preparar()
        wa.salvar_numero_admin(2, wa.NumeroAdministrado(numero='43888887777'),
                               self.c.req(1), self.db)
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'impedido')
        self.assertEqual(resposta['status_fila'], 'cancelada')
        self.assertFalse(resposta['envio_autorizado'])

    def test_origem_ausente_falha_conservadora(self):
        _, fila_id = self.preparar()
        fila = self.db.get(models.FilaWhatsApp, fila_id)
        self.db.get(models.ServicoAviso, fila.aviso_id).evento_id = None
        self.db.commit()
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'revisar')
        self.assertIn('sem evento', ' '.join(resposta['pendencias']).lower())
        self.assertFalse(resposta['envio_autorizado'])

    def test_duplicacao_mesmo_evento_mesmo_destinatario_impede(self):
        _, fila_id = self.preparar()
        fila = self.db.get(models.FilaWhatsApp, fila_id)
        aviso = self.db.get(models.ServicoAviso, fila.aviso_id)
        duplicado = models.ServicoAviso(
            servico_id=aviso.servico_id, usuario_id=aviso.usuario_id,
            evento_id=aviso.evento_id, tipo_evento=aviso.tipo_evento,
            mensagem='Outro aviso fictício repetido',
        )
        self.db.add(duplicado)
        self.db.flush()
        self.db.add(models.FilaWhatsApp(
            aviso_id=duplicado.id, usuario_id=aviso.usuario_id,
            servico_id=aviso.servico_id, status='preparada',
        ))
        self.db.commit()
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'impedido')
        self.assertIn('múltiplos avisos', ' '.join(resposta['impedimentos']).lower())

    def test_consentimento_revogado_sem_cancelar_manual_falha_fechado(self):
        _, fila_id = self.preparar()
        self.db.get(models.PreferenciaWhatsApp, 2).consentimento = 0
        self.db.commit()
        resposta = self.conferir(fila_id)
        self.assertEqual(resposta['situacao'], 'impedido')
        self.assertIn('Sem número', ' '.join(resposta['impedimentos']))
        self.assertEqual(self.db.get(models.FilaWhatsApp, fila_id).status, 'preparada')


if __name__ == '__main__':
    unittest.main()
