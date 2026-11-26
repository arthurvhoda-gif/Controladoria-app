# -*- coding: utf-8 -*-
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_cobertura_v80 import diagnosticar_cobertura_v80

class TestCoberturaV80(unittest.TestCase):
    def linha(self,l=2,cid=1,dt='2026-07-01',v='10',cat='',desc='Taxa'):
        return dict(linha=l,condominio_id=cid,data=dt,valor=Decimal(v) if v is not None else None,categoria=cat,descricao=desc)
    def diag(self,*rs): return diagnosticar_cobertura_v80({1:'Alfa',2:'Beta'},rs,date(2026,8,10))
    def test_totais(self):
        r=self.diag(self.linha(),self.linha(3,v='20',cat='Manutenção'))
        self.assertEqual(r['totais']['nao_classificado']['positivos_centavos'],1000)
        self.assertEqual(r['totais']['classificado']['positivos_centavos'],2000)
        self.assertIsNone(r['economia_comprovada_centavos'])
    def test_normalizacao(self):
        self.assertEqual(self.diag(self.linha(cat=' NÃO  CLASSIFICADO '))['totais']['nao_classificado']['registros'],1)
    def test_negativo_zero_invalido(self):
        g=self.diag(self.linha(v='-12'),self.linha(3,v='0'),self.linha(4,v=None),self.linha(5,v='NaN'))['totais']['nao_classificado']
        self.assertEqual((g['negativos_centavos'],g['zeros'],g['valor_invalido'],g['positivos_centavos']),(-1200,1,2,0))
    def test_data_invalida(self):
        r=self.diag(self.linha(dt='2026-02-30')); self.assertEqual(r['datas_invalidas'],1); self.assertFalse(r['concentracoes'])
    def test_data_futura(self):
        r=self.diag(self.linha(dt='2026-08-11')); self.assertEqual(r['datas_futuras'],1); self.assertFalse(r['concentracoes'])
    def test_mes_corrente_nao_confirma_anterior(self):
        r=self.diag(self.linha(dt='2026-08-01',cat='Manutenção')); self.assertTrue(r['cobertura'][0]['competencia_anterior_sem_positivo_classificado'])
    def test_cobertura(self):
        r=self.diag(self.linha(cat='Manutenção')); self.assertFalse(r['cobertura'][0]['competencia_anterior_sem_positivo_classificado']); self.assertIsNone(r['cobertura'][1]['ultimo_mes_classificado_positivo'])
    def test_concentracao(self):
        r=self.diag(self.linha(v='80'),self.linha(cid=2,v='20')); self.assertEqual(r['concentracoes'][0]['participacao_pontos_base'],8000)
    def test_duplicidade_candidata(self):
        r=self.diag(self.linha(desc='ÁGUA'),self.linha(3,desc=' agua ',cat='Água')); self.assertEqual(r['candidatos_duplicidade'][0]['linhas'],[2,3]); self.assertEqual(sum(g['registros'] for g in r['totais'].values()),2)
    def test_valor_igual_nao_basta(self):
        self.assertFalse(self.diag(self.linha(),self.linha(3,desc='Outro'))['candidatos_duplicidade'])
    def test_condominio_diferente(self):
        self.assertFalse(self.diag(self.linha(),self.linha(cid=2))['candidatos_duplicidade'])
    def test_linha_repetida(self):
        with self.assertRaises(ValueError): self.diag(self.linha(),self.linha())
    def test_sinal_temporal(self):
        r=self.diag(self.linha(2,dt='2026-04-01'),self.linha(3,dt='2026-05-01'),self.linha(4,dt='2026-06-01'),self.linha(5,v='40')); self.assertEqual([x['mes'] for x in r['sinais']],['2026-07'])
    def test_sem_base_temporal(self):
        self.assertFalse(self.diag(self.linha(2,dt='2026-04-01'),self.linha(3,v='100'))['sinais'])
    def test_maiores(self):
        r=self.diag(*[self.linha(i,v=str(i)) for i in range(2,7)]); self.assertEqual([x['linha'] for x in r['concentracoes'][0]['maiores_linhas']],[6,5,4])

if __name__=='__main__': unittest.main()
