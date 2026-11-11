# -*- coding: utf-8 -*-
"""V7.7 — proposta de tabelas para custos históricos (NÃO ATIVADA).

Importar este módulo registra tabelas no metadata SQLAlchemy apenas.
A API de produção não importa o módulo e nenhuma migração é executada.
A criação de tabelas só é permitida em testes SQLite descartáveis nesta etapa.
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Date, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from database import Base


class CustoImportacaoLoteV77(Base):
    __tablename__ = "custos_historicos_lotes_v77"

    id = Column(Integer, primary_key=True)
    origem = Column(String(32), nullable=False)
    arquivo_sha256 = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="planejado")
    qtd_registros = Column(Integer, nullable=False)
    total_centavos = Column(BigInteger, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("qtd_registros >= 0", name="ck_custos_v77_qtd_nao_negativa"),
    )


class CustoHistoricoV77(Base):
    __tablename__ = "custos_historicos_v77"
    __table_args__ = (
        UniqueConstraint(
            "condominio_id", "origem", "id_origem",
            name="uq_custos_v77_condominio_origem_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    condominio_id = Column(
        Integer, ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    origem = Column(String(32), nullable=False)
    id_origem = Column(String(180), nullable=False)
    data_original = Column(Date, nullable=False)
    competencia = Column(Date, nullable=False, index=True)
    descricao = Column(Text, nullable=False)
    categoria_original = Column(String(180), nullable=False)
    categoria_chave = Column(String(180), nullable=False)
    valor_centavos = Column(BigInteger, nullable=False)
    hash_conteudo = Column(String(64), nullable=False)
    lote_primeira_entrada_id = Column(
        Integer, ForeignKey("custos_historicos_lotes_v77.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lote_ultima_atualizacao_id = Column(
        Integer, ForeignKey("custos_historicos_lotes_v77.id", ondelete="RESTRICT"),
        nullable=False,
    )
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CustoHistoricoEventoV77(Base):
    """Trilha append-only planejada. Não é usada para gravações nesta fase."""
    __tablename__ = "custos_historicos_eventos_v77"

    id = Column(Integer, primary_key=True)
    custo_historico_id = Column(
        Integer, ForeignKey("custos_historicos_v77.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    lote_id = Column(
        Integer, ForeignKey("custos_historicos_lotes_v77.id", ondelete="RESTRICT"),
        nullable=False,
    )
    acao = Column(String(32), nullable=False)
    hash_anterior = Column(String(64), nullable=True)
    hash_novo = Column(String(64), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
