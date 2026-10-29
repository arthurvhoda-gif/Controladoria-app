"""Testes offline: contatos centralizados e consentimento (SQLite)."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
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

class WhatsappV61Teste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        models.Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls): cls.engine.dispose()

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
    def admin_salva(self,usuario_id=2,numero='(43) 99999-1111'):
        return wa.salvar_numero_admin(usuario_id,wa.NumeroAdministrado(numero=numero),self.req(1),self.db)
    def aceitar(self,uid=2):
        return wa.salvar_preferencias(wa.PreferenciaEntrada(receber_alertas=True),self.req(uid),self.db)

    def test_admin_cadastra_numero_e_pessoa_autoriza(self):
        r=self.admin_salva()
        self.assertEqual(r['numero'],'+5543999991111')
        self.assertFalse(r['receber_alertas'])
        prefs=self.aceitar()
        self.assertTrue(prefs['receber_alertas'])
        self.assertFalse(prefs['envios_ativos'])

    def test_numero_invalido_rejeitado(self):
        with self.assertRaises(HTTPException) as exc:
            self.admin_salva(numero='123')
        self.assertEqual(exc.exception.status_code,422)

    def test_avisos_so_com_optin_e_sem_envio(self):
        self.admin_salva(); self.aceitar()
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Verificar portão',descricao='Teste da fila de tarefas',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        fila=self.db.query(models.FilaWhatsApp).all()
        self.assertEqual(len(fila),1)
        self.assertEqual(fila[0].status,'preparada')
        self.assertEqual(wa.resumo_fila(self.req(1),self.db)['por_status'],{'preparada':1})
        with self.assertRaises(HTTPException):wa.resumo_fila(self.req(2),self.db)

    def test_sem_optin_sem_fila(self):
        self.admin_salva()
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Conferir luz',descricao='Teste sem opt-in',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).count(),0)

    def test_revogar_impede_novas_entradas(self):
        self.admin_salva(); self.aceitar()
        wa.salvar_preferencias(wa.PreferenciaEntrada(receber_alertas=False),self.req(2),self.db)
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Conferir luz',descricao='Teste apos revogacao',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).count(),0)

    def test_todos_os_cadastros_visiveis_somente_administrador(self):
        lista=wa.listar_contatos(self.req(1),self.db)
        self.assertEqual(len(lista),3)
        self.assertEqual({u['perfil'] for u in lista},{'Controladoria','Checklist','Solicitante'})
        zelador=next(u for u in lista if u['id']==2)
        self.assertEqual(zelador['condominio_nome'],'Teste A')
        with self.assertRaises(HTTPException) as exc:
            wa.listar_contatos(self.req(2),self.db)
        self.assertEqual(exc.exception.status_code,403)

    def test_so_controladoria_pode_alterar_telefone(self):
        with self.assertRaises(HTTPException) as exc:
            wa.salvar_numero_admin(2,wa.NumeroAdministrado(numero='43999991111'),self.req(3),self.db)
        self.assertEqual(exc.exception.status_code,403)
        self.assertIsNone(self.db.get(models.PreferenciaWhatsApp,2))

    def test_usuario_sem_numero_nao_autoriza(self):
        with self.assertRaises(HTTPException) as exc:
            self.aceitar()
        self.assertEqual(exc.exception.status_code,422)
        self.assertEqual(wa.minhas_preferencias(self.req(2),self.db)['numero'],'')

    def test_atualizacao_numero_revoga_consentimento_e_cancela_pendencias(self):
        self.admin_salva(); self.aceitar()
        api.criar(api.ServicoNovo(condominio_id=1,executores_ids=[2],titulo='Verificar portão',descricao='Teste de troca de numero',prazo=__import__('datetime').date.today()+__import__('datetime').timedelta(days=3)),self.req(1),self.db)
        self.assertEqual(self.db.query(models.FilaWhatsApp).filter_by(status='preparada').count(),1)
        atualizacao=self.admin_salva(numero='(43) 98888-2222')
        self.assertEqual(atualizacao['numero'],'+5543988882222')
        self.assertFalse(atualizacao['receber_alertas'])
        self.assertEqual(self.db.query(models.FilaWhatsApp).filter_by(status='cancelada').count(),1)
        self.assertFalse(self.db.get(models.PreferenciaWhatsApp,2).consentimento)
        audit=self.db.query(models.WhatsAppAuditoriaContato).order_by(models.WhatsAppAuditoriaContato.id.desc()).first()
        self.assertEqual(audit.telefone_anterior_final,'1111')
        self.assertEqual(audit.telefone_novo_final,'2222')
        self.assertEqual(audit.consentimento_revogado,1)

    def test_apagar_numero_invalida_optin(self):
        self.admin_salva(); self.aceitar()
        ret=self.admin_salva(numero='')
        self.assertEqual(ret['numero'],'')
        self.assertFalse(ret['receber_alertas'])
        with self.assertRaises(HTTPException): self.aceitar()

    def test_salvar_mesmo_numero_nao_revoga(self):
        self.admin_salva(); self.aceitar()
        r=self.admin_salva(numero='+5543999991111')
        self.assertFalse(r['alterado'])
        self.assertTrue(r['receber_alertas'])

    def test_nao_permite_cadastro_inexistente(self):
        with self.assertRaises(HTTPException) as exc:
            self.admin_salva(usuario_id=999)
        self.assertEqual(exc.exception.status_code,404)

    def test_matriz_admin_bloqueia_outros_perfis(self):
        import ast, re
        codigo=Path(__file__).resolve().parents[1].joinpath('backend/main.py').read_text(encoding='utf-8')
        arvore=ast.parse(codigo)
        fn=next(n for n in arvore.body if isinstance(n,ast.FunctionDef) and n.name=='_permissao_rota')
        ns={'re':re}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<matriz>','exec'),ns)
        permitido=ns['_permissao_rota']
        for caminho,metodo in [('/avisos-whatsapp/admin/usuarios','GET'),
                               ('/avisos-whatsapp/admin/usuarios/2/numero','PUT')]:
            self.assertTrue(permitido(metodo,caminho,'Controladoria'))
            self.assertFalse(permitido(metodo,caminho,'Checklist'))
            self.assertFalse(permitido(metodo,caminho,'Solicitante'))
            self.assertFalse(permitido('DELETE',caminho,'Controladoria'))

    def test_self_api_nao_permite_mudar_numero(self):
        self.admin_salva()
        # Cliente malicioso envia um campo extra; Pydantic não o utiliza.
        data=wa.PreferenciaEntrada.model_validate({'numero':'43988887777','receber_alertas':True})
        prefs=wa.salvar_preferencias(data,self.req(2),self.db)
        self.assertEqual(prefs['numero'],'+5543999991111')
