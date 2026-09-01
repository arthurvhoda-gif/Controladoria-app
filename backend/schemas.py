from pydantic import BaseModel
from typing import Optional, List

# ==========================================
# USUÁRIOS E AUTENTICAÇÃO
# ==========================================
class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str

class UsuarioLogin(BaseModel):
    email: str
    senha: str

class Token(BaseModel):
    access_token: str
    token_type: str
    usuario: dict

class TokenData(BaseModel):
    email: Optional[str] = None

# ==========================================
# CONDOMÍNIOS, FORNECEDORES E CATEGORIAS
# ==========================================
class CondominioCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    codigo: Optional[str] = None

class FornecedorCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    categoria: Optional[str] = None

class LimiteCategoria(BaseModel):
    condominio: str
    limite: float

class CategoriaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    limites: Optional[List[LimiteCategoria]] = []

# ==========================================
# SOLICITAÇÕES DE COMPRA
# ==========================================
class SolicitacaoCompraCreate(BaseModel):
    solicitante: str
    condominio: str
    descricao: str
    categoria: Optional[str] = None
    fornecedor: Optional[str] = None
    valor_servico: float = 0.0
    valor_produto: float = 0.0
    observacao: Optional[str] = None
    prioridade: Optional[str] = "Normal"

# ==========================================
# AÇÕES DE STATUS
# ==========================================
class AtualizarStatus(BaseModel):
    status: str
    valor_aprovado: Optional[float] = None
    motivo_ajuste: Optional[str] = None

class IniciarExecucao(BaseModel):
    observacao_execucao: Optional[str] = None

class FinalizarCompra(BaseModel):
    valor_realizado: float
    observacao_execucao: Optional[str] = None