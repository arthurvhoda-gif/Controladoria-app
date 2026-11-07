# -*- coding: utf-8 -*-
"""V7.3: historico de consentimento no WhatsApp sem disparos externos."""
import json
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
import test_servicos as fixture
import models
import servicos_api as servicos
import whatsapp_alertas as wa
import main as app

class AuditoriaConsentimentoV73(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome='Condominio Ficticio'),
            models.Usuario(id=1, nome='Controladoria', email='gestor@teste.local',
                           senha='x', perfil='Controladoria'),
            models.Usuario(id=2, nome='Zelador', email='zelador@teste.local',
                           senha='x', perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Outro', email='outro@teste.local',
                           senha='x', perfil='Solicitante'),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def req(uid):
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))

    def numero(self, numero='(43) 99999-1111'):
        return wa.salvar_numero_admin(2, wa.NumeroAdministrado(numero=numero),
                                     self.req(1), self.db)

    def consentir(self, valor, confirmado=None):
        pref = self.db.get(models.PreferenciaWhatsApp, 2)
        return wa.salvar_preferencias(wa.PreferenciaEntrada(
            receber_alertas=valor,
            numero_confirmado=confirmado if confirmado is not None else
                (pref.telefone if pref else None)),
            self.req(2), self.db)

    def auditoria(self):
        return wa.consultar_auditoria(2, self.req(1), self.db)['historico']

    def test_optin_optout_auditados_uma_unica_vez(self):
        self.numero()
        self.consentir(True)
        self.consentir(True)  # reenvio idempotente
        self.consentir(False)
        self.consentir(False)
        logs = self.db.query(models.WhatsAppAuditoriaConsentimento).order_by(
            models.WhatsAppAuditoriaConsentimento.id).all()
        self.assertEqual([x.acao for x in logs], ['concedido', 'revogado'])
        self.assertEqual([x.origem for x in logs], ['usuario', 'usuario'])
        self.assertTrue(all(x.alterado_por_id == 2 for x in logs))
        self.assertTrue(all(x.telefone_final == '1111' for x in logs))
        self.assertIsNone(self.db.get(models.PreferenciaWhatsApp, 2).consentido_em)

    def test_troca_numero_revoga_consentimento_e_fila(self):
        self.numero()
        self.consentir(True)
        servicos.criar(servicos.ServicoNovo(
            condominio_id=1, executores_ids=[2],
            titulo='Conferir portao', descricao='Teste de notificacao ao zelador',
            prazo=__import__('datetime').date.today() + __import__('datetime').timedelta(days=2)),
            self.req(1), self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).filter_by(status='preparada').count(), 1)
        self.numero('(43) 98888-2222')
        self.assertEqual(self.db.query(models.FilaWhatsApp).filter_by(status='cancelada').count(), 1)
        self.assertEqual([x.acao for x in self.db.query(models.WhatsAppAuditoriaConsentimento).order_by(
            models.WhatsAppAuditoriaConsentimento.id).all()], ['concedido', 'revogado_troca_numero'])
        log = self.db.query(models.WhatsAppAuditoriaConsentimento).order_by(
            models.WhatsAppAuditoriaConsentimento.id.desc()).first()
        self.assertEqual((log.origem, log.alterado_por_id, log.telefone_final),
                         ('controladoria', 1, '1111'))
        self.assertFalse(self.db.get(models.PreferenciaWhatsApp, 2).consentimento)

    def test_historico_restrito_sem_telefone_completo(self):
        self.numero()
        self.consentir(True)
        dados = wa.consultar_auditoria(2, self.req(1), self.db)
        self.assertEqual(dados['usuario_id'], 2)
        self.assertEqual({x['tipo'] for x in dados['historico']}, {'numero_atualizado', 'concedido'})
        serializado = json.dumps(dados, ensure_ascii=False)
        self.assertNotIn('+5543999991111', serializado)
        self.assertNotIn('43999991111', serializado)
        with self.assertRaises(HTTPException) as err:
            wa.consultar_auditoria(2, self.req(2), self.db)
        self.assertEqual(err.exception.status_code, 403)
        with self.assertRaises(HTTPException) as err:
            wa.consultar_auditoria(999, self.req(1), self.db)
        self.assertEqual(err.exception.status_code, 404)

    def test_matriz_restringe_auditoria_sem_expor_nova_rota(self):
        p = '/avisos-whatsapp/admin/usuarios/2/auditoria'
        self.assertTrue(app._permissao_rota('GET', p, 'Controladoria'))
        for perfil in ('Checklist', 'Solicitante', 'Financeiro'):
            self.assertFalse(app._permissao_rota('GET', p, perfil))
        self.assertFalse(app._permissao_rota('POST', p, 'Controladoria'))

    def test_numero_duplicado_bloqueado_sem_revogar_consentimento(self):
        self.numero()
        self.consentir(True)
        antes = self.db.query(models.WhatsAppAuditoriaContato).count()
        with self.assertRaises(HTTPException) as err:
            wa.salvar_numero_admin(
                3, wa.NumeroAdministrado(numero='+55 43 99999-1111'),
                self.req(1), self.db)
        self.assertEqual(err.exception.status_code, 409)
        self.assertIsNone(self.db.get(models.PreferenciaWhatsApp, 3))
        self.assertEqual(self.db.query(models.WhatsAppAuditoriaContato).count(), antes)
        self.assertTrue(self.db.get(models.PreferenciaWhatsApp, 2).consentimento)

    def test_schema_novo_impede_duplicacao_ate_sem_endpoint(self):
        from sqlalchemy.exc import IntegrityError
        self.numero()
        self.db.add(models.PreferenciaWhatsApp(
            usuario_id=3, telefone='+5543999991111', consentimento=0))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        self.assertIsNone(self.db.get(models.PreferenciaWhatsApp, 3))
        self.assertEqual(self.db.get(models.PreferenciaWhatsApp, 2).telefone, '+5543999991111')

    def test_numero_sem_optin_nao_cria_auditoria_falsa(self):
        self.numero()
        self.consentir(False)
        self.assertEqual(self.db.query(models.WhatsAppAuditoriaConsentimento).count(), 0)
        self.assertEqual(self.db.query(models.WhatsAppAuditoriaContato).count(), 1)


if __name__ == '__main__':
    unittest.main()
