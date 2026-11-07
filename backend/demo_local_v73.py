"""Servidor SOMENTE de demonstração local da Controladoria V7.3.

Não substitui main:app e jamais deve ser implantado. Banco SQLite temporário
criado pelo lançador, contas fictícias, sem migrations de PostgreSQL,
WhatsApp real, e-mails ou armazenamento externo.
"""
import os
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.engine import make_url

url_esperada = 'sqlite:///' + Path(os.environ.get('HAIZE_DEMO_DB_FILE', '')).as_posix()
url_obtida = os.environ.get('DATABASE_URL', '')
raiz = Path(os.environ.get('HAIZE_DEMO_TEMP_DIR', '')).resolve()
arquivo = Path(os.environ.get('HAIZE_DEMO_DB_FILE', '')).resolve()

if (os.environ.get('HAIZE_DEMO_LOCAL_V73') != '1'
        or not os.environ.get('HAIZE_DEMO_TEMP_DIR')
        or not os.environ.get('HAIZE_DEMO_DB_FILE')
        or raiz != arquivo.parent
        or arquivo.name != 'haize_v73_demo.sqlite3'
        or not raiz.is_dir()
        or url_obtida != url_esperada
        or make_url(url_obtida).get_backend_name() != 'sqlite'
        or os.environ.get('FRONTEND_ORIGINS') != 'http://127.0.0.1:5174'
        or os.environ.get('FRONTEND_PUBLIC_URL') != 'http://127.0.0.1:5174'
        or os.environ.get('ENABLE_CHECKLIST_EMAILS') != 'false'
        or os.environ.get('HAIZE_STORAGE_MODE') != 'local'
        or os.environ.get('GAS_WEB_APP_URL')
        or os.environ.get('HAIZE_STORAGE_URL')
        or os.environ.get('HAIZE_STORAGE_SECRET')
        or os.environ.get('RESEND_API_KEY')
        or os.environ.get('AUTOMATION_SECRET')):
    raise RuntimeError(
        'DEMO BLOQUEADA: use somente scripts/iniciar_demo_local_v73.cmd. '
        'Não é permitido conectar banco ou serviços reais.'
    )

import auth_utils
from database import SessionLocal, engine
import models
import servicos_api
import main as principal

app = principal.app

# Anexos criados na demo também ficam dentro da pasta temporária. Não escrever
# anexos nem fotografias de teste na pasta do projeto ou em serviços externos.
principal.UPLOAD_DIR = str(raiz / 'uploads')
principal.FOTOS_CHECKLIST_DIR = str(raiz / 'uploads' / 'checklists')
Path(principal.FOTOS_CHECKLIST_DIR).mkdir(parents=True, exist_ok=True)

# As migrações de main:app são exclusivas de PostgreSQL. Aqui apenas, sem
# alterar a aplicação de produção, evitamos executar migrações em SQLite.
if principal.startup_event not in app.router.on_startup:
    raise RuntimeError('Configuração inesperada do servidor. Demo bloqueada.')
app.router.on_startup.remove(principal.startup_event)


@app.on_event('startup')
def iniciar_demo_ficticia():
    auth_utils.get_secret()
    models.Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(models.Usuario).first():
            raise RuntimeError('Banco da demonstração não está vazio. Demo bloqueada.')
        db.add_all([
            models.Condominio(id=1, nome='Condomínio Fictício Alfa'),
            models.Condominio(id=2, nome='Condomínio Fictício Beta'),
        ])
        db.flush()
        senha = auth_utils.hash_password('SenhaFicticiaDeTeste123')
        db.add_all([
            models.Usuario(id=1, nome='Gestora Demonstração',
                           email='gestora.demo@local.test', senha=senha,
                           perfil='Controladoria'),
            models.Usuario(id=2, nome='Zelador Alfa Demonstração',
                           email='zelador.alfa.demo@local.test', senha=senha,
                           perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Zelador Beta Demonstração',
                           email='zelador.beta.demo@local.test', senha=senha,
                           perfil='Checklist', condominio_id=2),
        ])
        db.commit()
        req = SimpleNamespace(state=SimpleNamespace(auth_user_id=1))
        servicos_api.criar(
            servicos_api.ServicoNovo(
                condominio_id=1,
                executores_ids=[2],
                titulo='Verificar iluminação fictícia',
                descricao='Tarefa criada exclusivamente para demonstração local.',
                prazo=servicos_api.hoje() + timedelta(days=7),
            ),
            req, db,
        )
