# -*- coding: utf-8 -*-
"""Fluxo V8.0: SQLite em memória, sem envios externos."""
import asyncio
import unittest
from datetime import timedelta
from io import BytesIO
from PIL import Image
from starlette.datastructures import Headers
from fastapi import HTTPException, UploadFile
import test_servicos as base

api, models = base.api, base.models


class FluxoServicosV80(unittest.TestCase):
    def setUp(self):
        self.fixture = base.ServicosTeste()
        self.fixture.setUp()
        self.db = self.fixture.db

    def tearDown(self):
        self.fixture.tearDown()

    def criar(self, fiscais=(1,), executor=2):
        return api.criar(api.ServicoNovo(condominio_id=1, executores_ids=[executor],
            fiscalizadores_ids=list(fiscais), titulo='Reparo de teste', descricao='Executar reparo fictício',
            prazo=api.hoje()+timedelta(days=2)), self.fixture.req(1), self.db)['id']

    def acao(self, sid, uid, acao, obs=''):
        return api.atualizar(sid, api.ServicoAcao(acao=acao, observacao=obs), self.fixture.req(uid), self.db)

    def detalhe(self, sid, uid=2):
        return api.detalhes(sid, self.fixture.req(uid), self.db)

    def foto(self, sid, uid=2, etapa='depois'):
        arquivo = BytesIO()
        Image.new('RGB', (32, 32), 'blue').save(arquivo, 'PNG')
        arquivo.seek(0)
        return asyncio.run(api.adicionar_foto(sid, self.fixture.req(uid),
            UploadFile(file=arquivo, filename='evidencia.png', headers=Headers({'content-type':'image/png'})), etapa, '', self.db))

    def iniciar(self, sid):
        self.acao(sid, 2, 'confirmar')
        self.acao(sid, 2, 'iniciar')

    def test_foto_propria_depois_e_texto_opcional(self):
        sid = self.criar()
        self.foto(sid, 1, 'antes')
        self.iniciar(sid)
        self.foto(sid, 1, 'depois')
        self.foto(sid, 2, 'durante')
        with self.assertRaises(HTTPException) as cm:
            self.acao(sid, 2, 'concluir', 'Texto não substitui foto.')
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(self.detalhe(sid)['status'], 'Em andamento')
        self.foto(sid)
        self.assertTrue(self.detalhe(sid)['foto_conclusao_ok'])
        self.assertEqual(self.acao(sid, 2, 'concluir')['status'], 'Aguardando validação')

    def test_controladoria_sem_ciencia_e_aprovacao_unica(self):
        sid = self.criar()
        self.assertNotIn('confirmar', self.detalhe(sid, 1)['acoes_disponiveis'])
        self.iniciar(sid)
        self.foto(sid)
        self.acao(sid, 2, 'concluir')
        self.assertEqual(self.acao(sid, 1, 'validar')['status'], 'Concluído')
        with self.assertRaises(HTTPException):
            self.acao(sid, 1, 'validar')
        eventos = api.historico(sid, self.fixture.req(1), self.db)
        self.assertEqual(sum(x['acao']=='validar' for x in eventos), 1)

    def test_fiscal_independente_preservado(self):
        sid = self.criar((1, 4))
        self.acao(sid, 4, 'confirmar')
        self.iniciar(sid)
        self.foto(sid)
        self.assertEqual(self.acao(sid, 2, 'concluir')['status'], 'Aguardando fiscalização')
        with self.assertRaises(HTTPException):
            self.acao(sid, 1, 'validar')
        self.assertEqual(self.acao(sid, 4, 'validar')['status'], 'Aguardando validação')
        self.assertEqual(self.acao(sid, 1, 'validar')['status'], 'Concluído')

    def test_devolucao_exige_nova_evidencia(self):
        sid = self.criar()
        self.iniciar(sid)
        self.foto(sid)
        self.acao(sid, 2, 'concluir')
        self.acao(sid, 1, 'devolver', 'Refazer parte do reparo.')
        self.assertFalse(self.detalhe(sid)['foto_conclusao_ok'])
        with self.assertRaises(HTTPException):
            self.acao(sid, 2, 'concluir')
        self.foto(sid)
        self.assertEqual(self.acao(sid, 2, 'concluir')['status'], 'Aguardando validação')

    def test_avisos_resolvidos_sem_simular_leitura(self):
        sid = self.criar()
        avisos = lambda uid: api.notificacoes(self.fixture.req(uid), self.db)
        self.assertTrue(any(not x['lida'] for x in avisos(2)))
        self.iniciar(sid)
        self.assertTrue(all(x['lida'] and x['resolvido'] for x in avisos(2)))
        self.assertIsNone(self.db.query(models.ServicoAviso).filter_by(usuario_id=2).first().lida_em)
        self.foto(sid)
        self.acao(sid, 2, 'concluir')
        self.assertTrue(any(not x['lida'] for x in avisos(1)))
        self.acao(sid, 1, 'validar')
        self.assertTrue(all(x['lida'] for x in avisos(1)))
        self.assertTrue(any(not x['lida'] for x in avisos(2)))  # aviso informativo de encerramento
        self.assertEqual(avisos(3), [])

    def test_outras_funcoes_preservam_regra_de_texto(self):
        sid = self.criar((), executor=4)
        self.acao(sid, 4, 'confirmar')
        self.acao(sid, 4, 'iniciar')
        with self.assertRaises(HTTPException):
            self.acao(sid, 4, 'concluir')
        self.assertEqual(self.acao(sid, 4, 'concluir', 'Serviço concluído pelo responsável.')['status'], 'Aguardando validação')

    def test_controladoria_executora_sem_ciencia(self):
        sid = self.criar((), executor=1)
        self.assertEqual(self.detalhe(sid, 1)['status'], 'Recebido')
        self.assertNotIn('confirmar', self.detalhe(sid, 1)['acoes_disponiveis'])
        self.assertEqual(self.acao(sid, 1, 'iniciar')['status'], 'Em andamento')


if __name__ == '__main__':
    unittest.main()
