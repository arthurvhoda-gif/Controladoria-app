import copy
import sqlite3
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_memoria_real_v80 import registrar


def fixture(i=1, casos=None):
    if casos is None:
        casos=[dict(chave='historico:1:agua',origem='planilhas',condominio_id=1,economia_comprovada_centavos=None,valor_centavos=100),dict(chave='agenda:1:2',origem='planilhas',condominio_id=1,economia_comprovada_centavos=None,referencias={'nome':'bomba'})]
    return dict(versao='8.0-previa-local-1',estado='PREVIA_LOCAL_AUDITADA',envio_autorizado=False,economia_comprovada_centavos=None,app_definitivo='indisponivel_nao_publicado',execucao=f'{i:032x}',referencia='2026-11-26',utc=f'2026-11-26T12:00:{i:02d}+00:00',selecao=dict(fechamento_confirmado=False,competencia='2026-07',janela=['2026-02','2026-03','2026-04','2026-05','2026-06','2026-07']),nomes={str(k):f'C{k}' for k in range(1,11)},manifesto=dict(arquivos=[dict(condominio_id=k,arquivo=f'C{k}.xlsm') for k in range(1,11)],sem_aba_prazos=[]),central=dict(simulacao=True,competencia='2026-07',data_referencia='2026-11-26',economia_comprovada_centavos=None,contextos=[],fontes=dict(historico='simulacao_cobertura_nao_confirmada',agenda='disponivel_datas_registradas',financeiro='indisponivel',operacional='indisponivel',compras='indisponivel'),decisoes=casos),auditoria=dict(estado='APROVADO_ESCOPO_LOCAL_SIMULADO',decisoes=len(casos),economia_comprovada_centavos=None),carteira=dict(total_casos=len(casos)))


class TestMemoriaReal(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); self.addCleanup(self.db.close)
        # Testes unitarios do armazenamento: auditoria de carteira existente
        # tem suite propria; simular sua aprovacao nestes fixtures minimos.
        audit=types.ModuleType('intelligence_auditoria_v80'); audit.auditar_carteira_v80=lambda c,p: True
        self.p=patch.dict(sys.modules,{'intelligence_auditoria_v80':audit}); self.p.start(); self.addCleanup(self.p.stop)
    def cont(self,r,t='historico'): return registrar(self.db,r)['escopos'][t]['contagem']
    def test_novo(self): self.assertEqual(self.cont(fixture())['novo'],1)
    def test_persistente(self):
        self.cont(fixture()); self.assertEqual(self.cont(fixture(2))['persistente'],1)
    def test_alterado(self):
        self.cont(fixture()); x=fixture(2); x['central']['decisoes'][0]['valor_centavos']=200; self.assertEqual(self.cont(x)['alterado'],1)
    def test_ausencia_reaparece(self):
        self.cont(fixture()); self.assertEqual(self.cont(fixture(2,[]))['nao_observado'],1); self.assertEqual(self.cont(fixture(3))['reaparecido'],1)
    def test_idempotencia(self):
        x=fixture(); registrar(self.db,x); self.assertTrue(registrar(self.db,x)['reprocessamento']); self.assertEqual(self.db.execute('SELECT count(*) FROM ciclos').fetchone()[0],1)
    def test_adulteracao(self):
        x=fixture(); registrar(self.db,x); x['central']['decisoes'][0]['valor_centavos']=0
        with self.assertRaisesRegex(ValueError,'CICLO_ALTERADO'): registrar(self.db,x)
    def test_janela(self):
        self.cont(fixture()); x=fixture(2); x['selecao']['janela']=['2026-01']+x['selecao']['janela'][:-1]; x['selecao']['competencia']=x['central']['competencia']='2026-06'; r=registrar(self.db,x)['escopos']; self.assertIsNone(r['historico']['execucao_anterior']); self.assertEqual(r['agenda']['contagem']['persistente'],1)
    def test_agenda_nome(self):
        self.cont(fixture()); x=fixture(2); x['central']['decisoes'][1]['referencias']['nome']='elevador'; c=self.cont(x,'agenda'); self.assertEqual((c['novo'],c['nao_observado']),(1,1))
    def test_cadastro(self):
        self.cont(fixture()); x=fixture(2); x['nomes']['1']='Outro'; self.assertEqual(self.cont(x)['novo'],1)
    def test_recusa_app(self):
        x=fixture(); x['central']['fontes']['financeiro']='disponivel'
        with self.assertRaisesRegex(ValueError,'FONTES'): registrar(self.db,x)
    def test_recusa_sem_auditoria(self):
        x=fixture(); x['auditoria']['estado']='REPROVADO'
        with self.assertRaisesRegex(ValueError,'AUDITORIA'): registrar(self.db,x)
    def test_recusa_fora_ordem(self):
        self.cont(fixture(2));
        with self.assertRaisesRegex(ValueError,'ORDEM'): registrar(self.db,fixture(1))
    def test_banco_incompativel(self):
        self.db.execute('CREATE TABLE antiga(x)');
        with self.assertRaisesRegex(ValueError,'BANCO'): registrar(self.db,fixture())
    def test_recusa_carteira(self):
        sys.modules['intelligence_auditoria_v80'].auditar_carteira_v80=lambda c,p: False
        with self.assertRaisesRegex(ValueError,'CARTEIRA'): registrar(self.db,fixture())

if __name__=='__main__': unittest.main()
