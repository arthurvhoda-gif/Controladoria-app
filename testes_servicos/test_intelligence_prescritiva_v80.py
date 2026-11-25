import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_prescritiva_v80 import priorizar_v80, comparar_alternativas_v80


def d(k='agenda:1:2',cid=1,p=1,origem='planilhas',v=None,n=None):
    return dict(chave=k,condominio_id=cid,prioridade=p,origem=origem,valor_centavos=v,natureza_valor=n,
                fato='fato',acao='validar',referencias={},hipoteses_nao_comprovadas=[],economia_comprovada_centavos=None)


def central(ds):
    return dict(versao='8.0-central-1',fontes={k:'disponivel' for k in ('historico','agenda','financeiro','operacional','compras')},decisoes=ds,economia_comprovada_centavos=None)


def alt(nome='A',inv=10000,custo=100,beneficios=(2000,2500,3000)):
    return dict(id=nome,evidencia='premissas fictícias',cenarios={k:dict(investimento=inv,custo_mensal=custo,beneficio_mensal=v) for k,v in zip(('pessimista','base','otimista'),beneficios)})


class TestPrescritivaV80(unittest.TestCase):
    def test_agrupamento(self):
        r=priorizar_v80(central([d(),d('agenda:1:3')]))
        self.assertEqual(r['total_grupos'],1); self.assertEqual(r['executivo'][0]['quantidade_casos'],2)
    def test_preserva_p1_acima_limite(self):
        r=priorizar_v80(central([d(f'agenda:{i}:2',i) for i in range(1,8)]),5)
        self.assertEqual(len(r['executivo']),7); self.assertEqual(r['fila'],[])
    def test_fila_preservada(self):
        r=priorizar_v80(central([d(f'agenda:{i}:2',i,2) for i in range(1,8)]),5)
        self.assertEqual(sum(g['quantidade_casos'] for g in r['fila']),2)
    def test_prioridade(self):
        r=priorizar_v80(central([d(p=3),d('agenda:2:2',2,1)]),1)
        self.assertEqual(r['executivo'][0]['condominio_id'],2)
    def test_isolamento_ids(self):
        r=priorizar_v80(central([d(),d('operacional:servico:1',1,1,'app')]))
        self.assertEqual(r['total_grupos'],2)
    def test_sem_soma(self):
        r=priorizar_v80(central([d('historico:1:x',v=100,n='impacto'),d('recorrencia:1:x:y',v=200,n='gasto'),d('historico:1:z',v=150,n='impacto')]))
        self.assertEqual(r['executivo'][0]['maiores_valores_por_natureza'],{'impacto':150,'gasto':200})
        self.assertIsNone(r['economia_comprovada_centavos'])
    def test_duplicidade(self):
        with self.assertRaises(ValueError): priorizar_v80(central([d(),d()]))
    def test_prioridade_bool(self):
        with self.assertRaises(ValueError): priorizar_v80(central([d(p=True)]))
    def test_natureza_ausente(self):
        with self.assertRaises(ValueError): priorizar_v80(central([d(v=100)]))
    def test_origem(self):
        with self.assertRaises(ValueError): priorizar_v80(central([d(origem='app')]))
    def test_fonte_indisponivel(self):
        c=central([d()]); c['fontes']['agenda']='indisponivel'
        with self.assertRaises(ValueError): priorizar_v80(c)
    def test_fonte_indisponivel_preservada(self):
        c=central([d()]); c['fontes']['financeiro']='indisponivel'
        self.assertEqual(priorizar_v80(c)['fontes']['financeiro'],'indisponivel')
    def test_recorrencia_requer_duas_fontes(self):
        c=central([d('recorrencia:1:x:y')]); c['fontes']['historico']='indisponivel'
        with self.assertRaises(ValueError): priorizar_v80(c)
    def test_economia_falsa(self):
        c=central([d()]); c['decisoes'][0]['economia_comprovada_centavos']=100
        with self.assertRaises(ValueError): priorizar_v80(c)
    def test_ordem_reprodutivel(self):
        ds=[d(),d('agenda:1:3'),d('agenda:2:2',2)]
        self.assertEqual(priorizar_v80(central(ds)),priorizar_v80(central(ds[::-1])))
    def test_vazio(self):
        self.assertEqual(priorizar_v80(central([]))['total_grupos'],0)
    def test_calculo(self):
        r=comparar_alternativas_v80([alt()],12)
        b=r['alternativas'][0]['cenarios']['base']; self.assertEqual(b['saldo_incremental_centavos'],18800); self.assertEqual(b['payback_meses'],5)
    def test_dominancia_e_restricoes(self):
        r=comparar_alternativas_v80([alt(),alt('B',inv=15000)],12)
        self.assertEqual(r['dominantes_financeiras'],['A']); self.assertIsNone(r['alternativa_para_avaliacao_humana'])
        r=comparar_alternativas_v80([alt(),alt('B',inv=15000)],12,restricoes_confirmadas=True)
        self.assertEqual(r['alternativa_para_avaliacao_humana'],'A')
    def test_nao_agir(self):
        r=comparar_alternativas_v80([alt(inv=50000)],12,restricoes_confirmadas=True)
        self.assertEqual(r['dominantes_financeiras'],[])
    def test_empate(self):
        self.assertEqual(comparar_alternativas_v80([alt(),alt('B')],12)['dominantes_financeiras'],[])
    def test_cenarios_cruzados(self):
        self.assertEqual(comparar_alternativas_v80([alt(),alt('B',beneficios=(1500,3000,4000))],12)['dominantes_financeiras'],[])
    def test_sem_premissas(self):
        a=alt(); del a['cenarios']['base']['beneficio_mensal']
        with self.assertRaises(ValueError): comparar_alternativas_v80([a],12)
    def test_ordem_cenarios(self):
        with self.assertRaises(ValueError): comparar_alternativas_v80([alt(beneficios=(3000,2000,4000))],12)
    def test_sem_payback_no_horizonte(self):
        r=comparar_alternativas_v80([alt(inv=99999)],12)
        self.assertIsNone(r['alternativas'][0]['cenarios']['base']['payback_meses'])
    def test_valor_bool(self):
        with self.assertRaises(ValueError): comparar_alternativas_v80([alt(inv=True)],12)
    def test_evidencia_obrigatoria(self):
        a=alt(); a['evidencia']=''
        with self.assertRaises(ValueError): comparar_alternativas_v80([a],12)

if __name__=='__main__': unittest.main()
