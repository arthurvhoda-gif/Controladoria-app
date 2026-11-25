# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
from datetime import date
from hashlib import sha256
from copy import deepcopy
from unittest.mock import patch
import tempfile
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from custos_importacao_v77 import LancamentoValidado, ORIGEM
from intelligence_executor_v80 import executar_ciclo_v80
from intelligence_central_v80 import executar_central_v80
from intelligence_auditoria_v80 import ErroAuditoria


def fixture():
    registros=tuple(LancamentoValidado(1,ORIGEM,str(m),date(2026,m,10),date(2026,m,1),'reparo','MANUTENCAO CONDOMINIO','manutencao condominio',v,sha256(str(m).encode()).hexdigest()) for m,v in enumerate([10000,10000,10000,25000,26000,10000],1))
    agenda=[dict(condominio_id=1,linha=2,nome='Bomba',periodicidade='Anual',ultima='2025-06-01',proxima='2026-06-01')]
    s=dict(data_referencia='2026-11-25',condominios={1:'Condominio Ficticio Alfa',2:'Condominio Ficticio Beta'},solicitacoes=[dict(id=1,condominio_id=1,status='Finalizada',data='2026-11-01 09:00:00',categoria='Material',fornecedor='Ficticio',descricao='Reparo',valor_aprovado=1000,valor_realizado=1200)],lancamentos=[dict(id=1,solicitacao_id=1,tipo='pagamento',valor_centavos=140000,estorno_de_id=None)],servicos=[dict(id=1,condominio_id=1,status='Em andamento',prazo='2026-11-18',prioridade='Urgente')],participantes=[dict(id=1,servico_id=1,papel='executor',status='Em andamento')],itens=[dict(id=1,condominio_id=1)],execucoes=[dict(id=1,item_id=1,status_conformidade='Não Conforme',data_execucao='2026-11-11 08:00:00'),dict(id=2,item_id=1,status_conformidade='Não Conforme',data_execucao='2026-11-18 08:00:00')])
    return dict(registros=registros,agenda=agenda,nomes={i:f'Local {i}' for i in range(1,11)},sem_aba=[],competencia='2026-06',snapshot=s)


def cli():
    spec=importlib.util.spec_from_file_location('haize_executor_cli',ROOT/'sincronizador'/'intelligence_executor_v80.py')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class TestExecutorV80(unittest.TestCase):
    def setUp(self): self.kw=fixture()
    def run_cycle(self): return executar_ciclo_v80(**self.kw)
    def rejeita(self):
        with self.assertRaises(ErroAuditoria): self.run_cycle()
    def test_ciclo_integrado(self):
        r=self.run_cycle(); self.assertEqual(r['estado'],'APROVADO_HOMOLOGACAO_MISTA'); self.assertEqual(r['auditoria_local']['decisoes'],3); self.assertEqual(r['auditoria_app']['decisoes'],3); self.assertEqual(r['carteira']['total_casos'],6)
    def test_ids_nao_vinculam(self):
        r=self.run_cycle(); self.assertEqual(r['central']['contextos'],[]); self.assertEqual({g['origem'] for g in r['carteira']['executivo']+r['carteira']['fila']},{'app','planilhas'})
    def test_valores_separados(self):
        r=self.run_cycle(); self.assertEqual(r['auditoria_local']['impacto_historico_centavos'],31000); self.assertEqual(r['auditoria_app']['pago_liquido_centavos'],140000); self.assertIsNone(r['central']['economia_comprovada_centavos'])
    def test_sem_alterar_entradas(self):
        antes=deepcopy(self.kw); self.run_cycle(); self.assertEqual(antes,self.kw)
    def test_producao_recusada(self):
        self.kw['snapshot']['condominios'][1]='Condominio Real'; self.rejeita()
    def test_app_incompleto(self):
        del self.kw['snapshot']['execucoes']; self.rejeita()
    def test_cadastro_local_incompleto(self):
        del self.kw['nomes'][10]; self.rejeita()
    def test_competencia_corrente(self):
        self.kw['competencia']='2026-11'; self.rejeita()
    def test_competencia_futura(self):
        self.kw['competencia']='2027-01'; self.rejeita()
    def test_agenda_parcial(self):
        self.kw['sem_aba']=[2]; r=self.run_cycle(); self.assertEqual(r['central']['fontes']['agenda'],'parcial_sem_aba_em_alguns_condominios')
    def test_agenda_ausente(self):
        self.kw['sem_aba']=list(self.kw['nomes']); self.kw['agenda']=[]; r=self.run_cycle(); self.assertEqual(r['central']['fontes']['agenda'],'indisponivel'); self.assertEqual(r['auditoria_local']['decisoes'],1)
    def test_agenda_inconsistente(self):
        self.kw['sem_aba']=[1]; self.rejeita()
    def test_p1_preservado(self):
        self.kw['limite']=1; r=self.run_cycle(); self.assertTrue(all(g['prioridade']!=1 for g in r['carteira']['fila'])); self.assertEqual(r['carteira']['total_p1'],3)
    def test_omissao_local_na_integracao(self):
        def adulterar(**kwargs):
            c=executar_central_v80(**kwargs)
            if 'snapshot_app' in kwargs: c['decisoes']=[d for d in c['decisoes'] if d['origem']=='app']
            return c
        with patch('intelligence_executor_v80.executar_central_v80',side_effect=adulterar): self.rejeita()
    def test_omissao_app(self):
        def adulterar(**kwargs):
            c=executar_central_v80(**kwargs)
            if 'snapshot_app' in kwargs: c['decisoes']=[d for d in c['decisoes'] if d['origem']!='app' or not d['chave'].startswith('solicitacao:')]
            return c
        with patch('intelligence_executor_v80.executar_central_v80',side_effect=adulterar): self.rejeita()
    def test_publicacao(self):
        with tempfile.TemporaryDirectory() as p:
            r=self.run_cycle(); destino=cli().publicar(Path(p),r,self.kw['snapshot'],dict(lancamentos_validados=6))
            self.assertEqual({x.name for x in destino.iterdir()},{'PARECER_EXECUTIVO.txt','CICLO_AUDITADO.json','SNAPSHOT_APP_FICTICIO.json','EVIDENCIAS_CENTRAL.json'})
            j=json.loads((destino/'CICLO_AUDITADO.json').read_bytes()); self.assertEqual(j['sha256_snapshot_app'],sha256((destino/'SNAPSHOT_APP_FICTICIO.json').read_bytes()).hexdigest())
            self.assertIn('APP FICTICIO',(destino/'PARECER_EXECUTIVO.txt').read_text(encoding='utf-8'))
            local=json.loads((destino/'EVIDENCIAS_CENTRAL.json').read_bytes()); self.assertEqual(local['fontes']['financeiro'],'indisponivel')
    def test_publicacao_bloqueada(self):
        with tempfile.TemporaryDirectory() as p:
            with self.assertRaises(ErroAuditoria): cli().publicar(Path(p),{'estado':'REPROVADO'},self.kw['snapshot'],{})
            self.assertEqual(list(Path(p).iterdir()),[])
    def test_publicacao_atomica_falha(self):
        with tempfile.TemporaryDirectory() as p:
            r=self.run_cycle(); m=cli()
            with patch.object(m,'serializar',side_effect=[b'{}',ValueError('falha')]):
                with self.assertRaises(ValueError): m.publicar(Path(p),r,self.kw['snapshot'],{})
            self.assertEqual(list(Path(p).iterdir()),[])

if __name__=='__main__': unittest.main()
