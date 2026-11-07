# -*- coding: utf-8 -*-
"""V7.3: avisos internos respeitam o acesso ATUAL à tarefa.

Usa banco SQLite fictício; não acessa Neon, Drive, Render, e-mail ou WhatsApp.
"""
import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
import test_servicos as fixture
import models
import servicos_api as api


class TesteEscopoNotificacoesV73(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome='Condominio A'),
            models.Condominio(id=2, nome='Condominio B'),
            models.Usuario(id=1, nome='Gestora', email='gestora@teste.local',
                           senha='x', perfil='Controladoria'),
            models.Usuario(id=2, nome='Zelador A', email='a@teste.local',
                           senha='x', perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Zelador B', email='b@teste.local',
                           senha='x', perfil='Checklist', condominio_id=2),
            models.Usuario(id=4, nome='Colaborador', email='c@teste.local',
                           senha='x', perfil='Solicitante'),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def req(uid):
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))

    def criar(self, condominio_id=1, responsavel_id=2):
        return api.criar(api.ServicoNovo(
            condominio_id=condominio_id,
            responsavel_id=responsavel_id,
            titulo='Verificar elevador',
            descricao='Vistoria do elevador do condomínio',
            prazo=date.today() + timedelta(days=2),
        ), self.req(1), self.db)

    def test_notificacao_normal_e_confirmacao_persistida(self):
        servico = self.criar()
        avisos = api.notificacoes(self.req(2), self.db)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['servico_id'], servico['id'])
        self.assertFalse(avisos[0]['lida'])
        self.assertEqual(api.ler_aviso(avisos[0]['id'], self.req(2), self.db), {'ok': True})
        self.assertTrue(api.notificacoes(self.req(2), self.db)[0]['lida'])

    def test_transferencia_de_condominio_revoga_visibilidade_e_leitura(self):
        self.criar()
        aviso = api.notificacoes(self.req(2), self.db)[0]
        user = self.db.get(models.Usuario, 2)
        user.condominio_id = None
        self.db.commit()
        self.assertEqual(api.notificacoes(self.req(2), self.db), [])
        with self.assertRaises(HTTPException) as cm:
            api.ler_aviso(aviso['id'], self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIsNone(self.db.get(models.ServicoAviso, aviso['id']).lida_em)

    def test_zelador_de_outro_condominio_nao_enxerga_aviso(self):
        self.criar(condominio_id=2, responsavel_id=3)
        self.assertEqual(len(api.notificacoes(self.req(3), self.db)), 1)
        self.assertEqual(api.notificacoes(self.req(2), self.db), [])

    def test_lista_filtra_antes_do_limite_de_100(self):
        visivel = self.criar()
        aviso_correto = api.notificacoes(self.req(2), self.db)[0]
        outro = self.criar(condominio_id=2, responsavel_id=3)
        for indice in range(105):
            self.db.add(models.ServicoAviso(
                usuario_id=2, servico_id=outro['id'],
                mensagem=f'Antigo aviso fora do escopo {indice}',
            ))
        self.db.commit()
        avisos = api.notificacoes(self.req(2), self.db)
        self.assertEqual([a['id'] for a in avisos], [aviso_correto['id']])
        self.assertEqual(avisos[0]['servico_id'], visivel['id'])

    def test_aviso_antigo_nao_lido_sobrevive_a_cem_lidos_recentissimos(self):
        self.criar()
        antigo = api.notificacoes(self.req(2), self.db)[0]
        for indice in range(115):
            self.db.add(models.ServicoAviso(
                usuario_id=2, servico_id=antigo['servico_id'],
                mensagem=f'Aviso recente já lido {indice}',
                lida_em=api.agora(),
            ))
        self.db.commit()
        avisos = api.notificacoes(self.req(2), self.db)
        self.assertEqual(len(avisos), 100)
        self.assertEqual(avisos[0]['id'], antigo['id'])
        self.assertFalse(avisos[0]['lida'])
        self.assertTrue(all(a['lida'] for a in avisos[1:]))

    def test_ordem_pendentes_mais_recentes_e_depois_lidos(self):
        self.criar()
        primeiro = api.notificacoes(self.req(2), self.db)[0]
        self.criar()
        segundo = api.notificacoes(self.req(2), self.db)[0]
        self.assertGreater(segundo['id'], primeiro['id'])
        api.ler_aviso(segundo['id'], self.req(2), self.db)
        avisos = api.notificacoes(self.req(2), self.db)
        self.assertEqual([x['id'] for x in avisos], [primeiro['id'], segundo['id']])

    def test_legado_visivel_ate_participantes_assumirem_fonte_de_verdade(self):
        servico = models.ServicoInterno(
            condominio_id=1, condominio_nome='Condominio A',
            responsavel_id=2, responsavel_nome='Zelador A',
            criador_id=1, criador_nome='Gestora',
            titulo='Tarefa antiga', descricao='Atividade anterior ao controle de participantes',
            prazo=date.today() + timedelta(days=1),
        )
        self.db.add(servico)
        self.db.flush()
        aviso = models.ServicoAviso(
            usuario_id=2, servico_id=servico.id, mensagem='Tarefa antiga para você',
        )
        self.db.add(aviso)
        self.db.commit()
        self.assertEqual(len(api.notificacoes(self.req(2), self.db)), 1)
        self.db.add(models.ServicoParticipante(
            servico_id=servico.id, usuario_id=4,
            usuario_nome='Colaborador', papel='executor', status='Aguardando ciência',
        ))
        self.db.commit()
        self.assertEqual(api.notificacoes(self.req(2), self.db), [])
        with self.assertRaises(HTTPException) as cm:
            api.ler_aviso(aviso.id, self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 404)

    def test_alertas_atraso_somente_de_servicos_abertos_do_proprio_condominio(self):
        self.criar()  # prazo no futuro: não deve aparecer no alerta
        for ident, condo, responsavel, status in (
            (41, 1, 2, 'Em andamento'),
            (42, 2, 3, 'Aguardando ciência'),
            (43, 1, 2, 'Concluído'),
        ):
            self.db.add(models.ServicoInterno(
                id=ident, condominio_id=condo, condominio_nome=f'Condominio {condo}',
                responsavel_id=responsavel, responsavel_nome='Zelador',
                criador_id=1, criador_nome='Gestora',
                titulo=f'Serviço atrasado {ident}', descricao='Atividade fictícia',
                status=status, prazo=date.today() - timedelta(days=3),
            ))
        self.db.commit()
        admin = api.alertas_prazos(self.req(1), self.db)
        self.assertEqual(admin['total'], 2)
        self.assertEqual({x['servico_id'] for x in admin['alertas']}, {41, 42})
        zelador_a = api.alertas_prazos(self.req(2), self.db)
        self.assertEqual(zelador_a['total'], 1)
        self.assertEqual(zelador_a['alertas'][0]['servico_id'], 41)
        self.assertGreaterEqual(zelador_a['alertas'][0]['dias_atraso'], 1)
        zelador_b = api.alertas_prazos(self.req(3), self.db)
        self.assertEqual(zelador_b['alertas'][0]['servico_id'], 42)
        self.assertEqual(api.alertas_prazos(self.req(4), self.db)['alertas'], [])

    def test_alerta_atraso_revogado_ao_perder_vinculo(self):
        self.db.add(models.ServicoInterno(
            id=44, condominio_id=1, condominio_nome='Condominio A',
            responsavel_id=2, responsavel_nome='Zelador A',
            criador_id=1, criador_nome='Gestora',
            titulo='Serviço legado em atraso', descricao='Atividade fictícia',
            status='Em andamento', prazo=date.today() - timedelta(days=2),
        ))
        self.db.commit()
        self.assertEqual(api.alertas_prazos(self.req(2), self.db)['total'], 1)
        self.db.get(models.Usuario, 2).condominio_id = 2
        self.db.commit()
        self.assertEqual(api.alertas_prazos(self.req(2), self.db)['total'], 0)

    def test_outro_usuario_nao_pode_marcar_aviso_como_lido(self):
        self.criar()
        aviso = api.notificacoes(self.req(2), self.db)[0]
        with self.assertRaises(HTTPException) as cm:
            api.ler_aviso(aviso['id'], self.req(4), self.db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIsNone(self.db.get(models.ServicoAviso, aviso['id']).lida_em)


if __name__ == '__main__':
    unittest.main()
