"""Rateio V8.0: HTTP real/JWT e SQLite em memória, sem provedores externos."""
import os
import unittest
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import test_servicos as fixture
import auth_utils
import main as api

models = fixture.models


class RateioV80(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AUTH_SECRET_KEY': 'chave-teste-rateio-nao-producao-v80',
            'ENABLE_CHECKLIST_EMAILS': 'false', 'GAS_WEB_APP_URL': '', 'AUTOMATION_SECRET': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.addCleanup(self.db.close)
        self.db.add_all([models.Condominio(id=1, nome='Alfa'), models.Condominio(id=2, nome='Beta'),
            models.Usuario(id=1, nome='Gestora', email='gestora@teste.local', senha='hash-teste', perfil='Controladoria'),
            models.Usuario(id=2, nome='Solicitante', email='solicitante@teste.local', senha='hash-teste', perfil='Solicitante'),
            models.Usuario(id=3, nome='Financeiro', email='financeiro@teste.local', senha='hash-teste', perfil='Financeiro'),
            models.Usuario(id=4, nome='Zelador', email='zelador@teste.local', senha='hash-teste', perfil='Checklist', condominio_id=1)])
        self.db.commit()
        self.client = TestClient(api.app, raise_server_exceptions=True)
        self.addCleanup(self.client.close)

    def auth(self, uid=1):
        return {'Authorization': 'Bearer ' + auth_utils.create_token(self.db.get(models.Usuario, uid))}

    def criar(self, fracao, nome='U', cond=1, uid=1):
        return self.client.post(f'/condominios/{cond}/unidades', headers=self.auth(uid),
                                json={'identificacao': nome, 'fracao_ideal': fracao})

    def compra(self, valor, cond='Alfa', data='2026-11-10 10:00:00', status='Finalizada', aprovado=0, solicitado=0):
        self.db.add(models.Solicitacao(condominio=cond, categoria='Teste', fornecedor='Ficticio',
            descricao='Teste', solicitante='Teste', valor=solicitado, valor_aprovado=aprovado,
            valor_realizado=valor, status=status, data=data))
        self.db.commit()

    def rateio(self, cond=1, uid=1, mes=None):
        return self.client.get(f'/condominios/{cond}/rateio', headers=self.auth(uid),
                               params={'mes': mes} if mes else {})

    def dados(self, **kwargs):
        r = self.rateio(**kwargs)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def parcelas(self, dados):
        return [Decimal(str(u['valor_devido'])) for u in dados['rateio_unidades']]

    def test_fracoes_invalidas_na_api(self):
        for f in (-1, 0, 100.01, 'NaN', 'Infinity', '-Infinity'):
            with self.subTest(fracao=f):
                r = self.criar(f)
                self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(self.db.query(models.Unidade).count(), 0)

    def test_soma_excedente_bloqueada_e_isolada(self):
        self.assertEqual(self.criar(60, '101').status_code, 200)
        self.assertEqual(self.criar(41, '102').status_code, 409)
        self.assertEqual(self.criar(40, '102').status_code, 200)
        self.assertEqual(self.criar(100, '201', cond=2).status_code, 200)
        self.assertEqual(self.db.query(models.Unidade).count(), 3)

    def test_centavos_e_desempate_deterministico(self):
        for f in (25, 25, 25, 25):
            self.assertEqual(self.criar(f).status_code, 200)
        self.compra(100.03)
        d = self.dados()
        self.assertEqual(self.parcelas(d), list(map(Decimal, ['25.01', '25.01', '25.01', '25.00'])))
        self.assertEqual(sum(self.parcelas(d)), Decimal('100.03'))
        self.assertEqual(d['saldo_nao_rateado'], 0)
        self.assertEqual(self.dados(), d)

    def test_cadastro_parcial_nao_redistribui_saldo(self):
        self.assertEqual(self.criar(20).status_code, 200)
        self.assertEqual(self.criar(30).status_code, 200)
        self.compra(100.01)
        d = self.dados()
        self.assertEqual(d['percentual_cadastrado'], 50)
        self.assertEqual(d['total_rateado'], 50.01)
        self.assertEqual(d['saldo_nao_rateado'], 50)
        self.assertEqual(sum(self.parcelas(d)), Decimal('50.01'))

    def test_sem_unidades(self):
        self.compra(120)
        d = self.dados()
        self.assertEqual(d['rateio_unidades'], [])
        self.assertEqual(d['total_rateado'], 0)
        self.assertEqual(d['saldo_nao_rateado'], 120)

    def test_legado_invalido_bloqueia_sem_alterar_cadastro(self):
        self.db.add(models.Unidade(condominio_id=1, identificacao='Legado', fracao_ideal=-5))
        self.db.commit()
        self.assertEqual(self.rateio().status_code, 409)
        self.assertEqual(self.criar(30).status_code, 409)
        self.assertEqual(self.db.query(models.Unidade).one().fracao_ideal, -5)

    def test_legado_soma_superior_a_100_bloqueia(self):
        self.db.add_all([models.Unidade(condominio_id=1, identificacao='A', fracao_ideal=60),
                         models.Unidade(condominio_id=1, identificacao='B', fracao_ideal=50)])
        self.db.commit()
        self.assertEqual(self.rateio().status_code, 409)

    def test_mes_condominio_status_e_criterio_legado(self):
        self.assertEqual(self.criar(100).status_code, 200)
        self.compra(10.01)
        self.compra(0, aprovado=20.02, solicitado=25)
        self.compra(99, cond='Beta')
        self.compra(99, data='2026-10-01 10:00:00')
        self.compra(99, status='Aprovada')
        d = self.dados(mes='2026-11')
        self.assertEqual(d['total_gasto_condominio'], 30.03)
        self.assertEqual(d['quantidade_solicitacoes'], 2)
        self.assertEqual(self.parcelas(d), [Decimal('30.03')])

    def test_perfis_sem_acesso_administrativo(self):
        for uid in (2, 3, 4):
            self.assertEqual(self.rateio(uid=uid).status_code, 403)
            self.assertEqual(self.criar(50, uid=uid).status_code, 403)

    def test_fracoes_periodicas_com_residuo_numerico(self):
        for _ in range(3):
            self.assertEqual(self.criar(33.333333333333336).status_code, 200)
        self.compra(100.01)
        d = self.dados()
        self.assertEqual(d['percentual_cadastrado'], 100)
        self.assertEqual(sum(self.parcelas(d)), Decimal('100.01'))

    def test_arredondamento_exato_inclusive_creditos(self):
        self.assertEqual(api._arredondar_rateio(Fraction('0.5')), 1)
        self.assertEqual(api._arredondar_rateio(Fraction('-0.5')), -1)
        unidades = [SimpleNamespace(id=i, fracao_ideal=25) for i in range(4)]
        parcelas, soma = api._distribuir_rateio(-3, unidades)
        self.assertEqual(parcelas, [-1, -1, -1, 0])
        self.assertEqual(soma, 100)
