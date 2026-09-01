from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from database import Base
from datetime import datetime

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    senha = Column(String)
    perfil = Column(String)

class Condominio(Base):
    __tablename__ = "condominios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    cnpj = Column(String, nullable=True)
    codigo = Column(String, nullable=True)

class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    cnpj = Column(String, nullable=True)
    categoria = Column(String, nullable=True)

class Categoria(Base):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    descricao = Column(String, nullable=True)

# TABELA NOVA DE REGRAS DE APROVAÇÃO
class LimiteCategoriaCondominio(Base):
    __tablename__ = "limites_categoria_condominio"
    id = Column(Integer, primary_key=True, index=True)
    categoria_nome = Column(String, index=True)
    condominio_nome = Column(String, index=True)
    limite = Column(Float, default=0.0)

class SolicitacaoCompra(Base):
    __tablename__ = "solicitacoes_compra"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True)
    solicitante = Column(String)
    condominio = Column(String)
    categoria = Column(String, nullable=True)
    descricao = Column(String)
    fornecedor = Column(String, nullable=True)
    
    valor_servico = Column(Float, default=0.0)
    valor_produto = Column(Float, default=0.0)
    valor = Column(Float)
    
    observacao = Column(String, nullable=True)
    
    valor_aprovado = Column(Float, nullable=True)
    tipo_aprovacao = Column(String, nullable=True)
    
    valor_realizado = Column(Float, nullable=True)
    data_inicio_execucao = Column(DateTime, nullable=True)
    data_finalizacao = Column(DateTime, nullable=True)
    observacao_execucao = Column(String, nullable=True)
    
    prioridade = Column(String)
    status = Column(String, default="Pendente")
    motivo_ajuste = Column(String, nullable=True)
    data = Column(DateTime)

class HistoricoSolicitacao(Base):
    __tablename__ = "historico_solicitacoes"
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey('solicitacoes_compra.id'))
    data = Column(DateTime)
    acao = Column(String)
    status_anterior = Column(String, nullable=True)
    status_novo = Column(String, nullable=True)
    responsavel = Column(String)
    descricao = Column(String, nullable=True)
    valor_anterior = Column(Float, nullable=True)
    valor_novo = Column(Float, nullable=True)
    observacao = Column(String, nullable=True)

class Anexo(Base):
    __tablename__ = "anexos"
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey('solicitacoes_compra.id'))
    nome_arquivo = Column(String)
    caminho_arquivo = Column(String)
    tipo = Column(String)
    data_upload = Column(DateTime, default=datetime.now)