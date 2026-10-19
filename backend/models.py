from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, default="Solicitante")  # "Controladoria", "Solicitante" ou "Checklist"

class Condominio(Base):
    __tablename__ = "condominios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    cnpj = Column(String, nullable=True)
    codigo = Column(String, nullable=True)
    unidades = relationship("Unidade", back_populates="condominio", cascade="all, delete-orphan")

class Unidade(Base):
    __tablename__ = "unidades"
    id = Column(Integer, primary_key=True, index=True)
    condominio_id = Column(Integer, ForeignKey("condominios.id"), nullable=False)
    identificacao = Column(String, nullable=False)
    fracao_ideal = Column(Float, default=0.0)
    condominio = relationship("Condominio", back_populates="unidades")

class Categoria(Base):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    descricao = Column(String, nullable=True)
    limites = Column(Text, nullable=True)

class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    cnpj = Column(String, nullable=True)
    categoria = Column(String, nullable=True)

class Solicitacao(Base):
    __tablename__ = "solicitacoes"
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True)
    condominio = Column(String, nullable=False)
    condominio_id = Column(Integer, ForeignKey("condominios.id"), nullable=True)
    categoria = Column(String, nullable=False)
    fornecedor = Column(String, nullable=False)
    descricao = Column(Text, nullable=False)
    valor_servico = Column(Float, default=0.0)
    valor_produto = Column(Float, default=0.0)
    valor = Column(Float, default=0.0)
    valor_aprovado = Column(Float, default=0.0)
    valor_realizado = Column(Float, default=0.0)
    solicitante = Column(String, nullable=False)
    status = Column(String, default="Aprovação pendente")
    motivo_ajuste = Column(Text, nullable=True)
    observacao = Column(Text, nullable=True)
    data = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

class HistoricoSolicitacao(Base):
    __tablename__ = "historico_solicitacoes"
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey("solicitacoes.id"), nullable=False)
    acao = Column(String, nullable=False)
    responsavel = Column(String, nullable=False)
    data = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

class Anexo(Base):
    __tablename__ = "anexos"
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey("solicitacoes.id"), nullable=False)
    nome_arquivo = Column(String, nullable=False)
    caminho = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    responsavel = Column(String, nullable=False)
    data_upload = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ==========================================
# MÓDULO DE CHECKLIST E VISTORIAS
# ==========================================
class ChecklistItem(Base):
    __tablename__ = "checklist_itens"
    id = Column(Integer, primary_key=True, index=True)
    condominio = Column(String, nullable=False)
    titulo = Column(String, nullable=False)
    descricao_orientacao = Column(Text, nullable=True)
    frequencia = Column(String, nullable=False)  # Diária, Semanal, Quinzenal, Mensal
    criado_em = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

class ChecklistExecucao(Base):
    __tablename__ = "checklist_execucoes"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("checklist_itens.id"), nullable=False)
    responsavel = Column(String, nullable=False)
    status_conformidade = Column(String, default="Conforme")  # "Conforme" ou "Não Conforme"
    observacao = Column(Text, nullable=True)
    nome_foto = Column(String, nullable=True)
    caminho_foto = Column(String, nullable=True)
    data_execucao = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Aliases de compatibilidade
UsuarioDB = Usuario
CondominioDB = Condominio
UnidadeDB = Unidade
CategoriaDB = Categoria
FornecedorDB = Fornecedor
SolicitacaoDB = Solicitacao
ChecklistItemDB = ChecklistItem
ChecklistExecucaoDB = ChecklistExecucao