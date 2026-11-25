import copy
import sys
import unittest
from pathlib import Path
from datetime import date
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from intelligence_investigacao_v80 import investigar_aumento, verificar_investigacao

MESES = [f'2026-{i:02d}' for i in range(1,7)]

def dados():
    rs=[]
    for i in range(1,7):
        for j,(desc,val) in enumerate([('Contrato',10000),('Reparo',5000 if i<=3 else 20000)]):
            rs.append(SimpleNamespace(condominio_id=1,categoria_chave='manutencao',competencia=date(2026,i,1),data_original=date(2026,i,10),id_origem=f'{i}-{j}',descricao=desc,valor_centavos=val,hash_conteudo='f'*64))
    op=SimpleNamespace(condominio_id=1,categoria='manutencao',referencia_mensal_centavos=15000,total_recente_centavos=90000,impacto_adicional_centavos=45000,meses_com_aumento=3)
    return rs,op

def analisar(rs=None,op=None,meses=MESES):
    a,b=dados()
    return investigar_aumento(a if rs is None else rs,b if op is None else op,meses)

class TestInvestigacaoV80(unittest.TestCase):
    def test_contribuicao(self):
        r=analisar(); self.assertEqual(r['decomposicao'][0]['descricao_normalizada'],'reparo'); self.assertEqual(r['decomposicao'][0]['contribuicao_centavos'],45000)
    def test_verificacao(self): self.assertTrue(verificar_investigacao(analisar()))
    def test_desempate(self): self.assertEqual(analisar()['mes_referencia'],'2026-01')
    def test_valor_medio(self):
        x=analisar()['decomposicao'][0]; self.assertEqual(x['efeito_frequencia_centavos'],0); self.assertEqual(x['efeito_valor_medio_centavos'],45000)
    def test_ordem_independente(self):
        rs,op=dados(); self.assertEqual(analisar(rs,op),analisar(rs[::-1],op))
    def test_isolamento(self):
        rs,op=dados(); outro=copy.copy(rs[0]); outro.condominio_id=2; outro.valor_centavos=999999; self.assertEqual(analisar(rs,op),analisar(rs+[outro],op))
    def test_duplicidade(self):
        rs,op=dados()
        with self.assertRaises(ValueError): analisar(rs+[rs[0]],op)
    def test_mes_faltante(self):
        rs,op=dados()
        with self.assertRaises(ValueError): analisar(rs[2:],op)
    def test_impacto_incorreto(self):
        rs,op=dados(); op.impacto_adicional_centavos+=1
        with self.assertRaises(ValueError): analisar(rs,op)
    def test_adulteracao(self):
        r=analisar(); r['decomposicao'][0]['contribuicao_centavos']+=1
        with self.assertRaises(ValueError): verificar_investigacao(r)
    def test_nova_descricao(self):
        rs,op=dados()
        for x in rs:
            if x.competencia.month>=4 and x.descricao=='Reparo': x.descricao='Novo reparo'
        r=analisar(rs,op); x=r['decomposicao'][0]; self.assertEqual(x['status'],'nao_observado_nos_tres_meses_anteriores'); self.assertEqual(x['efeito_sem_referencia_centavos'],60000); self.assertEqual(r['compensacoes_centavos'],-15000)
    def test_frequencia(self):
        rs,op=dados()
        for x in list(rs):
            if x.competencia.month>=4 and x.descricao=='Reparo':
                x.valor_centavos=5000
                for i in range(3):
                    y=copy.copy(x); y.id_origem+=f'-{i}'; rs.append(y)
        x=analisar(rs,op)['decomposicao'][0]; self.assertEqual(x['efeito_frequencia_centavos'],45000); self.assertEqual(x['efeito_valor_medio_centavos'],0)
    def test_referencia_nao_consecutiva(self):
        with self.assertRaises(ValueError): analisar(meses=MESES[:5]+['2026-08'])
