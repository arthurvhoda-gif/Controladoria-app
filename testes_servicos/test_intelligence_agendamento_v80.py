# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_agendamento_v80 import executar_diario, ErroAgendamento, registrar_log, atomico

class TestAgendamentoV80(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name).resolve(); self.dia=date(2026,11,25); self.comp='2026-06'
        self.producoes=[]; self.memorias=[]; self.importados=set()
    def produzir(self,stage):
        run=uuid.uuid4().hex; p=stage/('ciclo_'+run); p.mkdir(); self.producoes.append(run)
        (p/'CICLO_AUDITADO.json').write_text(json.dumps(dict(execucao=run,estado='APROVADO_HOMOLOGACAO_MISTA',central=dict(data_referencia=self.dia.isoformat(),competencia=self.comp))),encoding='utf-8')
        for n in ('EVIDENCIAS_CENTRAL.json','SNAPSHOT_APP_FICTICIO.json','PARECER_EXECUTIVO.txt'): (p/n).write_text('{}',encoding='utf-8')
        return p
    def memorizar(self,raiz,run):
        self.assertTrue((raiz/('ciclo_'+run)).is_dir()); self.memorias.append(run); self.importados.add(run)
        return dict(execucao=run,origens={'planilhas':{},'app_ficticio':{}})
    def rodar(self,p=None,m=None): return executar_diario(self.raiz,self.dia,self.comp,p or self.produzir,m or self.memorizar)
    def slot(self): return self.raiz/'AGENDAMENTO_V80'/self.dia.isoformat()
    def test_ciclo(self):
        r=self.rodar(); self.assertEqual(r['estado'],'CONCLUIDO'); self.assertEqual(self.producoes,self.memorias); self.assertEqual(json.loads((self.slot()/'estado.json').read_text())['estado'],'concluido')
    def test_duplicidade(self):
        r=self.rodar(); s=self.rodar(); self.assertEqual(s,dict(estado='JA_CONCLUIDO',run=r['run'])); self.assertEqual(len(self.producoes),1); self.assertEqual(len(self.memorias),1)
    def test_dia_seguinte(self):
        self.rodar(); self.dia=date(2026,11,26); self.rodar(); self.assertEqual(len(self.importados),2)
    def test_competencia_futura(self):
        self.comp='2026-11'; self.assertRaises(ErroAgendamento,self.rodar); self.assertFalse(self.producoes)
    def test_competencia_mudada_no_dia(self):
        self.rodar(); self.comp='2026-07'; self.assertRaises(ErroAgendamento,self.rodar); self.assertEqual(len(self.producoes),1)
    def test_falha_antes_publicacao(self):
        def falha(stage): raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,falha); self.assertFalse(self.memorias); self.assertEqual(self.rodar()['estado'],'CONCLUIDO')
    def test_falha_apos_staging(self):
        def falha(stage): self.produzir(stage); raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,falha); self.assertEqual(self.rodar()['run'],self.producoes[0]); self.assertEqual(len(self.producoes),1)
    def test_falha_memoria(self):
        def falha(*a): raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,None,falha); self.assertEqual(self.rodar()['run'],self.producoes[0]); self.assertEqual(len(self.producoes),1)
    def test_falha_apos_commit_memoria(self):
        def falha(*a): self.memorizar(*a); raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,None,falha); self.rodar(); self.assertEqual(len(self.importados),1); self.assertEqual(len(self.memorias),2); self.assertEqual(len(self.producoes),1)
    def test_recuperar_dia_anterior(self):
        def falha(stage): self.produzir(stage); raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,falha); self.dia=date(2026,11,26); self.rodar(); self.assertEqual(self.producoes,self.memorias); self.assertEqual(len(self.memorias),2)
    def test_dia_anterior_sem_snapshot(self):
        def falha(stage): raise RuntimeError('erro')
        self.assertRaises(RuntimeError,self.rodar,falha); self.dia=date(2026,11,26); self.rodar(); self.assertEqual(len(self.producoes),1)
    def test_simultaneo(self):
        def produzir(stage):
            with self.assertRaisesRegex(ErroAgendamento,'SIMULTANEA'): self.rodar()
            return self.produzir(stage)
        self.rodar(produzir); self.assertEqual(len(self.producoes),1)
    def test_arquivo_faltante(self):
        def produzir(stage):
            p=self.produzir(stage); (p/'PARECER_EXECUTIVO.txt').unlink(); return p
        self.assertRaises(ErroAgendamento,self.rodar,produzir); self.assertFalse(self.memorias)
    def test_dia_divergente(self):
        def produzir(stage):
            p=self.produzir(stage); ar=p/'CICLO_AUDITADO.json'; x=json.loads(ar.read_text()); x['central']['data_referencia']='2026-11-24'; ar.write_text(json.dumps(x)); return p
        self.assertRaises(ErroAgendamento,self.rodar,produzir); self.assertFalse(self.memorias)
    def test_memoria_sem_confirmacao(self):
        self.assertRaises(ErroAgendamento,self.rodar,None,lambda *a:{}); self.assertEqual(self.rodar()['estado'],'CONCLUIDO'); self.assertEqual(len(self.producoes),1)
    def test_staging_ambiguo(self):
        def produzir(stage): self.produzir(stage); return self.produzir(stage)
        self.assertRaises(ErroAgendamento,self.rodar,produzir); self.assertFalse(self.memorias)
    def test_log(self):
        registrar_log(self.raiz,'FALHA','extracao:CONEXAO_FALHOU'); x=json.loads((self.raiz/'AGENDAMENTO_V80.log').read_text()); self.assertEqual(x['estado'],'FALHA'); self.assertIn('utc',x)
    def test_atomico(self):
        p=self.raiz/'dados'; atomico(p,b'primeiro'); atomico(p,b'segundo'); self.assertEqual(p.read_bytes(),b'segundo'); self.assertEqual(list(self.raiz.iterdir()),[p])

if __name__=='__main__': unittest.main()
