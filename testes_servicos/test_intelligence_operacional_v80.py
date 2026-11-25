# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_operacional_v80 import (
    investigar_operacao_v80, ErroOperacional, NOVO, CIENTE, EXECUCAO,
    VALIDACAO, FECHADO, FINALIZADO, FISCALIZACAO, APROVADO,
)

def serv(id=1,cid=1,status=NOVO,prazo='2026-06-29'):
    return dict(id=id,condominio_id=cid,status=status,prazo=prazo,prioridade='Alta')
def part(id=1,sid=1,papel='executor',status=NOVO):
    return dict(id=id,servico_id=sid,papel=papel,status=status)
def item(id=1,cid=1):
    return dict(id=id,condominio_id=cid)
def vist(id=1,iid=1,status='Não Conforme',data='2026-06-20 10:00:00'):
    return dict(id=id,item_id=iid,status_conformidade=status,data_execucao=data)
def run(s=(),p=(),i=(),e=()):
    return investigar_operacao_v80(s,p,i,e,'2026-06-30')

class TestOperacionalV80(unittest.TestCase):
    def test_vazio(self):
        self.assertEqual(run()['casos'],[])
    def test_atrasado(self):
        self.assertEqual(run([serv()])['casos'][0]['dias_atraso'],1)
    def test_vence_hoje(self):
        self.assertEqual(run([serv(prazo='2026-06-30')])['casos'],[])
    def test_concluido(self):
        self.assertEqual(run([serv(status=FECHADO)])['casos'],[])
    def test_gargalo(self):
        r=run([serv(status=EXECUCAO)],[part(status=EXECUCAO)])['casos'][0]
        self.assertEqual(r['etapa_registrada'],'execucao'); self.assertFalse(r['divergencia_estado'])
    def test_validacao_antes_prazo(self):
        r=run([serv(status=VALIDACAO,prazo='2026-07-02')],[part(status=FINALIZADO)])['casos'][0]
        self.assertEqual(r['dias_atraso'],0); self.assertEqual(r['estado_derivado'],VALIDACAO)
    def test_fiscalizacao(self):
        r=run([serv(status=FISCALIZACAO)],[part(status=FINALIZADO),part(2,papel='fiscalizador',status=CIENTE)])['casos'][0]
        self.assertEqual(r['estado_derivado'],FISCALIZACAO)
    def test_fiscal_aprovado(self):
        r=run([serv(status=VALIDACAO)],[part(status=FINALIZADO),part(2,papel='fiscalizador',status=APROVADO)])['casos'][0]
        self.assertFalse(r['divergencia_estado'])
    def test_divergencia_estado(self):
        r=run([serv(status=VALIDACAO)],[part()])['casos'][0]
        self.assertTrue(r['divergencia_estado'])
    def test_legado_sem_participantes(self):
        r=run([serv()]); self.assertIsNone(r['casos'][0]['estado_derivado']); self.assertEqual(r['condominios'][0]['servicos_sem_base_participantes'],1)
    def test_participante_orfao(self):
        with self.assertRaises(ErroOperacional): run(p=[part()])
    def test_vistoria_orfa(self):
        with self.assertRaises(ErroOperacional): run(e=[vist()])
    def test_duplicado(self):
        with self.assertRaises(ErroOperacional): run([serv(),serv()])
    def test_vistoria_recorrente(self):
        r=run(i=[item()],e=[vist(),vist(2,data='2026-06-21 10:00:00')])['casos'][0]
        self.assertTrue(r['recorrente']); self.assertEqual(r['ocorrencias_distintas_90d'],2)
    def test_vistoria_conforme_posterior(self):
        self.assertEqual(run(i=[item()],e=[vist(),vist(2,status='Conforme',data='2026-06-21 10:00:00')])['casos'],[])
    def test_vistoria_antiga(self):
        self.assertEqual(run(i=[item()],e=[vist(data='2026-01-01 10:00:00')])['casos'],[])
    def test_simultaneos(self):
        r=run(i=[item()],e=[vist(),vist(2)])['casos'][0]; self.assertFalse(r['recorrente'])
    def test_estado_ambiguo(self):
        r=run(i=[item()],e=[vist(),vist(2,status='Conforme')])['casos'][0]; self.assertEqual(r['tipo'],'vistoria_estado_ambiguo')
    def test_data_futura(self):
        with self.assertRaises(ErroOperacional): run(i=[item()],e=[vist(data='2026-07-01 10:00:00')])
    def test_isolamento(self):
        r=run([serv(cid=1)],i=[item(cid=2)],e=[vist()]); self.assertEqual([c['condominio_id'] for c in r['casos']],[1,2])
    def test_sem_vinculo_condominio(self):
        r=run(i=[item(cid=None)],e=[vist()]); self.assertIsNone(r['casos'][0]['condominio_id'])
    def test_ordem_independente(self):
        self.assertEqual(run([serv(),serv(2)]),run([serv(2),serv()]))
    def test_sem_vistoria_nao_atraso(self):
        r=run(i=[item()]); self.assertEqual(r['casos'],[]); self.assertEqual(r['condominios'][0]['itens_sem_vistoria'],1)
    def test_status_invalido(self):
        with self.assertRaises(ErroOperacional): run([serv(status='Desconhecido')])
