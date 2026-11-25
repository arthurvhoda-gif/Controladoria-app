# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import sqlite3
import tempfile
import unittest
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_memoria_v80 import registrar_memoria_v80


def entrada(n=1, presente=True, valor=100, fonte='disponivel_datas_registradas', mes='2026-06', nome='Condomínio A', evidencia=True):
    d={'chave':'agenda:1:2','origem':'planilhas','condominio_id':1,'prioridade':1,'fato':'prazo_registrado_vencido','acao':'Confirmar execução.','referencias':{'linha':2},'hipoteses_nao_comprovadas':['Execução não confirmada.'],'valor_centavos':None,'natureza_valor':None,'economia_comprovada_centavos':None}
    e={'condominio_id':1,'nome':'atividade','estado':'prazo_registrado_vencido','dias_ate_prazo':-valor,'evidencia':{'linha':2}}
    return {'versao':'8.0-central-1','execucao':f'{n:032x}','utc':f'2026-11-25T12:00:{n:02d}+00:00','data_referencia':'2026-11-25','competencia':mes,'simulacao':True,'fontes':{'historico':'simulacao_cobertura_nao_confirmada','agenda':fonte,'financeiro':'indisponivel','operacional':'indisponivel','compras':'indisponivel'},'nomes_locais':{'1':nome},'arquivos':[{'condominio_id':1,'arquivo':'a.xlsm','sha256':'a'*64}],'resultados':{'manutencao':{'agenda':[e] if presente and evidencia else []}},'decisoes':[d] if presente else [],'economia_comprovada_centavos':None}


def raw(c): return json.dumps(c,ensure_ascii=False).encode('utf-8')

class TestMemoriaV80(unittest.TestCase):
    def setUp(self): self.db=sqlite3.connect(':memory:')
    def tearDown(self): self.db.close()
    def reg(self, **kw): return registrar_memoria_v80(self.db,raw(entrada(**kw)))
    def test_novo(self): self.assertEqual(self.reg()['contagem']['novo'],1)
    def test_reprocessamento(self):
        self.reg(); self.assertTrue(self.reg()['reprocessamento']); self.assertEqual(self.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
    def test_mesmo_id_adulterado(self):
        self.reg()
        with self.assertRaises(ValueError): self.reg(valor=99)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
    def test_persistente(self):
        self.reg(); self.assertEqual(self.reg(n=2)['contagem']['persistente'],1)
    def test_alteracao_evidencia(self):
        self.reg(); self.assertEqual(self.reg(n=2,valor=99)['contagem']['alterado'],1)
    def test_nao_observado(self):
        self.reg(); r=self.reg(n=2,presente=False); self.assertEqual(r['contagem']['nao_observado'],1); self.assertIsNone(r['economia_comprovada_centavos'])
    def test_indisponivel(self):
        self.reg(); self.assertEqual(self.reg(n=2,presente=False,fonte='indisponivel')['contagem']['fonte_indisponivel'],1)
    def test_reaparecido(self):
        self.reg(); self.reg(n=2,presente=False); self.assertEqual(self.reg(n=3)['contagem']['reaparecido'],1)
    def test_nova_competencia(self):
        self.reg(); r=self.reg(n=2,mes='2026-07'); self.assertEqual(r['contagem']['novo'],1); self.assertIsNone(r['execucao_anterior'])
    def test_cadastro_diferente(self):
        self.reg(); self.assertEqual(self.reg(n=2,nome='B')['contagem']['novo'],1)
    def test_fora_de_ordem(self):
        self.reg(n=2)
        with self.assertRaises(ValueError): self.reg(n=1)
        self.assertFalse(self.db.in_transaction)
    def test_sem_evidencia(self):
        with self.assertRaises(ValueError): self.reg(evidencia=False)
    def test_fonte_app_nao_homologada(self):
        c=entrada(); c['fontes']['compras']='disponivel'
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,raw(c))
    def test_id_invalido(self):
        c=entrada(); c['execucao']='../../foo'
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,raw(c))
    def test_sem_fuso(self):
        c=entrada(); c['utc']='2026-11-25T12:00:00'
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,raw(c))
    def test_json_duplicado(self):
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,b'{"a":1,"a":2}')
    def test_manifesto_ausente(self):
        c=entrada(); del c['arquivos']
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,raw(c))
    def test_banco_alheio(self):
        self.db.execute('CREATE TABLE outra(id INTEGER)')
        with self.assertRaises(ValueError): self.reg()
        self.assertEqual(self.db.execute('SELECT count(*) FROM outra').fetchone()[0],0)
    def test_transacao_pendente(self):
        self.db.execute('BEGIN')
        with self.assertRaises(ValueError): self.reg()
        self.assertTrue(self.db.in_transaction)
    def test_integridade(self):
        self.reg(); self.db.execute("UPDATE casos SET corpo='{}'"); self.db.commit()
        with self.assertRaises(ValueError): self.reg(n=2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
    def test_persistencia_em_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'mem.sqlite3'; db=sqlite3.connect(p)
            registrar_memoria_v80(db,raw(entrada())); db.close(); db=sqlite3.connect(p)
            try: self.assertEqual(registrar_memoria_v80(db,raw(entrada(n=2)))['contagem']['persistente'],1)
            finally: db.close()
    def test_manifesto_hash_muda_sem_novo_escopo(self):
        self.reg(); c=entrada(n=2); c['arquivos'][0]['sha256']='b'*64
        self.assertEqual(registrar_memoria_v80(self.db,raw(c))['contagem']['persistente'],1)
    def test_sem_falsa_economia(self):
        c=entrada(); c['decisoes'][0]['economia_comprovada_centavos']=1000
        with self.assertRaises(ValueError): registrar_memoria_v80(self.db,raw(c))
    def test_ausencia_nao_repetida(self):
        self.reg(); self.reg(n=2,presente=False); self.assertEqual(self.reg(n=3,presente=False)['contagem']['nao_observado'],0)

if __name__=='__main__': unittest.main()
