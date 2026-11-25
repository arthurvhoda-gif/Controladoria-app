# -*- coding: utf-8 -*-
import sys
import unittest
from datetime import date
from hashlib import sha256
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from custos_importacao_v77 import LancamentoValidado, ORIGEM
from intelligence_central_v80 import executar_central_v80

MESES=[f'2026-{m:02d}' for m in range(1,7)]
DIA='2026-07-10'

def hist():
    return tuple(LancamentoValidado(1,ORIGEM,str(m),date(2026,m,10),date(2026,m,1),'reparo','MANUTENCAO CONDOMINIO','manutencao condominio',v,sha256(str(m).encode()).hexdigest()) for m,v in enumerate([10000,10000,10000,25000,26000,10000],1))

def sol(i=1,cid=9,real=150):
    return dict(id=i,condominio_id=cid,status='Finalizada',data='2026-05-10 09:00:00',categoria='Limpeza',fornecedor='Fornecedor fictício',descricao='Material',valor_aprovado=100,valor_realizado=real)

def pag(i=1,sid=1,valor=20000):
    return dict(id=i,solicitacao_id=sid,tipo='pagamento',valor_centavos=valor,estorno_de_id=None)

def app(**kw):
    return {'data_referencia':DIA,'condominios':{9:'Alfa'},**kw}

def executar(**kw):
    return executar_central_v80(data_referencia=DIA,competencia='2026-06',**kw)

def local(**kw):
    return dict(historico=hist(),nomes_locais={1:'Alfa'},**kw)

def agenda():
    return [dict(condominio_id=1,linha=2,nome='Equipamento fictício',periodicidade='Anual',ultima='2025-06-01',proxima='2026-06-01')]

class TestCentralV80(unittest.TestCase):
    def test_fontes_ausentes(self):
        r=executar(); self.assertEqual(set(r['fontes'].values()),{'indisponivel'}); self.assertEqual(r['decisoes'],[])
    def test_app_vazio_diferente_de_ausente(self):
        r=executar(snapshot_app=app(solicitacoes=[],lancamentos=[],servicos=[],participantes=[],itens=[],execucoes=[])); self.assertEqual(r['fontes']['financeiro'],'disponivel'); self.assertEqual(r['fontes']['operacional'],'disponivel'); self.assertEqual(r['decisoes'],[])
    def test_snapshot_outra_data(self):
        with self.assertRaises(ValueError): executar(snapshot_app=app(data_referencia='2026-07-09'))
    def test_grupo_operacional_parcial(self):
        with self.assertRaises(ValueError): executar(snapshot_app=app(servicos=[]))
    def test_livro_sem_solicitacoes(self):
        with self.assertRaises(ValueError): executar(snapshot_app=app(lancamentos=[]))
    def test_compras_sem_livro(self):
        r=executar(snapshot_app=app(solicitacoes=[sol()])); self.assertEqual(r['fontes']['financeiro'],'indisponivel'); self.assertEqual(r['decisoes'][0]['chave'],'solicitacao:1')
    def test_financeiro_deduplica(self):
        r=executar(snapshot_app=app(solicitacoes=[sol()],lancamentos=[pag()])); ds=r['decisoes']; self.assertEqual(len(ds),1); self.assertEqual(ds[0]['valor_centavos'],10000); self.assertIsNotNone(ds[0]['referencias']['auditoria_compras_mesma_solicitacao']); self.assertIsNone(ds[0]['economia_comprovada_centavos'])
    def test_estorno_integro_exige_motor(self):
        with self.assertRaises(ValueError): executar(snapshot_app=app(solicitacoes=[sol()],lancamentos=[dict(pag(),tipo='estorno',estorno_de_id=99)]))
    def test_cadastro_invalido(self):
        with self.assertRaises(ValueError): executar(snapshot_app=app(solicitacoes=[sol(cid=1)]))
    def test_urgencia_operacional(self):
        s=dict(id=1,condominio_id=9,status='Aguardando ciência',prazo='2026-07-01',prioridade='Urgente')
        r=executar(snapshot_app=app(servicos=[s],participantes=[],itens=[],execucoes=[])); self.assertEqual(r['decisoes'][0]['prioridade'],1); self.assertEqual(r['decisoes'][0]['referencias']['dias_atraso'],9)
    def test_sem_fechamentos_nao_conclui(self):
        r=executar(**local()); self.assertEqual(r['resultados']['historico']['sem_fechamento'],[1]); self.assertEqual(r['decisoes'],[])
    def test_simulacao_explicita(self):
        r=executar(**local(simulacao=True)); self.assertEqual(r['fontes']['historico'],'simulacao_cobertura_nao_confirmada'); self.assertEqual(r['decisoes'][0]['valor_centavos'],31000)
    def test_fechamento_confirmado(self):
        r=executar(**local(fechamentos={1:MESES})); self.assertEqual(r['decisoes'][0]['natureza_valor'],'impacto_adicional_historico'); self.assertFalse(r['simulacao'])
    def test_nao_mistura_simulacao(self):
        with self.assertRaises(ValueError): executar(**local(simulacao=True,fechamentos={1:MESES}))
    def test_fechamento_futuro(self):
        with self.assertRaises(ValueError): executar(**local(fechamentos={1:MESES+['2026-07']}))
    def test_agenda_e_recorrencia(self):
        r=executar(**local(simulacao=True,agenda=agenda())); d={x['chave']:x for x in r['decisoes']}; self.assertEqual(d['agenda:1:2']['prioridade'],1); rec=next(x for x in d.values() if x['chave'].startswith('recorrencia:')); self.assertEqual(rec['referencias']['relacoes_mesma_fonte'][0]['registros_em_comum'],3); self.assertFalse(rec['referencias']['relacoes_mesma_fonte'][0]['independente']); self.assertEqual(rec['natureza_valor'],'gasto_observado_nao_adicional')
    def test_ids_iguais_nao_vinculam(self):
        r=executar(**local(simulacao=True),snapshot_app=app(condominios={1:'Outro'},solicitacoes=[sol(cid=1)],lancamentos=[pag()])); self.assertEqual(r['contextos'],[])
    def test_vinculo_explicito(self):
        r=executar(**local(simulacao=True),snapshot_app=app(solicitacoes=[sol()],lancamentos=[pag()]),vinculos={1:9}); self.assertEqual(r['contextos'][0]['estado'],'contexto_mesmo_condominio_sem_vinculo_causal')
    def test_vinculo_nome_divergente(self):
        with self.assertRaises(ValueError): executar(**local(simulacao=True),snapshot_app=app(condominios={9:'Outro'}),vinculos={1:9})
    def test_ordem_estavel_e_sem_soma(self):
        a=app(solicitacoes=[sol(),sol(2)],lancamentos=[pag(),pag(2,2)])
        b=app(solicitacoes=a['solicitacoes'][::-1],lancamentos=a['lancamentos'][::-1])
        r=executar(snapshot_app=a); self.assertEqual(r,executar(snapshot_app=b)); self.assertIsNone(r['economia_comprovada_centavos'])

if __name__=='__main__': unittest.main()
