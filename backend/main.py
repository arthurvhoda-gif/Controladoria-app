import os
import json
import uuid
import bcrypt
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import engine, Base, SessionLocal
import models
import schemas

# Cria tabelas se não existirem
Base.metadata.create_all(bind=engine)

# Migração segura para SQLite: adiciona a coluna plano_acao_padrao se ainda não existir
def executar_migracoes():
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE checklist_itens ADD COLUMN plano_acao_padrao TEXT"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

executar_migracoes()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Controladoria API - Haize")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_password_hash(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode("utf-8")

def verify_password(senha_plana: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha_plana.encode("utf-8")[:72], senha_hash.encode("utf-8"))
    except Exception:
        return False

def inicializar_admin():
    db = SessionLocal()
    try:
        admin = db.query(models.Usuario).filter(models.Usuario.email == "admin@controladoria.com").first()
        if not admin:
            db.add(models.Usuario(
                nome="Administrador",
                email="admin@controladoria.com",
                senha=get_password_hash("admin123"),
                perfil="Controladoria"
            ))
            db.commit()
    finally:
        db.close()

inicializar_admin()

# ==========================================
# FUNÇÃO AUXILIAR DE ALÇADA AUTOMÁTICA (PASSO 1)
# ==========================================
def obter_limite_aprovacao(db: Session, nome_categoria: str, condominio_nome: Optional[str], condominio_id: Optional[int]) -> Optional[float]:
    """
    Busca a categoria pelo nome, lê o JSON de limites e verifica se há alçada
    configurada para o condomínio (por ID, por nome ou global 'Todos').
    """
    if not nome_categoria:
        return None

    cat = db.query(models.Categoria).filter(
        models.Categoria.nome == nome_categoria.strip()
    ).first()

    if not cat or not cat.limites:
        return None

    try:
        lista_limites = json.loads(cat.limites)
        if not isinstance(lista_limites, list):
            return None
    except Exception:
        return None

    limite_global = None

    for item in lista_limites:
        if not isinstance(item, dict):
            continue

        # Suporta diferentes chaves possíveis vindas do frontend (valor, limite, valor_maximo, valor_limite)
        val_raw = item.get("valor") if item.get("valor") is not None else (
                  item.get("limite") if item.get("limite") is not None else (
                  item.get("valor_maximo") if item.get("valor_maximo") is not None else item.get("valor_limite")))

        if val_raw is None or val_raw == "":
            continue

        try:
            valor_limite = float(val_raw)
        except ValueError:
            continue

        item_cond_id = item.get("condominio_id") or item.get("condominioId")
        item_cond_nome = str(item.get("condominio") or item.get("condominio_nome") or "").strip()

        # 1. Bate pelo ID do condomínio
        if condominio_id is not None and item_cond_id is not None:
            if str(item_cond_id) == str(condominio_id):
                return valor_limite

        # 2. Bate pelo Nome do condomínio
        if condominio_nome and item_cond_nome:
            if item_cond_nome.lower() == condominio_nome.strip().lower():
                return valor_limite

        # 3. Guarda caso exista uma regra geral ("Todos" / "Geral")
        if item_cond_nome.lower() in ["todos", "geral", "todos os condomínios"]:
            limite_global = valor_limite

    return limite_global


@app.get("/")
@app.get("/status")
def status_api():
    return {"status": "online", "hora": datetime.now().isoformat()}

# ==========================================
# AUTENTICAÇÃO
# ==========================================
@app.post("/login")
def login(credenciais: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == credenciais.email.lower().strip()).first()
    if not usuario or not verify_password(credenciais.senha, usuario.senha):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    
    return {
        "access_token": f"token-{usuario.id}-{uuid.uuid4().hex[:8]}",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil
        }
    }

@app.get("/usuarios", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

# ==========================================
# CONDOMÍNIOS
# ==========================================
@app.get("/condominios")
def listar_condominios(db: Session = Depends(get_db)):
    return db.query(models.Condominio).order_by(models.Condominio.nome).all()

@app.post("/condominios")
def criar_condominio(dados: schemas.CondominioCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Condominio).filter(models.Condominio.nome == dados.nome.strip()).first()
    if existente:
        raise HTTPException(status_code=400, detail="Condomínio já cadastrado com este nome.")
    novo = models.Condominio(nome=dados.nome.strip(), cnpj=dados.cnpj, codigo=dados.codigo)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/condominios/{condominio_id}")
def atualizar_condominio(condominio_id: int, dados: schemas.CondominioCreate, db: Session = Depends(get_db)):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    cond.nome = dados.nome.strip()
    cond.cnpj = dados.cnpj
    cond.codigo = dados.codigo
    db.commit()
    db.refresh(cond)
    return cond

@app.delete("/condominios/{condominio_id}")
def excluir_condominio(condominio_id: int, db: Session = Depends(get_db)):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    db.delete(cond)
    db.commit()
    return {"mensagem": "Condomínio excluído com sucesso."}

# ==========================================
# UNIDADES E RATEIO POR FRAÇÃO IDEAL
# ==========================================
@app.get("/condominios/{condominio_id}/unidades", response_model=List[schemas.UnidadeResponse])
def listar_unidades(condominio_id: int, db: Session = Depends(get_db)):
    return db.query(models.Unidade).filter(models.Unidade.condominio_id == condominio_id).all()

@app.post("/condominios/{condominio_id}/unidades", response_model=schemas.UnidadeResponse)
def criar_unidade(condominio_id: int, dados: schemas.UnidadeCreate, db: Session = Depends(get_db)):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
    nova_unidade = models.Unidade(
        condominio_id=condominio_id,
        identificacao=dados.identificacao.strip(),
        fracao_ideal=dados.fracao_ideal
    )
    db.add(nova_unidade)
    db.commit()
    db.refresh(nova_unidade)
    return nova_unidade

@app.delete("/unidades/{unidade_id}")
def excluir_unidade(unidade_id: int, db: Session = Depends(get_db)):
    unidade = db.query(models.Unidade).filter(models.Unidade.id == unidade_id).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")
    db.delete(unidade)
    db.commit()
    return {"mensagem": "Unidade excluída com sucesso."}

@app.get("/condominios/{condominio_id}/rateio")
def calcular_rateio(condominio_id: int, mes: Optional[str] = None, db: Session = Depends(get_db)):
    unidades = db.query(models.Unidade).filter(models.Unidade.condominio_id == condominio_id).all()
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    
    query = db.query(models.Solicitacao).filter(
        models.Solicitacao.status.ilike("%Finalizada%")
    )
    if cond:
        query = query.filter((models.Solicitacao.condominio_id == condominio_id) | (models.Solicitacao.condominio == cond.nome))
    else:
        query = query.filter(models.Solicitacao.condominio_id == condominio_id)

    if mes:
        query = query.filter(models.Solicitacao.data.like(f"{mes}%"))
        
    solicitacoes = query.all()
    total_gasto = sum([s.valor_realizado or s.valor_aprovado or s.valor for s in solicitacoes])
    
    resultado_rateio = []
    for u in unidades:
        valor_devido = total_gasto * (u.fracao_ideal / 100.0)
        resultado_rateio.append({
            "unidade": u.identificacao,
            "fracao_ideal": u.fracao_ideal,
            "valor_devido": round(valor_devido, 2)
        })
        
    return {
        "total_gasto_condominio": round(total_gasto, 2),
        "quantidade_solicitacoes": len(solicitacoes),
        "rateio_unidades": resultado_rateio
    }

# ==========================================
# CATEGORIAS
# ==========================================
@app.get("/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    try:
        cats = db.query(models.Categoria).order_by(models.Categoria.nome).all()
        res = []
        for c in cats:
            limites_parsed = []
            if c.limites:
                try:
                    limites_parsed = json.loads(c.limites)
                except Exception:
                    limites_parsed = []
            res.append({
                "id": c.id,
                "nome": c.nome,
                "descricao": c.descricao or "",
                "limites": limites_parsed
            })
        return res
    except Exception as e:
        return []

@app.post("/categorias")
def criar_categoria(cat: schemas.CategoriaCreate, db: Session = Depends(get_db)):
    limites_str = json.dumps(cat.limites) if cat.limites is not None else None
    nova_categoria = models.Categoria(nome=cat.nome.strip(), descricao=cat.descricao, limites=limites_str)
    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)
    return nova_categoria

@app.put("/categorias/{categoria_id}")
def atualizar_categoria(categoria_id: int, cat: schemas.CategoriaCreate, db: Session = Depends(get_db)):
    c = db.query(models.Categoria).filter(models.Categoria.id == categoria_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    c.nome = cat.nome.strip()
    c.descricao = cat.descricao
    c.limites = json.dumps(cat.limites) if cat.limites is not None else None
    db.commit()
    db.refresh(c)
    return c

@app.delete("/categorias/{categoria_id}")
def excluir_categoria(categoria_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Categoria).filter(models.Categoria.id == categoria_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    db.delete(c)
    db.commit()
    return {"mensagem": "Categoria excluída com sucesso."}

# ==========================================
# FORNECEDORES
# ==========================================
@app.get("/fornecedores")
def listar_fornecedores(db: Session = Depends(get_db)):
    return db.query(models.Fornecedor).order_by(models.Fornecedor.nome).all()

@app.post("/fornecedores")
def criar_fornecedor(forn: schemas.FornecedorCreate, db: Session = Depends(get_db)):
    novo = models.Fornecedor(nome=forn.nome.strip(), cnpj=forn.cnpj, categoria=forn.categoria)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/fornecedores/{fornecedor_id}")
def atualizar_fornecedor(fornecedor_id: int, forn: schemas.FornecedorCreate, db: Session = Depends(get_db)):
    f = db.query(models.Fornecedor).filter(models.Fornecedor.id == fornecedor_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    f.nome = forn.nome.strip()
    f.cnpj = forn.cnpj
    f.categoria = forn.categoria
    db.commit()
    db.refresh(f)
    return f

@app.delete("/fornecedores/{fornecedor_id}")
def excluir_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    f = db.query(models.Fornecedor).filter(models.Fornecedor.id == fornecedor_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    db.delete(f)
    db.commit()
    return {"mensagem": "Fornecedor excluído com sucesso."}

# ==========================================
# SOLICITAÇÕES
# ==========================================
@app.get("/solicitacoes")
def listar_solicitacoes(db: Session = Depends(get_db)):
    return db.query(models.Solicitacao).order_by(models.Solicitacao.id.desc()).all()

@app.post("/solicitacoes")
def criar_solicitacao(dados: schemas.SolicitacaoCreate, db: Session = Depends(get_db)):
    qtd = db.query(models.Solicitacao).count() + 1
    numero_sol = f"SOL-{datetime.now().year}-{qtd:04d}"
    valor_total = (dados.valor_servico or 0.0) + (dados.valor_produto or 0.0)
    
    # Verifica se há limite de aprovação automática configurado para a categoria e condomínio
    limite_alcada = obter_limite_aprovacao(
        db=db,
        nome_categoria=dados.categoria,
        condominio_nome=dados.condominio,
        condominio_id=dados.condominio_id
    )

    if limite_alcada is not None and valor_total > 0 and valor_total <= limite_alcada:
        status_inicial = "Aprovada"
        valor_aprovado_inicial = valor_total
        acao_historico = f"Solicitação criada e aprovada automaticamente por regra de alçada da Controladoria (Limite: R$ {limite_alcada:.2f})"
        responsavel_historico = "Sistema (Alçada Automática)"
    else:
        status_inicial = "Aprovação pendente"
        valor_aprovado_inicial = None
        acao_historico = "Solicitação criada"
        responsavel_historico = dados.solicitante or "Solicitante"

    nova = models.Solicitacao(
        numero=numero_sol,
        condominio=dados.condominio,
        condominio_id=dados.condominio_id,
        categoria=dados.categoria,
        fornecedor=dados.fornecedor,
        descricao=dados.descricao,
        valor_servico=dados.valor_servico or 0.0,
        valor_produto=dados.valor_produto or 0.0,
        valor=valor_total,
        valor_aprovado=valor_aprovado_inicial,
        solicitante=dados.solicitante or "Solicitante",
        status=status_inicial,
        observacao=dados.observacao
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=nova.id,
        acao=acao_historico,
        responsavel=responsavel_historico
    ))
    db.commit()
    return nova

@app.put("/solicitacoes/{solicitacao_id}")
def editar_solicitacao(solicitacao_id: int, dados: schemas.SolicitacaoCreate, db: Session = Depends(get_db)):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    sol.condominio = dados.condominio
    sol.condominio_id = dados.condominio_id
    sol.categoria = dados.categoria
    sol.fornecedor = dados.fornecedor
    sol.descricao = dados.descricao
    sol.valor_servico = dados.valor_servico or 0.0
    sol.valor_produto = dados.valor_produto or 0.0
    sol.valor = sol.valor_servico + sol.valor_produto
    sol.observacao = dados.observacao
    sol.motivo_ajuste = None

    # Reavalia a regra de alçada caso o valor ajustado caia dentro do limite automático
    limite_alcada = obter_limite_aprovacao(
        db=db,
        nome_categoria=sol.categoria,
        condominio_nome=sol.condominio,
        condominio_id=sol.condominio_id
    )

    if limite_alcada is not None and sol.valor > 0 and sol.valor <= limite_alcada:
        sol.status = "Aprovada"
        sol.valor_aprovado = sol.valor
        acao_historico = f"Solicitação ajustada e aprovada automaticamente por regra de alçada (Limite: R$ {limite_alcada:.2f})"
        responsavel_historico = "Sistema (Alçada Automática)"
    else:
        sol.status = "Aprovação pendente"
        acao_historico = "Solicitação ajustada e reenviada para aprovação"
        responsavel_historico = dados.solicitante or "Solicitante"
    
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=sol.id,
        acao=acao_historico,
        responsavel=responsavel_historico
    ))
    db.commit()
    db.refresh(sol)
    return sol

@app.put("/solicitacoes/{solicitacao_id}/status")
def atualizar_status(solicitacao_id: int, dados: schemas.StatusUpdate, db: Session = Depends(get_db)):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    sol.status = dados.status
    if dados.valor_aprovado is not None:
        sol.valor_aprovado = dados.valor_aprovado
    if dados.motivo_ajuste is not None:
        sol.motivo_ajuste = dados.motivo_ajuste
        
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=sol.id,
        acao=f"Status alterado para: {dados.status}",
        responsavel="Controladoria"
    ))
    db.commit()
    db.refresh(sol)
    return sol

@app.put("/solicitacoes/{solicitacao_id}/iniciar-execucao")
def iniciar_execucao(solicitacao_id: int, dados: schemas.IniciarExecucaoUpdate, db: Session = Depends(get_db)):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    sol.status = "Em execução"
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=sol.id,
        acao="Execução da compra iniciada",
        responsavel="Controladoria"
    ))
    db.commit()
    db.refresh(sol)
    return sol

@app.put("/solicitacoes/{solicitacao_id}/finalizar")
def finalizar_solicitacao(solicitacao_id: int, dados: schemas.FinalizarUpdate, db: Session = Depends(get_db)):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    sol.status = "Finalizada"
    sol.valor_realizado = dados.valor_realizado
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=sol.id,
        acao=f"Solicitação finalizada com valor realizado de R$ {dados.valor_realizado:.2f}",
        responsavel="Controladoria"
    ))
    db.commit()
    db.refresh(sol)
    return sol

@app.delete("/solicitacoes/{solicitacao_id}")
def excluir_solicitacao(solicitacao_id: int, db: Session = Depends(get_db)):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    db.query(models.HistoricoSolicitacao).filter(models.HistoricoSolicitacao.solicitacao_id == solicitacao_id).delete()
    db.query(models.Anexo).filter(models.Anexo.solicitacao_id == solicitacao_id).delete()
    db.delete(sol)
    db.commit()
    return {"mensagem": "Solicitação excluída com sucesso."}

# ==========================================
# HISTÓRICO E ANEXOS DE SOLICITAÇÕES
# ==========================================
@app.get("/solicitacoes/{solicitacao_id}/historico")
def obter_historico(solicitacao_id: int, db: Session = Depends(get_db)):
    return db.query(models.HistoricoSolicitacao).filter(models.HistoricoSolicitacao.solicitacao_id == solicitacao_id).order_by(models.HistoricoSolicitacao.id.desc()).all()

@app.get("/solicitacoes/{solicitacao_id}/anexos")
def listar_anexos(solicitacao_id: int, db: Session = Depends(get_db)):
    return db.query(models.Anexo).filter(models.Anexo.solicitacao_id == solicitacao_id).all()

@app.post("/solicitacoes/{solicitacao_id}/anexos")
async def anexar_arquivo(
    solicitacao_id: int,
    tipo: str = Form(...),
    responsavel: str = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    extensao = os.path.splitext(arquivo.filename)[1]
    nome_seguro = f"{uuid.uuid4().hex}{extensao}"
    caminho_completo = os.path.join(UPLOAD_DIR, nome_seguro)
    
    with open(caminho_completo, "wb") as buffer:
        buffer.write(await arquivo.read())
        
    novo_anexo = models.Anexo(
        solicitacao_id=solicitacao_id,
        nome_arquivo=arquivo.filename,
        caminho=caminho_completo,
        tipo=tipo,
        responsavel=responsavel
    )
    db.add(novo_anexo)
    db.add(models.HistoricoSolicitacao(
        solicitacao_id=solicitacao_id,
        acao=f"Anexo adicionado: {arquivo.filename} ({tipo})",
        responsavel=responsavel
    ))
    db.commit()
    db.refresh(novo_anexo)
    return novo_anexo

@app.get("/anexos/{anexo_id}/download")
def baixar_anexo(anexo_id: int, db: Session = Depends(get_db)):
    anexo = db.query(models.Anexo).filter(models.Anexo.id == anexo_id).first()
    if not anexo or not os.path.exists(anexo.caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(anexo.caminho, filename=anexo.nome_arquivo)

# ==========================================
# MÓDULO DE CHECKLIST E RELATÓRIO DE DIVERGÊNCIAS
# ==========================================
@app.get("/checklists")
def listar_checklists(condominio: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        query = db.query(models.ChecklistItem)
        if condominio and condominio != "todos":
            query = query.filter(models.ChecklistItem.condominio == condominio)
        itens = query.order_by(models.ChecklistItem.id.desc()).all()
        
        resultado = []
        for item in itens:
            execucoes = db.query(models.ChecklistExecucao).filter(
                models.ChecklistExecucao.item_id == item.id
            ).order_by(models.ChecklistExecucao.id.desc()).all()
            
            ultima = execucoes[0] if execucoes else None
            
            # Garante compatibilidade caso o atributo ainda não tenha sido populado
            plano_acao = getattr(item, 'plano_acao_padrao', None)
            
            resultado.append({
                "id": item.id,
                "condominio": item.condominio,
                "titulo": item.titulo,
                "descricao_orientacao": item.descricao_orientacao or "",
                "frequencia": item.frequencia,
                "plano_acao_padrao": plano_acao or "",
                "criado_em": item.criado_em,
                "ultima_execucao": {
                    "id": ultima.id,
                    "responsavel": ultima.responsavel,
                    "status_conformidade": ultima.status_conformidade,
                    "observacao": ultima.observacao or "",
                    "nome_foto": ultima.nome_foto,
                    "data_execucao": ultima.data_execucao,
                    "tem_foto": bool(ultima.caminho_foto)
                } if ultima else None,
                "historico_execucoes": [
                    {
                        "id": ex.id,
                        "responsavel": ex.responsavel,
                        "status_conformidade": ex.status_conformidade,
                        "observacao": ex.observacao or "",
                        "nome_foto": ex.nome_foto,
                        "data_execucao": ex.data_execucao,
                        "tem_foto": bool(ex.caminho_foto)
                    } for ex in execucoes
                ]
            })
        return resultado
    except Exception as e:
        return []

@app.post("/checklists")
def criar_item_checklist(dados: schemas.ChecklistItemCreate, db: Session = Depends(get_db)):
    novo = models.ChecklistItem(
        condominio=dados.condominio.strip(),
        titulo=dados.titulo.strip(),
        descricao_orientacao=dados.descricao_orientacao.strip() if dados.descricao_orientacao else None,
        frequencia=dados.frequencia,
        plano_acao_padrao=dados.plano_acao_padrao.strip() if dados.plano_acao_padrao else None
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.delete("/checklists/{item_id}")
def excluir_item_checklist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item de checklist não encontrado.")
    db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.item_id == item_id).delete()
    db.delete(item)
    db.commit()
    return {"mensagem": "Atividade de checklist excluída com sucesso."}

@app.post("/checklists/{item_id}/executar")
async def executar_checklist(
    item_id: int,
    responsavel: str = Form(...),
    status_conformidade: str = Form("Conforme"),
    observacao: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item de checklist não encontrado.")
        
    nome_foto_original = None
    caminho_completo = None
    
    if foto and foto.filename:
        extensao = os.path.splitext(foto.filename)[1]
        nome_seguro = f"chk_{uuid.uuid4().hex}{extensao}"
        caminho_completo = os.path.join(UPLOAD_DIR, nome_seguro)
        with open(caminho_completo, "wb") as buffer:
            buffer.write(await foto.read())
        nome_foto_original = foto.filename
        
    execucao = models.ChecklistExecucao(
        item_id=item_id,
        responsavel=responsavel,
        status_conformidade=status_conformidade,
        observacao=observacao.strip() if observacao else None,
        nome_foto=nome_foto_original,
        caminho_foto=caminho_completo
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)
    return {"mensagem": "Checklist registrado com sucesso!", "id": execucao.id}

@app.get("/checklists/execucoes/{execucao_id}/foto")
def baixar_foto_checklist(execucao_id: int, db: Session = Depends(get_db)):
    ex = db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.id == execucao_id).first()
    if not ex or not ex.caminho_foto or not os.path.exists(ex.caminho_foto):
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return FileResponse(ex.caminho_foto, filename=ex.nome_foto or "evidencia.jpg")

@app.get("/condominios/{condominio_id}/checklist-relatorio-divergencias")
def relatorio_divergencias_checklist(condominio_id: int, db: Session = Depends(get_db)):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")
        
    itens = db.query(models.ChecklistItem).filter(models.ChecklistItem.condominio == cond.nome).all()
    
    divergencias = []
    total_divergencias = 0
    
    for item in itens:
        execucoes_problema = db.query(models.ChecklistExecucao).filter(
            models.ChecklistExecucao.item_id == item.id,
            models.ChecklistExecucao.status_conformidade == "Não Conforme"
        ).order_by(models.ChecklistExecucao.id.desc()).all()
        
        if execucoes_problema:
            ultima_falha = execucoes_problema[0]
            total_divergencias += 1
            plano = getattr(item, 'plano_acao_padrao', None) or "Ação corretiva padrão não definida pela controladoria."
            divergencias.append({
                "atividade": item.titulo,
                "frequencia": item.frequencia,
                "data_ocorrencia": ultima_falha.data_execucao,
                "responsavel": ultima_falha.responsavel,
                "relato": ultima_falha.observacao or "Nenhuma observação descrita.",
                "plano_acao": plano,
                "tem_foto": bool(ultima_falha.caminho_foto)
            })
            
    return {
        "condominio": cond.nome,
        "total_divergencias": total_divergencias,
        "divergencias": divergencias
    }
# ==========================================
# MÓDULO DE EDIÇÃO DE CHECKLIST (PASSO 4)
# ==========================================
@app.put("/checklists/{item_id}")
def editar_item_checklist(item_id: int, dados: schemas.ChecklistItemCreate, db: Session = Depends(get_db)):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item de checklist não encontrado.")
    
    item.condominio = dados.condominio.strip()
    item.titulo = dados.titulo.strip()
    item.descricao_orientacao = dados.descricao_orientacao.strip() if dados.descricao_orientacao else None
    item.frequencia = dados.frequencia
    item.plano_acao_padrao = dados.plano_acao_padrao.strip() if dados.plano_acao_padrao else None

    db.commit()
    db.refresh(item)
    return {"mensagem": "Atividade de checklist atualizada com sucesso!", "item": item}


# ==========================================
# MÓDULO DE GESTÃO DE USUÁRIOS / EQUIPE (PASSO 4)
# ==========================================
@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    email_limpo = dados.email.lower().strip()
    existente = db.query(models.Usuario).filter(models.Usuario.email == email_limpo).first()
    if existente:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado no sistema.")
    
    novo_usuario = models.Usuario(
        nome=dados.nome.strip(),
        email=email_limpo,
        senha=get_password_hash(dados.senha),
        perfil=dados.perfil
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return {"mensagem": "Usuário criado com sucesso!", "id": novo_usuario.id}


@app.put("/usuarios/{usuario_id}/senha")
def trocar_senha_usuario(usuario_id: int, dados: schemas.SenhaUpdate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    usuario.senha = get_password_hash(dados.nova_senha)
    db.commit()
    return {"mensagem": "Senha alterada com sucesso!"}


@app.delete("/usuarios/{usuario_id}")
def excluir_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    db.delete(usuario)
    db.commit()
    return {"mensagem": "Usuário excluído com sucesso."}