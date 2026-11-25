# -*- coding: utf-8 -*-
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from intelligence_reconciliacao_v80 import (
    ErroReconciliacao, reconciliar_financeiro_v80, ensaiar_fonte_sqlite_v80,
)


def sol(i=1, cid=1, status='Finalizada', aprovado=100, realizado=100):
    return dict(id=i, condominio_id=cid, status=status, valor_aprovado=aprovado, valor_realizado=realizado)


def lan(i=1, sid=1, tipo='pagamento', valor=10000, ref=None):
    return dict(id=i, solicitacao_id=sid, tipo=tipo, valor_centavos=valor, estorno_de_id=ref)


def caso(s, ls):
    return reconciliar_financeiro_v80([s], ls)['casos'][0]


def alertas(c):
    return {x['codigo']: x['diferenca_centavos'] for x in c['alertas']}


class TestReconciliacaoV80(unittest.TestCase):
    def test_conciliado(self):
        self.assertEqual(alertas(caso(sol(), [lan()])), {})

    def test_pagamentos_parciais(self):
        c = caso(sol(), [lan(valor=4000), lan(2, valor=6000)])
        self.assertEqual(c['pago_liquido_centavos'], 10000)
        self.assertEqual(alertas(c), {})

    def test_sobrepagamento(self):
        a = alertas(caso(sol(), [lan(valor=15000)]))
        self.assertEqual(a['pago_acima_do_aprovado'], 5000)
        self.assertEqual(a['pago_acima_do_realizado'], 5000)

    def test_estorno_integral(self):
        c = caso(sol(status='Aprovada'), [lan(), lan(2, tipo='estorno', ref=1)])
        self.assertEqual(c['pago_liquido_centavos'], 0)
        self.assertEqual(c['estornos_centavos'], 10000)
        self.assertEqual(alertas(c), {})

    def test_estorno_duplicado(self):
        with self.assertRaises(ErroReconciliacao):
            caso(sol(), [lan(), lan(2, tipo='estorno', ref=1), lan(3, tipo='estorno', ref=1)])

    def test_estorno_valor_incorreto(self):
        with self.assertRaises(ErroReconciliacao):
            caso(sol(), [lan(), lan(2, tipo='estorno', ref=1, valor=9999)])

    def test_estorno_cruzado(self):
        with self.assertRaises(ErroReconciliacao):
            reconciliar_financeiro_v80([sol(), sol(2,2)], [lan(), lan(2,2,'estorno',10000,1)])

    def test_orfao(self):
        with self.assertRaises(ErroReconciliacao):
            caso(sol(), [lan(sid=99)])

    def test_duplicidade_id(self):
        with self.assertRaises(ErroReconciliacao):
            caso(sol(), [lan(), lan()])

    def test_valor_invalido(self):
        for v in (0,-1,1.5,True):
            with self.subTest(v=v), self.assertRaises(ErroReconciliacao):
                caso(sol(), [lan(valor=v)])

    def test_realizado_acima_aprovado(self):
        self.assertEqual(alertas(caso(sol(realizado=150),[lan()]))['realizado_acima_do_aprovado'],5000)

    def test_aprovacao_ausente(self):
        a = alertas(caso(sol(aprovado=0), [lan()]))
        self.assertIn('pagamento_sem_aprovacao_positiva',a)
        self.assertNotIn('pago_acima_do_aprovado',a)

    def test_realizado_zero_nao_confirma_excesso(self):
        a = alertas(caso(sol(realizado=0), [lan()]))
        self.assertIn('realizado_nao_confirmado',a)
        self.assertNotIn('pago_acima_do_realizado',a)

    def test_status_atual(self):
        a = alertas(caso(sol(status='Reprovada'), [lan()]))
        self.assertIn('pagamento_em_status_nao_pagavel',a)
        self.assertNotIn('saldo_a_conciliar_com_realizado',a)

    def test_separacao_condominios_e_totais(self):
        r = reconciliar_financeiro_v80([sol(2,2),sol()], [lan(2,2,valor=5000),lan()])
        self.assertEqual(r['totais']['pago_liquido_centavos'],15000)
        self.assertEqual(r['casos'][0]['condominio_id'],1)
        self.assertEqual(r['casos'][1]['condominio_id'],2)
        self.assertEqual(alertas(r['casos'][1])['saldo_a_conciliar_com_realizado'],5000)

    def test_sem_vinculo(self):
        self.assertIn('condominio_nao_vinculado',alertas(caso(sol(cid=None),[])))

    def test_ordem_reprodutivel(self):
        s = [sol(), sol(2,2)]; l = [lan(),lan(2,2)]
        self.assertEqual(reconciliar_financeiro_v80(s,l),reconciliar_financeiro_v80(s[::-1],l[::-1]))

    def test_fonte_sqlite_memoria(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript('CREATE TABLE solicitacoes(id INTEGER, condominio_id INTEGER,status TEXT,valor_aprovado REAL,valor_realizado REAL); CREATE TABLE financeiro_lancamentos(id INTEGER,solicitacao_id INTEGER,tipo TEXT,valor_centavos INTEGER,estorno_de_id INTEGER); INSERT INTO solicitacoes VALUES(1,1,"Finalizada",100,100); INSERT INTO financeiro_lancamentos VALUES(1,1,"pagamento",12000,NULL);')
            antes = db.total_changes
            r = ensaiar_fonte_sqlite_v80(db)
            self.assertEqual(alertas(r['casos'][0])['pago_acima_do_aprovado'],2000)
            self.assertEqual(db.total_changes,antes)
            self.assertFalse(db.in_transaction)

    def test_banco_em_arquivo_recusado(self):
        with tempfile.TemporaryDirectory() as p:
            db = sqlite3.connect(str(Path(p)/'teste.sqlite'))
            try:
                with self.assertRaises(ErroReconciliacao):
                    ensaiar_fonte_sqlite_v80(db)
            finally:
                db.close()

    def test_banco_anexo_recusado(self):
        with sqlite3.connect(':memory:') as db:
            db.execute("ATTACH DATABASE ':memory:' AS extra")
            with self.assertRaises(ErroReconciliacao):
                ensaiar_fonte_sqlite_v80(db)


if __name__ == '__main__':
    unittest.main()
