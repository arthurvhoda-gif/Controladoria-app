# -*- coding: utf-8 -*-
"""API de consulta do painel de Inteligência de Custos.

Exclusivamente leitura sobre custos_lancamentos; acesso bloqueado por padrão
pelo middleware de autorização da aplicação (somente Controladoria).
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from custos_api import LancamentoCusto, sessao

router = APIRouter(prefix="/custos", tags=["Inteligência de Custos"])


def _valor(valor):
    return str(valor if valor is not None else Decimal("0.00"))


@router.get("/painel")
def painel(
    condominio: Optional[str] = Query(default=None, max_length=180),
    categoria: Optional[str] = Query(default=None, max_length=180),
    inicio: Optional[date] = None,
    fim: Optional[date] = None,
    db: Session = Depends(sessao),
):
    """Sumários financeiros filtráveis; não expõe dados a perfis não autorizados."""
    if inicio and fim and inicio > fim:
        raise HTTPException(status_code=422, detail="A data inicial deve anteceder a data final.")

    base = db.query(LancamentoCusto).filter(LancamentoCusto.ativo.is_(True))
    if condominio:
        base = base.filter(LancamentoCusto.condominio == condominio)
    if categoria:
        base = base.filter(LancamentoCusto.categoria == categoria)
    if inicio:
        base = base.filter(LancamentoCusto.competencia >= inicio)
    if fim:
        base = base.filter(LancamentoCusto.competencia <= fim)

    total_registros, total_valor, total_condominios = (
        base.with_entities(
            func.count(LancamentoCusto.id),
            func.coalesce(func.sum(LancamentoCusto.valor), 0),
            func.count(func.distinct(LancamentoCusto.condominio)),
        ).one()
    )

    por_condominio = (
        base.with_entities(
            LancamentoCusto.condominio,
            func.count(LancamentoCusto.id),
            func.coalesce(func.sum(LancamentoCusto.valor), 0),
        )
        .group_by(LancamentoCusto.condominio)
        .order_by(func.sum(LancamentoCusto.valor).desc())
        .all()
    )

    por_categoria = (
        base.with_entities(
            LancamentoCusto.categoria,
            func.count(LancamentoCusto.id),
            func.coalesce(func.sum(LancamentoCusto.valor), 0),
        )
        .group_by(LancamentoCusto.categoria)
        .order_by(func.sum(LancamentoCusto.valor).desc())
        .all()
    )

    # Usamos uma expressão compatível com PostgreSQL (Neon).
    mes_expr = func.date_trunc("month", LancamentoCusto.competencia)
    por_mes = (
        base.with_entities(
            mes_expr.label("mes"),
            func.count(LancamentoCusto.id),
            func.coalesce(func.sum(LancamentoCusto.valor), 0),
        )
        .group_by(mes_expr)
        .order_by(mes_expr)
        .all()
    )

    # Opções de filtro vêm da base completa, não dos resultados filtrados.
    condominio_opcoes = [row[0] for row in (
        db.query(LancamentoCusto.condominio)
        .filter(LancamentoCusto.ativo.is_(True))
        .distinct().order_by(LancamentoCusto.condominio).all()
    )]
    categoria_opcoes = [row[0] for row in (
        db.query(LancamentoCusto.categoria)
        .filter(LancamentoCusto.ativo.is_(True))
        .distinct().order_by(LancamentoCusto.categoria).all()
    )]

    return {
        "filtros": {
            "condominio": condominio,
            "categoria": categoria,
            "inicio": inicio.isoformat() if inicio else None,
            "fim": fim.isoformat() if fim else None,
        },
        "opcoes": {"condominios": condominio_opcoes, "categorias": categoria_opcoes},
        "indicadores": {
            "condominios": total_condominios,
            "lancamentos": total_registros,
            "valor_total": _valor(total_valor),
        },
        "por_condominio": [
            {"nome": nome, "lancamentos": qtd, "valor_total": _valor(valor)}
            for nome, qtd, valor in por_condominio
        ],
        "por_categoria": [
            {"nome": nome, "lancamentos": qtd, "valor_total": _valor(valor)}
            for nome, qtd, valor in por_categoria
        ],
        "por_mes": [
            {"mes": mes.strftime("%Y-%m"), "lancamentos": qtd, "valor_total": _valor(valor)}
            for mes, qtd, valor in por_mes
        ],
    }
