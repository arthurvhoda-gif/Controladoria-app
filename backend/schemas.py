from pydantic import BaseModel
from typing import Optional, List, Any

class LoginRequest(BaseModel):
    email: str
    senha: str

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str = "Solicitante"

class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    class Config:
        from_attributes = True

class UnidadeCreate(BaseModel):
    identificacao: str
    fracao_ideal: float

class UnidadeResponse(UnidadeCreate):
    id: int
    condominio_id: int
    class Config:
        from_attributes = True

class CondominioCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    codigo: Optional[str] = None

class CondominioResponse(CondominioCreate):
    id: int
    class Config:
        from_attributes = True

class CategoriaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    limites: Optional[Any] = None

class CategoriaResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = None
    limites: Optional[Any] = None
    class Config:
        from_attributes = True

class FornecedorCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    categoria: Optional[str] = None

class FornecedorResponse(FornecedorCreate):
    id: int
    class Config:
        from_attributes = True

class SolicitacaoCreate(BaseModel):
    condominio: str
    condominio_id: Optional[int] = None
    categoria: str
    fornecedor: str
    descricao: str
    valor_servico: Optional[float] = 0.0
    valor_produto: Optional[float] = 0.0
    observacao: Optional[str] = None
    solicitante: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
    valor_aprovado: Optional[float] = None
    motivo_ajuste: Optional[str] = None

class FinalizarUpdate(BaseModel):
    valor_realizado: float

class IniciarExecucaoUpdate(BaseModel):
    observacao_execucao: Optional[str] = ""