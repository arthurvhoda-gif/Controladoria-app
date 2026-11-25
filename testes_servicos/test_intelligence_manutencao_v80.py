# -*- coding: utf-8 -*-
import sys, unittest
from datetime import date
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from custos_importacao_v77 import LancamentoValidado, ORIGEM
from intelligence_manutencao_v80 import investigar_manutencao_v80


def gasto(i,d='2026-06-01',v=10000,cid=1,desc='Reparo bomba',cat='manutencao condominio'):
    dt=date.fromisoformat(d)
    return LancamentoValidado(cid,ORIGEM,str(i),dt,dt.replace(day=1),desc,cat,cat,v,'a'*64)


def agenda(**kw):
    return dict({'condominio_id':1,'linha':2,'nome':'Bomba','periodicidade':'mensal','ultima':'2026-06-01','proxima':'2026-07-01'},**kw)


def executar(rs=None,ps=None,cats=None,mes='2026-06',hoje='2026-11-25'):
    return investigar_manutencao_v80([gasto(1)] if rs is None else rs,[] if ps is None else ps,hoje,mes,['manutencao condominio'] if cats is None else cats)


class TestManutencaoV80(unittest.TestCase):
    def test_vencido(self):
        self.assertEqual(executar(ps=[agenda()])['agenda'][0]['estado'],'prazo_registrado_vencido')
    def test_vence_hoje(self):
        self.assertEqual(executar(ps=[agenda(proxima='2026-11-25')])['agenda'][0]['dias_ate_prazo'],0)
    def test_30_dias(self):
        self.assertEqual(executar(ps=[agenda(proxima='2026-12-25')])['agenda'][0]['estado'],'prazo_em_30_dias')
    def test_31_dias(self):
        self.assertEqual(executar(ps=[agenda(proxima='2026-12-26')])['agenda'][0]['estado'],'prazo_futuro')
    def test_data_ausente(self):
        self.assertEqual(executar(ps=[agenda(proxima='')])['agenda'][0]['estado'],'sem_proxima_data')
    def test_data_invalida(self):
        self.assertEqual(executar(ps=[agenda(proxima='2026-02-30')])['agenda'][0]['estado'],'datas_inconsistentes')
    def test_ultima_posterior(self):
        self.assertEqual(executar(ps=[agenda(ultima='2026-12-01')])['agenda'][0]['estado'],'datas_inconsistentes')
    def test_inversao(self):
        self.assertEqual(executar(ps=[agenda(proxima='2026-05-01')])['agenda'][0]['estado'],'datas_inconsistentes')
    def test_nome_ambiguo(self):
        r=executar(ps=[agenda(),agenda(linha=3,nome='BÓMBA')]); self.assertEqual(r['contagem_agenda'],{'identificacao_ambigua':2})
    def test_duplicidade_linha(self):
        with self.assertRaises(ValueError): executar(ps=[agenda(),agenda()])
    def test_isolamento_agenda(self):
        self.assertEqual(executar(ps=[agenda(),agenda(condominio_id=2)])['contagem_agenda'],{'prazo_registrado_vencido':2})
    def test_recorrencia(self):
        rs=[gasto(1,'2026-05-01'),gasto(2,'2026-06-01'),gasto(3,'2026-06-02',desc='REPARO BÓMBA')]; r=executar(rs); self.assertEqual(r['total_recorrencias_centavos'],30000); self.assertEqual(r['recorrencias'][0]['datas_distintas'],3)
    def test_mes_unico(self):
        self.assertEqual(executar([gasto(i,f'2026-06-0{i}') for i in range(1,4)])['recorrencias'],[])
    def test_mesmo_dia(self):
        self.assertEqual(executar([gasto(1,'2026-05-01'),gasto(2),gasto(3)])['recorrencias'],[])
    def test_isolamento_despesa(self):
        self.assertEqual(executar([gasto(1,'2026-05-01'),gasto(2),gasto(3,'2026-06-02',cid=2)])['recorrencias'],[])
    def test_exclusao_negativos_e_futuro(self):
        rs=[gasto(1,'2026-05-01'),gasto(2),gasto(3,'2026-06-02'),gasto(4,'2026-06-03',v=-10000),gasto(5,'2026-07-01')]; self.assertEqual(executar(rs)['total_recorrencias_centavos'],30000)
    def test_categoria_explicita(self):
        rs=[gasto(1,'2026-05-01'),gasto(2),gasto(3,'2026-06-02')]; self.assertEqual(executar(rs,cats=['limpeza'])['recorrencias'],[])
    def test_competencia_futura(self):
        with self.assertRaises(ValueError): executar(mes='2026-12')
    def test_id_invalido(self):
        with self.assertRaises(ValueError): executar(ps=[agenda(condominio_id=True)])
    def test_sem_categoria(self):
        with self.assertRaises(ValueError): executar(cats=[])
    def test_ordem(self):
        rs=[gasto(1,'2026-05-01'),gasto(2),gasto(3,'2026-06-02')]; self.assertEqual(executar(rs,[agenda(),agenda(linha=3,nome='Portao')]),executar(rs[::-1],[agenda(linha=3,nome='Portao'),agenda()]))

if __name__=='__main__': unittest.main()
