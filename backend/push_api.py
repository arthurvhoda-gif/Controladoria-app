"""V7.4: cadastro de dispositivos para Web Push, sem despacho de mensagens.

Somente contas autenticadas registram/revogam suas assinaturas.
Os endpoints de push são credenciais do aparelho: nunca os devolva ao cliente,
nem os escreva em logs. O envio real será implementado e revisado separadamente.
"""
import base64
import hashlib
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from database import SessionLocal


router = APIRouter(prefix='/push', tags=['Web Push - dispositivos'])
MAX_DISPOSITIVOS = 5
# Restringe destinos para prevenir SSRF quando houver um despachante.
PROVEDORES = frozenset({
    'fcm.googleapis.com',
    'fcm-xm.googleapis.com',
    'android.googleapis.com',
    'updates.push.services.mozilla.com',
    'push.services.mozilla.com',
    'web.push.apple.com',
})


def sessao():
    with SessionLocal() as db:
        yield db


class ChavesPush(BaseModel):
    p256dh: str = Field(min_length=80, max_length=180)
    auth: str = Field(min_length=16, max_length=60)


class RegistroPush(BaseModel):
    endpoint: str = Field(min_length=30, max_length=2048)
    keys: ChavesPush


class RemocaoPush(BaseModel):
    endpoint: str = Field(min_length=30, max_length=2048)


def _decodificar(valor: str, tamanho: int) -> bytes:
    if not re.fullmatch(r'[A-Za-z0-9_-]+', valor):
        raise HTTPException(422, 'Assinatura Web Push inválida.')
    try:
        dados = base64.b64decode(valor + '=' * (-len(valor) % 4), altchars=b'-_', validate=True)
    except (ValueError, base64.binascii.Error):
        raise HTTPException(422, 'Assinatura Web Push inválida.') from None
    if len(dados) != tamanho:
        raise HTTPException(422, 'Assinatura Web Push inválida.')
    return dados


def _validar_endpoint(endpoint: str) -> str:
    # Nunca aceitar URLs arbitrárias, IPs internos ou HTTP.
    if endpoint != endpoint.strip() or any(c.isspace() for c in endpoint):
        raise HTTPException(422, 'Endpoint Web Push inválido.')
    try:
        u = urlsplit(endpoint)
        if (u.scheme != 'https' or not u.hostname or u.hostname not in PROVEDORES or
            u.username is not None or u.password is not None or
            u.port not in (None, 443) or not u.path.startswith('/') or
            len(u.path) < 5 or u.fragment):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Endpoint Web Push inválido.') from None
    return endpoint


def _chave_publica() -> str:
    valor = os.getenv('VAPID_PUBLIC_KEY', '').strip()
    if not valor:
        return ''
    try:
        chave = _decodificar(valor, 65)
        if chave[0] != 4:
            return ''
    except HTTPException:
        return ''
    return valor


def _usuario(request: Request, db: Session):
    pessoa = db.get(models.Usuario, request.state.auth_user_id)
    if pessoa is None:
        raise HTTPException(401, 'Conta não encontrada.')
    return pessoa


@router.get('/config')
def configuracao(request: Request, db: Session = Depends(sessao)):
    _usuario(request, db)
    publica = _chave_publica()
    return {
        'registro_disponivel': bool(publica),
        'chave_publica': publica,
        'envios_ativos': False,  # Gate de segurança: V7.4 ainda não despacha.
        'maximo_dispositivos': MAX_DISPOSITIVOS,
    }


@router.get('/dispositivos')
def meus_dispositivos(request: Request, db: Session = Depends(sessao)):
    usuario = _usuario(request, db)
    total = db.query(models.PushDispositivo).filter(
        models.PushDispositivo.usuario_id == usuario.id
    ).count()
    return {'total': total, 'maximo': MAX_DISPOSITIVOS}


@router.post('/dispositivos')
def registrar(dados: RegistroPush, request: Request, db: Session = Depends(sessao)):
    usuario = _usuario(request, db)
    if not _chave_publica():
        raise HTTPException(503, 'Registro de Web Push ainda não configurado.')
    endpoint = _validar_endpoint(dados.endpoint)
    chave_publica = _decodificar(dados.keys.p256dh, 65)
    if chave_publica[0] != 4:
        raise HTTPException(422, 'Chave de dispositivo inválida.')
    _decodificar(dados.keys.auth, 16)

    identificador = hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
    dispositivo = db.query(models.PushDispositivo).filter(
        models.PushDispositivo.endpoint_sha256 == identificador
    ).with_for_update().one_or_none()

    if dispositivo is None or dispositivo.usuario_id != usuario.id:
        total = db.query(models.PushDispositivo).filter(
            models.PushDispositivo.usuario_id == usuario.id
        ).count()
        if total >= MAX_DISPOSITIVOS:
            raise HTTPException(409, 'Limite de dispositivos atingido. Revogue um aparelho antigo.')

    if dispositivo is None:
        dispositivo = models.PushDispositivo(
            usuario_id=usuario.id, endpoint_sha256=identificador
        )
        db.add(dispositivo)
    else:
        # Ao trocar de conta no mesmo navegador, transfere o aparelho: não
        # podem continuar chegando avisos da conta anterior nesse dispositivo.
        dispositivo.usuario_id = usuario.id

    dispositivo.endpoint = endpoint
    dispositivo.p256dh = dados.keys.p256dh
    dispositivo.chave_auth = dados.keys.auth
    dispositivo.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return {'registrado': True}


@router.delete('/dispositivos')
def revogar(dados: RemocaoPush, request: Request, db: Session = Depends(sessao)):
    usuario = _usuario(request, db)
    endpoint = _validar_endpoint(dados.endpoint)
    identificador = hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
    # Revogação limitada ao dono: nunca remover dispositivos de outras contas.
    db.query(models.PushDispositivo).filter(
        models.PushDispositivo.usuario_id == usuario.id,
        models.PushDispositivo.endpoint_sha256 == identificador,
    ).delete(synchronize_session=False)
    db.commit()
    return {'revogado': True}
