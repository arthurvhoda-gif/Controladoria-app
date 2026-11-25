# -*- coding: utf-8 -*-
import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_intelligence_executor_v80 import fixture, cli
from intelligence_executor_v80 import executar_ciclo_v80
from intelligence_memoria_integrada_v80 import registrar_ciclo_memoria_v80


def bytes_json(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')

class TestMemoriaIntegradaV80(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); self.kw=fixture(); self.n=0
    def tearDown(self): self.db.close()
    def ciclo(self,kw=None):
        kw=kw or self.kw; self.n+=1
        r=executar_ciclo_v80(**kw)
        manifesto=dict(hash_cadastro='0'*64,arquivos=[dict(condominio_id=i,arquivo=f'{i}.xlsm',sha256='1'*64) for i in kw['nomes']],sem_aba_prazos=kw['sem_aba'],nao_classificados_excluidos=0,lancamentos_validados=len(kw['registros']))
        with tempfile.TemporaryDirectory() as p:
            d=cli().publicar(Path(p),r,kw['snapshot'],manifesto)
            c=json.loads((d/'CICLO_AUDITADO.json').read_bytes()); l=json.loads((d/'EVIDENCIAS_CENTRAL.json').read_bytes()); s=(d/'SNAPSHOT_APP_FICTICIO.json').read_bytes()
        c['utc']=l['utc']=f'2026-11-25T12:00:{self.n:02d}+00:00'; c['local_para_memoria']=l
        return bytes_json(c),bytes_json(l),s
    def registrar(self,rs=None): return registrar_ciclo_memoria_v80(self.db,*(rs or self.ciclo()))
    def test_primeiro_ciclo(self):
        r=self.registrar(); self.assertEqual(r['origens']['planilhas']['contagem']['novo'],3); self.assertEqual(r['origens']['app_ficticio']['contagem']['novo'],3); self.assertIsNone(r['economia_comprovada_centavos'])
    def test_reprocessamento(self):
        x=self.ciclo(); self.registrar(x); self.assertTrue(self.registrar(x)['reprocessamento']); self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
    def test_persistencia(self):
        self.registrar(); r=self.registrar(); self.assertEqual(r['origens']['planilhas']['contagem']['persistente'],3); self.assertEqual(r['origens']['app_ficticio']['contagem']['persistente'],3)
    def test_alterado(self):
        self.registrar(); self.kw['snapshot']['lancamentos'][0]['valor_centavos']+=100; r=self.registrar(); self.assertEqual(r['origens']['app_ficticio']['contagem']['alterado'],1); self.assertEqual(r['origens']['planilhas']['contagem']['alterado'],0)
    def test_ausencia_reaparecimento(self):
        self.registrar(); antigo=deepcopy(self.kw); self.kw['snapshot']['servicos']=[]; self.kw['snapshot']['participantes']=[]; r=self.registrar(); self.assertEqual(r['origens']['app_ficticio']['contagem']['nao_observado'],1); self.kw=antigo; r=self.registrar(); self.assertEqual(r['origens']['app_ficticio']['contagem']['reaparecido'],1)
    def test_escopos_independentes(self):
        self.registrar(); self.kw['nomes'][10]='Local renomeado'; r=self.registrar(); self.assertIsNone(r['origens']['planilhas']['execucao_anterior']); self.assertEqual(r['origens']['app_ficticio']['contagem']['persistente'],3)
    def test_cobertura_agenda_muda_escopo(self):
        self.registrar(); self.kw['sem_aba']=[2]; r=self.registrar(); self.assertIsNone(r['origens']['planilhas']['execucao_anterior']); self.assertIsNotNone(r['origens']['app_ficticio']['execucao_anterior'])
    def test_snapshot_modificado(self):
        c,l,s=self.ciclo(); self.assertRaises(ValueError,self.registrar,(c,l,s+b' '))
    def test_local_modificado(self):
        c,l,s=self.ciclo(); x=json.loads(l); x['utc']='2026-11-25T01:00:00+00:00'; self.assertRaises(ValueError,self.registrar,(c,bytes_json(x),s))
    def test_auditoria_app_adulterada(self):
        c,l,s=self.ciclo(); x=json.loads(c); x['auditoria_app']['pago_liquido_centavos']+=1; self.assertRaises(ValueError,self.registrar,(bytes_json(x),l,s))
    def test_ciclo_nao_aprovado(self):
        c,l,s=self.ciclo(); x=json.loads(c); x['estado']='BLOQUEADO'; self.assertRaises(ValueError,self.registrar,(bytes_json(x),l,s))
    def test_app_nao_ficticio(self):
        c,l,s=self.ciclo(); x=json.loads(c); ss=json.loads(s); ss['condominios']['1']='Real'; s=bytes_json(ss); x['nomes_app']=ss['condominios']; x['sha256_snapshot_app']=sha256(s).hexdigest(); self.assertRaises(ValueError,self.registrar,(bytes_json(x),l,s))
    def test_mesmo_id_outro_conteudo(self):
        c,l,s=self.ciclo(); self.registrar((c,l,s)); self.assertRaises(ValueError,self.registrar,(c+b' ',l,s)); self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
    def test_ordem(self):
        primeiro=self.ciclo(); segundo=self.ciclo(); self.registrar(segundo); self.assertRaises(ValueError,self.registrar,primeiro); self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
    def test_banco_incompativel(self):
        self.db.execute('CREATE TABLE usuarios(id INTEGER)'); self.db.commit(); self.assertRaises(ValueError,self.registrar); self.assertEqual(self.db.execute('SELECT name FROM sqlite_master').fetchall(),[('usuarios',)])
    def test_integridade_memoria(self):
        self.registrar(); self.db.execute("UPDATE casos SET corpo='{}'"); self.db.commit(); self.assertRaises(ValueError,self.registrar); self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
    def test_rollback_insercao(self):
        self.registrar(); x=self.ciclo()
        self.db.set_authorizer(lambda ac,a,b,c,d: sqlite3.SQLITE_DENY if ac==sqlite3.SQLITE_INSERT and a=='casos' else sqlite3.SQLITE_OK)
        try: self.assertRaises(sqlite3.DatabaseError,self.registrar,x)
        finally: self.db.set_authorizer(None)
        self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM fontes').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM casos').fetchone()[0],6)
    def test_cli_persistente(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('haize_memoria_cli',ROOT/'sincronizador'/'intelligence_memoria_integrada_v80.py')
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        c,l,s=self.ciclo(); run=json.loads(c)['execucao']
        with tempfile.TemporaryDirectory() as d:
            raiz=Path(d); p=raiz/('ciclo_'+run); p.mkdir()
            for nome,raw in zip(('CICLO_AUDITADO.json','EVIDENCIAS_CENTRAL.json','SNAPSHOT_APP_FICTICIO.json'),(c,l,s)): (p/nome).write_bytes(raw)
            self.assertFalse(m.registrar_pasta(raiz,run)['reprocessamento']); self.assertTrue(m.registrar_pasta(raiz,run)['reprocessamento'])
            self.assertTrue((raiz/'MEMORIA_INTEGRADA_V80.sqlite3').is_file())
    def test_rollback_duas_origens(self):
        self.registrar(); self.db.execute("CREATE TRIGGER erro BEFORE INSERT ON casos WHEN NEW.origem='app_ficticio' BEGIN SELECT RAISE(ABORT,'falha'); END"); self.db.commit()
        # O schema com trigger inesperado é rejeitado antes de qualquer inserção.
        self.assertRaises(ValueError,self.registrar); self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)

if __name__=='__main__': unittest.main()
