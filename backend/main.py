from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
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

app = FastAPI(title="Controladoria", version="1.1.0")

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

@app.post("/categorias")
def criar_categoria(cat: CategoriaCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    try:
        existente = db.query(models.Categoria).filter(models.Categoria.nome == cat.nome).first()
        if existente:
            raise HTTPException(status_code=400, detail="Essa categoria já está cadastrada.")
            
        novo = models.Categoria(nome=cat.nome, descricao=cat.descricao)
        db.add(novo)
        db.commit()
        db.refresh(novo)
        
        if cat.limites:
            for lim in cat.limites:
                if lim.limite > 0:
                    db.add(models.LimiteCategoriaCondominio(
                        categoria_nome=novo.nome, 
                        condominio_nome=lim.condominio, 
                        limite=lim.limite
                    ))
            db.commit()
            
        return novo
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/categorias/{id}")
def atualizar_categoria(id: int, cat: CategoriaCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    try:
        item = db.query(models.Categoria).filter(models.Categoria.id == id).first()
        if not item: raise HTTPException(status_code=404, detail="Categoria não encontrada.")
        
        nome_antigo = item.nome
        item.nome, item.descricao = cat.nome, cat.descricao
        
        db.query(models.LimiteCategoriaCondominio).filter(models.LimiteCategoriaCondominio.categoria_nome == nome_antigo).delete()
        if cat.limites:
            for lim in cat.limites:
                if lim.limite > 0:
                    db.add(models.LimiteCategoriaCondominio(
                        categoria_nome=cat.nome, 
                        condominio_nome=lim.condominio, 
                        limite=lim.limite
                    ))
                
        db.commit()
        db.refresh(item)
        return item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/categorias/{id}")
def deletar_categoria(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    item = db.query(models.Categoria).filter(models.Categoria.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    
    db.query(models.LimiteCategoriaCondominio).filter(models.LimiteCategoriaCondominio.categoria_nome == item.nome).delete()
    db.delete(item)
    db.commit()
    return {"msg": "Excluída"}

@app.get("/condominios")
def listar_condominios(db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    return db.query(models.Condominio).order_by(models.Condominio.nome.asc()).all()

@app.post("/condominios")
def criar_condominio(cond: CondominioCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    novo = models.Condominio(nome=cond.nome, cnpj=cond.cnpj, codigo=cond.codigo)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/condominios/{id}")
def atualizar_condominio(id: int, cond: CondominioCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    item = db.query(models.Condominio).filter(models.Condominio.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    item.nome, item.cnpj, item.codigo = cond.nome, cond.cnpj, cond.codigo
    db.commit()
    db.refresh(item)
    return item

@app.delete("/condominios/{id}")
def deletar_condominio(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    item = db.query(models.Condominio).filter(models.Condominio.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    db.delete(item)
    db.commit()
    return {"msg": "Excluído"}

@app.get("/fornecedores")
def listar_fornecedores(db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    return db.query(models.Fornecedor).order_by(models.Fornecedor.nome.asc()).all()

@app.post("/fornecedores")
def criar_fornecedor(forn: FornecedorCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    novo = models.Fornecedor(nome=forn.nome, cnpj=forn.cnpj, categoria=forn.categoria)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/fornecedores/{id}")
def atualizar_fornecedor(id: int, forn: FornecedorCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    item = db.query(models.Fornecedor).filter(models.Fornecedor.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    item.nome, item.cnpj, item.categoria = forn.nome, forn.cnpj, forn.categoria
    db.commit()
    db.refresh(item)
    return item

@app.delete("/fornecedores/{id}")
def deletar_fornecedor(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    item = db.query(models.Fornecedor).filter(models.Fornecedor.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    db.delete(item)
    db.commit()
    return {"msg": "Excluído"}

@app.post("/solicitacoes")
def criar_solicitacao(solicitacao: SolicitacaoCompraCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    quantidade = db.query(models.SolicitacaoCompra).count()
    valor_total = solicitacao.valor_servico + solicitacao.valor_produto

    status_final = "Aprovação pendente"
    valor_aprovado_final = None
    mensagem_historico = "Solicitação criada"

    if solicitacao.categoria and solicitacao.condominio:
        limite_obj = db.query(models.LimiteCategoriaCondominio).filter(
            models.LimiteCategoriaCondominio.categoria_nome == solicitacao.categoria,
            models.LimiteCategoriaCondominio.condominio_nome == solicitacao.condominio
        ).first()
        
        if limite_obj and limite_obj.limite > 0:
            # SOMA ACUMULADA: Pega todas as solicitações já aprovadas, em execução ou finalizadas para essa categoria no condomínio
            sols_existentes = db.query(models.SolicitacaoCompra).filter(
                models.SolicitacaoCompra.condominio == solicitacao.condominio,
                models.SolicitacaoCompra.categoria == solicitacao.categoria,
                models.SolicitacaoCompra.status.in_(["Aprovada", "Em execução", "Finalizada"])
            ).all()
            
            soma_atual = sum((s.valor_aprovado if s.valor_aprovado is not None else s.valor) for s in sols_existentes)
            
            # Se a soma acumulada + o novo pedido não ultrapassar o teto, aprova automaticamente!
            if (soma_atual + valor_total) <= limite_obj.limite:
                status_final = "Aprovada"
                valor_aprovado_final = valor_total
                mensagem_historico = f"Aprovada automaticamente (Dentro do teto acumulado de {solicitacao.categoria})"

    nova = models.SolicitacaoCompra(
        numero=f"SC-{(quantidade + 1):06d}", solicitante=solicitacao.solicitante,
        condominio=solicitacao.condominio, categoria=solicitacao.categoria,
        descricao=solicitacao.descricao, fornecedor=solicitacao.fornecedor,
        valor_servico=solicitacao.valor_servico, valor_produto=solicitacao.valor_produto,
        valor=valor_total, observacao=solicitacao.observacao, prioridade=solicitacao.prioridade,
        status=status_final, valor_aprovado=valor_aprovado_final, data=datetime.now()
    )
    
    db.add(nova)
    db.commit()
    db.refresh(nova)

    registrar_historico(
        db, nova, acao=mensagem_historico, responsavel="Sistema" if status_final == "Aprovada" else solicitacao.solicitante,
        status_novo=status_final, valor_novo=nova.valor
    )
    db.commit()
    
    return {"mensagem": "Criada", "solicitacao": montar_solicitacao(nova)}

@app.get("/solicitacoes")
def listar_solicitacoes(db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    return [montar_solicitacao(s) for s in db.query(models.SolicitacaoCompra).order_by(models.SolicitacaoCompra.id.desc()).all()]

@app.put("/solicitacoes/{id}")
def atualizar_solicitacao(id: int, solicitacao: SolicitacaoCompraCreate, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    status_anterior, valor_anterior = sol.status, sol.valor
    valor_total = solicitacao.valor_servico + solicitacao.valor_produto

    sol.condominio, sol.categoria, sol.descricao = solicitacao.condominio, solicitacao.categoria, solicitacao.descricao
    sol.fornecedor, sol.valor_servico, sol.valor_produto = solicitacao.fornecedor, solicitacao.valor_servico, solicitacao.valor_produto
    sol.valor, sol.observacao, sol.motivo_ajuste = valor_total, solicitacao.observacao, None

    status_final = "Aprovação pendente"
    valor_aprovado_final = None
    mensagem_historico = "Solicitação corrigida"

    if solicitacao.categoria and solicitacao.condominio:
        limite_obj = db.query(models.LimiteCategoriaCondominio).filter(
            models.LimiteCategoriaCondominio.categoria_nome == solicitacao.categoria,
            models.LimiteCategoriaCondominio.condominio_nome == solicitacao.condominio
        ).first()
        
        if limite_obj and limite_obj.limite > 0:
            # SOMA ACUMULADA (Excluindo o próprio item que está sendo editado)
            sols_existentes = db.query(models.SolicitacaoCompra).filter(
                models.SolicitacaoCompra.condominio == solicitacao.condominio,
                models.SolicitacaoCompra.categoria == solicitacao.categoria,
                models.SolicitacaoCompra.status.in_(["Aprovada", "Em execução", "Finalizada"]),
                models.SolicitacaoCompra.id != id
            ).all()
            
            soma_atual = sum((s.valor_aprovado if s.valor_aprovado is not None else s.valor) for s in sols_existentes)
            
            if (soma_atual + valor_total) <= limite_obj.limite:
                status_final = "Aprovada"
                valor_aprovado_final = valor_total
                mensagem_historico = f"Aprovada automaticamente após correção (Teto acumulado respeitado)"

    sol.status = status_final
    sol.valor_aprovado = valor_aprovado_final

    db.commit()
    db.refresh(sol)

    registrar_historico(
        db, sol, acao=mensagem_historico, responsavel="Sistema" if status_final == "Aprovada" else solicitacao.solicitante,
        status_anterior=status_anterior, status_novo=status_final, valor_anterior=valor_anterior, valor_novo=sol.valor
    )
    db.commit()
    return {"mensagem": "Solicitação atualizada.", "solicitacao": montar_solicitacao(sol)}

@app.delete("/solicitacoes/{id}")
def deletar_solicitacao(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    db.query(models.HistoricoSolicitacao).filter(models.HistoricoSolicitacao.solicitacao_id == id).delete()
    db.query(models.Anexo).filter(models.Anexo.solicitacao_id == id).delete()
    db.delete(sol)
    db.commit()
    return {"mensagem": "Excluída."}

@app.get("/solicitacoes/{id}/historico")
def listar_historico(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    return [montar_historico(i) for i in db.query(models.HistoricoSolicitacao).filter(models.HistoricoSolicitacao.solicitacao_id == id).order_by(models.HistoricoSolicitacao.data.asc()).all()]

@app.put("/solicitacoes/{id}/status")
def atualizar_status(id: int, dados: AtualizarStatus, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    status_ant, v_aprov_ant = sol.status, sol.valor_aprovado

    if dados.status in ["Aprovada", "Pagamento aprovado"]:
        sol.valor_aprovado = dados.valor_aprovado if dados.valor_aprovado is not None else sol.valor
        sol.status, acao, descricao = "Aprovada", "Aprovada", "Solicitação aprovada pela Controladoria."
    elif dados.status == "Ajuste solicitado":
        sol.motivo_ajuste, sol.status, acao, descricao = dados.motivo_ajuste, "Ajuste solicitado", "Ajuste solicitado", "Solicitação devolvida para correção."
    elif dados.status == "Reprovada":
        sol.valor_aprovado, sol.motivo_ajuste, sol.status, acao, descricao = 0, dados.motivo_ajuste, "Reprovada", "Reprovação", "Solicitação reprovada pela Controladoria."
    else: raise HTTPException(status_code=400, detail=f"Status não suportado via esse endpoint.")

    db.commit()
    db.refresh(sol)
    registrar_historico(db, sol, acao=acao, responsavel="Controladoria", status_anterior=status_ant, status_novo=sol.status, valor_anterior=v_aprov_ant, valor_novo=sol.valor_aprovado, observacao=dados.motivo_ajuste, descricao=descricao)
    db.commit()
    return {"solicitacao": montar_solicitacao(sol)}

@app.put("/solicitacoes/{id}/iniciar-execucao")
def iniciar_execucao(id: int, dados: IniciarExecucao, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    if sol.status not in ["Pagamento aprovado", "Aprovada"]: raise HTTPException(status_code=400, detail="Somente uma solicitação aprovada pode entrar em execução.")

    status_anterior = sol.status
    sol.status, sol.data_inicio_execucao, sol.observacao_execucao = "Em execução", datetime.now(), dados.observacao_execucao
    db.commit()
    db.refresh(sol)
    registrar_historico(db, sol, acao="Execução iniciada", responsavel="Controladoria", status_anterior=status_anterior, status_novo="Em execução", valor_anterior=sol.valor_aprovado, valor_novo=sol.valor_aprovado, observacao=dados.observacao_execucao)
    db.commit()
    return {"solicitacao": montar_solicitacao(sol)}

@app.put("/solicitacoes/{id}/finalizar")
def finalizar_compra(id: int, dados: FinalizarCompra, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    if sol.status not in ["Em execução", "Pagamento aprovado", "Aprovada"]: raise HTTPException(status_code=400, detail="A solicitação precisa estar aprovada ou em execução para ser finalizada.")

    status_anterior, valor_anterior = sol.status, sol.valor_realizado
    sol.valor_realizado, sol.status, sol.data_finalizacao, sol.observacao_execucao = dados.valor_realizado, "Finalizada", datetime.now(), dados.observacao_execucao
    db.commit()
    db.refresh(sol)
    registrar_historico(db, sol, acao="Compra finalizada", responsavel="Controladoria", status_anterior=status_anterior, status_novo="Finalizada", valor_anterior=valor_anterior, valor_novo=dados.valor_realizado, observacao=dados.observacao_execucao)
    db.commit()
    return {"solicitacao": montar_solicitacao(sol)}

@app.post("/solicitacoes/{id}/anexos")
def upload_anexo(id: int, arquivo: UploadFile = File(...), tipo: str = Form(...), responsavel: str = Form(...), db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    sol = db.query(models.SolicitacaoCompra).filter(models.SolicitacaoCompra.id == id).first()
    if not sol: raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    nome_seguro = (arquivo.filename or "arquivo").replace(" ", "_").replace("/", "_").replace("\\", "_")
    caminho = f"uploads/{id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{nome_seguro}"
    with open(caminho, "wb") as buffer: shutil.copyfileobj(arquivo.file, buffer)

    db.add(models.Anexo(solicitacao_id=id, nome_arquivo=arquivo.filename, caminho_arquivo=caminho, tipo=tipo, data_upload=datetime.now()))
    db.add(models.HistoricoSolicitacao(solicitacao_id=id, data=datetime.now(), acao=f"Anexo: {tipo}", responsavel=responsavel, descricao=f"Arquivo '{arquivo.filename}' anexado."))
    db.commit()
    return {"mensagem": "Arquivo anexado!"}

@app.get("/solicitacoes/{id}/anexos")
def listar_anexos(id: int, db: Session = Depends(get_db), usuario=Depends(get_usuario_atual)):
    return [{"id": a.id, "nome_arquivo": a.nome_arquivo, "tipo": a.tipo, "data_upload": a.data_upload} for a in db.query(models.Anexo).filter(models.Anexo.solicitacao_id == id).order_by(models.Anexo.data_upload.desc()).all()]

@app.get("/anexos/{id}/download")
def baixar_anexo(id: int, db: Session = Depends(get_db)):
    anexo = db.query(models.Anexo).filter(models.Anexo.id == id).first()
    if not anexo or not os.path.exists(anexo.caminho_arquivo): raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(path=anexo.caminho_arquivo, filename=anexo.nome_arquivo)