import sys
import sqlite3
import tempfile
import unittest
from datetime import date
from email import policy
from email.parser import BytesParser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from intelligence_parecer_email_v80 import preparar,conferir_memoria,sha,serial,ESTADOS,DESTINO

HOJE=date(2026,11,26)

def fixture():
    nomes={str(i):f'C{i}' for i in range(1,11)}
    manifesto=dict(hash_cadastro='a'*64,arquivos=[])
    d=dict(chave='agenda:1:2',origem='planilhas',condominio_id=1,prioridade=1,fato='prazo vencido',acao='Conferir documento',valor_centavos=None,natureza_valor=None,hipoteses_nao_comprovadas=['Execução não comprovada.'],economia_comprovada_centavos=None)
    doc=dict(versao='8.0-previa-local-1',estado='PREVIA_LOCAL_AUDITADA',envio_autorizado=False,app_definitivo='indisponivel_nao_publicado',economia_comprovada_centavos=None,referencia=HOJE.isoformat(),execucao='a'*32,nomes=nomes,manifesto=manifesto,selecao=dict(fechamento_confirmado=False,competencia='2026-07',janela=['2026-02','2026-03','2026-04','2026-05','2026-06','2026-07'],ultimo_mes_calendario_encerrado='2026-10',condominios_com_positivo_em_seis_meses=[1]),central=dict(simulacao=True,data_referencia=HOJE.isoformat(),competencia='2026-07',fontes=dict(historico='simulacao_cobertura_nao_confirmada',financeiro='indisponivel',operacional='indisponivel',compras='indisponivel'),contextos=[],decisoes=[d],economia_comprovada_centavos=None),auditoria=dict(estado='APROVADO_ESCOPO_LOCAL_SIMULADO',decisoes=1,economia_comprovada_centavos=None),carteira=dict(total_casos=1,executivo=[dict(chaves=[d['chave']],condominio_id=1,prioridade=1,tema='manutencao')],fila=[],economia_comprovada_centavos=None),cobertura=dict(referencia=HOJE.isoformat(),nomes=nomes,manifesto=manifesto,economia_comprovada_centavos=None,totais=dict(classificado=dict(registros=1,positivos_centavos=12345),nao_classificado=dict(registros=1,positivos_centavos=100)),candidatos_duplicidade=[],datas_invalidas=0,datas_futuras=0,cobertura=[],sinais=[],concentracoes=[]))
    mem=dict(versao='8.0-memoria-real-1',execucao=doc['execucao'],referencia=doc['referencia'],sha256_previa=sha(doc),economia_comprovada_centavos=None,escopos=dict(agenda=dict(casos_atual=1,contagem={k:int(k=='persistente') for k in ESTADOS},execucao_anterior='b'*32)),reprocessamento=False)
    return doc,mem

class ParecerEmail(unittest.TestCase):
    def setUp(self): self.d,self.m=fixture()
    def gerar(self): return preparar(self.d,self.m,HOJE)
    def rehash(self): self.m['sha256_previa']=sha(self.d)
    def test_destinatario_e_sem_anexo(self):
        msg=BytesParser(policy=policy.default).parsebytes(self.gerar()); self.assertEqual(str(msg['To']),DESTINO); self.assertIsNone(msg['Cc']); self.assertIsNone(msg['Bcc']); self.assertFalse(msg.is_multipart())
    def test_corpo(self):
        corpo=BytesParser(policy=policy.default).parsebytes(self.gerar()).get_content()
        for x in ('R$ 123,45','persistente=1','App definitivo indisponível','sem fechamento contábil confirmado','Conferir documento','Nenhuma economia comprovada'): self.assertIn(x,corpo)
    def test_determinismo(self): self.assertEqual(self.gerar(),self.gerar())
    def test_adulteracao(self):
        self.d['cobertura']['datas_invalidas']=1
        with self.assertRaisesRegex(ValueError,'PARECER_MEMORIA'): self.gerar()
    def test_app_recusado(self):
        self.d['central']['fontes']['financeiro']='disponivel'; self.rehash()
        with self.assertRaisesRegex(ValueError,'PARECER_FONTES'): self.gerar()
    def test_sem_auditoria(self):
        self.d['auditoria']['estado']='REPROVADO'; self.rehash()
        with self.assertRaisesRegex(ValueError,'PARECER_AUDITORIA'): self.gerar()
    def test_data(self):
        with self.assertRaisesRegex(ValueError,'PARECER_REFERENCIA'): preparar(self.d,self.m,date(2026,11,27))
    def test_fila_p1(self):
        self.d['carteira']['fila']=self.d['carteira']['executivo']; self.d['carteira']['executivo']=[]; self.rehash()
        with self.assertRaisesRegex(ValueError,'PARECER_CARTEIRA'): self.gerar()
    def test_banco_ausente(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'mem.sqlite3'
            with self.assertRaisesRegex(ValueError,'PARECER_MEMORIA_AUSENTE'): conferir_memoria(p,self.d,self.m)
            self.assertFalse(p.exists())
    def test_banco_registrado(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'mem.sqlite3'; db=sqlite3.connect(p)
            db.execute('PRAGMA application_id=1212238138'); db.execute('PRAGMA user_version=1'); db.execute('CREATE TABLE ciclos(run TEXT,sha TEXT,resumo TEXT)'); db.execute('INSERT INTO ciclos VALUES (?,?,?)',(self.d['execucao'],sha(self.d),serial(self.m))); db.commit(); db.close()
            self.assertTrue(conferir_memoria(p,self.d,self.m)); self.m['escopos']['agenda']['contagem']['persistente']=0
            with self.assertRaisesRegex(ValueError,'PARECER_MEMORIA_DIVERGENTE'): conferir_memoria(p,self.d,self.m)
if __name__=='__main__': unittest.main()
