"""Contatos gerenciados pela Controladoria; consentimento individual. SEM ENVIOS.

Os endpoints /admin são exclusivos da Controladoria. O funcionário pode apenas
autorizar/revogar avisos para o número atribuído pela Controladoria.
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

def exigir_controladoria(request: Request, db: Session):
    usuario = usuario_atual(request, db)
    if usuario.perfil != 'Controladoria':
        raise HTTPException(403, detail='Apenas Controladoria.')
    return usuario

class PreferenciaEntrada(BaseModel):
    # Número não é aceito: somente a Controladoria define telefones.
    receber_alertas: bool

class NumeroAdministrado(BaseModel):
    numero: str = Field(default='', max_length=35)

def normalizar_numero(numero: str):
    """Formato brasileiro +55DDD9XXXXXXXX; sem validar titularidade."""
    limpo = re.sub(r'[^\d+]', '', numero.strip())
    if limpo.startswith('+'):
        limpo = limpo[1:]
    if limpo.startswith('55') and len(limpo) in (12, 13):
        limpo = limpo[2:]
    if not re.fullmatch(r'[1-9][0-9]9[0-9]{8}', limpo):
        raise HTTPException(422, detail='Informe celular brasileiro com DDD: (43) 99999-9999.')
    return '+55' + limpo

def mostrar(preferencia):
    return {
        'numero': preferencia.telefone if preferencia and preferencia.telefone else '',
        'receber_alertas': bool(preferencia.consentimento) if preferencia else False,
        'envios_ativos': False,
        'mensagem': 'Os números são gerenciados pela Controladoria. Nenhum WhatsApp é enviado nesta versão.',
    }

def cancelar_pendentes(db: Session, usuario_id: int):
    db.query(models.FilaWhatsApp).filter(
        models.FilaWhatsApp.usuario_id == usuario_id,
        models.FilaWhatsApp.status == 'preparada',
    ).update({'status': 'cancelada'}, synchronize_session=False)

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
    if dados.receber_alertas:
        if not prefs.telefone:
            raise HTTPException(422, detail='A Controladoria precisa cadastrar seu número antes de você autorizar os avisos.')
        # Cada pessoa autoriza o número que já foi administrativamente cadastrado.
        if not prefs.consentimento:
            prefs.consentido_em = datetime.now(timezone.utc)
        prefs.consentimento = 1
    else:
        prefs.consentimento = 0
        prefs.consentido_em = None
        cancelar_pendentes(db, usuario.id)
    prefs.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return mostrar(prefs)

@router.get('/admin/usuarios')
def listar_contatos(request: Request, db: Session = Depends(sessao)):
    exigir_controladoria(request, db)
    usuarios = db.query(models.Usuario).order_by(models.Usuario.nome, models.Usuario.id).all()
    preferencias = {p.usuario_id: p for p in db.query(models.PreferenciaWhatsApp).all()}
    condominios = {c.id: c.nome for c in db.query(models.Condominio).all()}
    return [{
        'id': u.id, 'nome': u.nome, 'email': u.email, 'perfil': u.perfil,
        'condominio_id': u.condominio_id,
        'condominio_nome': condominios.get(u.condominio_id),
        'numero': preferencias[u.id].telefone if u.id in preferencias else '',
        'receber_alertas': bool(preferencias[u.id].consentimento) if u.id in preferencias else False,
        'consentido_em': preferencias[u.id].consentido_em.isoformat()
            if u.id in preferencias and preferencias[u.id].consentido_em else None,
    } for u in usuarios]

@router.put('/admin/usuarios/{usuario_id}/numero')
def salvar_numero_admin(usuario_id: int, dados: NumeroAdministrado, request: Request,
                        db: Session = Depends(sessao)):
    admin = exigir_controladoria(request, db)
    destinatario = db.get(models.Usuario, usuario_id)
    if destinatario is None:
        raise HTTPException(404, detail='Cadastro não encontrado.')
    novo = normalizar_numero(dados.numero) if dados.numero.strip() else None
    prefs = db.get(models.PreferenciaWhatsApp, usuario_id)
    anterior = prefs.telefone if prefs else None
    if anterior == novo:
        return {'numero': anterior or '', 'receber_alertas': bool(prefs.consentimento) if prefs else False,
                'alterado': False, 'mensagem': 'Nenhuma alteração necessária.'}
    if prefs is None:
        prefs = models.PreferenciaWhatsApp(usuario_id=usuario_id)
        db.add(prefs)
    estava_autorizado = bool(prefs.consentimento)
    prefs.telefone = novo
    prefs.consentimento = 0
    prefs.consentido_em = None
    prefs.atualizado_em = datetime.now(timezone.utc)
    cancelar_pendentes(db, usuario_id)
    db.add(models.WhatsAppAuditoriaContato(
        usuario_id=usuario_id, alterado_por_id=admin.id,
        telefone_anterior_final=anterior[-4:] if anterior else None,
        telefone_novo_final=novo[-4:] if novo else None,
        consentimento_revogado=int(estava_autorizado),
    ))
    db.commit()
    return {'numero': novo or '', 'receber_alertas': False, 'alterado': True,
            'mensagem': 'Número atualizado. A pessoa deverá autorizar os avisos neste número.'}

@router.get('/fila/resumo')
def resumo_fila(request: Request, db: Session = Depends(sessao)):
    exigir_controladoria(request, db)
    registros = (db.query(models.FilaWhatsApp.status, func.count(models.FilaWhatsApp.id))
                .group_by(models.FilaWhatsApp.status).all())
    return {
        'envios_ativos': False,
        'por_status': {status: quantidade for status, quantidade in registros},
        'observacao': 'Simulação da fila; nenhuma mensagem enviada ao WhatsApp.',
    }
