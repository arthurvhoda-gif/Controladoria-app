import os
import json
import shutil
import hashlib
import re
import base64
import io
import logging
import hmac
from math import isfinite
import unicodedata
from datetime import timedelta
from html import escape
from urllib import request as urllib_request, error as urllib_error
from urllib.parse import urlparse
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, or_, and_
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether

import models
import schemas
from database import engine, SessionLocal
from pydantic import BaseModel
import auth_utils
import custos_api  # módulo isolado: Inteligência de Custos
import custos_painel  # Consultas analiticas de custos

# Cria todas as tabelas caso ainda não existam
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Controladoria Haize API")
app.include_router(custos_api.router)
app.include_router(custos_painel.router)

# A autenticação é validada no servidor, inclusive em downloads e fotografias.
# OPTIONS é liberado para permitir o preflight do navegador (CORS).


def _permissao_rota(method: str, path: str, perfil: str) -> bool:
    """Matriz de acesso explícita; rotas desconhecidas são negadas."""
    gestor = perfil == 'Controladoria'
    solicitante = perfil == 'Solicitante'
    vistoriador = perfil == 'Checklist'
    if path in ('/custos/resumo', '/custos/painel') and method == 'GET':
        return gestor
    if path == '/checklists/alertas' and method == 'GET':
        return gestor or vistoriador
    if path == '/checklists/envios' and method == 'GET':
        return gestor
    if path == '/checklists/envios/reprocessar' and method == 'POST':
        return gestor
    if path == '/usuarios/me' and method == 'GET':
        return True
    if path == '/usuarios/me/senha' and method == 'PUT':
        return True
    if path.startswith('/usuarios'):
        return gestor
    if path == '/condominios':
        return method == 'GET' or gestor
    if re.fullmatch(r'/condominios/\d+', path):
        return gestor
    if re.fullmatch(r'/condominios/\d+/(?:unidades|rateio)', path):
        return gestor
    if path.startswith('/unidades/'):
        return gestor
    if re.fullmatch(r'/condominios/\d+/checklist-relatorio-divergencias(?:/enviar)?', path):
        return gestor or vistoriador
    if path in ('/categorias', '/fornecedores'):
        return gestor or ((solicitante) and method == 'GET')
    if re.fullmatch(r'/(?:categorias|fornecedores)/\d+', path):
        return gestor
    if path == '/solicitacoes':
        return (gestor or solicitante) and method in ('GET', 'POST')
    if re.fullmatch(r'/solicitacoes/\d+', path):
        return gestor or (solicitante and method in ('PUT', 'DELETE'))
    # Solicitante pode iniciar e finalizar SOMENTE as próprias solicitações,
    # e somente nos status correspondentes (validados dentro de cada rota).
    # Aprovação, reprovação e ajuste de status continuam só para Controladoria.
    if re.fullmatch(r'/solicitacoes/\d+/(?:iniciar-execucao|finalizar)', path):
        return (gestor or solicitante) and method == 'PUT'
    if re.fullmatch(r'/solicitacoes/\d+/status', path):
        return gestor
    if re.fullmatch(r'/solicitacoes/\d+/(?:anexos|historico)', path):
        return gestor or solicitante
    if re.fullmatch(r'/anexos/\d+/download', path):
        return gestor or solicitante
    if path == '/checklists':
        return gestor or (vistoriador and method == 'GET')
    if re.fullmatch(r'/checklists/\d+', path):
        return gestor
    if re.fullmatch(r'/checklists/\d+/executar', path):
        return gestor or vistoriador
    if re.fullmatch(r'/checklists/execucoes/\d+/foto', path):
        return gestor or vistoriador
    return False


def _solicitacao_visivel(db: Session, user, sol_id: int):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == sol_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail='Solicitação não encontrada.')
    if user.auth_user_role != 'Controladoria' and sol.solicitante != user.auth_user_name:
        raise HTTPException(status_code=403, detail='Você não tem acesso a esta solicitação.')
    return sol


@app.middleware('http')
async def proteger_api(request: Request, call_next):
    path, method = request.url.path, request.method.upper()
    if method == 'OPTIONS' or (method == 'GET' and path in ('/', '/status', '/docs', '/openapi.json', '/redoc')) or (method == 'POST' and path == '/login'):
        return await call_next(request)

    # Endpoint exclusivo do gatilho diário do Google Apps Script.
    # Nenhum dado pessoal é retornado sem a chave forte do servidor.
    if method == 'POST' and path == '/automacoes/checklists/atrasos':
        chave = os.getenv('AUTOMATION_SECRET', '').strip()
        recebida = request.headers.get('X-Haize-Automation', '')
        if not chave or len(chave) < 32 or not hmac.compare_digest(recebida, chave):
            return JSONResponse(status_code=403, content={'detail': 'Automação não autorizada.'})
        return await call_next(request)

    # Sincronizador Windows: apenas o endpoint de importação; senha só no Render.
    if method == 'POST' and path == '/custos/sincronizar':
        chave = os.getenv('COST_SYNC_SECRET', '').strip()
        recebida = request.headers.get('X-Haize-Custos', '')
        if not chave or len(chave) < 32 or not hmac.compare_digest(
            recebida.encode('utf-8'), chave.encode('utf-8')
        ):
            return JSONResponse(status_code=403, content={'detail': 'Sincronização não autorizada.'})
        return await call_next(request)

    authorization = request.headers.get('authorization', '')
    if not authorization.lower().startswith('bearer '):
        return JSONResponse(status_code=401, content={'detail': 'Faça login para continuar.'})
    token = authorization[7:].strip()
    try:
        claims = auth_utils.decode_token(token)
        uid = int(claims['sub'])
        if uid <= 0:
            raise ValueError('ID inválido')
        with SessionLocal() as session:
            user = session.query(models.Usuario).filter(models.Usuario.id == uid).first()
            if not user or not auth_utils.token_matches_user(claims, user):
                raise ValueError('Usuário inválido')
            request.state.auth_user_id = user.id
            request.state.auth_user_name = user.nome
            request.state.auth_user_role = user.perfil
            request.state.auth_condominio_id = user.condominio_id
            perfil = user.perfil
    except Exception:
        return JSONResponse(status_code=401, content={'detail': 'Sessão inválida ou expirada. Entre novamente.'})

    if not _permissao_rota(method, path, perfil):
        return JSONResponse(status_code=403, content={'detail': 'Seu perfil não tem permissão para esta operação.'})
    return await call_next(request)


# Middleware CORS externo à autenticação, inclusive para respostas 401 e 403.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.getenv(
            'FRONTEND_ORIGINS', 'https://controladoria-app-lilac.vercel.app,http://localhost:5173'
        ).split(',') if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'],
)


# Diretórios para salvar anexos de solicitações e fotos de vistorias
UPLOAD_DIR = "uploads"
FOTOS_CHECKLIST_DIR = os.path.join(UPLOAD_DIR, "checklists")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FOTOS_CHECKLIST_DIR, exist_ok=True)

# =========================================================================
# ENVIO DE RELATORIO PDF VIA GOOGLE APPS SCRIPT (HTTPS)
# Configure GAS_WEB_APP_URL e HAIZE_SECRET no Environment do Render.
# Guarde a chave somente no servidor; nunca inclua no App.jsx nem no GitHub.
# =========================================================================
EMAILS_DESTINO_RELATORIO = [
    "atendimento@haize.com.br",
    "Igor@armagni.adv.br",
]
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL", "").strip()
HAIZE_SECRET = os.getenv("HAIZE_SECRET", "").strip()
logger = logging.getLogger("haize.checklist.email")
# Desativado por padrão para evitar envio real no ambiente Preview/testes.
ENVIO_AUTOMATICO_CHECKLIST = os.getenv('ENABLE_CHECKLIST_EMAILS', 'false').strip().lower() in ('1', 'true', 'yes')


# =========================================================================
# BANCO DE DADOS E MIGRAÇÃO AUTOMÁTICA DE COLUNAS
# =========================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def executar_migracoes_automaticas():
    """Garante que colunas novas existam no banco antigo sem precisar apagar o banco."""
    comandos_migracao = [
        "ALTER TABLE categorias ADD COLUMN limites TEXT",
        "ALTER TABLE categorias ADD COLUMN descricao VARCHAR",
        "ALTER TABLE solicitacoes ADD COLUMN condominio_id INTEGER",
        "ALTER TABLE solicitacoes ADD COLUMN motivo_ajuste TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN observacao TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN valor_servico FLOAT DEFAULT 0.0",
        "ALTER TABLE solicitacoes ADD COLUMN valor_produto FLOAT DEFAULT 0.0",
        "ALTER TABLE solicitacoes ADD COLUMN valor_aprovado FLOAT DEFAULT 0.0",
        "ALTER TABLE solicitacoes ADD COLUMN valor_realizado FLOAT DEFAULT 0.0",
        "ALTER TABLE checklist_itens ADD COLUMN plano_acao_padrao TEXT",
        "ALTER TABLE checklist_itens ADD COLUMN descricao_orientacao TEXT",
        # Compatibilidade com estruturas antigas de anexos no Neon.
        "ALTER TABLE anexos ADD COLUMN IF NOT EXISTS nome_arquivo VARCHAR",
        "ALTER TABLE anexos ADD COLUMN IF NOT EXISTS caminho VARCHAR",
        "ALTER TABLE anexos ADD COLUMN IF NOT EXISTS tipo VARCHAR",
        "ALTER TABLE anexos ADD COLUMN IF NOT EXISTS responsavel VARCHAR",
        "ALTER TABLE anexos ADD COLUMN IF NOT EXISTS data_upload VARCHAR"
    ]
    db = SessionLocal()
    try:
        for cmd in comandos_migracao:
            try:
                db.execute(text(cmd))
                db.commit()
            except Exception:
                db.rollback()
                if "IF NOT EXISTS" in cmd:
                    logging.exception("Falha na migração: %s", cmd)
    finally:
        db.close()

    # Migração crítica de isolamento: se falhar, o serviço não deve abrir
    # com proteção parcial dos condomínios.
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS condominio_id INTEGER'))
        conn.execute(text('ALTER TABLE checklist_itens ADD COLUMN IF NOT EXISTS condominio_id INTEGER'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_usuarios_condominio_id ON usuarios(condominio_id)'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_checklist_itens_condominio_id ON checklist_itens(condominio_id)'))
        # Garante também no PostgreSQL que não existam dois zeladores do mesmo condomínio.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_checklist_condominio ON usuarios(condominio_id) WHERE perfil = 'Checklist' AND condominio_id IS NOT NULL"))
        # Migração dos checklists antigos associados pelo nome.
        conn.execute(text("UPDATE checklist_itens AS i SET condominio_id = c.id FROM condominios AS c WHERE i.condominio_id IS NULL AND LOWER(TRIM(i.condominio)) = LOWER(TRIM(c.nome))"))


# =========================================================================
# UTILITÁRIOS DE SENHA E USUÁRIOS PADRÃO
# =========================================================================
def verificar_senha(senha_digitada: str, senha_banco: str) -> bool:
    return auth_utils.verify_password(senha_digitada, senha_banco)[0]


def criar_usuarios_iniciais():
    """Nunca cria contas públicas com senhas padrão como '123'."""
    db = SessionLocal()
    try:
        if db.query(models.Usuario).count() != 0:
            return
        email = os.getenv('INITIAL_ADMIN_EMAIL', '').strip().lower()
        password = os.getenv('INITIAL_ADMIN_PASSWORD', '')
        if not email or not password:
            logging.warning('Banco sem usuários. Configure INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD para criar o primeiro administrador.')
            return
        if len(password) < 12:
            raise RuntimeError('INITIAL_ADMIN_PASSWORD deve conter ao menos 12 caracteres.')
        db.add(models.Usuario(nome='Administrador Haize', email=email,
                              senha=auth_utils.hash_password(password), perfil='Controladoria'))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    auth_utils.get_secret()  # Fail closed: Render precisa ter AUTH_SECRET_KEY configurada.
    executar_migracoes_automaticas()
    custos_api.criar_tabelas_custos(engine)  # Apenas tabelas novas de custos
    criar_usuarios_iniciais()


# =========================================================================
# STATUS E AUTENTICAÇÃO
# =========================================================================
@app.get("/")
def root():
    return {"status": "online", "servico": "Controladoria Haize API"}


@app.get("/status")
def status():
    return {"status": "online", "timestamp": datetime.now().isoformat()}


@app.post("/login")
def login(dados: schemas.LoginRequest, db: Session = Depends(get_db)):
    email_limpo = dados.email.strip().lower()
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_limpo).first()
    valido, atualizar_hash = auth_utils.verify_password(dados.senha, usuario.senha if usuario else '')
    if not usuario or not valido:
        raise HTTPException(status_code=401, detail='E-mail ou senha incorretos.')
    if atualizar_hash:
        # Migração transparente de senhas antigas (texto, SHA256 e bcrypt) para Argon2id.
        usuario.senha = auth_utils.hash_password(dados.senha) if len(dados.senha) >= 10 else auth_utils.hasher.hash(dados.senha)
        db.commit()
        db.refresh(usuario)
    return {
        'access_token': auth_utils.create_token(usuario),
        'token_type': 'bearer',
        'expires_in': auth_utils.SESSION_HOURS * 3600,
        'usuario': {'id': usuario.id, 'nome': usuario.nome, 'email': usuario.email, 'perfil': usuario.perfil, 'condominio_id': usuario.condominio_id},
    }


@app.get('/usuarios/me', response_model=schemas.UsuarioResponse)
def usuario_me(request: Request, db: Session = Depends(get_db)):
    return db.query(models.Usuario).filter(models.Usuario.id == request.state.auth_user_id).first()


class AlterarMinhaSenha(BaseModel):
    senha_atual: str
    nova_senha: str


@app.put('/usuarios/me/senha')
def trocar_minha_senha(dados: AlterarMinhaSenha, request: Request, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == request.state.auth_user_id).first()
    if not verificar_senha(dados.senha_atual, usuario.senha):
        raise HTTPException(status_code=400, detail='A senha atual está incorreta.')
    if len(dados.nova_senha) < 10 or dados.nova_senha == dados.senha_atual:
        raise HTTPException(status_code=400, detail='Use uma senha nova, diferente, com pelo menos 10 caracteres.')
    usuario.senha = auth_utils.hash_password(dados.nova_senha)
    db.commit()
    return {'mensagem': 'Senha atualizada. Entre novamente para continuar.'}


@app.get('/usuarios', response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).order_by(models.Usuario.nome.asc()).all()


@app.post('/usuarios', response_model=schemas.UsuarioResponse)
def criar_usuario(user: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    email_limpo = user.email.strip().lower()
    if user.perfil not in ('Controladoria', 'Solicitante', 'Checklist'):
        raise HTTPException(status_code=400, detail='Perfil inválido.')
    if db.query(models.Usuario).filter(models.Usuario.email == email_limpo).first():
        raise HTTPException(status_code=400, detail='Já existe um usuário com este e-mail.')
    try:
        senha_hash = auth_utils.hash_password(user.senha)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    if not user.nome.strip():
        raise HTTPException(status_code=400, detail='Informe o nome do usuário.')
    condominio_id = None
    if user.perfil == 'Checklist':
        if user.condominio_id is None:
            raise HTTPException(status_code=400, detail='Selecione o condomínio do zelador.')
        condominio = db.query(models.Condominio).filter(models.Condominio.id == user.condominio_id).first()
        if not condominio:
            raise HTTPException(status_code=400, detail='Condomínio inválido.')
        condominio_id = condominio.id
        # Um zelador por condomínio, conforme a operação informada pela Haize.
        if db.query(models.Usuario).filter(models.Usuario.perfil == 'Checklist', models.Usuario.condominio_id == condominio_id).first():
            raise HTTPException(status_code=409, detail='Este condomínio já possui um zelador vinculado.')
    novo = models.Usuario(nome=user.nome.strip(), email=email_limpo,
                          senha=senha_hash, perfil=user.perfil, condominio_id=condominio_id)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo



@app.put('/usuarios/{usuario_id}/condominio', response_model=schemas.UsuarioResponse)
def vincular_zelador(usuario_id: int, dados: schemas.UsuarioCondominioUpdate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario or usuario.perfil != 'Checklist':
        raise HTTPException(status_code=404, detail='Zelador não encontrado.')
    cond = db.query(models.Condominio).filter(models.Condominio.id == dados.condominio_id).first()
    if not cond:
        raise HTTPException(status_code=400, detail='Condomínio inválido.')
    ocupado = db.query(models.Usuario).filter(
        models.Usuario.id != usuario_id,
        models.Usuario.perfil == 'Checklist',
        models.Usuario.condominio_id == cond.id,
    ).first()
    if ocupado:
        raise HTTPException(status_code=409, detail='Este condomínio já possui um zelador vinculado.')
    usuario.condominio_id = cond.id
    db.commit()
    db.refresh(usuario)
    return usuario

@app.put('/usuarios/{usuario_id}/senha')
def alterar_senha_usuario(usuario_id: int, dados: schemas.SenhaUpdate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail='Usuário não encontrado.')
    try:
        usuario.senha = auth_utils.hash_password(dados.nova_senha)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    db.commit()
    return {'mensagem': 'Senha atualizada com sucesso.'}


@app.delete('/usuarios/{usuario_id}')
def excluir_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    if usuario_id == request.state.auth_user_id:
        raise HTTPException(status_code=400, detail='Não é possível excluir seu próprio usuário.')
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail='Usuário não encontrado.')
    db.delete(usuario)
    db.commit()
    return {'mensagem': 'Usuário removido com sucesso.'}


# =========================================================================
# CONDOMÍNIOS, UNIDADES E RATEIO POR FRAÇÃO IDEAL
# =========================================================================
@app.get("/condominios", response_model=List[schemas.CondominioResponse])
def listar_condominios(request: Request, db: Session = Depends(get_db)):
    query = db.query(models.Condominio)
    if request.state.auth_user_role == 'Checklist':
        if request.state.auth_condominio_id is None:
            return []  # Sem vínculo = nenhum condomínio visível.
        query = query.filter(models.Condominio.id == request.state.auth_condominio_id)
    return query.order_by(models.Condominio.nome.asc()).all()


@app.post("/condominios", response_model=schemas.CondominioResponse)
def criar_condominio(cond: schemas.CondominioCreate, db: Session = Depends(get_db)):
    nome_limpo = cond.nome.strip()
    existente = db.query(models.Condominio).filter(models.Condominio.nome == nome_limpo).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe um condomínio com este nome.")

    novo = models.Condominio(
        nome=nome_limpo,
        cnpj=cond.cnpj,
        codigo=cond.codigo
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@app.put("/condominios/{condominio_id}", response_model=schemas.CondominioResponse)
def atualizar_condominio(condominio_id: int, cond: schemas.CondominioCreate, db: Session = Depends(get_db)):
    db_cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not db_cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")

    nome_antigo = db_cond.nome
    novo_nome = cond.nome.strip()

    db_cond.nome = novo_nome
    db_cond.cnpj = cond.cnpj
    db_cond.codigo = cond.codigo

    if nome_antigo != novo_nome:
        db.query(models.Solicitacao).filter(models.Solicitacao.condominio == nome_antigo).update(
            {models.Solicitacao.condominio: novo_nome}
        )
        db.query(models.ChecklistItem).filter(models.ChecklistItem.condominio == nome_antigo).update(
            {models.ChecklistItem.condominio: novo_nome}
        )

    db.commit()
    db.refresh(db_cond)
    return db_cond


@app.delete("/condominios/{condominio_id}")
def excluir_condominio(condominio_id: int, db: Session = Depends(get_db)):
    db_cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not db_cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    if db.query(models.Usuario).filter(models.Usuario.condominio_id == condominio_id).first():
        raise HTTPException(status_code=409, detail='Desvincule o zelador antes de excluir este condomínio.')
    db.delete(db_cond)
    db.commit()
    return {"mensagem": "Condomínio excluído com sucesso."}


@app.get("/condominios/{condominio_id}/unidades", response_model=List[schemas.UnidadeResponse])
def listar_unidades(condominio_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Unidade)
        .filter(models.Unidade.condominio_id == condominio_id)
        .order_by(models.Unidade.identificacao.asc())
        .all()
    )


@app.post("/condominios/{condominio_id}/unidades", response_model=schemas.UnidadeResponse)
def criar_unidade(condominio_id: int, unidade: schemas.UnidadeCreate, db: Session = Depends(get_db)):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")

    nova = models.Unidade(
        condominio_id=condominio_id,
        identificacao=unidade.identificacao.strip(),
        fracao_ideal=float(unidade.fracao_ideal or 0.0)
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


@app.delete("/unidades/{unidade_id}")
def excluir_unidade(unidade_id: int, db: Session = Depends(get_db)):
    un = db.query(models.Unidade).filter(models.Unidade.id == unidade_id).first()
    if not un:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")
    db.delete(un)
    db.commit()
    return {"mensagem": "Unidade removida com sucesso."}


@app.get("/condominios/{condominio_id}/rateio")
def calcular_rateio_condominio(
    condominio_id: int,
    mes: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")

    unidades = db.query(models.Unidade).filter(models.Unidade.condominio_id == condominio_id).all()
    query_sols = db.query(models.Solicitacao).filter(
        models.Solicitacao.condominio == cond.nome,
        models.Solicitacao.status == "Finalizada"
    )

    if mes:
        query_sols = query_sols.filter(models.Solicitacao.data.startswith(mes))

    solicitacoes_finalizadas = query_sols.all()
    total_gasto = sum(
        float(s.valor_realizado or s.valor_aprovado or s.valor or 0.0)
        for s in solicitacoes_finalizadas
    )

    rateio_lista = []
    for u in unidades:
        fracao = float(u.fracao_ideal or 0.0)
        valor_devido = (total_gasto * fracao) / 100.0
        rateio_lista.append({
            "unidade_id": u.id,
            "unidade": u.identificacao,
            "fracao_ideal": fracao,
            "valor_devido": round(valor_devido, 2)
        })

    return {
        "condominio": cond.nome,
        "mes": mes or "Todos",
        "total_gasto_condominio": round(total_gasto, 2),
        "quantidade_solicitacoes": len(solicitacoes_finalizadas),
        "rateio_unidades": rateio_lista
    }


# =========================================================================
# CATEGORIAS E LIMITES DE ALÇADA AUTOMÁTICA
# =========================================================================
def parse_limites_seguro(limites_raw):
    if not limites_raw:
        return []
    if isinstance(limites_raw, list):
        return limites_raw
    if isinstance(limites_raw, str):
        try:
            parsed = json.loads(limites_raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def formatar_categoria_retorno(cat_obj):
    return {
        "id": cat_obj.id,
        "nome": cat_obj.nome,
        "descricao": cat_obj.descricao,
        "limites": parse_limites_seguro(cat_obj.limites)
    }


@app.get("/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    categorias = db.query(models.Categoria).order_by(models.Categoria.nome.asc()).all()
    return [formatar_categoria_retorno(c) for c in categorias]


@app.post("/categorias")
def criar_categoria(cat: schemas.CategoriaCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("ALTER TABLE categorias ADD COLUMN limites TEXT"))
        db.commit()
    except Exception:
        db.rollback()

    nome_limpo = cat.nome.strip()
    existente = db.query(models.Categoria).filter(models.Categoria.nome == nome_limpo).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe uma categoria com este nome.")

    limites_lista = cat.limites if isinstance(cat.limites, list) else []
    limites_str = json.dumps(limites_lista, ensure_ascii=False)

    nova_categoria = models.Categoria(
        nome=nome_limpo,
        descricao=cat.descricao,
        limites=limites_str
    )
    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)
    return formatar_categoria_retorno(nova_categoria)


@app.put("/categorias/{categoria_id}")
def atualizar_categoria(categoria_id: int, cat: schemas.CategoriaCreate, db: Session = Depends(get_db)):
    db_cat = db.query(models.Categoria).filter(models.Categoria.id == categoria_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    limites_lista = cat.limites if isinstance(cat.limites, list) else []
    limites_str = json.dumps(limites_lista, ensure_ascii=False)

    nome_antigo = db_cat.nome
    novo_nome = cat.nome.strip()

    db_cat.nome = novo_nome
    db_cat.descricao = cat.descricao
    db_cat.limites = limites_str

    if nome_antigo != novo_nome:
        db.query(models.Solicitacao).filter(models.Solicitacao.categoria == nome_antigo).update(
            {models.Solicitacao.categoria: novo_nome}
        )

    db.commit()
    db.refresh(db_cat)
    return formatar_categoria_retorno(db_cat)


@app.delete("/categorias/{categoria_id}")
def excluir_categoria(categoria_id: int, db: Session = Depends(get_db)):
    db_cat = db.query(models.Categoria).filter(models.Categoria.id == categoria_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    db.delete(db_cat)
    db.commit()
    return {"mensagem": "Categoria excluída com sucesso."}


# =========================================================================
# FORNECEDORES
# =========================================================================
@app.get("/fornecedores", response_model=List[schemas.FornecedorResponse])
def listar_fornecedores(db: Session = Depends(get_db)):
    return db.query(models.Fornecedor).order_by(models.Fornecedor.nome.asc()).all()


@app.post("/fornecedores", response_model=schemas.FornecedorResponse)
def criar_fornecedor(forn: schemas.FornecedorCreate, db: Session = Depends(get_db)):
    novo = models.Fornecedor(
        nome=forn.nome.strip(),
        cnpj=forn.cnpj,
        categoria=forn.categoria
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@app.put("/fornecedores/{fornecedor_id}", response_model=schemas.FornecedorResponse)
def atualizar_fornecedor(fornecedor_id: int, forn: schemas.FornecedorCreate, db: Session = Depends(get_db)):
    db_forn = db.query(models.Fornecedor).filter(models.Fornecedor.id == fornecedor_id).first()
    if not db_forn:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")

    db_forn.nome = forn.nome.strip()
    db_forn.cnpj = forn.cnpj
    db_forn.categoria = forn.categoria
    db.commit()
    db.refresh(db_forn)
    return db_forn


@app.delete("/fornecedores/{fornecedor_id}")
def excluir_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    db_forn = db.query(models.Fornecedor).filter(models.Fornecedor.id == fornecedor_id).first()
    if not db_forn:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    db.delete(db_forn)
    db.commit()
    return {"mensagem": "Fornecedor excluído com sucesso."}


# =========================================================================
# SOLICITAÇÕES DE COMPRA, ALÇADA AUTOMÁTICA, HISTÓRICO E ANEXOS
# =========================================================================
def verificar_alcada_automatica(db: Session, nome_categoria: str, nome_condominio: str, valor_total: float):
    """Retorna True se o valor_total estiver dentro do limite pré-aprovado da categoria para o condomínio."""
    try:
        cat_db = db.query(models.Categoria).filter(models.Categoria.nome == nome_categoria).first()
        if not cat_db or not cat_db.limites:
            return False
        limites_lista = parse_limites_seguro(cat_db.limites)
        for item_lim in limites_lista:
            if isinstance(item_lim, dict):
                cond_lim = str(item_lim.get("condominio", "")).strip().lower()
                teto = float(item_lim.get("limite", 0) or 0.0)
                if cond_lim == str(nome_condominio or "").strip().lower() and teto > 0:
                    return valor_total <= teto
    except Exception as e:
        print("Aviso ao verificar alcada automatica:", e)
    return False


def registrar_historico_seguro(db: Session, solicitacao_id: int, acao: str, responsavel: str):
    try:
        hist = models.HistoricoSolicitacao(
            solicitacao_id=solicitacao_id,
            acao=acao,
            responsavel=responsavel or "Sistema"
        )
        db.add(hist)
        db.commit()
    except Exception as e:
        db.rollback()
        print("Aviso ao gravar historico:", e)


@app.get("/solicitacoes")
def listar_solicitacoes(request: Request, db: Session = Depends(get_db)):
    query = db.query(models.Solicitacao)
    if request.state.auth_user_role == 'Solicitante':
        query = query.filter(models.Solicitacao.solicitante == request.state.auth_user_name)
    return query.order_by(models.Solicitacao.id.desc()).all()


@app.post("/solicitacoes")
def criar_solicitacao(sol: schemas.SolicitacaoCreate, request: Request, db: Session = Depends(get_db)):
    valor_servico = float(sol.valor_servico or 0.0)
    valor_produto = float(sol.valor_produto or 0.0)
    valor_total = valor_servico + valor_produto

    aprovado_auto = verificar_alcada_automatica(db, sol.categoria, sol.condominio, valor_total)
    status_inicial = "Aprovada" if aprovado_auto else "Aprovação pendente"
    valor_aprovado_inicial = valor_total if aprovado_auto else 0.0

    ultimo = db.query(models.Solicitacao).order_by(models.Solicitacao.id.desc()).first()
    prox_num = (ultimo.id + 1) if ultimo else 1
    codigo_gerado = f"SOL-{prox_num:04d}"
    while db.query(models.Solicitacao).filter(models.Solicitacao.numero == codigo_gerado).first():
        prox_num += 1
        codigo_gerado = f"SOL-{prox_num:04d}"

    nova_sol = models.Solicitacao(
        numero=codigo_gerado,
        condominio=sol.condominio,
        condominio_id=sol.condominio_id,
        categoria=sol.categoria,
        fornecedor=sol.fornecedor,
        descricao=sol.descricao,
        valor_servico=valor_servico,
        valor_produto=valor_produto,
        valor=valor_total,
        valor_aprovado=valor_aprovado_inicial,
        valor_realizado=0.0,
        solicitante=request.state.auth_user_name,
        status=status_inicial,
        observacao=sol.observacao
    )
    db.add(nova_sol)
    db.commit()
    db.refresh(nova_sol)

    acao_txt = (
        f"Solicitação criada e APROVADA AUTOMATICAMENTE pela alçada (R$ {valor_total:.2f})"
        if aprovado_auto
        else "Solicitação criada e enviada para análise da Controladoria"
    )
    registrar_historico_seguro(db, nova_sol.id, acao_txt, request.state.auth_user_name)

    return nova_sol


@app.put("/solicitacoes/{solicitacao_id}")
def atualizar_solicitacao(solicitacao_id: int, sol: schemas.SolicitacaoCreate, request: Request, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    if request.state.auth_user_role == 'Solicitante':
        _solicitacao_visivel(db, request.state, solicitacao_id)
        if db_sol.status not in ('Aprovação pendente', 'Ajuste solicitado'):
            raise HTTPException(status_code=403, detail='Este pedido não pode mais ser editado.')

    valor_servico = float(sol.valor_servico or 0.0)
    valor_produto = float(sol.valor_produto or 0.0)
    valor_total = valor_servico + valor_produto

    aprovado_auto = verificar_alcada_automatica(db, sol.categoria, sol.condominio, valor_total)

    db_sol.condominio = sol.condominio
    db_sol.condominio_id = sol.condominio_id
    db_sol.categoria = sol.categoria
    db_sol.fornecedor = sol.fornecedor
    db_sol.descricao = sol.descricao
    db_sol.valor_servico = valor_servico
    db_sol.valor_produto = valor_produto
    db_sol.valor = valor_total
    db_sol.observacao = sol.observacao
    db_sol.motivo_ajuste = None

    if aprovado_auto:
        db_sol.status = "Aprovada"
        db_sol.valor_aprovado = valor_total
    else:
        db_sol.status = "Aprovação pendente"

    db.commit()
    db.refresh(db_sol)

    registrar_historico_seguro(
        db,
        db_sol.id,
        "Solicitação editada/corrigida pelo solicitante",
        request.state.auth_user_name
    )
    return db_sol


@app.put("/solicitacoes/{solicitacao_id}/status")
def atualizar_status_solicitacao(solicitacao_id: int, dados: schemas.StatusUpdate, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    db_sol.status = dados.status
    if dados.valor_aprovado is not None:
        db_sol.valor_aprovado = float(dados.valor_aprovado)
    if dados.motivo_ajuste is not None:
        db_sol.motivo_ajuste = dados.motivo_ajuste

    db.commit()
    db.refresh(db_sol)

    detalhe = f"Status alterado para '{dados.status}'"
    if dados.valor_aprovado:
        detalhe += f" (Valor Aprovado: R$ {float(dados.valor_aprovado):.2f})"
    if dados.motivo_ajuste:
        detalhe += f" — Motivo: {dados.motivo_ajuste}"

    registrar_historico_seguro(db, db_sol.id, detalhe, "Controladoria")
    return db_sol


@app.put("/solicitacoes/{solicitacao_id}/iniciar-execucao")
def iniciar_execucao_solicitacao(
    solicitacao_id: int,
    dados: schemas.IniciarExecucaoUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    # Controladoria tem acesso a todas; Solicitante, apenas às próprias.
    db_sol = _solicitacao_visivel(db, request.state, solicitacao_id)
    if db_sol.status != "Aprovada":
        raise HTTPException(
            status_code=409,
            detail="Somente solicitações aprovadas podem iniciar a execução.",
        )

    db_sol.status = "Em execução"
    db.commit()
    db.refresh(db_sol)

    registrar_historico_seguro(
        db, db_sol.id, "Solicitação enviada para execução",
        request.state.auth_user_name,
    )
    return db_sol


@app.put("/solicitacoes/{solicitacao_id}/finalizar")
def finalizar_solicitacao(
    solicitacao_id: int,
    dados: schemas.FinalizarUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    # A Controladoria pode finalizar qualquer compra; o Solicitante,
    # somente uma solicitação criada por ele. A checagem ocorre no servidor.
    if request.state.auth_user_role not in ('Controladoria', 'Solicitante'):
        raise HTTPException(status_code=403, detail='Perfil sem permissão para finalizar compras.')
    db_sol = _solicitacao_visivel(db, request.state, solicitacao_id)
    if db_sol.status != "Em execução":
        raise HTTPException(
            status_code=409,
            detail="Somente solicitações em execução podem ser finalizadas.",
        )

    valor = float(dados.valor_realizado or 0.0)
    if not isfinite(valor) or valor <= 0:
        raise HTTPException(status_code=422, detail="O valor realizado deve ser maior que zero.")

    db_sol.status = "Finalizada"
    db_sol.valor_realizado = valor
    db.commit()
    db.refresh(db_sol)

    registrar_historico_seguro(
        db,
        db_sol.id,
        f"Solicitação finalizada (Valor Realizado: R$ {db_sol.valor_realizado:.2f})",
        request.state.auth_user_name,
    )
    return db_sol


@app.delete("/solicitacoes/{solicitacao_id}")
def excluir_solicitacao(solicitacao_id: int, request: Request, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    if request.state.auth_user_role == 'Solicitante':
        _solicitacao_visivel(db, request.state, solicitacao_id)
        if db_sol.status not in ('Aprovação pendente', 'Ajuste solicitado'):
            raise HTTPException(status_code=403, detail='Este pedido não pode mais ser excluído.')

    # Não apague os arquivos antes de o banco confirmar a exclusão.
    try:
        # Um SELECT do modelo inteiro exige todas as colunas de anexos.
        # Bancos antigos podem não ter algumas delas, impedindo a exclusão.
        # Lemos SOMENTE o caminho, e apenas se a coluna realmente existir.
        caminhos_anexos = []
        colunas_anexos = {
            coluna["name"] for coluna in inspect(db.get_bind()).get_columns("anexos")
        }
        if "caminho" in colunas_anexos:
            caminhos_anexos = [
                caminho
                for caminho in db.execute(
                    text("SELECT caminho FROM anexos WHERE solicitacao_id = :solicitacao_id"),
                    {"solicitacao_id": solicitacao_id}
                ).scalars().all()
                if isinstance(caminho, str) and caminho
            ]
        db.query(models.HistoricoSolicitacao).filter(
            models.HistoricoSolicitacao.solicitacao_id == solicitacao_id
        ).delete(synchronize_session=False)
        db.query(models.Anexo).filter(
            models.Anexo.solicitacao_id == solicitacao_id
        ).delete(synchronize_session=False)
        db.delete(db_sol)
        db.commit()
    except Exception:
        db.rollback()
        logging.exception("Falha ao excluir solicitação %s", solicitacao_id)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível excluir a solicitação no banco de dados. Consulte os Logs do Render."
        )

    # A limpeza dos anexos é posterior à confirmação: problemas com arquivo
    # não devem desfazer nem falsificar a exclusão já feita no banco.
    for caminho in caminhos_anexos:
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
        except OSError:
            logging.warning("Não foi possível limpar anexo após excluir solicitação %s", solicitacao_id, exc_info=True)

    return {"mensagem": "Solicitação excluída com sucesso."}


@app.get("/solicitacoes/{solicitacao_id}/historico")
def listar_historico_solicitacao(solicitacao_id: int, request: Request, db: Session = Depends(get_db)):
    _solicitacao_visivel(db, request.state, solicitacao_id)
    return (
        db.query(models.HistoricoSolicitacao)
        .filter(models.HistoricoSolicitacao.solicitacao_id == solicitacao_id)
        .order_by(models.HistoricoSolicitacao.id.desc())
        .all()
    )


@app.get("/solicitacoes/{solicitacao_id}/anexos")
def listar_anexos_solicitacao(solicitacao_id: int, request: Request, db: Session = Depends(get_db)):
    _solicitacao_visivel(db, request.state, solicitacao_id)
    return (
        db.query(models.Anexo)
        .filter(models.Anexo.solicitacao_id == solicitacao_id)
        .order_by(models.Anexo.id.desc())
        .all()
    )


@app.post("/solicitacoes/{solicitacao_id}/anexos")
def upload_anexo_solicitacao(
    solicitacao_id: int,
    request: Request,
    arquivo: UploadFile = File(...),
    tipo: str = Form("Orçamento"),
    responsavel: str = Form("Usuário"),
    db: Session = Depends(get_db)
):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    _solicitacao_visivel(db, request.state, solicitacao_id)

    nome_seguro = f"{solicitacao_id}_{uuid.uuid4().hex[:8]}_{arquivo.filename}"
    caminho_completo = os.path.join(UPLOAD_DIR, nome_seguro)

    with open(caminho_completo, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    novo_anexo = models.Anexo(
        solicitacao_id=solicitacao_id,
        nome_arquivo=arquivo.filename,
        caminho=caminho_completo,
        tipo=tipo,
        responsavel=request.state.auth_user_name
    )
    db.add(novo_anexo)
    db.commit()
    db.refresh(novo_anexo)

    registrar_historico_seguro(
        db,
        solicitacao_id,
        f"Arquivo anexado ({tipo}): {arquivo.filename}",
        request.state.auth_user_name
    )
    return novo_anexo


@app.get("/anexos/{anexo_id}/download")
def download_anexo(anexo_id: int, request: Request, db: Session = Depends(get_db)):
    anexo = db.query(models.Anexo).filter(models.Anexo.id == anexo_id).first()
    if not anexo or not os.path.exists(anexo.caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor.")
    _solicitacao_visivel(db, request.state, anexo.solicitacao_id)
    return FileResponse(anexo.caminho, filename=anexo.nome_arquivo)


# =========================================================================
# CHECKLIST OPERACIONAL, VISTORIAS E ENVIO AUTOMÁTICO DE RELATÓRIO POR E-MAIL
# =========================================================================
# Prazos calculados no servidor (fonte única das notificações).
# Primeira vistoria vence após a frequência contada da criação da atividade.
def _data_checklist(valor):
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(valor).strip().replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _intervalo_checklist(frequencia):
    nome = unicodedata.normalize('NFKD', str(frequencia or '').lower())
    nome = ''.join(c for c in nome if not unicodedata.combining(c)).strip()
    return timedelta(days={'diaria': 1, 'diario': 1, 'semanal': 7,
                           'quinzenal': 15, 'mensal': 30}.get(nome, 1))


def _alertas_atraso_checklist(db: Session, condominio_id=None):
    itens_query = db.query(models.ChecklistItem)
    if condominio_id is not None:
        itens_query = itens_query.filter(models.ChecklistItem.condominio_id == condominio_id)
    itens = itens_query.all()
    ids = [i.id for i in itens]
    ultimas = {}
    # Uma consulta para o histórico, em vez de N consultas por atividade.
    if ids:
        for ex in db.query(models.ChecklistExecucao).filter(
                models.ChecklistExecucao.item_id.in_(ids)).order_by(
                    models.ChecklistExecucao.id.desc()).all():
            ultimas.setdefault(ex.item_id, ex)
    agora = datetime.now()
    alertas = []
    for item in itens:
        ultima = ultimas.get(item.id)
        referencia = _data_checklist(ultima.data_execucao if ultima else item.criado_em)
        if referencia is None:
            continue
        vencimento = referencia + _intervalo_checklist(item.frequencia)
        if agora <= vencimento:
            continue
        atraso_horas = round((agora - vencimento).total_seconds() / 3600, 1)
        alertas.append({
            'item_id': item.id,
            'condominio_id': item.condominio_id,
            'condominio': item.condominio,
            'titulo': item.titulo,
            'frequencia': item.frequencia,
            'ultima_execucao': ultima.data_execucao if ultima else None,
            'vencimento': vencimento.isoformat(timespec='seconds'),
            'horas_atraso': atraso_horas,
            'nunca_executado': ultima is None,
        })
    return sorted(alertas, key=lambda x: x['horas_atraso'], reverse=True)


@app.get('/checklists/alertas')
def listar_alertas_checklist(request: Request, db: Session = Depends(get_db)):
    if request.state.auth_user_role == 'Checklist':
        if not request.state.auth_condominio_id:
            return {'total': 0, 'alertas': []}
        condominio_id = request.state.auth_condominio_id
    else:
        condominio_id = None
    dados = _alertas_atraso_checklist(db, condominio_id)
    return {'total': len(dados), 'alertas': dados}


@app.post('/automacoes/checklists/atrasos')
def listar_destinatarios_atrasos(db: Session = Depends(get_db)):
    """Consulta para gatilho diário GAS; a chave é verificada no middleware."""
    alertas = _alertas_atraso_checklist(db)
    por_condominio = {}
    for a in alertas:
        por_condominio.setdefault(a['condominio_id'], []).append(a)
    destinatarios = []
    usuarios = db.query(models.Usuario).filter(
        models.Usuario.perfil.in_(['Controladoria', 'Checklist'])).all()
    for usuario in usuarios:
        if not usuario.email or '@' not in usuario.email:
            continue
        if usuario.perfil == 'Controladoria':
            pessoais = alertas
        else:
            pessoais = por_condominio.get(usuario.condominio_id, [])
        if pessoais:
            destinatarios.append({'email': usuario.email.strip().lower(), 'nome': usuario.nome,
                                  'perfil': usuario.perfil, 'alertas': pessoais})
    return {'total_atividades_atrasadas': len(alertas), 'destinatarios': destinatarios}


def formatar_item_checklist(db: Session, item: models.ChecklistItem):
    execucoes = (
        db.query(models.ChecklistExecucao)
        .filter(models.ChecklistExecucao.item_id == item.id)
        .order_by(models.ChecklistExecucao.id.desc())
        .all()
    )
    historico = [
        {
            "id": ex.id,
            "item_id": ex.item_id,
            "responsavel": ex.responsavel,
            "status_conformidade": ex.status_conformidade,
            "observacao": ex.observacao,
            "data_execucao": ex.data_execucao,
            "tem_foto": bool(ex.caminho_foto)
        }
        for ex in execucoes
    ]
    return {
        "id": item.id,
        "condominio": item.condominio,
        "condominio_id": item.condominio_id,
        "titulo": item.titulo,
        "descricao_orientacao": item.descricao_orientacao,
        "frequencia": item.frequencia,
        "plano_acao_padrao": item.plano_acao_padrao,
        "criado_em": item.criado_em,
        "ultima_execucao": historico[0] if historico else None,
        "historico_execucoes": historico
    }


@app.get("/checklists")
def listar_checklists(request: Request, db: Session = Depends(get_db)):
    query = db.query(models.ChecklistItem)
    if request.state.auth_user_role == 'Checklist':
        if request.state.auth_condominio_id is None:
            return []
        query = query.filter(models.ChecklistItem.condominio_id == request.state.auth_condominio_id)
    itens = query.order_by(models.ChecklistItem.id.desc()).all()
    return [formatar_item_checklist(db, item) for item in itens]


def _condominio_para_atividade(db: Session, dados: schemas.ChecklistItemCreate):
    # A API deriva o nome pelo ID cadastrado; nunca confia apenas em um nome
    # recebido do navegador para definir o condomínio de uma vistoria.
    if dados.condominio_id is not None:
        cond = db.query(models.Condominio).filter(models.Condominio.id == dados.condominio_id).first()
    else:
        cond = db.query(models.Condominio).filter(models.Condominio.nome == dados.condominio.strip()).first()
    if not cond:
        raise HTTPException(status_code=400, detail='Condomínio não encontrado para a atividade.')
    return cond


def _validar_acesso_item(request: Request, item: models.ChecklistItem) -> None:
    if request.state.auth_user_role == 'Checklist':
        if (request.state.auth_condominio_id is None or
                item.condominio_id != request.state.auth_condominio_id):
            # Não divulga a existência de atividades de outros condomínios.
            raise HTTPException(status_code=404, detail='Atividade não encontrada.')


def _validar_acesso_condominio(request: Request, condominio_id: int) -> None:
    if request.state.auth_user_role == 'Checklist':
        if (request.state.auth_condominio_id is None or
                condominio_id != request.state.auth_condominio_id):
            raise HTTPException(status_code=404, detail='Condomínio não encontrado.')


@app.post("/checklists")
def criar_checklist(item: schemas.ChecklistItemCreate, db: Session = Depends(get_db)):
    cond = _condominio_para_atividade(db, item)
    novo = models.ChecklistItem(
        condominio=cond.nome,
        condominio_id=cond.id,
        titulo=item.titulo.strip(),
        descricao_orientacao=item.descricao_orientacao,
        frequencia=item.frequencia,
        plano_acao_padrao=item.plano_acao_padrao
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return formatar_item_checklist(db, novo)


@app.put("/checklists/{item_id}")
def atualizar_checklist(item_id: int, dados: schemas.ChecklistItemCreate, db: Session = Depends(get_db)):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Atividade não encontrada.")

    cond = _condominio_para_atividade(db, dados)
    item.condominio = cond.nome
    item.condominio_id = cond.id
    item.titulo = dados.titulo.strip()
    item.descricao_orientacao = dados.descricao_orientacao
    item.frequencia = dados.frequencia
    item.plano_acao_padrao = dados.plano_acao_padrao

    db.commit()
    db.refresh(item)
    return formatar_item_checklist(db, item)


@app.delete("/checklists/{item_id}")
def excluir_checklist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Atividade não encontrada.")

    execs = db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.item_id == item_id).all()
    for ex in execs:
        if ex.caminho_foto and os.path.exists(ex.caminho_foto):
            try:
                os.remove(ex.caminho_foto)
            except Exception:
                pass
    db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.item_id == item_id).delete()
    db.delete(item)
    db.commit()
    return {"mensagem": "Atividade excluída com sucesso."}


@app.post("/checklists/{item_id}/executar")
def executar_checklist(
    item_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    responsavel: str = Form(...),
    status_conformidade: str = Form("Conforme"),
    observacao: Optional[str] = Form(""),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item de checklist não encontrado.")
    _validar_acesso_item(request, item)

    nome_foto = None
    caminho_foto = None

    if foto and foto.filename:
        nome_foto = foto.filename
        nome_seguro = f"chk_{item_id}_{uuid.uuid4().hex[:8]}_{foto.filename}"
        caminho_foto = os.path.join(FOTOS_CHECKLIST_DIR, nome_seguro)
        with open(caminho_foto, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

    execucao = models.ChecklistExecucao(
        item_id=item_id,
        responsavel=request.state.auth_user_name,
        status_conformidade=status_conformidade,
        observacao=observacao,
        nome_foto=nome_foto,
        caminho_foto=caminho_foto
    )
    db.add(execucao)
    db.flush()  # obtém o ID antes do commit para criar a fila na mesma transação
    if ENVIO_AUTOMATICO_CHECKLIST:
        db.flush()
        dados_envio = _dados_pdf_execucao(item, execucao)
        novo_envio = models.ChecklistEnvioRelatorio(
            execucao_id=execucao.id,
            dados_json=json.dumps(dados_envio, ensure_ascii=False),
            status='pendente',
        )
        db.add(novo_envio)
        db.flush()
        envio_id = novo_envio.id
    else:
        envio_id = None
    db.commit()
    db.refresh(execucao)
    if envio_id is not None:
        background_tasks.add_task(_processar_envio_execucao, envio_id)
    resultado = formatar_item_checklist(db, item)
    resultado['envio_relatorio'] = 'em_fila' if envio_id is not None else 'desativado'
    return resultado


def _dados_pdf_execucao(item, execucao):
    return {
        'condominio': item.condominio,
        'atividade': item.titulo,
        'frequencia': item.frequencia,
        'descricao_orientacao': item.descricao_orientacao or '',
        'plano_acao': item.plano_acao_padrao or '',
        'responsavel': execucao.responsavel,
        'data_execucao': execucao.data_execucao,
        'status': execucao.status_conformidade,
        'observacao': execucao.observacao or '',
        'tem_foto': bool(execucao.caminho_foto),
    }


def gerar_pdf_execucao_checklist(dados: dict) -> bytes:
    """PDF individual, inclusive para vistorias conformes (e não só divergências)."""
    memoria = io.BytesIO()
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle('HaizeTextoExecucao', parent=estilos['Normal'],
                            fontName='Helvetica', fontSize=10, leading=15,
                            textColor=colors.HexColor('#334155'))
    cab = ParagraphStyle('HaizeCabExecucao', parent=normal, fontName='Helvetica-Bold',
                         textColor=colors.HexColor('#0f172a'))
    titulo = ParagraphStyle('HaizeTituloExecucao', parent=cab, fontSize=16, leading=20)
    def p(valor, estilo=normal):
        return Paragraph(escape(str(valor or '-')).replace('\n', '<br/>'), estilo)
    doc = SimpleDocTemplate(memoria, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm,
                            title='Registro de vistoria - Haize')
    linhas = [
        [p('Condomínio', cab), p(dados['condominio'])],
        [p('Atividade', cab), p(dados['atividade'])],
        [p('Frequência', cab), p(dados['frequencia'])],
        [p('Realizado por', cab), p(dados['responsavel'])],
        [p('Registrado em', cab), p(dados['data_execucao'])],
        [p('Resultado', cab), p(dados['status'])],
        [p('Observações', cab), p(dados.get('observacao') or 'Sem observações')],
        [p('Orientações', cab), p(dados.get('descricao_orientacao') or '-')],
        [p('Plano de ação', cab), p(dados.get('plano_acao') or '-')],
        [p('Foto', cab), p('Registrada no aplicativo' if dados.get('tem_foto') else 'Não anexada')],
    ]
    tabela = Table(linhas, colWidths=[38*mm, 132*mm], hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f8fafc')]),
        ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#e2e8f0')),
        ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
    ]))
    doc.build([Paragraph('HAIZE | RELATÓRIO DE VISTORIA', titulo), Spacer(1,8*mm), tabela,
               Spacer(1,10*mm),p('Relatório gerado automaticamente após o registro da atividade.')])
    return memoria.getvalue()


def _processar_envio_execucao(envio_id: int):
    # Reivindicação atômica evita duas tarefas enviando o mesmo PDF simultaneamente.
    with SessionLocal() as db:
        agora = datetime.now()
        vencido = (agora - timedelta(minutes=15)).isoformat(timespec='seconds')
        elegivel = or_(
            models.ChecklistEnvioRelatorio.status.in_(['pendente', 'falhou']),
            and_(models.ChecklistEnvioRelatorio.status == 'processando',
                 models.ChecklistEnvioRelatorio.inicio_tentativa < vencido),
        )
        linhas = db.query(models.ChecklistEnvioRelatorio).filter(
            models.ChecklistEnvioRelatorio.id == envio_id, elegivel).update({
                'status': 'processando',
                'inicio_tentativa': agora.isoformat(timespec='seconds'),
                'tentativas': models.ChecklistEnvioRelatorio.tentativas + 1,
                'ultimo_erro': None,
            }, synchronize_session=False)
        db.commit()
        if not linhas:
            return
        envio = db.query(models.ChecklistEnvioRelatorio).filter_by(id=envio_id).first()
        try:
            dados = json.loads(envio.dados_json)
            pdf = gerar_pdf_execucao_checklist(dados)
            enviar_relatorio_google_apps_script({'condominio': dados['condominio']}, pdf_bytes=pdf)
            envio.status = 'enviado'
            envio.enviado_em = datetime.now().isoformat(timespec='seconds')
        except Exception as exc:
            logger.exception('Falha no envio automático da vistoria %s', envio.execucao_id)
            envio.status = 'falhou'
            envio.ultimo_erro = str(exc)[:400]
        db.commit()


@app.get('/checklists/envios')
def listar_envios_checklist(db: Session = Depends(get_db)):
    envios = db.query(models.ChecklistEnvioRelatorio).order_by(
        models.ChecklistEnvioRelatorio.id.desc()).limit(100).all()
    return [{'id': x.id, 'execucao_id': x.execucao_id, 'status': x.status,
             'tentativas': x.tentativas, 'enviado_em': x.enviado_em,
             'criado_em': x.criado_em} for x in envios]


@app.post('/checklists/envios/reprocessar')
def reprocessar_envios_checklist(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not ENVIO_AUTOMATICO_CHECKLIST:
        raise HTTPException(status_code=503, detail='Envio automático de relatórios está desativado neste ambiente.')
    vencido = (datetime.now() - timedelta(minutes=15)).isoformat(timespec='seconds')
    envios = db.query(models.ChecklistEnvioRelatorio).filter(
        or_(models.ChecklistEnvioRelatorio.status.in_(['pendente', 'falhou']),
            and_(models.ChecklistEnvioRelatorio.status == 'processando',
                 models.ChecklistEnvioRelatorio.inicio_tentativa < vencido)),
        models.ChecklistEnvioRelatorio.tentativas < 4).order_by(
            models.ChecklistEnvioRelatorio.id.asc()).limit(20).all()
    for envio in envios:
        background_tasks.add_task(_processar_envio_execucao, envio.id)
    return {'fila_reprocessamento': len(envios)}


@app.get("/checklists/execucoes/{execucao_id}/foto")
def ver_foto_execucao(execucao_id: int, request: Request, db: Session = Depends(get_db)):
    ex = db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.id == execucao_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail='Foto não encontrada.')
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == ex.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Foto não encontrada.')
    _validar_acesso_item(request, item)
    if not ex.caminho_foto or not os.path.exists(ex.caminho_foto):
        raise HTTPException(status_code=404, detail='Foto não encontrada.')
    return FileResponse(ex.caminho_foto)


def gerar_pdf_relatorio_checklist(dados: dict) -> bytes:
    """Gera um PDF A4 horizontal em memória, sem armazenar no disco do Render."""
    memoria = io.BytesIO()
    documento = SimpleDocTemplate(
        memoria, pagesize=landscape(A4),
        rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=17 * mm,
        title=f"Relatório de Divergências - {dados['condominio']}",
        author="Haize Síndico Profissional",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloHaize", parent=estilos["Heading1"],
        fontName="Helvetica-Bold", fontSize=16, leading=19,
        textColor=colors.HexColor("#0f172a"), spaceAfter=5,
    )
    texto = ParagraphStyle(
        "TextoHaize", parent=estilos["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#334155"),
    )
    pequeno = ParagraphStyle(
        "PequenoHaize", parent=texto, fontSize=8, leading=11,
    )
    cabecalho = ParagraphStyle(
        "CabecalhoHaize", parent=pequeno, fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    def p(texto_bruto, estilo=pequeno):
        seguro = escape(str(texto_bruto or "-")).replace("\n", "<br/>")
        return Paragraph(seguro, estilo)

    elementos = [
        Paragraph("HAIZE SÍNDICO PROFISSIONAL", titulo),
        Paragraph("Relatório de Auditoria e Divergências de Vistoria", texto),
        Spacer(1, 7 * mm),
        p(f"Condomínio: {dados['condominio']}", texto),
        p(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Total de divergências: {dados['total_divergencias']}", texto),
        Spacer(1, 6 * mm),
    ]

    colunas = [
        Paragraph("ITEM VISTORIADO", cabecalho),
        Paragraph("APONTAMENTO / NÃO CONFORMIDADE", cabecalho),
        Paragraph("DIRETRIZ / PLANO DE AÇÃO", cabecalho),
    ]
    linhas = [colunas]
    for d in dados["divergencias"]:
        informacoes = [
            p(d.get("atividade")),
            p(f"Frequência: {d.get('frequencia') or '-'}"),
            p(f"Data: {d.get('data_ocorrencia') or '-'}"),
            p(f"Vistoriador: {d.get('responsavel') or '-'}"),
        ]
        linhas.append([
            informacoes,
            p(d.get("relato")),
            p(d.get("plano_acao")),
        ])
    if not dados["divergencias"]:
        linhas.append([
            p("Nenhuma irregularidade identificada; todas as vistorias estão em conformidade."),
            "", "",
        ])

    largura_util = landscape(A4)[0] - 32 * mm
    tabela = Table(
        linhas, colWidths=[largura_util * 0.31, largura_util * 0.35, largura_util * 0.34],
        repeatRows=1, hAlign="LEFT",
    )
    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]
    if not dados["divergencias"]:
        estilo_tabela.append(("SPAN", (0, 1), (-1, 1)))
    tabela.setStyle(TableStyle(estilo_tabela))
    elementos.append(tabela)
    elementos.append(Spacer(1, 16 * mm))
    elementos.append(Paragraph("Relatório gerado pelo sistema de Controladoria Haize.", pequeno))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(landscape(A4)[0] - 16 * mm, 9 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return memoria.getvalue()


def enviar_relatorio_google_apps_script(dados: dict, pdf_bytes: Optional[bytes] = None) -> None:
    """Envia o PDF a um Google Apps Script que usa MailApp.sendEmail.

    A resposta sucesso=true significa que o Apps Script concluiu a chamada
    do MailApp sem erro, mas não garante entrega na caixa de entrada.
    """
    if not GAS_WEB_APP_URL or not HAIZE_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Envio não configurado. Cadastre GAS_WEB_APP_URL e HAIZE_SECRET no Render.",
        )

    destino = urlparse(GAS_WEB_APP_URL)
    if (
        destino.scheme != "https"
        or destino.hostname != "script.google.com"
        or not destino.path.startswith("/macros/s/")
        or not destino.path.endswith("/exec")
    ):
        raise HTTPException(
            status_code=503,
            detail="GAS_WEB_APP_URL inválida. Use a URL de implantação do Apps Script terminada em /exec.",
        )

    pdf = pdf_bytes if pdf_bytes is not None else gerar_pdf_relatorio_checklist(dados)
    # O script espera exatamente estas chaves, como configurado anteriormente.
    payload = {
        "chave": HAIZE_SECRET,
        "condominio": dados["condominio"],
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
    }
    req = urllib_request.Request(
        GAS_WEB_APP_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # O ContentService do Google redireciona a resposta para googleusercontent.
        # urllib segue esse redirecionamento e lê o JSON de resposta.
        with urllib_request.urlopen(req, timeout=45) as resp:
            corpo = resp.read(100_000).decode("utf-8")
    except urllib_error.HTTPError as exc:
        logger.error("Google Apps Script respondeu com HTTP %s", exc.code)
        raise HTTPException(
            status_code=502,
            detail=f"Google Apps Script recusou o envio (HTTP {exc.code}). Confira a implantação e os logs.",
        ) from exc
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        logger.exception("Não foi possível acessar o Google Apps Script")
        raise HTTPException(
            status_code=502,
            detail="Erro de conexão com Google Apps Script. Confira a URL e a implantação.",
        ) from exc

    try:
        resposta = json.loads(corpo)
    except (json.JSONDecodeError, TypeError):
        logger.error("Resposta não JSON do Google Apps Script (possível página de login ou autorização)")
        raise HTTPException(
            status_code=502,
            detail="Google Apps Script não retornou JSON. Confirme o acesso 'Qualquer pessoa' e a autorização do script.",
        )

    if resposta.get("sucesso") is not True:
        erro_publico = resposta.get("erro", "Falha não especificada.")
        logger.error("Google Apps Script não concluiu o envio do checklist: %s", erro_publico)
        # Não exibe dados confidenciais do Script na interface.
        raise HTTPException(
            status_code=502,
            detail="O Google Apps Script não conseguiu enviar o e-mail. Confira a chave e os logs do Apps Script.",
        )

    logger.info("Google Apps Script confirmou envio do checklist para condomínio: %s", dados["condominio"])


@app.get("/condominios/{condominio_id}/checklist-relatorio-divergencias")
def relatorio_divergencias_checklist(
    condominio_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Consulta dados do relatório. GET não envia e-mail para evitar disparos acidentais."""
    _validar_acesso_condominio(request, condominio_id)
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")

    itens = db.query(models.ChecklistItem).filter(models.ChecklistItem.condominio_id == cond.id).all()
    divergencias = []
    for item in itens:
        ultima = (
            db.query(models.ChecklistExecucao)
            .filter(models.ChecklistExecucao.item_id == item.id)
            .order_by(models.ChecklistExecucao.id.desc())
            .first()
        )
        if ultima and ultima.status_conformidade == "Não Conforme":
            divergencias.append({
                "item_id": item.id,
                "atividade": item.titulo,
                "frequencia": item.frequencia,
                "responsavel": ultima.responsavel,
                "data_ocorrencia": ultima.data_execucao,
                "relato": ultima.observacao or "Sem descrição detalhada.",
                "plano_acao": item.plano_acao_padrao or "Acionar controladoria para definição corretiva.",
                "tem_foto": bool(ultima.caminho_foto),
            })
    return {
        "condominio": cond.nome,
        "total_divergencias": len(divergencias),
        "divergencias": divergencias,
        "emails_notificados": EMAILS_DESTINO_RELATORIO,
    }


@app.post("/condominios/{condominio_id}/checklist-relatorio-divergencias/enviar")
def enviar_relatorio_divergencias_checklist(
    condominio_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Gera PDF e solicita envio por HTTPS aos dois destinatários."""
    _validar_acesso_condominio(request, condominio_id)
    dados = relatorio_divergencias_checklist(condominio_id, request, db)
    enviar_relatorio_google_apps_script(dados)
    return {
        "status": "enviado_pelo_apps_script",
        "mensagem": "O Google Apps Script confirmou o envio do e-mail com o PDF anexado.",
        "emails_destino": EMAILS_DESTINO_RELATORIO,
        "condominio": dados["condominio"],
    }
