"""Testes offline (SQLite em memória)."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
# Os testes também devem funcionar quando carregados isoladamente.
if 'database' not in sys.modules:
    import types
    from sqlalchemy.orm import declarative_base
    stub=types.ModuleType('database')
    stub.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    stub.SessionLocal=sessionmaker(bind=stub.engine)
    stub.Base=declarative_base()
    sys.modules['database']=stub

import models
import servicos_api as api
import whatsapp_alertas as wa

class WhatsappV6Teste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        models.Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        models.Base.metadata.drop_all(self.engine)
        models.Base.metadata.create_all(self.engine)
        self.db = self.Session()
        self.db.add(models.Condominio(id=1,nome='Teste A'))
        self.db.add(models.Usuario(id=1,nome='Controladoria',email='gestor@local',senha='x',perfil='Controladoria'))
        self.db.add(models.Usuario(id=2,nome='Zelador',email='zelador@local',senha='x',perfil='Checklist',condominio_id=1))
        self.db.add(models.Usuario(id=3,nome='Outro',email='outro@local',senha='x',perfil='Solicitante'))
        self.db.commit()

    def tearDown(self):self.db.close()
    def req(self,uid):return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid))

    def test_optin_e_conversao_numero(self):
        d=wa.salvar_preferencias(wa.PreferenciaEntrada(numero='(43) 99999-1111',receber_alertas=True),self.req(2),self.db)
        self.assertEqual(d['numero'],'+5543999991111')
        self.assertTrue(d['receber_alertas'])
        self.assertFalse(d['envios_ativos'])

    def test_numero_invalido_rejeitado(self):
        with self.assertRaises(HTTPException) as exc:
            wa.salvar_preferencias(wa.PreferenciaEntrada(numero='123',receber_alertas=True),self.req(2),self.db)
        self.assertEqual(exc.exception.status_code,422)

    def test_avisos_so_com_optin_e_sem_envio(self):
        # Preferência individual e serviços compartilham a mesma transação.
        wa.salvar_preferencias(wa.PreferenciaEntrada(numero='43999991111',receber_alertas=True),self.req(2),self.db)
        s=api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Verificar portão',descricao='Teste da fila de tarefas',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        fila=self.db.query(models.FilaWhatsApp).all()
        self.assertEqual(len(fila),1)
        self.assertEqual(fila[0].status,'preparada')
        self.assertEqual(wa.resumo_fila(self.req(1),self.db)['por_status'],{'preparada':1})
        with self.assertRaises(HTTPException):wa.resumo_fila(self.req(2),self.db)

    def test_sem_optin_sem_fila(self):
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Conferir luz',descricao='Teste sem opt-in',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).count(),0)

    def test_revogar_impede_novas_entradas(self):
        wa.salvar_preferencias(wa.PreferenciaEntrada(numero='43999991111',receber_alertas=True),self.req(2),self.db)
        wa.salvar_preferencias(wa.PreferenciaEntrada(numero='',receber_alertas=False),self.req(2),self.db)
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Conferir luz',descricao='Teste apos revogacao',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).count(),0)
