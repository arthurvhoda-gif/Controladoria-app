import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_compras_v80 import investigar_compras_v80, ErroCompras


def compra(i=1, **kw):
    r=dict(id=i,condominio_id=1,status='Finalizada',data='2026-06-01 10:00:00',
           categoria='Limpeza',fornecedor='Fornecedor A',descricao='Material de limpeza',
           valor_aprovado=500,valor_realizado=500)
    r.update(kw); return r


def analise(*rs, dias=180):
    return investigar_compras_v80(list(rs),'2026-07-31',dias)


class TestComprasV80(unittest.TestCase):
    def test_vazio(self):
        self.assertEqual(analise()['totais']['incluidas'],0)
    def test_total(self):
        self.assertEqual(analise(compra(),compra(2))['totais']['total_realizado_centavos_aproximado'],100000)
    def test_concentracao(self):
        self.assertTrue(analise(compra(),compra(2),compra(3))['concentracoes'][0]['sinal_concentracao'])
    def test_amostra_pequena(self):
        self.assertFalse(analise(compra(valor_realizado=2000))['concentracoes'][0]['sinal_concentracao'])
    def test_rotulo_ausente_denominador(self):
        g=analise(compra(),compra(2),compra(3,fornecedor=''))['concentracoes'][0]
        self.assertEqual(g['participacao_lider_pontos_base'],6666)
        self.assertFalse(g['sinal_concentracao'])
    def test_normalizacao_rotulos(self):
        g=analise(compra(),compra(2,fornecedor=' FORNECEDOR  A '))['concentracoes'][0]
        self.assertEqual(len(g['ranking_rotulos']),1)
    def test_isolamento(self):
        r=analise(compra(),compra(2,condominio_id=2))
        self.assertEqual(len(r['concentracoes']),2)
        self.assertTrue(r['demandas'][0]['demanda_compartilhada_candidata'])
    def test_categoria_separada(self):
        self.assertEqual(analise(compra(),compra(2,categoria='Obras',condominio_id=2))['demandas'],[])
    def test_recorrencia(self):
        r=analise(compra(data='2026-05-01 10:00:00'),compra(2),compra(3,data='2026-07-01 10:00:00'))
        self.assertTrue(r['demandas'][0]['recorrente'])
    def test_mesmo_dia_nao_recorrente(self):
        self.assertEqual(analise(compra(),compra(2),compra(3))['demandas'],[])
    def test_descricao_ausente(self):
        r=analise(compra(descricao=''),compra(2,descricao='',condominio_id=2))
        self.assertEqual(r['demandas'],[]); self.assertEqual(r['totais']['sem_descricao'],2)
    def test_coorte(self):
        r=analise(compra(data='2025-01-01 10:00:00'),compra(2,status='Aprovada'),compra(3))
        self.assertEqual((r['totais']['fora_da_janela'],r['totais']['nao_finalizadas_na_janela'],r['totais']['incluidas']),(1,1,1))
    def test_cobertura(self):
        r=analise(compra(condominio_id=None),compra(2,valor_realizado=0),compra(3,categoria=''))
        self.assertEqual(r['totais']['excluidas_por_cobertura'],3)
        self.assertEqual(r['totais']['total_realizado_centavos_aproximado'],0)
    def test_orcamento(self):
        r=analise(compra(valor_realizado=550),compra(2,valor_aprovado=0))
        self.assertEqual([a['diferenca_centavos'] for a in r['auditoria_orcamento']],[5000,None])
    def test_data_futura(self):
        with self.assertRaises(ErroCompras): analise(compra(data='2026-08-01 10:00:00'))
    def test_data_invalida(self):
        with self.assertRaises(ErroCompras): analise(compra(data='2026-02-30 10:00:00'))
    def test_id_repetido(self):
        with self.assertRaises(ErroCompras): analise(compra(),compra())
    def test_valores_invalidos(self):
        for v in (True,-1,float('nan'),float('inf')):
            with self.subTest(v=v), self.assertRaises(ErroCompras): analise(compra(valor_realizado=v))
    def test_ordem_reprodutivel(self):
        a,b=compra(),compra(2,condominio_id=2)
        self.assertEqual(analise(a,b),analise(b,a))
    def test_janela_invalida(self):
        with self.assertRaises(ErroCompras): analise(compra(),dias=0)
    def test_campos_ausentes(self):
        with self.assertRaises(ErroCompras): analise({'id':1})
    def test_centavos_aproximados(self):
        self.assertEqual(analise(compra(valor_realizado=100.005))['totais']['total_realizado_centavos_aproximado'],10001)

if __name__=='__main__': unittest.main()
