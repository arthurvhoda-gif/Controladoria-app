"""Preferências de WhatsApp e auditoria de fila, SEM ENVIOS.

V6 prepara o fluxo futuro pela API oficial; não contém credenciais, cliente HTTP,
webhook, agendamento ou endpoint para disparar mensagens.
"""
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
from database import SessionLocal

router = APIRouter(prefix='/avisos-whatsapp', tags=['Avisos WhatsApp - preparacao'])

def sessao():
    with SessionLocal() as db:
        yield db

def usuario_atual(request: Request, db: Session):
    pessoa = db.get(models.Usuario, request.state.auth_user_id)
    if pessoa is None:
        raise HTTPException(401, detail='Usuário não encontrado.')
    return pessoa

class PreferenciaEntrada(BaseModel):
    numero: str = Field(default='', max_length=30)
    receber_alertas: bool

def normalizar_numero(numero: str):
    """Aceita celular brasileiro com DDD e 11 dígitos, exige +55 como destino."""
    limpo = re.sub(r'[^\d+]', '', numero.strip())
    if limpo.startswith('+'):
        limpo = limpo[1:]
    if limpo.startswith('55') and len(limpo) in (12, 13):
        limpo = limpo[2:]
    if not re.fullmatch(r'[1-9][0-9]9[0-9]{8}', limpo):
        raise HTTPException(422, detail='Informe celular com DDD brasileiro válido.')
    return '+55' + limpo

def mostrar(preferencia):
    return {
        'numero': preferencia.telefone if preferencia else '',
        'receber_alertas': bool(preferencia.consentimento) if preferencia else False,
        'envios_ativos': False,
        'mensagem': 'Configuração salva. Envios pelo WhatsApp ainda não estão ativados.',
    }

@router.get('/me')
def minhas_preferencias(request: Request, db: Session = Depends(sessao)):
    usuario = usuario_atual(request, db)
    return mostrar(db.get(models.PreferenciaWhatsApp, usuario.id))

@router.put('/me')
def salvar_preferencias(dados: PreferenciaEntrada, request: Request, db: Session = Depends(sessao)):
    usuario = usuario_atual(request, db)
    prefs = db.get(models.PreferenciaWhatsApp, usuario.id)
    if prefs is None:
        prefs = models.PreferenciaWhatsApp(usuario_id=usuario.id)
        db.add(prefs)
    # Somente o dono da conta registra seu celular e concordância.
    # Desabilitar não exige o telefone, e impede enfileiramentos futuros.
    if dados.receber_alertas:
        prefs.telefone = normalizar_numero(dados.numero)
        prefs.consentimento = 1
        prefs.consentido_em = datetime.now(timezone.utc)
    else:
        prefs.consentimento = 0
        prefs.consentido_em = None
        # Remoção de número opcional quando usuário apagar o campo.
        if not dados.numero.strip():
            prefs.telefone = None
    prefs.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return mostrar(prefs)

@router.get('/fila/resumo')
def resumo_fila(request: Request, db: Session = Depends(sessao)):
    usuario = usuario_atual(request, db)
    if usuario.perfil != 'Controladoria':
        raise HTTPException(403, detail='Apenas Controladoria.')
    registros = (db.query(models.FilaWhatsApp.status, func.count(models.FilaWhatsApp.id))
                .group_by(models.FilaWhatsApp.status).all())
    return {
        'envios_ativos': False,
        'por_status': {status: quantidade for status, quantidade in registros},
        'observacao': 'Simulação da fila; nenhuma mensagem enviada ao WhatsApp.',
    }
