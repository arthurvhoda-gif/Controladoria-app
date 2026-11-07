"""Contatos gerenciados pela Controladoria; consentimento individual. SEM ENVIOS.

Os endpoints /admin são exclusivos da Controladoria. O funcionário pode apenas
autorizar/revogar avisos para o número atribuído pela Controladoria.
"""
import re
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session
import models
from database import SessionLocal
from whatsapp_mensagens import preparar_previa_whatsapp, link_direto_servico
from whatsapp_validade import avaliar_vigencia
from whatsapp_historico import avaliar_historico
from whatsapp_preenvio import avaliar_preenvio
from servicos_api import pessoa_visivel

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


def registrar_consentimento(db: Session, usuario_id: int, ator_id: int,
                            acao: str, origem: str, telefone: str | None):
    """Registra opt-in e revogacao na mesma transacao, sem armazenar o numero."""
    db.add(models.WhatsAppAuditoriaConsentimento(
        usuario_id=usuario_id, alterado_por_id=ator_id,
        acao=acao, origem=origem,
        telefone_final=telefone[-4:] if telefone else None,
    ))

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
            registrar_consentimento(db, usuario.id, usuario.id, 'concedido',
                                    'usuario', prefs.telefone)
        prefs.consentimento = 1
    else:
        if prefs.consentimento:
            registrar_consentimento(db, usuario.id, usuario.id, 'revogado',
                                    'usuario', prefs.telefone)
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
    if estava_autorizado:
        registrar_consentimento(db, usuario_id, admin.id,
                                'revogado_troca_numero', 'controladoria', anterior)
    db.commit()
    return {'numero': novo or '', 'receber_alertas': False, 'alterado': True,
            'mensagem': 'Número atualizado. A pessoa deverá autorizar os avisos neste número.'}

@router.get('/admin/usuarios/{usuario_id}/auditoria')
def consultar_auditoria(usuario_id: int, request: Request, db: Session = Depends(sessao)):
    """Historico auditavel restrito à Controladoria; sem telefones completos."""
    exigir_controladoria(request, db)
    if db.get(models.Usuario, usuario_id) is None:
        raise HTTPException(404, detail='Cadastro não encontrado.')
    contatos = (
        db.query(models.WhatsAppAuditoriaContato)
        .filter(models.WhatsAppAuditoriaContato.usuario_id == usuario_id)
        .order_by(models.WhatsAppAuditoriaContato.id.desc()).limit(100).all()
    )
    consentimentos = (
        db.query(models.WhatsAppAuditoriaConsentimento)
        .filter(models.WhatsAppAuditoriaConsentimento.usuario_id == usuario_id)
        .order_by(models.WhatsAppAuditoriaConsentimento.id.desc()).limit(100).all()
    )
    registros = [{
        'tipo': 'numero_atualizado', 'origem': 'controladoria',
        'alterado_por_id': x.alterado_por_id,
        'telefone_anterior_final': x.telefone_anterior_final,
        'telefone_novo_final': x.telefone_novo_final,
        'consentimento_revogado': bool(x.consentimento_revogado),
        'criado_em': x.criado_em.isoformat() if x.criado_em else None,
    } for x in contatos] + [{
        'tipo': x.acao, 'origem': x.origem,
        'alterado_por_id': x.alterado_por_id,
        'telefone_final': x.telefone_final,
        'criado_em': x.criado_em.isoformat() if x.criado_em else None,
    } for x in consentimentos]
    registros.sort(key=lambda x: x['criado_em'] or '', reverse=True)
    return {'usuario_id': usuario_id, 'historico': registros[:100], 'limite': 100}


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

@router.get('/fila/previas')
def listar_previas_fila(request: Request, db: Session = Depends(sessao)):
    """Lista somente avisos preparados; exclusivos da Controladoria. SEM ENVIOS."""
    exigir_controladoria(request, db)
    frontend_url = os.getenv('FRONTEND_PUBLIC_URL', '').strip()
    # Falhar explicitamente se não houver URL configurada evita links do ambiente errado.
    try:
        link_direto_servico(1, frontend_url)
    except ValueError as exc:
        raise HTTPException(503, detail='Configure FRONTEND_PUBLIC_URL válida neste ambiente.') from exc

    registros = (
        db.query(models.FilaWhatsApp, models.ServicoAviso, models.ServicoInterno,
                 models.Usuario, models.PreferenciaWhatsApp)
        .join(models.ServicoAviso, models.FilaWhatsApp.aviso_id == models.ServicoAviso.id)
        .join(models.ServicoInterno, models.FilaWhatsApp.servico_id == models.ServicoInterno.id)
        .join(models.Usuario, models.FilaWhatsApp.usuario_id == models.Usuario.id)
        .outerjoin(models.PreferenciaWhatsApp,
                   models.FilaWhatsApp.usuario_id == models.PreferenciaWhatsApp.usuario_id)
        .filter(models.FilaWhatsApp.status == 'preparada')
        .order_by(models.FilaWhatsApp.criada_em.desc(), models.FilaWhatsApp.id.desc())
        .limit(30)
        .all()
    )
    # Carrega apenas os participantes relacionados aos avisos exibidos (maximo 30).
    # Consulta somente leitura; nao muda a fila ou o andamento dos servicos.
    participantes = {}
    if registros:
        pares = {(servico.id, destinatario.id)
                 for _, _, servico, destinatario, _ in registros}
        participantes = {
            (p.servico_id, p.usuario_id, p.papel): p
            for p in db.query(models.ServicoParticipante).filter(
                tuple_(models.ServicoParticipante.servico_id,
                       models.ServicoParticipante.usuario_id).in_(pares)
            ).all()
        }

    # Historico completo das tarefas presentes na pagina (maximo 30 avisos).
    # Limite defensivo: historico truncado NUNCA pode gerar conclusao de vigencia.
    historicos = {}
    historico_completo = True
    if registros:
        servicos_ids = {servico.id for _, _, servico, _, _ in registros}
        eventos_db = (
            db.query(models.ServicoEvento)
            .filter(models.ServicoEvento.servico_id.in_(servicos_ids))
            .order_by(models.ServicoEvento.id.asc())
            .limit(10001)
            .all()
        )
        historico_completo = len(eventos_db) <= 10000
        if historico_completo:
            for e in eventos_db:
                historicos.setdefault(e.servico_id, []).append({
                    'id': e.id, 'servico_id': e.servico_id,
                    'acao': e.acao, 'autor_id': e.autor_id,
                })

    itens = []
    for fila, aviso, servico, destinatario, preferencia in registros:
        previa = preparar_previa_whatsapp(
            servico_id=servico.id,
            titulo=servico.titulo,
            mensagem_aviso=aviso.mensagem,
            tipo_evento=aviso.tipo_evento,
            frontend_public_url=frontend_url,
        )
        # O papel deve corresponder ao tipo do aviso; nunca usar um executor
        # para inferir a pendencia de um fiscalizador (ou vice-versa).
        papel_esperado = {
            'nova_tarefa': 'executor',
            'devolucao': 'executor',
            'designacao_fiscal': 'fiscalizador',
            'pronto_fiscalizacao': 'fiscalizador',
        }.get(previa['evento'])
        participante = participantes.get((servico.id, destinatario.id, papel_esperado))
        diagnostico = avaliar_vigencia(
            previa['evento'], servico.status,
            papel=participante.papel if participante else None,
            status_participante=participante.status if participante else None,
            destinatario_eh_criador=(servico.criador_id == destinatario.id),
        )
        diagnostico_historico = (
            avaliar_historico(
                tipo=previa['evento'], evento_origem_id=aviso.evento_id,
                destinatario_id=destinatario.id, servico_id=servico.id,
                eventos=historicos.get(servico.id, []),
            ) if historico_completo else {
                'situacao': 'revisar',
                'motivo': 'Historico excede o limite de leitura; revisar manualmente.',
                'evento_superador': None,
            }
        )
        # V6.7 - TRIAGEM EXCLUSIVAMENTE INFORMATIVA (SEM ENVIOS).
        # O cadastro atual nao possui campo "usuario_ativo". O telefone
        # cadastrado nao prova que sua linha esta ativa. E a deteccao de
        # duplicidades ainda nao foi aferida atomicamente. Usar None.
        if previa['evento'] == 'validacao_final':
            acesso_destinatario = bool(
                servico.criador_id == destinatario.id and
                destinatario.perfil == 'Controladoria'
            )
        else:
            participante_preenvio = participante
            if previa['evento'] == 'servico_validado':
                participante_preenvio = next((
                    p for papel in ('executor', 'fiscalizador')
                    if (p := participantes.get((servico.id, destinatario.id, papel))) is not None
                ), None)
            acesso_destinatario = (
                pessoa_visivel(participante_preenvio, servico, destinatario)
                if participante_preenvio is not None else None
            )

        referencias_corretas = bool(
            fila.aviso_id == aviso.id and fila.servico_id == servico.id and
            aviso.servico_id == servico.id and
            fila.usuario_id == destinatario.id and aviso.usuario_id == destinatario.id
        )
        if not referencias_corretas:
            vinculos_preenvio = False
        elif aviso.evento_id is None or not historico_completo:
            vinculos_preenvio = None
        else:
            vinculos_preenvio = any(
                e['id'] == aviso.evento_id and e['servico_id'] == servico.id
                for e in historicos.get(servico.id, [])
            )

        diagnostico_preenvio = avaliar_preenvio(
            status_fila=fila.status,
            consentimento=bool(preferencia and preferencia.consentimento),
            telefone_ativo=False if not (preferencia and preferencia.telefone) else None,
            usuario_ativo=None,
            destinatario_autorizado=acesso_destinatario,
            vinculos_consistentes=vinculos_preenvio,
            evento_origem_id=aviso.evento_id,
            diagnostico_atual=diagnostico['situacao'],
            diagnostico_historico=diagnostico_historico['situacao'],
            duplicidade_detectada=None,
        )
        itens.append({
            'fila_id': fila.id,
            'servico_id': servico.id,
            'destinatario': destinatario.nome,
            'status': fila.status,
            'evento': previa['evento'],
            'diagnostico': diagnostico,
            'diagnostico_historico': diagnostico_historico,
            'diagnostico_preenvio': diagnostico_preenvio,
            'sem_evento_origem': bool(aviso.evento_id is None and historico_completo),
            'mensagem': previa['mensagem'],
            'link': previa['link'],
            'elegivel_agora': bool(preferencia and preferencia.telefone and preferencia.consentimento),
            'criada_em': fila.criada_em.isoformat() if fila.criada_em else None,
        })
    return {'envios_ativos': False, 'previa': itens, 'limite': 30}
