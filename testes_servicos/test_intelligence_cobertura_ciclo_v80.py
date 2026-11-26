# -*- coding: utf-8 -*-
import sys
import unittest
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_cobertura_v80 import diagnosticar_cobertura_v80
from intelligence_cobertura_ciclo_v80 import conferir_cobertura, linhas_cobertura


class TestCoberturaCiclo(unittest.TestCase):
    def setUp(self):
        self.dia=date(2026,11,26); self.nomes={1:'Alfa',2:'Beta'}
        self.dados=[SimpleNamespace(condominio_id=1,valor_centavos=12345),SimpleNamespace(condominio_id=2,valor_centavos=-100)]
        self.m=dict(hash_cadastro='a'*64,arquivos=[dict(condominio_id=1,arquivo='alfa.xlsm',sha256='b'*64),dict(condominio_id=2,arquivo='beta.xlsm',sha256='c'*64)],lancamentos_validados=2,nao_classificados_excluidos=1)
        linhas=[dict(condominio_id=i,linha=l,descricao='Despesa',data='2026-07-01',valor=Decimal(v),categoria=c) for i,l,v,c in [(1,2,'123.45','Limpeza'),(2,2,'-1','Limpeza'),(1,3,'500','')]]
        self.c=diagnosticar_cobertura_v80(self.nomes,linhas,self.dia)
        self.c['manifesto']=deepcopy({k:self.m[k] for k in ('hash_cadastro','arquivos')})
    def conferir(self): return conferir_cobertura(self.c,self.m,self.nomes,self.dados,self.dia)
    def test_aceita(self): self.assertEqual(self.conferir(),self.c)
    def test_hash(self):
        self.c['manifesto']['arquivos'][0]['sha256']='d'*64
        with self.assertRaisesRegex(ValueError,'ARQUIVOS'): self.conferir()
    def test_data(self):
        self.c['referencia']='2026-11-25'
        with self.assertRaisesRegex(ValueError,'REFERENCIA'): self.conferir()
    def test_cadastro(self):
        self.c['nomes'][1]='Outro'
        with self.assertRaisesRegex(ValueError,'CADASTRO'): self.conferir()
    def test_contagem(self):
        self.c['totais']['nao_classificado']['registros']=0
        with self.assertRaisesRegex(ValueError,'CONTAGEM'): self.conferir()
    def test_valor(self):
        self.c['totais']['classificado']['positivos_centavos']+=1
        with self.assertRaisesRegex(ValueError,'VALORES'): self.conferir()
    def test_condominio(self):
        self.dados[0].condominio_id=2
        with self.assertRaisesRegex(ValueError,'CONDOMINIO'): self.conferir()
    def test_parecer(self):
        t='\n'.join(linhas_cobertura(self.conferir())); self.assertIn('R$ 123,45',t); self.assertIn('R$ 500,00',t); self.assertIn('Nao comprova',t); self.assertIn('Alfa',t)

if __name__=='__main__': unittest.main()
