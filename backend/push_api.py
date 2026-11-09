"""V7.4: cadastro e teste MANUAL, sem notificacoes automaticas.

Somente contas autenticadas registram/revogam suas assinaturas.
Os endpoints de push são credenciais do aparelho: nunca os devolva ao cliente,
nem os escreva em logs. O envio real será implementado e revisado separadamente.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pywebpush import webpush, WebPushException

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
        'envios_ativos': False,  # Notificacoes de eventos continuam desativadas.
        'teste_disponivel': _modo_teste_habilitado(),
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


def _modo_teste_habilitado():
    """Habilita somente a rota de teste controlado e acionado manualmente."""
    if os.getenv('PUSH_TESTS_ENABLED', '').strip() != 'true' or not _chave_publica():
        return False
    chave = os.getenv('VAPID_PRIVATE_KEY', '').strip()
    try:
        _decodificar(chave, 32)
    except HTTPException:
        return False
    return True


def _consumir_cota_teste(usuario_id: int, db: Session):
    """No maximo um teste por minuto e por usuario, inclusive apos restart."""
    agora = int(time.time())
    atualizado = db.query(models.PushTesteControle).filter(
        models.PushTesteControle.usuario_id == usuario_id,
        models.PushTesteControle.ultimo_envio_epoch <= agora - 60,
    ).update({'ultimo_envio_epoch': agora}, synchronize_session=False)
    if not atualizado:
        if db.get(models.PushTesteControle, usuario_id):
            raise HTTPException(429, 'Aguarde 60 segundos antes de repetir o teste.')
        db.add(models.PushTesteControle(
            usuario_id=usuario_id, ultimo_envio_epoch=agora
        ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(429, 'Aguarde antes de repetir o teste.') from None


@router.post('/teste')
def enviar_teste_manual(request: Request, db: Session = Depends(sessao)):
    """Envia SOMENTE para os aparelhos da propria conta, mediante clique.

    Sem dados de tarefa, sem notificacao de terceiros e sem execucao automatica.
    O aceite pelo provedor nao comprova exibicao no aparelho.
    """
    usuario = _usuario(request, db)
    if not _modo_teste_habilitado():
        raise HTTPException(503, 'Envio de teste ainda não habilitado.')
    dispositivos = db.query(models.PushDispositivo).filter(
        models.PushDispositivo.usuario_id == usuario.id
    ).order_by(models.PushDispositivo.id).limit(MAX_DISPOSITIVOS).all()
    if not dispositivos:
        raise HTTPException(409, 'Nenhum aparelho cadastrado nesta conta.')

    _consumir_cota_teste(usuario.id, db)
    privada = os.getenv('VAPID_PRIVATE_KEY', '').strip()
    identificador = secrets.token_hex(8)
    mensagem = json.dumps({'tipo': 'haize-teste-v1', 'id': identificador})
    aceitos, falhas, revogados = 0, 0, 0

    for aparelho in dispositivos:
        try:
            # Defender também assinaturas persistidas contra alterações posteriores.
            _validar_endpoint(aparelho.endpoint)
            webpush(
                subscription_info={
                    'endpoint': aparelho.endpoint,
                    'keys': {'p256dh': aparelho.p256dh, 'auth': aparelho.chave_auth},
                },
                data=mensagem,
                vapid_private_key=privada,
                vapid_claims={'sub': 'mailto:app1haize@gmail.com'},
                ttl=120,
                timeout=8,
            )
            aceitos += 1
        except WebPushException as erro:
            falhas += 1
            if erro.status_code in (404, 410):
                db.delete(aparelho)
                revogados += 1
        except (Exception):
            # Erros de infraestrutura não devem expor endpoint, chaves ou token.
            falhas += 1

    if revogados:
        db.commit()
    return {
        'aparelhos_consultados': len(dispositivos),
        'aceitos_pelo_provedor': aceitos,
        'falhas': falhas,
        'assinaturas_expiradas_removidas': revogados,
        'entrega_no_celular_confirmada': False,
    }
