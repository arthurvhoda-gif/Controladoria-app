# -*- coding: utf-8 -*-
import sys,unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
from copy import deepcopy
from unittest.mock import patch
from importlib.util import spec_from_file_location,module_from_spec
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from intelligence_previa_definitiva_v80 import escolher_competencia,gerar_previa,parecer
from intelligence_cobertura_v80 import diagnosticar_cobertura_v80

HOJE=date(2026,11,26)
NOMES={i:f'Local {i}' for i in range(1,11)}
def reg(i,m,v=10000): return SimpleNamespace(condominio_id=i,competencia=date(2026,m,1),data_original=date(2026,m,10),valor_centavos=v)
def fixture():
    d=[reg(1,m) for m in range(1,7)]
    c=diagnosticar_cobertura_v80(NOMES,[dict(condominio_id=1,linha=m+1,descricao='Reparo',data=f'2026-{m:02d}-10',valor=Decimal('100'),categoria='Manutencao') for m in range(1,7)],HOJE)
    c['manifesto']=dict(hash_cadastro='h',arquivos=[])
    m=dict(c['manifesto'],lancamentos_validados=6,nao_classificados_excluidos=0)
    return dict(registros=d,agenda=[],nomes=NOMES,sem_aba=[],manifesto=m,cobertura=c,hoje=HOJE)

class TestPrevia(unittest.TestCase):
    def test_empate_recente(self):
        r=escolher_competencia([reg(1,m) for m in range(1,9)],NOMES,HOJE); self.assertEqual(r['competencia'],'2026-08')
    def test_max_cobertura(self):
        r=escolher_competencia([reg(1,m) for m in range(1,9)]+[reg(2,m) for m in range(1,7)],NOMES,HOJE); self.assertEqual(r['competencia'],'2026-06'); self.assertEqual(r['condominios_com_positivo_em_seis_meses'],[1,2])
    def test_sem_base(self): self.assertIsNone(escolher_competencia([reg(1,1)],NOMES,HOJE)['competencia'])
    def test_lacuna(self): self.assertIsNone(escolher_competencia([reg(1,m) for m in (1,2,3,5,6,7)],NOMES,HOJE)['competencia'])
    def test_mes_corrente_futuro(self):
        r=escolher_competencia([reg(1,m) for m in range(6,13)],NOMES,HOJE); self.assertIsNone(r['competencia']); self.assertEqual(r['ultimo_mes_positivo_observado'],'2026-10')
    def test_zeros_negativos(self): self.assertIsNone(escolher_competencia([reg(1,m,0 if m==1 else -1 if m==2 else 1) for m in range(1,7)],NOMES,HOJE)['competencia'])
    def test_fechamento_nao_inferido(self): self.assertFalse(escolher_competencia([reg(1,m) for m in range(1,7)],NOMES,HOJE)['fechamento_confirmado'])
    def test_dado_invalido(self):
        with self.assertRaisesRegex(ValueError,'PREVIA_REGISTRO'): escolher_competencia([reg(99,1)],NOMES,HOJE)
    def test_manifesto_divergente(self):
        kw=fixture(); kw['manifesto']['hash_cadastro']='outro'
        with self.assertRaisesRegex(ValueError,'COBERTURA_ARQUIVOS_DIVERGENTES'): gerar_previa(**kw)
    def test_cadastro_ficticio(self):
        kw=fixture(); kw['nomes']=dict(NOMES,**{}); kw['nomes'][1]='Condominio Ficticio Alfa'
        with self.assertRaisesRegex(ValueError,'PREVIA_CADASTRO_LOCAL'): gerar_previa(**kw)
    def test_sem_janela_publica_so_cobertura(self):
        kw=fixture(); kw['registros']=kw['registros'][:1]; kw['cobertura']=diagnosticar_cobertura_v80(NOMES,[dict(condominio_id=1,linha=2,descricao='Reparo',data='2026-01-10',valor=Decimal('100'),categoria='Manutencao')],HOJE); kw['cobertura']['manifesto']=dict(hash_cadastro='h',arquivos=[]); kw['manifesto']['lancamentos_validados']=1
        r=gerar_previa(**kw); self.assertIsNone(r['central']); self.assertFalse(r['envio_autorizado']); self.assertIn('nao auditados',parecer(r))
    def test_envio_bloqueado(self):
        with self.assertRaisesRegex(ValueError,'PREVIA_ENVIO'): parecer(dict(envio_autorizado=True))
    def test_previa_motor_real(self):
        from test_intelligence_executor_v80 import fixture as fixture_real
        kw=fixture_real(); d=kw['registros']; nomes=kw['nomes']; c=diagnosticar_cobertura_v80(nomes,[dict(condominio_id=r.condominio_id,linha=i+2,descricao=r.descricao,data=r.data_original.isoformat(),valor=Decimal(r.valor_centavos)/100,categoria='MANUTENCAO CONDOMINIO') for i,r in enumerate(d)],HOJE); c['manifesto']=dict(hash_cadastro='h',arquivos=[]); m=dict(c['manifesto'],lancamentos_validados=len(d),nao_classificados_excluidos=0)
        r=gerar_previa(registros=d,agenda=kw['agenda'],nomes=nomes,sem_aba=[],manifesto=m,cobertura=c,hoje=HOJE)
        self.assertEqual(r['estado'],'PREVIA_LOCAL_AUDITADA'); self.assertEqual(r['auditoria']['decisoes'],3); self.assertTrue(all(x['origem']=='planilhas' for x in r['central']['decisoes'])); self.assertIn('SEM ENVIO',parecer(r))

if __name__=='__main__': unittest.main()
