# -*- coding: utf-8 -*-
"""Central Financeira V6.8: escrituração auditável; sem disparos externos.

Pagamentos e estornos são NOVOS lançamentos, nunca edições ou exclusões.
O livro usa centavos inteiros. Autorização refeita no servidor em toda rota.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import BytesIO
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

import models
from database import SessionLocal

router = APIRouter(prefix='/financeiro', tags=['Central Financeira'])
MAX_COMPROVANTE = 5 * 1024 * 1024
STATUS_PAGAVEIS = frozenset(('Aprovada', 'Em execução', 'Finalizada'))


def sessao():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def usuario_financeiro(request: Request, db: Session, *, so_controladoria=False):
    uid = getattr(request.state, 'auth_user_id', None)
    user = db.get(models.Usuario, uid) if uid else None
    permitidos = ('Controladoria',) if so_controladoria else ('Controladoria', 'Financeiro')
    if user is None or user.perfil not in permitidos:
        raise HTTPException(status_code=403, detail='Acesso restrito à Central Financeira.')
    return user


def centavos(valor):
    """Conversão estrita: não aceitar floats binários, expoentes ou 3ª casa."""
    if not isinstance(valor, str) or not re.fullmatch(r'(?:0|[1-9]\d{0,11})(?:\.\d{1,2})?', valor):
        raise HTTPException(status_code=422, detail='Informe o valor com até duas casas decimais, usando ponto.')
    try:
        n = Decimal(valor)
    except InvalidOperation:
        raise HTTPException(status_code=422, detail='Valor monetário inválido.')
    r = int(n * 100)
    if r <= 0 or r > 99_999_999_999_999:
        raise HTTPException(status_code=422, detail='Valor deve ser positivo e dentro do limite permitido.')
    return r


def valor_herdado_centavos(valor):
    """Campos Float legados são aproximados; nunca os tratar como valor pago."""
    try:
        d = Decimal(str(valor or 0))
        if not d.is_finite() or d < 0:
            return None
        return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, OverflowError):
        return None


def chave_validada(valor):
    try:
        u = UUID(str(valor))
        if u.version != 4:
            raise ValueError('UUID v4 exigido')
        return str(u)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422, detail='Chave de operação inválida (UUID v4).')


def resumo_lancamentos(db: Session, ids):
    ids = list(ids)
    if not ids:
        return {}
    dados = db.query(models.FinanceiroLancamento.solicitacao_id,
                     models.FinanceiroLancamento.tipo,
                     func.sum(models.FinanceiroLancamento.valor_centavos)).filter(
        models.FinanceiroLancamento.solicitacao_id.in_(ids)
    ).group_by(models.FinanceiroLancamento.solicitacao_id, models.FinanceiroLancamento.tipo).all()
    totais = {}
    for sol_id, tipo, valor in dados:
        totais.setdefault(sol_id, {'pagamentos': 0, 'estornos': 0})[tipo + 's' if tipo == 'pagamento' else 'estornos'] = int(valor)
    return totais


def serializar_resumo(sol, totais):
    pago = totais.get('pagamentos', 0) - totais.get('estornos', 0)
    aprovado = valor_herdado_centavos(sol.valor_aprovado)
    solicitado = valor_herdado_centavos(sol.valor)
    realizado = valor_herdado_centavos(sol.valor_realizado) if sol.status == 'Finalizada' else None
    excedente = max(0, pago - aprovado) if aprovado is not None else None
    return {
        'solicitacao_id': sol.id, 'numero': sol.numero or f'SOL-{sol.id:04d}',
        'condominio': sol.condominio, 'categoria': sol.categoria,
        'fornecedor': sol.fornecedor, 'descricao': sol.descricao,
        'status': sol.status, 'solicitante_id': sol.solicitante_id,
        'solicitado_centavos': solicitado,
        'aprovado_centavos': aprovado, 'realizado_centavos': realizado,
        'pago_centavos': pago,
        'saldo_centavos': (aprovado - pago) if aprovado is not None else None,
        'excedente_centavos': excedente,
        'alerta_sobrepagamento': excedente is not None and excedente > 0,
        'pagamento_permitido': sol.status in STATUS_PAGAVEIS and aprovado is not None and aprovado > 0,
    }


def obter_solicitacao(db, solicitacao_id, *, bloquear=False):
    query = db.query(models.Solicitacao).filter(models.Solicitacao.id == solicitacao_id)
    if bloquear:
        query = query.with_for_update()
    sol = query.first()
    if sol is None:
        raise HTTPException(404, detail='Solicitação não encontrada.')
    return sol


def obter_lancamento(db, lancamento_id):
    lan = db.get(models.FinanceiroLancamento, lancamento_id)
    if lan is None:
        raise HTTPException(404, detail='Lançamento não encontrado.')
    return lan


def serializar_lancamento(lan, comprovante=None):
    return {
        'id': lan.id, 'solicitacao_id': lan.solicitacao_id, 'tipo': lan.tipo,
        'valor_centavos': lan.valor_centavos,
        'excedente_centavos_no_lancamento': lan.excedente_centavos_no_lancamento,
        'data_pagamento': lan.data_pagamento.isoformat() if lan.data_pagamento else None,
        'estorno_de_id': lan.estorno_de_id, 'autor_nome': lan.autor_nome,
        'observacao': lan.observacao, 'criado_em': lan.criado_em.isoformat() if lan.criado_em else None,
        'comprovante': ({'nome': comprovante.nome_arquivo, 'tamanho_bytes': comprovante.tamanho_bytes,
                          'sha256': comprovante.sha256} if comprovante else None),
    }


@router.get('/solicitacoes')
def listar_solicitacoes(request: Request, db: Session = Depends(sessao)):
    usuario_financeiro(request, db)
    sols = db.query(models.Solicitacao).order_by(models.Solicitacao.id.desc()).limit(1000).all()
    somas = resumo_lancamentos(db, (sol.id for sol in sols))
    return {'solicitacoes': [serializar_resumo(sol, somas.get(sol.id, {})) for sol in sols],
            'limite': 1000, 'observacao': 'Valores aprovados legados são aproximados; pago vem somente de lançamentos.'}


@router.get('/solicitacoes/{solicitacao_id}/lancamentos')
def listar_lancamentos(solicitacao_id: int, request: Request, db: Session = Depends(sessao)):
    usuario_financeiro(request, db)
    sol = obter_solicitacao(db, solicitacao_id)
    registros = db.query(models.FinanceiroLancamento).filter_by(solicitacao_id=sol.id).order_by(models.FinanceiroLancamento.id).all()
    cps = db.query(models.FinanceiroComprovante).options(load_only(
        models.FinanceiroComprovante.id, models.FinanceiroComprovante.lancamento_id,
        models.FinanceiroComprovante.nome_arquivo, models.FinanceiroComprovante.tamanho_bytes,
        models.FinanceiroComprovante.sha256)).filter(
        models.FinanceiroComprovante.lancamento_id.in_([r.id for r in registros])
    ).all() if registros else []
    cp_map = {c.lancamento_id: c for c in cps}
    totais = resumo_lancamentos(db, [sol.id])
    return {'resumo': serializar_resumo(sol, totais.get(sol.id, {})),
            'lancamentos': [serializar_lancamento(r, cp_map.get(r.id)) for r in registros]}


def _comprovante_validado(arquivo: UploadFile):
    nome = str(arquivo.filename or '').replace('\\', '/').split('/')[-1].strip()
    if not nome or len(nome) > 180 or any(ord(ch) < 32 for ch in nome):
        raise HTTPException(422, detail='Nome de comprovante inválido.')
    conteudo = arquivo.file.read(MAX_COMPROVANTE + 1)
    if not conteudo or len(conteudo) > MAX_COMPROVANTE:
        raise HTTPException(413, detail='Comprovante vazio ou acima de 5 MB.')
    # Tipo real checado por assinatura, não apenas pela extensão/MIME declarado.
    eh_pdf = conteudo.startswith(b'%PDF-')
    eh_png = conteudo.startswith(b'\x89PNG\r\n\x1a\n')
    eh_jpeg = conteudo.startswith(b'\xff\xd8\xff')
    extensao = nome.lower().rsplit('.', 1)[-1]
    if eh_pdf and extensao == 'pdf':
        mime = 'application/pdf'
    elif eh_png and extensao == 'png':
        mime = 'image/png'
    elif eh_jpeg and extensao in ('jpg', 'jpeg'):
        mime = 'image/jpeg'
    else:
        raise HTTPException(422, detail='Comprovante deve ser PDF, PNG ou JPG válido.')
    return nome, mime, conteudo


@router.post('/solicitacoes/{solicitacao_id}/pagamentos', status_code=201)
def registrar_pagamento(solicitacao_id: int, request: Request,
                       data_pagamento: date = Form(...), valor: str = Form(...),
                       chave_operacao: str = Form(...), observacao: str = Form(''),
                       comprovante: UploadFile = File(...), db: Session = Depends(sessao)):
    # Somente Controladoria pode registrar. Perfil Financeiro é consulta exclusiva.
    autor = usuario_financeiro(request, db, so_controladoria=True)
    chave = chave_validada(chave_operacao)
    valor_c = centavos(valor)
    if data_pagamento < date(2000, 1, 1) or data_pagamento > date.today():
        raise HTTPException(422, detail='Data de pagamento inválida ou futura.')
    if len(observacao) > 500:
        raise HTTPException(422, detail='Observação muito longa.')
    nome, mime, conteudo = _comprovante_validado(comprovante)
    # Mesmo em tentativas de repetição, nenhuma linha deve ser duplicada.
    try:
        sol = obter_solicitacao(db, solicitacao_id, bloquear=True)
        if sol.status not in STATUS_PAGAVEIS or not (valor_herdado_centavos(sol.valor_aprovado) or 0) > 0:
            raise HTTPException(409, detail='Só registre pagamentos de compras aprovadas com valor definido.')
        ja_existe = db.query(models.FinanceiroLancamento).filter_by(chave_operacao=chave).first()
        if ja_existe is not None:
            raise HTTPException(409, detail=f'Operação já registrada (lançamento #{ja_existe.id}).')
        anterior = resumo_lancamentos(db, [sol.id]).get(sol.id, {})
        pago_anterior = anterior.get('pagamentos', 0) - anterior.get('estornos', 0)
        aprovado = valor_herdado_centavos(sol.valor_aprovado)
        excedente_agora = max(0, pago_anterior + valor_c - aprovado) if aprovado is not None else 0
        lan = models.FinanceiroLancamento(
            solicitacao_id=sol.id, tipo='pagamento', valor_centavos=valor_c,
            excedente_centavos_no_lancamento=excedente_agora,
            data_pagamento=data_pagamento, chave_operacao=chave,
            observacao=observacao.strip(), autor_id=autor.id, autor_nome=autor.nome,
        )
        db.add(lan)
        db.flush()
        db.add(models.FinanceiroComprovante(
            lancamento_id=lan.id, nome_arquivo=nome, mime=mime,
            tamanho_bytes=len(conteudo), sha256=sha256(conteudo).hexdigest(),
            conteudo=conteudo,
        ))
        db.commit()
        db.refresh(lan)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail='Lançamento duplicado ou conflito de concorrência.')
    except Exception:
        db.rollback()
        raise
    totais = resumo_lancamentos(db, [sol.id])
    return {'lancamento': serializar_lancamento(lan),
            'resumo': serializar_resumo(sol, totais.get(sol.id, {}))}


class EstornoEntrada(BaseModel):
    motivo: str = Field(min_length=10, max_length=500)
    chave_operacao: str


@router.post('/lancamentos/{lancamento_id}/estornar', status_code=201)
def estornar_pagamento(lancamento_id: int, dados: EstornoEntrada, request: Request,
                       db: Session = Depends(sessao)):
    autor = usuario_financeiro(request, db, so_controladoria=True)
    chave = chave_validada(dados.chave_operacao)
    original = obter_lancamento(db, lancamento_id)
    if original.tipo != 'pagamento':
        raise HTTPException(409, detail='Somente pagamentos podem ser estornados.')
    sol = obter_solicitacao(db, original.solicitacao_id, bloquear=True)
    estorno_existente = db.query(models.FinanceiroLancamento).filter_by(estorno_de_id=original.id).first()
    if estorno_existente is not None:
        raise HTTPException(409, detail='Pagamento já estornado.')
    try:
        lan = models.FinanceiroLancamento(
            solicitacao_id=sol.id, tipo='estorno', valor_centavos=original.valor_centavos,
            chave_operacao=chave, estorno_de_id=original.id,
            observacao=dados.motivo.strip(), autor_id=autor.id, autor_nome=autor.nome,
        )
        db.add(lan)
        db.commit()
        db.refresh(lan)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail='Estorno duplicado ou conflito de concorrência.')
    totais = resumo_lancamentos(db, [sol.id])
    return {'lancamento': serializar_lancamento(lan),
            'resumo': serializar_resumo(sol, totais.get(sol.id, {}))}


@router.get('/comprovantes/{lancamento_id}')
def baixar_comprovante(lancamento_id: int, request: Request, db: Session = Depends(sessao)):
    usuario_financeiro(request, db)
    lan = obter_lancamento(db, lancamento_id)
    comprovante = db.query(models.FinanceiroComprovante).filter_by(lancamento_id=lan.id).first()
    if comprovante is None:
        raise HTTPException(404, detail='Comprovante não encontrado.')
    nome = comprovante.nome_arquivo.replace('"', '').replace('\\', '_')
    return StreamingResponse(BytesIO(comprovante.conteudo), media_type='application/octet-stream', headers={
        'Content-Disposition': f'attachment; filename="{nome.encode("ascii", "ignore").decode() or "comprovante"}"',
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'no-store',
    })
