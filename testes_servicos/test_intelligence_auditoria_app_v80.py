# -*- coding: utf-8 -*-
import sys
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_central_v80 import executar_central_v80
from intelligence_prescritiva_v80 import priorizar_v80
from intelligence_auditoria_v80 import ErroAuditoria
from intelligence_auditoria_app_v80 import auditar_app_v80


def fixture():
    def sol(i,cid,ap,real,dia):
        return dict(id=i,condominio_id=cid,status='Finalizada',data=dia+' 09:00:00',categoria='Material',fornecedor='Ficticio',descricao='Reparo',valor_aprovado=ap,valor_realizado=real)
    def l(i,s,v,t='pagamento',ref=None):
        return dict(id=i,solicitacao_id=s,tipo=t,valor_centavos=v,estorno_de_id=ref)
    return dict(data_referencia='2026-11-25',condominios={1:'Alfa',2:'Beta'},solicitacoes=[sol(1,1,1000,1200,'2026-09-02'),sol(2,1,500,500,'2026-10-03'),sol(3,1,600,600,'2026-11-01'),sol(4,2,300,300,'2026-11-02')],lancamentos=[l(1,1,140000),l(2,1,10000),l(3,1,10000,'estorno',2),l(4,2,50000),l(5,3,60000),l(6,4,30000)],servicos=[dict(id=1,condominio_id=1,status='Em andamento',prazo='2026-11-18',prioridade='Urgente')],participantes=[dict(id=1,servico_id=1,papel='executor',status='Em andamento')],itens=[dict(id=1,condominio_id=1)],execucoes=[dict(id=1,item_id=1,status_conformidade='Não Conforme',data_execucao='2026-11-11 08:00:00'),dict(id=2,item_id=1,status_conformidade='Não Conforme',data_execucao='2026-11-18 08:00:00')])


def gerar(s):
    c=executar_central_v80(data_referencia=s['data_referencia'],competencia='2026-11',snapshot_app=s)
    return c,priorizar_v80(c)


class TestAuditoriaAppV80(unittest.TestCase):
    def setUp(self): self.s=fixture(); self.c,self.p=gerar(self.s)
    def audit(self): return auditar_app_v80(self.s,self.c,self.p)
    def rejeita(self):
        with self.assertRaises(ErroAuditoria): self.audit()
    def test_integrado(self):
        r=self.audit(); self.assertEqual(r['decisoes'],5); self.assertEqual(r['pago_liquido_centavos'],280000)
    def test_financeiro_adulterado(self):
        self.c['resultados']['financeiro']['casos'][0]['pago_liquido_centavos']+=1; self.rejeita()
    def test_alerta_omitido(self):
        self.c['resultados']['financeiro']['casos'][0]['alertas'].pop(); self.rejeita()
    def test_estorno_duplicado(self):
        self.s['lancamentos'].append(dict(self.s['lancamentos'][2],id=99)); self.rejeita()
    def test_estorno_cruzado(self):
        self.s['lancamentos'][2]['solicitacao_id']=2; self.rejeita()
    def test_evidencia_financeira(self):
        self.c['resultados']['financeiro']['casos'][0]['evidencias'].pop(); self.rejeita()
    def test_compra_omitida(self):
        self.c['resultados']['compras']['evidencias'].pop(); self.rejeita()
    def test_concentracao(self):
        self.c['resultados']['compras']['concentracoes'][0]['sinal_concentracao']=False; self.rejeita()
    def test_demanda(self):
        self.c['resultados']['compras']['demandas'][0]['total_centavos']+=1; self.rejeita()
    def test_servico(self):
        self.c['resultados']['operacional']['casos'][0]['dias_atraso']=0; self.rejeita()
    def test_recorrencia(self):
        self.c['resultados']['operacional']['casos'][1]['recorrente']=False; self.rejeita()
    def test_operacao_omitida(self):
        self.c['resultados']['operacional']['casos'].pop(); self.rejeita()
    def test_decisao_omitida_mesmo_com_carteira_consistente(self):
        self.c['decisoes'].pop(); self.p=priorizar_v80(self.c); self.rejeita()
    def test_valor_decisao_adulterado(self):
        d=next(d for d in self.c['decisoes'] if d['chave']=='solicitacao:1'); d['valor_centavos']=999999; self.p=priorizar_v80(self.c); self.rejeita()
    def test_p1_na_fila(self):
        idx=next(i for i,g in enumerate(self.p['executivo']) if g['prioridade']==1); self.p['fila'].append(self.p['executivo'].pop(idx)); self.rejeita()
    def test_referencia_decisao_adulterada(self):
        d=next(d for d in self.c['decisoes'] if d['chave']=='solicitacao:1'); d['referencias']['lancamentos']=[]; self.rejeita()
    def test_fonte_ausente(self):
        self.c['fontes']['compras']='indisponivel'; self.rejeita()
    def test_economia_inventada(self):
        self.c['economia_comprovada_centavos']=100; self.rejeita()
    def test_snapshot_vazio(self):
        for k in ('solicitacoes','lancamentos','servicos','participantes','itens','execucoes'): self.s[k]=[]
        self.c,self.p=gerar(self.s); self.assertEqual(self.audit()['decisoes'],0)
    def test_vistoria_conforme_posterior(self):
        self.s['execucoes'].append(dict(id=3,item_id=1,status_conformidade='Conforme',data_execucao='2026-11-24 08:00:00')); self.c,self.p=gerar(self.s); self.assertEqual(self.audit()['decisoes'],4)
    def test_ordem_snapshot(self):
        for k in ('solicitacoes','lancamentos','servicos','participantes','itens','execucoes'): self.s[k].reverse()
        self.assertEqual(self.audit()['decisoes'],5)

if __name__=='__main__': unittest.main()
