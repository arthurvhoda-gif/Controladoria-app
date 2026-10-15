from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import os
import shutil
from jose import JWTError, jwt
import bcrypt

from database import engine, Base, SessionLocal
import models

from schemas import (
    CondominioCreate,
    FornecedorCreate,
    CategoriaCreate,
    SolicitacaoCompraCreate,
    AtualizarStatus,
    IniciarExecucao,
    FinalizarCompra,
    UsuarioCreate,
    UsuarioLogin,
    Token
)

os.makedirs("uploads", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Controladoria", version="1.2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "https://controladoria-app-lilac.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "chave_secreta_super_complexa_mudar_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

security = HTTPBearer()

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_usuario_atual(credentials: HTTPAuthorizationCredentials = Security(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise HTTPException(status_code=401, detail="Credenciais inválidas")
    except JWTError: raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario is None: raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return usuario

def registrar_historico(
    db: Session, solicitacao, acao, responsavel="Usuário", descricao=None,
    status_anterior=None, status_novo=None, valor_anterior=None,
    valor_novo=None, observacao=None
):
    historico = models.HistoricoSolicitacao(
        solicitacao_id=solicitacao.id, data=datetime.now(), acao=acao,
        status_anterior=status_anterior, status_novo=status_novo,
        responsavel=responsavel, descricao=descricao,
        valor_anterior=valor_anterior, valor_novo=valor_novo, observacao=observacao
    )
    db.add(historico)

def montar_solicitacao(solicitacao):
    valor_solicitado = solicitacao.valor or 0
    valor_aprovado = solicitacao.valor_aprovado
    valor_realizado = solicitacao.valor_realizado
    economia_aprovacao = (valor_solicitado - valor_aprovado if (valor_aprovado is not None and valor_aprovado < valor_solicitado) else 0)
    economia_total = (valor_solicitado - valor_realizado if valor_realizado is not None else 0)

    return {
        "id": solicitacao.id, "numero": solicitacao.numero, "solicitante": solicitacao.solicitante,
        "condominio": solicitacao.condominio, "categoria": solicitacao.categoria, "descricao": solicitacao.descricao,
        "fornecedor": solicitacao.fornecedor, "valor_servico": solicitacao.valor_servico,
        "valor_produto": solicitacao.valor_produto, "valor": valor_solicitado, "observacao": solicitacao.observacao,
        "valor_aprovado": valor_aprovado, "valor_realizado": valor_realizado,
        "economia_aprovacao": economia_aprovacao, "economia_total": economia_total,
        "status": solicitacao.status, "motivo_ajuste": solicitacao.motivo_ajuste,
        "data": solicitacao.data, "data_inicio_execucao": solicitacao.data_inicio_execucao,
        "data_finalizacao": solicitacao.data_finalizacao, "observacao_execucao": solicitacao.observacao_execucao
    }

def montar_historico(item):
    return {
        "id": item.id, "solicitacao_id": item.solicitacao_id, "data": item.data,
        "acao": item.acao, "status_anterior": item.status_anterior, "status_novo": item.status_novo,
        "responsavel": item.responsavel, "descricao": item.descricao,
        "valor_anterior": item.valor_anterior, "valor_novo": item.valor_novo, "observacao": item.observacao
    }

@app.on_event("startup")
def criar_usuario_admin():
    db = SessionLocal()
    try:
        if db.query(models.Usuario).count() == 0:
            db.add(models.Usuario(nome="Administrador", email="admin@controladoria.com", senha=get_password_hash("admin123"), perfil="Controladoria"))
            db.commit()
    finally: db.close()

@app.post("/login", response_model=Token)
def login(credenciais: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == credenciais.email).first()
    if not usuario or not verify_password(credenciais.senha, usuario.senha): raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    return {"access_token": create_access_token(data={"sub": usuario.email}), "token_type": "bearer", "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "perfil": usuario.perfil}}

@app.post("/usuarios")
def criar_usuario(dados: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter(models.Usuario.email == dados.email).first(): raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    db.add(models.Usuario(nome=dados.nome, email=dados.email, senha=get_password_hash(dados.senha), perfil=dados.perfil))
    db.commit()
    return {"mensagem": "Usuário criado com sucesso!"}

@app.get("/status")
def status(): return {"status": "online"}

@app.get("/categorias")
def listar_categorias(db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    cats = db.query(models.Categoria).order_by(models.Categoria.nome.asc()).all()
    resultado = []
    for c in cats:
        limites_db = db.query(models.LimiteCategoriaCondominio).filter(models.LimiteCategoriaCondominio.categoria_nome == c.nome).all()
        resultado.append({
            "id": c.id, "nome": c.nome, "descricao": c.descricao,
            "limites": [{"condominio": l.condominio_nome, "limite": l.limite} for l in limites_db]
        })
    return resultado

@app.get("/orcamento-categoria")
def consultar_orcamento_categoria(condominio: str, categoria: str, ignorar_id: Optional[int] = None, db: Session = Depends(get_db)):
    limite_obj = db.query(models.LimiteCategoriaCondominio).filter(
        models.LimiteCategoriaCondominio.categoria_nome == categoria,
        models.LimiteCategoriaCondominio.condominio_nome == condominio
    ).first()
    
    teto = limite_obj.limite if limite_obj else 0.0
    
    query = db.query(models.SolicitacaoCompra).filter(
        models.SolicitacaoCompra.condominio == condominio,
        models.SolicitacaoCompra.categoria == categoria,
        models.SolicitacaoCompra.status.in_(["Aprovada", "Em execução", "Finalizada"])
    )
    if ignorar_id is not None:
        query = query.filter(models.SolicitacaoCompra.id != ignorar_id)
        
    sols_existentes = query.all()
    gasto_atual = sum((s.valor_aprovado if s.valor_aprovado is not None else s.valor) for s in sols_existentes)
    
    return {
        "teto": teto,
        "gasto_atual": gasto_atual,
        "saldo": teto - gasto_atual if teto > 0 else 0
    }

@app.post("/categorias")
def criar_categoria(cat: CategoriaCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_