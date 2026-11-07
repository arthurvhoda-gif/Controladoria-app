# -*- coding: utf-8 -*-
"""V6.7 etapa 2: triagem informativa na previa; nao envia nem cancela."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import text
import test_multiplos_participantes as base
import whatsapp_alertas as wa
from whatsapp_preenvio import avaliar_preenvio

models = base.models


def entradas(**alt):
    dados = dict(status_fila='preparada', consentimento=True,
                 telefone_ativo=True, usuario_ativo=True,
                 destinatario_autorizado=True, vinculos_consistentes=True,
                 evento_origem_id=3, diagnostico_atual='coerente',
                 diagnostico_historico='nao_comprovado',
                 duplicidade_detectada=False)
    dados.update(alt)
    return dados


class TestesMotorDesconhecidos(unittest.TestCase):
    def test_sem_campo_ativo_revisar(self):
        r = avaliar_preenvio(**entradas(usuario_ativo=None))
        self.assertEqual(r['situacao'], 'revisar')
        self.assertFalse(r['envio_autorizado'])

    def test_superado_impedido_mesmo_com_desconhecidos(self):
        r = avaliar_preenvio(**entradas(usuario_ativo=None, telefone_ativo=None,
                                        duplicidade_detectada=None,
                                        diagnostico_historico='superado'))
        self.assertEqual(r['situacao'], 'impedido')
        self.assertFalse(r['envio_autorizado'])

    def test_sem_consentimento_impedido_mesmo_com_desconhecidos(self):
        r = avaliar_preenvio(**entradas(consentimento=False, usuario_ativo=None))
        self.assertEqual(r['situacao'], 'impedido')
        self.assertFalse(r['envio_autorizado'])

    def test_tipo_invalido_nao_autoriza(self):
        r = avaliar_preenvio(**entradas(consentimento=1, usuario_ativo=None))
        self.assertEqual(r['situacao'], 'revisar')
        self.assertFalse(r['envio_autorizado'])


class TestesPreviaIntegrada(unittest.TestCase):
    def setUp(self):
        self.c = base.MultiplosParticipantesTeste()
        self.c.setUp()
        self.db = self.c.db

    def tearDown(self):
        self.c.tearDown()

    def autorizar(self, uid):
        wa.salvar_numero_admin(
            uid, wa.NumeroAdministrado(numero=f'4399999{uid:04d}'),
            self.c.req(1), self.db)
        wa.salvar_preferencias(
            wa.PreferenciaEntrada(receber_alertas=True, numero_confirmado=f'+554399999{uid:04d}'),
            self.c.req(uid), self.db)

    def previas(self, uid=1):
        with patch.dict(os.environ, {'FRONTEND_PUBLIC_URL': 'http://127.0.0.1:5173'}):
            return wa.listar_previas_fila(self.c.req(uid), self.db)['previa']

    def test_05_aviso_novo_eh_revisar_sem_prova_atividade(self):
        self.autorizar(2)
        tarefa = self.c.novo(execs=[2], fisc=[6])
        aviso = next(a for a in self.previas() if a['servico_id'] == tarefa['id'] and a['evento'] == 'nova_tarefa')
        self.assertEqual(aviso['diagnostico_preenvio']['situacao'], 'revisar')
        self.assertIs(aviso['diagnostico_preenvio']['envio_autorizado'], False)

    def test_06_aviso_superado_eh_impedido(self):
        self.autorizar(2)
        tarefa = self.c.novo(execs=[2], fisc=[6])
        self.c.acao(tarefa, 2, 'confirmar')
        aviso = next(a for a in self.previas() if a['servico_id'] == tarefa['id'] and a['evento'] == 'nova_tarefa')
        self.assertEqual(aviso['diagnostico_preenvio']['situacao'], 'impedido')
        self.assertIs(aviso['diagnostico_preenvio']['envio_autorizado'], False)

    def test_07_nao_muda_fila_com_consultas(self):
        self.autorizar(2)
        tarefa = self.c.novo(execs=[2], fisc=[6])
        antes = [(f.id, f.status) for f in self.db.query(models.FilaWhatsApp).all()]
        self.previas()
        self.previas()
        depois = [(f.id, f.status) for f in self.db.query(models.FilaWhatsApp).all()]
        self.assertEqual(antes, depois)

    def test_08_legado_sem_origem_revisar(self):
        self.autorizar(2)
        tarefa = self.c.novo(execs=[2], fisc=[6])
        aviso_db = self.db.query(models.ServicoAviso).filter_by(servico_id=tarefa['id'], usuario_id=2).first()
        aviso_db.evento_id = None
        self.db.commit()
        aviso = next(a for a in self.previas() if a['servico_id'] == tarefa['id'] and a['evento'] == 'nova_tarefa')
        self.assertEqual(aviso['diagnostico_preenvio']['situacao'], 'revisar')
        self.assertIs(aviso['diagnostico_preenvio']['envio_autorizado'], False)

    def test_10_numero_compartilhado_em_base_legada_eh_impedido(self):
        # Apenas SQLite descartavel: simula tabela legada sem UNIQUE,
        # ANTES de aplicar a migracao opcional em PostgreSQL.
        self.autorizar(2)
        servico = self.c.novo(execs=[2], fisc=[])
        with self.db.begin_nested():
            self.db.execute(text('DROP TABLE whatsapp_preferencias'))
            self.db.execute(text(
                'CREATE TABLE whatsapp_preferencias ('
                'usuario_id INTEGER PRIMARY KEY, telefone VARCHAR(18), '
                'consentimento INTEGER NOT NULL, consentido_em DATETIME, '
                'atualizado_em DATETIME NOT NULL)'
            ))
            self.db.execute(text(
                "INSERT INTO whatsapp_preferencias "
                "(usuario_id, telefone, consentimento, atualizado_em) VALUES "
                "(2, '+5543999990002', 1, CURRENT_TIMESTAMP), "
                "(3, '+5543999990002', 1, CURRENT_TIMESTAMP)"
            ))
        self.db.commit()
        self.db.expire_all()
        aviso = next(x for x in self.previas() if x['servico_id'] == servico['id'])
        diag = aviso['diagnostico_preenvio']
        self.assertEqual(diag['situacao'], 'impedido')
        self.assertIn('duplicidade', diag['motivo'].lower())
        self.assertFalse(diag['envio_autorizado'])

    def test_09_restricao_controladoria_403(self):
        self.autorizar(2)
        self.c.novo(execs=[2], fisc=[6])
        with self.assertRaises(HTTPException) as err:
            self.previas(uid=2)
        self.assertEqual(err.exception.status_code, 403)


if __name__ == '__main__':
    unittest.main()
