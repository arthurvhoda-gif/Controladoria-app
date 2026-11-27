# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from indicadores_financeiros_v80 import indicadores_pagamento as i, FORMAS

class TestIndicadoresFinanceirosV80(unittest.TestCase):
    def test_parcial(self):
        r=i(100000,85000,50000)
        self.assertEqual(r['saldo_a_pagar_centavos'],35000)
        self.assertEqual(r['progresso_pagamento_pontos_base'],5882)
        self.assertEqual(r['situacao_pagamento'],'parcial')
    def test_quitacao(self):
        r=i(100000,85000,85000)
        self.assertEqual(r['saldo_a_pagar_centavos'],0)
        self.assertEqual(r['diferenca_orcamento_centavos'],15000)
        self.assertEqual(r['situacao_pagamento'],'quitado')
    def test_acima_final_abaixo_aprovado(self):
        r=i(100000,85000,90000)
        self.assertEqual(r['excedente_realizado_centavos'],5000)
        self.assertEqual(r['situacao_pagamento'],'divergencia_financeira')
        self.assertEqual(i(100000,85000,100000)['situacao_pagamento'],'divergencia_financeira')
    def test_sobrepagamento_antes_finalizacao(self):
        self.assertEqual(i(85000,None,90000)['situacao_pagamento'],'sobrepagamento')
    def test_sobrepagamento_abaixo_final(self):
        r=i(85000,100000,90000)
        self.assertEqual(r['situacao_pagamento'],'sobrepagamento')
        self.assertEqual(r['saldo_a_pagar_centavos'],10000)
    def test_acima_ambos(self):
        r=i(100000,85000,110000)
        self.assertEqual(r['excedente_realizado_centavos'],25000)
        self.assertEqual(r['progresso_pagamento_pontos_base'],10000)
        self.assertEqual(r['situacao_pagamento'],'sobrepagamento')
    def test_sem_final(self):
        r=i(100000,None,50000)
        self.assertIsNone(r['saldo_a_pagar_centavos'])
        self.assertIsNone(r['excedente_realizado_centavos'])
        self.assertIsNone(r['progresso_pagamento_pontos_base'])
    def test_zero_final(self):
        self.assertEqual(i(100000,0,0)['situacao_pagamento'],'quitado')
        self.assertEqual(i(100000,0,1)['excedente_realizado_centavos'],1)
    def test_acima_orcamento(self):
        self.assertEqual(i(100000,120000,0)['diferenca_orcamento_centavos'],-20000)
    def test_formas(self):
        self.assertEqual(len(set(FORMAS)),7)
        self.assertNotIn('nao_informado',FORMAS)
    def test_invalido(self):
        with self.assertRaises(ValueError): i(100000,-1,0)
        with self.assertRaises(ValueError): i(100000,85000,0.0)
