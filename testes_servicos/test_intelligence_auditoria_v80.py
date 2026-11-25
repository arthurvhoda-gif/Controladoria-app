# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import date
from hashlib import sha256
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_auditoria_v80 import auditar_local_v80,auditar_carteira_v80,ErroAuditoria,ev
from intelligence_investigacao_v80 import investigar_aumento
from intelligence_prescritiva_v80 import priorizar_v80


def fixture():
    ms=[f'2026-{i:02}' for i in range(1,7)]
    rs=[NS(condominio_id=1,categoria_chave='manutencao condominio',id_origem=str(i),data_original=date(2026,i,10),competencia=date(2026,i,1),descricao='reparo',valor_centavos=v,hash_conteudo=sha256(str(i).encode()).hexdigest()) for i,v in enumerate([10000,10000,10000,25000,26000,10000],1)]
    op=NS(condominio_id=1,categoria='manutencao condominio',referencia_mensal_centavos=10000,total_recente_centavos=61000,impacto_adicional_centavos=31000,meses_com_aumento=2)
    h=investigar_aumento(rs,op,ms)
    a=dict(condominio_id=1,linha=2,nome='Bomba',periodicidade='Anual',ultima='2025-06-01',proxima='2026-06-01')
    ar=dict(condominio_id=1,nome='bomba',estado='prazo_registrado_vencido',dias_ate_prazo=-39,evidencia=a,acao='confirmar')
    rec=dict(condominio_id=1,categoria='manutencao condominio',descricao='reparo',registros=6,datas_distintas=6,meses_observados=6,total_centavos=91000,evidencias=[ev(r) for r in rs])
    def d(k,p,v,n): return dict(chave=k,origem='planilhas',condominio_id=1,prioridade=p,fato='fato',acao='verificar',referencias={},hipoteses_nao_comprovadas=[],valor_centavos=v,natureza_valor=n,economia_comprovada_centavos=None)
    c=dict(versao='8.0-central-1',simulacao=True,data_referencia='2026-07-10',competencia='2026-06',fontes=dict(historico='simulacao_cobertura_nao_confirmada',agenda='disponivel_datas_registradas',financeiro='indisponivel',operacional='indisponivel',compras='indisponivel'),contextos=[],economia_comprovada_centavos=None,lancamentos_validados=6,resultados={'historico':{'casos':[h],'categorias_avaliadas':1,'categorias_sem_base':0,'sem_fechamento':[]},'manutencao':{'agenda':[ar],'contagem_agenda':{'prazo_registrado_vencido':1},'recorrencias':[rec],'total_recorrencias_centavos':91000}},decisoes=[d('historico:1:manutencao condominio',2,31000,'impacto_adicional_historico_simulado'),d('agenda:1:2',1,None,None),d('recorrencia:1:manutencao condominio:reparo',3,91000,'gasto_observado_nao_adicional')])
    return c,rs,[a]

class TestAuditoriaV80(unittest.TestCase):
    def setUp(self): self.c,self.rs,self.ag=fixture()
    def audit(self): return auditar_local_v80(self.c,self.rs,self.ag)
    def h(self): return self.c['resultados']['historico']['casos'][0]
    def m(self): return self.c['resultados']['manutencao']
    def rejeita(self):
        with self.assertRaises(ErroAuditoria): self.audit()
    def test_ok(self): self.assertEqual(self.audit()['impacto_historico_centavos'],31000)
    def test_impacto(self): self.h()['impacto_centavos']+=1; self.rejeita()
    def test_omissao(self): self.c['resultados']['historico']['casos']=[]; self.rejeita()
    def test_duplicacao(self): self.c['resultados']['historico']['casos']*=2; self.rejeita()
    def test_evidencia(self): self.h()['evidencias_tres_meses_anteriores'][0]['hash']='0'*64; self.rejeita()
    def test_descricao(self): self.h()['decomposicao'][0]['descricao_normalizada']='outro'; self.rejeita()
    def test_frequencia(self): self.h()['decomposicao'][0]['efeito_frequencia_centavos']+=1; self.rejeita()
    def test_total(self): self.h()['contribuicoes_positivas_centavos']+=1; self.rejeita()
    def test_agenda(self): self.m()['agenda'][0]['dias_ate_prazo']=0; self.rejeita()
    def test_agenda_omitida(self): self.m()['agenda']=[]; self.rejeita()
    def test_recorrencia(self): self.m()['recorrencias'][0]['total_centavos']+=1; self.rejeita()
    def test_recorrencia_omitida(self): self.m()['recorrencias']=[]; self.rejeita()
    def test_decisao_omitida(self): self.c['decisoes'].pop(); self.rejeita()
    def test_decisao_prioridade(self): self.c['decisoes'][1]['prioridade']=3; self.rejeita()
    def test_economia(self): self.c['economia_comprovada_centavos']=31000; self.rejeita()
    def test_fonte(self): self.c['fontes']['financeiro']='disponivel'; self.rejeita()
    def test_registro_duplicado(self): self.rs.append(self.rs[0]); self.rejeita()
    def test_cobertura_categorias(self): self.c['resultados']['historico']['categorias_sem_base']=1; self.rejeita()
    def test_categoria_so_ajuste(self):
        r=deepcopy(self.rs[0]); r.categoria_chave='ajuste'; r.id_origem='aj'; r.valor_centavos=-1; self.rs.append(r); self.c['lancamentos_validados']+=1; self.c['resultados']['historico']['categorias_sem_base']=1; self.assertEqual(self.audit()['casos_historicos'],1)
    def test_carteira_ok(self): self.assertTrue(auditar_carteira_v80(self.c,priorizar_v80(self.c)))
    def test_carteira_p1(self):
        p=priorizar_v80(self.c); p['fila'].append(p['executivo'].pop(0))
        with self.assertRaises(ErroAuditoria): auditar_carteira_v80(self.c,p)
    def test_carteira_omissao(self):
        p=priorizar_v80(self.c); p['executivo'].pop()
        with self.assertRaises(ErroAuditoria): auditar_carteira_v80(self.c,p)
    def test_carteira_valor(self):
        p=priorizar_v80(self.c); p['executivo'][0]['maiores_valores_por_natureza']={'falso':100}
        with self.assertRaises(ErroAuditoria): auditar_carteira_v80(self.c,p)
    def test_carteira_acao(self):
        p=priorizar_v80(self.c); p['executivo'][0]['acoes'][0]['acao']='pagar'
        with self.assertRaises(ErroAuditoria): auditar_carteira_v80(self.c,p)

if __name__=='__main__': unittest.main()
