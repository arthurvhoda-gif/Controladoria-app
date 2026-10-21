import os
import json
import shutil
import hashlib
import smtplib
import uuid
from datetime import datetime
from typing import Optional, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

import models
import schemas
from database import engine, SessionLocal

# Cria todas as tabelas caso ainda não existam
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Controladoria Haize API")

# Configuração aberta de CORS para evitar bloqueios e erros de "Failed to fetch"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretórios para salvar anexos de solicitações e fotos de vistorias
UPLOAD_DIR = "uploads"
FOTOS_CHECKLIST_DIR = os.path.join(UPLOAD_DIR, "checklists")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FOTOS_CHECKLIST_DIR, exist_ok=True)

# =========================================================================
# CONFIGURAÇÃO DE E-MAILS PARA ENVIO AUTOMÁTICO DO RELATÓRIO DE CHECKLIST
# =========================================================================
EMAILS_DESTINO_RELATORIO = [
    "atendimento@haize.com.br",
    "Igor@armagni.adv.br"
]

# Credenciais da conta que fará o disparo dos e-mails:
SMTP_REMETENTE = os.getenv("SMTP_EMAIL", "atendimento@haize.com.br")
SMTP_SENHA = os.getenv("SMTP_SENHA", "sua_senha_de_app_aqui")
SMTP_SERVIDOR = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORTA = int(os.getenv("SMTP_PORT", "587"))


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
        "ALTER TABLE checklist_itens ADD COLUMN descricao_orientacao TEXT"
    ]
    db = SessionLocal()
    try:
        for cmd in comandos_migracao:
            try:
                db.execute(text(cmd))
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


# =========================================================================
# UTILITÁRIOS DE SENHA E USUÁRIOS PADRÃO
# =========================================================================
def verificar_senha(senha_digitada: str, senha_banco: str) -> bool:
    if not senha_banco:
        return False
    # 1. Comparação direta (texto plano)
    if senha_digitada == senha_banco:
        return True
    # 2. Comparação SHA-256
    hash_sha256 = hashlib.sha256(senha_digitada.encode("utf-8")).hexdigest()
    if hash_sha256 == senha_banco:
        return True
    # 3. Comparação Bcrypt (caso existam senhas antigas criptografadas com passlib/bcrypt)
    try:
        import bcrypt
        if senha_banco.startswith("$2"):
            return bcrypt.checkpw(senha_digitada.encode("utf-8"), senha_banco.encode("utf-8"))
    except Exception:
        pass
    return False


def criar_usuarios_iniciais():
    db = SessionLocal()
    try:
        qtd = db.query(models.Usuario).count()
        if qtd == 0:
            usuarios_padrao = [
                models.Usuario(
                    nome="Controladoria Haize",
                    email="controladoria@haize.com.br",
                    senha="123",
                    perfil="Controladoria"
                ),
                models.Usuario(
                    nome="Solicitante Padrão",
                    email="solicitante@haize.com.br",
                    senha="123",
                    perfil="Solicitante"
                ),
                models.Usuario(
                    nome="Vistoriador Checklist",
                    email="checklist@haize.com.br",
                    senha="123",
                    perfil="Checklist"
                )
            ]
            db.add_all(usuarios_padrao)
            db.commit()
    except Exception as e:
        db.rollback()
        print("Aviso ao verificar usuarios iniciais:", e)
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    executar_migracoes_automaticas()
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

    if not usuario or not verificar_senha(dados.senha, usuario.senha):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    token_simples = hashlib.sha256(f"{usuario.email}-{usuario.id}".encode()).hexdigest()
    return {
        "access_token": token_simples,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil
        }
    }


# =========================================================================
# GESTÃO DE USUÁRIOS
# =========================================================================
@app.get("/usuarios", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).order_by(models.Usuario.nome.asc()).all()


@app.post("/usuarios", response_model=schemas.UsuarioResponse)
def criar_usuario(user: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    email_limpo = user.email.strip().lower()
    existente = db.query(models.Usuario).filter(models.Usuario.email == email_limpo).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe um usuário com este e-mail.")

    novo = models.Usuario(
        nome=user.nome.strip(),
        email=email_limpo,
        senha=user.senha,
        perfil=user.perfil or "Solicitante"
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@app.put("/usuarios/{usuario_id}/senha")
def alterar_senha_usuario(usuario_id: int, dados: schemas.SenhaUpdate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    usuario.senha = dados.nova_senha
    db.commit()
    return {"mensagem": "Senha atualizada com sucesso."}


@app.delete("/usuarios/{usuario_id}")
def excluir_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    db.delete(usuario)
    db.commit()
    return {"mensagem": "Usuário removido com sucesso."}


# =========================================================================
# CONDOMÍNIOS, UNIDADES E RATEIO POR FRAÇÃO IDEAL
# =========================================================================
@app.get("/condominios", response_model=List[schemas.CondominioResponse])
def listar_condominios(db: Session = Depends(get_db)):
    return db.query(models.Condominio).order_by(models.Condominio.nome.asc()).all()


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
def listar_solicitacoes(db: Session = Depends(get_db)):
    return db.query(models.Solicitacao).order_by(models.Solicitacao.id.desc()).all()


@app.post("/solicitacoes")
def criar_solicitacao(sol: schemas.SolicitacaoCreate, db: Session = Depends(get_db)):
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
        solicitante=sol.solicitante or "Usuário",
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
    registrar_historico_seguro(db, nova_sol.id, acao_txt, sol.solicitante or "Sistema")

    return nova_sol


@app.put("/solicitacoes/{solicitacao_id}")
def atualizar_solicitacao(solicitacao_id: int, sol: schemas.SolicitacaoCreate, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

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
        sol.solicitante or db_sol.solicitante
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
def iniciar_execucao_solicitacao(solicitacao_id: int, dados: schemas.IniciarExecucaoUpdate, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    db_sol.status = "Em execução"
    db.commit()
    db.refresh(db_sol)

    registrar_historico_seguro(db, db_sol.id, "Solicitação enviada para execução", "Controladoria")
    return db_sol


@app.put("/solicitacoes/{solicitacao_id}/finalizar")
def finalizar_solicitacao(solicitacao_id: int, dados: schemas.FinalizarUpdate, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    db_sol.status = "Finalizada"
    db_sol.valor_realizado = float(dados.valor_realizado or 0.0)
    db.commit()
    db.refresh(db_sol)

    registrar_historico_seguro(
        db,
        db_sol.id,
        f"Solicitação finalizada (Valor Realizado: R$ {db_sol.valor_realizado:.2f})",
        "Controladoria"
    )
    return db_sol


@app.delete("/solicitacoes/{solicitacao_id}")
def excluir_solicitacao(solicitacao_id: int, db: Session = Depends(get_db)):
    db_sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not db_sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    db.query(models.HistoricoSolicitacao).filter(models.HistoricoSolicitacao.solicitacao_id == solicitacao_id).delete()
    anexos = db.query(models.Anexo).filter(models.Anexo.solicitacao_id == solicitacao_id).all()
    for a in anexos:
        if a.caminho and os.path.exists(a.caminho):
            try:
                os.remove(a.caminho)
            except Exception:
                pass
    db.query(models.Anexo).filter(models.Anexo.solicitacao_id == solicitacao_id).delete()

    db.delete(db_sol)
    db.commit()
    return {"mensagem": "Solicitação excluída com sucesso."}


@app.get("/solicitacoes/{solicitacao_id}/historico")
def listar_historico_solicitacao(solicitacao_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.HistoricoSolicitacao)
        .filter(models.HistoricoSolicitacao.solicitacao_id == solicitacao_id)
        .order_by(models.HistoricoSolicitacao.id.desc())
        .all()
    )


@app.get("/solicitacoes/{solicitacao_id}/anexos")
def listar_anexos_solicitacao(solicitacao_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Anexo)
        .filter(models.Anexo.solicitacao_id == solicitacao_id)
        .order_by(models.Anexo.id.desc())
        .all()
    )


@app.post("/solicitacoes/{solicitacao_id}/anexos")
def upload_anexo_solicitacao(
    solicitacao_id: int,
    arquivo: UploadFile = File(...),
    tipo: str = Form("Orçamento"),
    responsavel: str = Form("Usuário"),
    db: Session = Depends(get_db)
):
    sol = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    nome_seguro = f"{solicitacao_id}_{uuid.uuid4().hex[:8]}_{arquivo.filename}"
    caminho_completo = os.path.join(UPLOAD_DIR, nome_seguro)

    with open(caminho_completo, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    novo_anexo = models.Anexo(
        solicitacao_id=solicitacao_id,
        nome_arquivo=arquivo.filename,
        caminho=caminho_completo,
        tipo=tipo,
        responsavel=responsavel
    )
    db.add(novo_anexo)
    db.commit()
    db.refresh(novo_anexo)

    registrar_historico_seguro(
        db,
        solicitacao_id,
        f"Arquivo anexado ({tipo}): {arquivo.filename}",
        responsavel
    )
    return novo_anexo


@app.get("/anexos/{anexo_id}/download")
def download_anexo(anexo_id: int, db: Session = Depends(get_db)):
    anexo = db.query(models.Anexo).filter(models.Anexo.id == anexo_id).first()
    if not anexo or not os.path.exists(anexo.caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor.")
    return FileResponse(anexo.caminho, filename=anexo.nome_arquivo)


# =========================================================================
# CHECKLIST OPERACIONAL, VISTORIAS E ENVIO AUTOMÁTICO DE RELATÓRIO POR E-MAIL
# =========================================================================
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
        "titulo": item.titulo,
        "descricao_orientacao": item.descricao_orientacao,
        "frequencia": item.frequencia,
        "plano_acao_padrao": item.plano_acao_padrao,
        "criado_em": item.criado_em,
        "ultima_execucao": historico[0] if historico else None,
        "historico_execucoes": historico
    }


@app.get("/checklists")
def listar_checklists(db: Session = Depends(get_db)):
    itens = db.query(models.ChecklistItem).order_by(models.ChecklistItem.id.desc()).all()
    return [formatar_item_checklist(db, item) for item in itens]


@app.post("/checklists")
def criar_checklist(item: schemas.ChecklistItemCreate, db: Session = Depends(get_db)):
    novo = models.ChecklistItem(
        condominio=item.condominio,
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

    item.condominio = dados.condominio
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
    responsavel: str = Form(...),
    status_conformidade: str = Form("Conforme"),
    observacao: Optional[str] = Form(""),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    item = db.query(models.ChecklistItem).filter(models.ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item de checklist não encontrado.")

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
        responsavel=responsavel,
        status_conformidade=status_conformidade,
        observacao=observacao,
        nome_foto=nome_foto,
        caminho_foto=caminho_foto
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)
    return formatar_item_checklist(db, item)


@app.get("/checklists/execucoes/{execucao_id}/foto")
def ver_foto_execucao(execucao_id: int, db: Session = Depends(get_db)):
    ex = db.query(models.ChecklistExecucao).filter(models.ChecklistExecucao.id == execucao_id).first()
    if not ex or not ex.caminho_foto or not os.path.exists(ex.caminho_foto):
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return FileResponse(ex.caminho_foto)


def enviar_relatorio_por_email_bg(dados_relatorio: dict):
    """Envia o relatório de divergências automaticamente para atendimento@haize.com.br e Igor@armagni.adv.br."""
    try:
        if not SMTP_SENHA or SMTP_SENHA == "sua_senha_de_app_aqui":
            print("Aviso: Configure SMTP_EMAIL e SMTP_SENHA para envio real de e-mails.")
            return

        linhas_html = ""
        if not dados_relatorio["divergencias"]:
            linhas_html = """
            <tr>
                <td colspan="3" style="padding:16px; text-align:center; color:#059669; font-weight:bold; background:#f0fdf4;">
                    ✓ Nenhuma irregularidade identificada. Todas as vistorias estão em conformidade.
                </td>
            </tr>
            """
        else:
            for d in dados_relatorio["divergencias"]:
                linhas_html += f"""
                <tr>
                    <td style="padding:10px; border:1px solid #cbd5e1;">
                        <strong>{d['atividade']}</strong><br>
                        <small style="color:#64748b;">Frequência: {d['frequencia']} | Data: {d['data_ocorrencia']} | Vistoriador: {d['responsavel']}</small>
                    </td>
                    <td style="padding:10px; border:1px solid #cbd5e1; color:#b91c1c;">{d['relato']}</td>
                    <td style="padding:10px; border:1px solid #cbd5e1; background:#fffbeb; color:#92400e; font-weight:bold;">{d['plano_acao']}</td>
                </tr>
                """

        corpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #0f172a;">
            <h2 style="margin-bottom:4px;">HAIZE SÍNDICO PROFISSIONAL</h2>
            <p style="margin-top:0; color:#475569;">Relatório Automático de Divergências de Vistoria</p>
            <p><strong>Condomínio:</strong> {dados_relatorio['condominio']} | <strong>Total de Divergências:</strong> {dados_relatorio['total_divergencias']}</p>
            <table style="width:100%; border-collapse:collapse; margin-top:12px;">
                <thead>
                    <tr style="background:#0f172a; color:#ffffff;">
                        <th style="padding:10px; text-align:left; border:1px solid #0f172a;">Item Vistoriado</th>
                        <th style="padding:10px; text-align:left; border:1px solid #0f172a;">Não Conformidade</th>
                        <th style="padding:10px; text-align:left; border:1px solid #0f172a;">Plano de Ação</th>
                    </tr>
                </thead>
                <tbody>{linhas_html}</tbody>
            </table>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Relatório de Divergências (Checklist) - {dados_relatorio['condominio']}"
        msg["From"] = SMTP_REMETENTE
        msg["To"] = ", ".join(EMAILS_DESTINO_RELATORIO)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA) as server:
            server.starttls()
            server.login(SMTP_REMETENTE, SMTP_SENHA)
            server.sendmail(SMTP_REMETENTE, EMAILS_DESTINO_RELATORIO, msg.as_string())
    except Exception as e:
        print("Erro ao enviar e-mail do relatorio:", e)


@app.get("/condominios/{condominio_id}/checklist-relatorio-divergencias")
def relatorio_divergencias_checklist(
    condominio_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    cond = db.query(models.Condominio).filter(models.Condominio.id == condominio_id).first()
    if not cond:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado.")

    itens = db.query(models.ChecklistItem).filter(models.ChecklistItem.condominio == cond.nome).all()
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
                "tem_foto": bool(ultima.caminho_foto)
            })

    resultado = {
        "condominio": cond.nome,
        "total_divergencias": len(divergencias),
        "divergencias": divergencias,
        "emails_notificados": EMAILS_DESTINO_RELATORIO
    }

    background_tasks.add_task(enviar_relatorio_por_email_bg, resultado)
    return resultado