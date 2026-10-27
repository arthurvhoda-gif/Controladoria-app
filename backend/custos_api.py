# -*- coding: utf-8 -*-
"""API isolada da Inteligência de Custos da Haize (etapa 2, piloto).

Somente a sincronização protegida por COST_SYNC_SECRET pode gravar dados.
Consultas de resumo exigem sessão Controladoria (middleware do main.py).
Nunca altera tabelas de solicitações, checklists ou usuários.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import declarative_base, Session

from database import SessionLocal

CostBase = declarative_base()
router = APIRouter(prefix="/custos", tags=["Inteligência de Custos"])


class LancamentoCusto(CostBase):
    __tablename__ = "custos_lancamentos"
    __table_args__ = (UniqueConstraint("arquivo_origem", "id_origem", name="uq_custos_arquivo_id"),)
    id = Column(Integer, primary_key=True)
    arquivo_origem = Column(String(180), nullable=False, index=True)
    condominio = Column(String(180), nullable=False, index=True)
    id_origem = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=False)
    competencia = Column(Date, nullable=False, index=True)
    categoria = Column(String(180), nullable=False, index=True)
    valor = Column(Numeric(16, 2), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True, index=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=False)


class PrazoCusto(CostBase):
    __tablename__ = "custos_prazos"
    __table_args__ = (UniqueConstraint("arquivo_origem", "chave_manutencao", name="uq_custos_prazo"),)
    id = Column(Integer, primary_key=True)
    arquivo_origem = Column(String(180), nullable=False, index=True)
    condominio = Column(String(180), nullable=False)
    chave_manutencao = Column(String(180), nullable=False)
    manutencao = Column(String(180), nullable=False)
    periodicidade = Column(String(100), nullable=True)
    ultima = Column(Date, nullable=True)
    proxima = Column(Date, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=False)


class EstadoSincronizacao(CostBase):
    __tablename__ = "custos_sincronizacoes"
    arquivo_origem = Column(String(180), primary_key=True)
    condominio = Column(String(180), nullable=False)
    total_lancamentos = Column(Integer, nullable=False)
    atualizado_em = Column(DateTime(timezone=True), nullable=False)


def criar_tabelas_custos(engine):
    """Só cria tabelas novas, sem DDL sobre as tabelas atuais do aplicativo."""
    CostBase.metadata.create_all(bind=engine)


def sessao():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Despesa(BaseModel):
    id_origem: str = Field(min_length=1, max_length=100)
    descricao: str = Field(min_length=1, max_length=1500)
    competencia: date
    categoria: str = Field(min_length=1, max_length=180)
    valor: Decimal


class Manutencao(BaseModel):
    chave: str = Field(min_length=1, max_length=180)
    nome: str = Field(min_length=1, max_length=180)
    periodicidade: Optional[str] = Field(default=None, max_length=100)
    ultima: Optional[date] = None
    proxima: Optional[date] = None


class Snapshot(BaseModel):
    arquivo: str = Field(min_length=5, max_length=180)
    condominio: str = Field(min_length=2, max_length=180)
    lancamentos: List[Despesa] = Field(min_length=1, max_length=20000)
    manutencoes: List[Manutencao] = Field(default_factory=list, max_length=100)


def conferir_payload(dados: Snapshot):
    if not re.fullmatch(r"[^/\\<>:|?*]+\.xlsm", dados.arquivo, flags=re.IGNORECASE):
        raise HTTPException(422, "Nome do arquivo XLSM inválido.")
    if dados.arquivo.casefold() in ("modelo.xlsm", "base_dados_geral.xlsm"):
        raise HTTPException(422, "Arquivo de modelo/base não pode ser sincronizado.")
    ids = [d.id_origem.strip() for d in dados.lancamentos]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "IDs de lançamentos repetidos na planilha.")
    if any(d.valor.is_nan() or d.valor.is_infinite() or d.valor.as_tuple().exponent < -2
           for d in dados.lancamentos):
        raise HTTPException(422, "Valor monetário inválido (use centavos).")
    if any(not d.categoria.strip() or d.categoria.strip().casefold() in ('não classificado', 'nao classificado')
           for d in dados.lancamentos):
        raise HTTPException(422, "A carga deve conter somente despesas classificadas.")
    chaves = [p.chave for p in dados.manutencoes]
    if len(chaves) != len(set(chaves)):
        raise HTTPException(422, "Manutenções repetidas na mesma planilha.")


def aplicar_snapshot(db: Session, dados: Snapshot):
    """Importação transacional; mesma planilha duas vezes não gera duplicidade."""
    conferir_payload(dados)
    agora = datetime.now(timezone.utc)
    atuais = {r.id_origem: r for r in db.query(LancamentoCusto).filter_by(arquivo_origem=dados.arquivo).all()}
    novos_ids = {p.id_origem for p in dados.lancamentos}
    ausentes = set(atuais) - novos_ids
    # Proteção contra leituras parciais/arquivos corrompidos.
    if len(atuais) >= 5 and len(ausentes) > max(5, int(len(atuais) * 0.25)):
        raise HTTPException(409, f"Carga bloqueada: {len(ausentes)} lançamentos sumiriam. Confira a planilha antes de reenviar.")
    criados = alterados = desativados = 0
    for l in dados.lancamentos:
        existente = atuais.get(l.id_origem)
        if existente is None:
            db.add(LancamentoCusto(
                arquivo_origem=dados.arquivo, condominio=dados.condominio,
                id_origem=l.id_origem, descricao=l.descricao, competencia=l.competencia,
                categoria=l.categoria, valor=l.valor, ativo=True, atualizado_em=agora))
            criados += 1
        else:
            antes = (existente.condominio, existente.descricao, existente.competencia,
                     existente.categoria, existente.valor, existente.ativo)
            depois = (dados.condominio, l.descricao, l.competencia, l.categoria, l.valor, True)
            if antes != depois:
                (existente.condominio, existente.descricao, existente.competencia,
                 existente.categoria, existente.valor, existente.ativo) = depois
                existente.atualizado_em = agora
                alterados += 1
    for uid in ausentes:
        if atuais[uid].ativo:
            atuais[uid].ativo = False  # preserva histórico
            atuais[uid].atualizado_em = agora
            desativados += 1

    prazos = {p.chave_manutencao: p for p in db.query(PrazoCusto).filter_by(arquivo_origem=dados.arquivo).all()}
    chaves_prazo = {p.chave for p in dados.manutencoes}
    for m in dados.manutencoes:
        p = prazos.get(m.chave)
        if p is None:
            db.add(PrazoCusto(arquivo_origem=dados.arquivo, condominio=dados.condominio,
                              chave_manutencao=m.chave, manutencao=m.nome,
                              periodicidade=m.periodicidade, ultima=m.ultima,
                              proxima=m.proxima, ativo=True, atualizado_em=agora))
        else:
            (p.condominio, p.manutencao, p.periodicidade, p.ultima,
             p.proxima, p.ativo, p.atualizado_em) = (
                dados.condominio, m.nome, m.periodicidade, m.ultima,
                m.proxima, True, agora)
    for chave, prazo in prazos.items():
        if chave not in chaves_prazo:
            prazo.ativo = False
            prazo.atualizado_em = agora

    estado = db.get(EstadoSincronizacao, dados.arquivo)
    if estado is None:
        db.add(EstadoSincronizacao(arquivo_origem=dados.arquivo, condominio=dados.condominio,
                                  total_lancamentos=len(dados.lancamentos), atualizado_em=agora))
    else:
        estado.condominio = dados.condominio
        estado.total_lancamentos = len(dados.lancamentos)
        estado.atualizado_em = agora
    db.commit()
    return {"status": "ok", "condominio": dados.condominio,
            "recebidos": len(dados.lancamentos), "novos": criados,
            "atualizados": alterados, "desativados": desativados}


@router.post("/sincronizar")
def sincronizar(dados: Snapshot, db: Session = Depends(sessao)):
    # Validação de COST_SYNC_SECRET é realizada antes no middleware de main.py.
    try:
        return aplicar_snapshot(db, dados)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get("/resumo")
def resumo(db: Session = Depends(sessao)):
    """Usado futuramente pelos painéis. Acesso exclusivamente Controladoria."""
    totais = (db.query(LancamentoCusto.condominio,
                       func.count(LancamentoCusto.id), func.sum(LancamentoCusto.valor))
              .filter(LancamentoCusto.ativo.is_(True))
              .group_by(LancamentoCusto.condominio)
              .order_by(LancamentoCusto.condominio).all())
    estados = {s.condominio: s.atualizado_em for s in db.query(EstadoSincronizacao).all()}
    return {"condominios": [
        {"nome": nome, "quantidade": qtd, "valor_total": str(soma or Decimal('0.00')),
         "ultima_sincronizacao": estados[nome].isoformat() if nome in estados else None}
        for nome, qtd, soma in totais]}
