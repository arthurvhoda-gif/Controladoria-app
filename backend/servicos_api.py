"""Serviços internos V2: múltiplos executores e fiscalizadores por solicitação.

WhatsApp não é integrado nesta etapa; apenas avisos internos. Registros V1 sem
participantes continuam legíveis via fallback da coluna responsavel_id.
"""
from datetime import date, datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

import models
from database import SessionLocal

router = APIRouter(prefix='/servicos', tags=['Serviços internos'])

STATUS_NOVO = 'Aguardando ciência'
STATUS_CIENTE = 'Recebido'
STATUS_EXECUCAO = 'Em andamento'
STATUS_FISCALIZACAO = 'Aguardando fiscalização'
STATUS_VALIDACAO = 'Aguardando validação'
STATUS_FECHADO = 'Concluído'
STATUS_EXEC_CONCLUIDO = 'Finalizado'
STATUS_FISC_APROVADO = 'Aprovado'
PRIORIDADES = ('Baixa', 'Normal', 'Alta', 'Urgente')
MAX_FOTO_ENTRADA = 4 * 1024 * 1024  # 4 MiB por arquivo antes de compactar
MAX_FOTOS_SERVICO = 15
ETAPAS_FOTOS = {'antes', 'durante', 'depois', 'fiscalizacao'}
Image.MAX_IMAGE_PIXELS = 18_000_000


def sessao():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def agora():
    return datetime.now(timezone.utc)


def hoje():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


class ServicoNovo(BaseModel):
    condominio_id: int = Field(gt=0)
    # responsavel_id permanece compatível com a V1 e com testes antigos.
    responsavel_id: int | None = Field(default=None, gt=0)
    executores_ids: list[int] = Field(default_factory=list, max_length=30)
    fiscalizadores_ids: list[int] = Field(default_factory=list, max_length=30)
    titulo: str = Field(min_length=4, max_length=180)
    descricao: str = Field(min_length=5, max_length=4000)
    prioridade: Literal['Baixa', 'Normal', 'Alta', 'Urgente'] = 'Normal'
    prazo: date


class ServicoAcao(BaseModel):
    acao: Literal['confirmar', 'iniciar', 'concluir', 'validar', 'devolver']
    observacao: str = Field(default='', max_length=3000)


def obter_usuario(request: Request, db: Session):
    user = db.get(models.Usuario, request.state.auth_user_id)
    if user is None:
        raise HTTPException(401, detail='Usuário não encontrado.')
    return user


def participantes(db, servico):
    registros = db.query(models.ServicoParticipante).filter(
        models.ServicoParticipante.servico_id == servico.id
    ).order_by(models.ServicoParticipante.id).all()
    if registros:
        return registros
    # Compatibilidade de leitura: tarefas V1 não são modificadas em GET.
    # A migração funcional do primeiro clique é feita somente em POST, sob lock.
    if servico.responsavel_id:
        return [models.ServicoParticipante(
            servico_id=servico.id, usuario_id=servico.responsavel_id,
            usuario_nome=servico.responsavel_nome, papel='executor',
            status={STATUS_NOVO: STATUS_NOVO, STATUS_CIENTE: STATUS_CIENTE,
                    STATUS_EXECUCAO: STATUS_EXECUCAO,
                    STATUS_VALIDACAO: STATUS_EXEC_CONCLUIDO,
                    STATUS_FECHADO: STATUS_EXEC_CONCLUIDO}.get(servico.status, STATUS_NOVO),
        )]
    return []


def garantir_participantes_legados(db, servico):
    atuais = db.query(models.ServicoParticipante).filter(
        models.ServicoParticipante.servico_id == servico.id
    ).first()
    if not atuais and servico.responsavel_id:
        p = participantes(db, servico)[0]
        db.add(p)
        db.flush()


def pessoa_visivel(p, servico, user):
    return p.usuario_id == user.id and (
        user.perfil != 'Checklist' or (
            user.condominio_id is not None and user.condominio_id == servico.condominio_id
        )
    )


def visivel(servico, user, db=None):
    if user.perfil == 'Controladoria':
        return True
    if db is None:
        return servico.responsavel_id == user.id and pessoa_visivel(
            models.ServicoParticipante(usuario_id=user.id), servico, user)
    return any(pessoa_visivel(p, servico, user) for p in participantes(db, servico))


def obter_servico(db: Session, id_servico: int, user):
    servico = db.get(models.ServicoInterno, id_servico)
    if not servico or not visivel(servico, user, db):
        raise HTTPException(404, detail='Serviço não encontrado.')
    return servico


def evento(db, servico, autor, acao, observacao=''):
    db.add(models.ServicoEvento(
        servico_id=servico.id, autor_id=autor.id, autor_nome=autor.nome,
        acao=acao, observacao=observacao.strip(), criado_em=agora(),
    ))


def notificar(db, destino_id, servico, mensagem):
    if destino_id:
        db.add(models.ServicoAviso(
            usuario_id=destino_id, servico_id=servico.id,
            mensagem=mensagem, criado_em=agora(),
        ))


def publicar_para(db, servico, pessoas, mensagem, excluir=None):
    ids = {p.usuario_id for p in pessoas if p.usuario_id and p.usuario_id != excluir}
    for uid in ids:
        notificar(db, uid, servico, mensagem)


def derivar_status(pessoas):
    executores = [p for p in pessoas if p.papel == 'executor']
    fiscais = [p for p in pessoas if p.papel == 'fiscalizador']
    if not executores:
        return STATUS_NOVO
    if not all(p.status == STATUS_EXEC_CONCLUIDO for p in executores):
        if any(p.status in (STATUS_EXECUCAO, STATUS_EXEC_CONCLUIDO) for p in executores):
            return STATUS_EXECUCAO
        if all(p.status != STATUS_NOVO for p in executores):
            return STATUS_CIENTE
        return STATUS_NOVO
    if fiscais and not all(p.status == STATUS_FISC_APROVADO for p in fiscais):
        return STATUS_FISCALIZACAO
    return STATUS_VALIDACAO


def serializar(servico, db=None, user=None):
    pessoas = participantes(db, servico) if db else []
    executores = [p for p in pessoas if p.papel == 'executor']
    fiscais = [p for p in pessoas if p.papel == 'fiscalizador']
    acoes = []
    if user is not None:
        me = next((p for p in pessoas if p.usuario_id == user.id), None)
        if me and me.status == STATUS_NOVO and servico.status != STATUS_FECHADO:
            acoes.append('confirmar')
        if me and me.papel == 'executor':
            if me.status == STATUS_CIENTE and servico.status != STATUS_FECHADO:
                acoes.append('iniciar')
            if me.status == STATUS_EXECUCAO and servico.status != STATUS_FECHADO:
                acoes.append('concluir')
        if me and me.papel == 'fiscalizador' and servico.status == STATUS_FISCALIZACAO and me.status == STATUS_CIENTE:
            acoes += ['validar', 'devolver']
        if user.perfil == 'Controladoria' and servico.status == STATUS_VALIDACAO:
            acoes += ['validar', 'devolver']
    return {
        'id': servico.id, 'condominio_id': servico.condominio_id,
        'condominio': servico.condominio_nome,
        'responsavel_id': servico.responsavel_id,
        'responsavel': servico.responsavel_nome,
        'executores': [{'usuario_id': p.usuario_id, 'nome': p.usuario_nome,
                        'status': p.status} for p in executores],
        'fiscalizadores': [{'usuario_id': p.usuario_id, 'nome': p.usuario_nome,
                            'status': p.status} for p in fiscais],
        'acoes_disponiveis': list(dict.fromkeys(acoes)),
        'criador_id': servico.criador_id, 'criador': servico.criador_nome,
        'titulo': servico.titulo, 'descricao': servico.descricao,
        'prioridade': servico.prioridade, 'prazo': servico.prazo.isoformat(),
        'status': servico.status,
        'criado_em': servico.criado_em.isoformat() if servico.criado_em else None,
        'atualizado_em': servico.atualizado_em.isoformat() if servico.atualizado_em else None,
        'atrasado': servico.status != STATUS_FECHADO and servico.prazo < hoje(),
    }


@router.get('/responsaveis')
def responsaveis(request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    if user.perfil != 'Controladoria':
        raise HTTPException(403, detail='Somente Controladoria.')
    pessoas = db.query(models.Usuario).filter(
        models.Usuario.perfil.in_(['Checklist', 'Solicitante', 'Controladoria'])
    ).order_by(models.Usuario.nome).all()
    return [{'id': p.id, 'nome': p.nome, 'perfil': p.perfil,
             'condominio_id': p.condominio_id} for p in pessoas]


@router.get('')
def listar(request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    query = db.query(models.ServicoInterno)
    if user.perfil == 'Checklist' and not user.condominio_id:
        return []
    if user.perfil != 'Controladoria':
        subq = db.query(models.ServicoParticipante.servico_id).filter(
            models.ServicoParticipante.usuario_id == user.id
        )
        query = query.filter(or_(
            models.ServicoInterno.id.in_(subq),
            and_(models.ServicoInterno.responsavel_id == user.id,
                 ~models.ServicoInterno.id.in_(db.query(models.ServicoParticipante.servico_id)))
        ))
        if user.perfil == 'Checklist':
            query = query.filter(models.ServicoInterno.condominio_id == user.condominio_id)
    return [serializar(s, db, user) for s in query.order_by(models.ServicoInterno.id.desc()).limit(500).all()]


@router.post('', status_code=201)
def criar(dados: ServicoNovo, request: Request, db: Session = Depends(sessao)):
    autor = obter_usuario(request, db)
    if autor.perfil != 'Controladoria':
        raise HTTPException(403, detail='Somente Controladoria pode criar serviços.')
    cond = db.get(models.Condominio, dados.condominio_id)
    if not cond:
        raise HTTPException(400, detail='Condomínio inválido.')
    exec_ids = dados.executores_ids or ([dados.responsavel_id] if dados.responsavel_id else [])
    fiscais_ids = dados.fiscalizadores_ids
    if not exec_ids or len(exec_ids) > 30 or len(fiscais_ids) > 30:
        raise HTTPException(400, detail='Selecione de 1 a 30 executores e até 30 fiscalizadores.')
    if any(type(uid) is not int or uid <= 0 for uid in exec_ids + fiscais_ids):
        raise HTTPException(400, detail='Participante inválido.')
    if len(set(exec_ids)) != len(exec_ids) or len(set(fiscais_ids)) != len(fiscais_ids):
        raise HTTPException(400, detail='Participantes duplicados não são permitidos.')
    if set(exec_ids) & set(fiscais_ids):
        raise HTTPException(400, detail='Uma pessoa não pode executar e fiscalizar a mesma tarefa.')
    ids = set(exec_ids + fiscais_ids)
    pessoas = db.query(models.Usuario).filter(models.Usuario.id.in_(ids)).all()
    por_id = {p.id: p for p in pessoas}
    if len(por_id) != len(ids):
        raise HTTPException(400, detail='Um dos participantes não foi encontrado.')
    for pessoa in pessoas:
        if pessoa.perfil not in ('Checklist', 'Solicitante', 'Controladoria'):
            raise HTTPException(400, detail='Participante sem perfil permitido.')
        if pessoa.perfil == 'Checklist' and pessoa.condominio_id != cond.id:
            raise HTTPException(400, detail=f'{pessoa.nome} não está vinculado ao condomínio escolhido.')
    if dados.prazo < hoje():
        raise HTTPException(400, detail='O prazo não pode estar no passado.')
    if len(dados.titulo.strip()) < 4 or len(dados.descricao.strip()) < 5:
        raise HTTPException(400, detail='Título ou descrição inválida.')

    principal = por_id[exec_ids[0]]
    servico = models.ServicoInterno(
        condominio_id=cond.id, condominio_nome=cond.nome,
        responsavel_id=principal.id, responsavel_nome=principal.nome,
        criador_id=autor.id, criador_nome=autor.nome,
        titulo=dados.titulo.strip(), descricao=dados.descricao.strip(),
        prioridade=dados.prioridade, prazo=dados.prazo,
        status=STATUS_NOVO, criado_em=agora(), atualizado_em=agora(),
    )
    db.add(servico)
    db.flush()
    for papel, lista in (('executor', exec_ids), ('fiscalizador', fiscais_ids)):
        for uid in lista:
            pessoa = por_id[uid]
            db.add(models.ServicoParticipante(
                servico_id=servico.id, usuario_id=uid,
                usuario_nome=pessoa.nome, papel=papel, status=STATUS_NOVO,
            ))
            notificar(db, uid, servico, (
                f'Nova tarefa para executar: {servico.titulo}' if papel == 'executor'
                else f'Você foi designado para fiscalizar: {servico.titulo}'
            ))
    evento(db, servico, autor, 'criado',
           f'Executores: {", ".join(por_id[i].nome for i in exec_ids)}; '
           f'Fiscalizadores: {", ".join(por_id[i].nome for i in fiscais_ids) or "nenhum"}')
    db.commit()
    db.refresh(servico)
    return serializar(servico, db, autor)


@router.get('/notificacoes')
def notificacoes(request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    avisos = db.query(models.ServicoAviso).filter(
        models.ServicoAviso.usuario_id == user.id
    ).order_by(models.ServicoAviso.id.desc()).limit(100).all()
    return [{'id': a.id, 'servico_id': a.servico_id, 'mensagem': a.mensagem,
             'lida': bool(a.lida_em), 'criada_em': a.criado_em.isoformat()} for a in avisos]


@router.post('/notificacoes/{aviso_id}/ler')
def ler_aviso(aviso_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    aviso = db.query(models.ServicoAviso).filter(
        models.ServicoAviso.id == aviso_id, models.ServicoAviso.usuario_id == user.id
    ).first()
    if not aviso:
        raise HTTPException(404, detail='Aviso não encontrado.')
    if aviso.lida_em is None:
        aviso.lida_em = agora()
        db.commit()
    return {'ok': True}


@router.get('/{servico_id}')
def detalhes(servico_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    return serializar(obter_servico(db, servico_id, user), db, user)


@router.get('/{servico_id}/historico')
def historico(servico_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    obter_servico(db, servico_id, user)
    eventos = db.query(models.ServicoEvento).filter(
        models.ServicoEvento.servico_id == servico_id
    ).order_by(models.ServicoEvento.id.asc()).all()
    return [{'id': e.id, 'acao': e.acao, 'autor': e.autor_nome,
             'observacao': e.observacao, 'data': e.criado_em.isoformat()} for e in eventos]


@router.post('/{servico_id}/acoes')
def atualizar(servico_id: int, dados: ServicoAcao, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    servico = db.query(models.ServicoInterno).filter(
        models.ServicoInterno.id == servico_id
    ).with_for_update().first()
    if not servico or not visivel(servico, user, db):
        raise HTTPException(404, detail='Serviço não encontrado.')
    garantir_participantes_legados(db, servico)
    pessoas = participantes(db, servico)
    eu = next((p for p in pessoas if p.usuario_id == user.id), None)
    acao = dados.acao
    observacao = dados.observacao.strip()
    if acao in ('concluir', 'devolver') and len(observacao) < 10:
        raise HTTPException(400, detail='Informe uma observação com pelo menos 10 caracteres.')
    if servico.status == STATUS_FECHADO:
        raise HTTPException(409, detail='Serviço já concluído.')

    if acao == 'confirmar':
        if not eu:
            raise HTTPException(403, detail='Você não está designado a este serviço.')
        if eu.status != STATUS_NOVO:
            raise HTTPException(409, detail='Recebimento já confirmado ou indisponível.')
        eu.status = STATUS_CIENTE
        eu.confirmado_em = agora()
        evento(db, servico, user, 'confirmar', f'{eu.papel}: confirmou recebimento. {observacao}')
    elif acao == 'iniciar':
        if not eu or eu.papel != 'executor':
            raise HTTPException(403, detail='Somente executor designado pode iniciar.')
        if eu.status != STATUS_CIENTE:
            raise HTTPException(409, detail='Confirme o recebimento antes de iniciar.')
        eu.status = STATUS_EXECUCAO
        eu.iniciado_em = agora()
        evento(db, servico, user, 'iniciar', observacao)
    elif acao == 'concluir':
        if not eu or eu.papel != 'executor':
            raise HTTPException(403, detail='Somente executor designado pode concluir.')
        if eu.status != STATUS_EXECUCAO:
            raise HTTPException(409, detail='Inicie sua etapa antes de concluir.')
        eu.status = STATUS_EXEC_CONCLUIDO
        eu.concluido_em = agora()
        evento(db, servico, user, 'concluir', observacao)
    elif acao == 'validar':
        if servico.status == STATUS_FISCALIZACAO:
            if not eu or eu.papel != 'fiscalizador':
                raise HTTPException(403, detail='Somente fiscalizador designado pode fiscalizar.')
            if eu.status != STATUS_CIENTE:
                raise HTTPException(409, detail='Confirme ciência antes de fiscalizar.')
            eu.status = STATUS_FISC_APROVADO
            eu.validado_em = agora()
            evento(db, servico, user, 'fiscalizar', observacao or 'Fiscalização aprovada.')
        elif servico.status == STATUS_VALIDACAO:
            if user.perfil != 'Controladoria':
                raise HTTPException(403, detail='Somente Controladoria pode encerrar.')
            servico.status = STATUS_FECHADO
            evento(db, servico, user, 'validar', observacao or 'Serviço validado pela Controladoria.')
            publicar_para(db, servico, pessoas, f'Serviço validado: {servico.titulo}', excluir=user.id)
        else:
            raise HTTPException(409, detail='Ainda não é possível validar o serviço.')
    elif acao == 'devolver':
        pode_fiscalizar = servico.status == STATUS_FISCALIZACAO and eu and eu.papel == 'fiscalizador' and eu.status == STATUS_CIENTE
        pode_gestor = servico.status == STATUS_VALIDACAO and user.perfil == 'Controladoria'
        if not (pode_fiscalizar or pode_gestor):
            raise HTTPException(403, detail='Você não pode devolver neste momento.')
        for p in pessoas:
            if p.papel == 'executor':
                p.status = STATUS_EXECUCAO
                p.concluido_em = None
            elif p.papel == 'fiscalizador' and p.status == STATUS_FISC_APROVADO:
                p.status = STATUS_CIENTE
                p.validado_em = None
        evento(db, servico, user, 'devolver', observacao)
        publicar_para(db, servico, [p for p in pessoas if p.papel == 'executor'],
                      f'Serviço devolvido para ajustes: {servico.titulo}')
    else:
        raise HTTPException(400, detail='Ação desconhecida.')

    if servico.status != STATUS_FECHADO:
        anterior = servico.status
        servico.status = derivar_status(pessoas)
        if anterior != servico.status:
            if servico.status == STATUS_FISCALIZACAO:
                publicar_para(db, servico, [p for p in pessoas if p.papel == 'fiscalizador'],
                              f'Serviço pronto para fiscalização: {servico.titulo}')
            elif servico.status == STATUS_VALIDACAO:
                notificar(db, servico.criador_id, servico,
                          f'Serviço aguardando validação final: {servico.titulo}')
    servico.atualizado_em = agora()
    db.commit()
    db.refresh(servico)
    return serializar(servico, db, user)


# ------------------------------------------------------------------------
# Evidências fotográficas: autenticação e escopo por condomínio em cada rota.
# Sem URLs públicas nem dados de imagem no JSON de listagem.
# ------------------------------------------------------------------------
def _foto_info(foto):
    return {
        'id': foto.id, 'servico_id': foto.servico_id,
        'etapa': foto.etapa, 'legenda': foto.legenda,
        'autor': foto.autor_nome, 'tamanho_bytes': foto.tamanho_bytes,
        'criada_em': foto.criado_em.isoformat() if foto.criado_em else None,
    }


@router.get('/{servico_id}/fotos')
def listar_fotos(servico_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    obter_servico(db, servico_id, user)
    registros = (db.query(models.ServicoFoto)
                 .filter(models.ServicoFoto.servico_id == servico_id)
                 .order_by(models.ServicoFoto.id.desc()).all())
    return [_foto_info(f) for f in registros]


@router.post('/{servico_id}/fotos', status_code=201)
async def adicionar_foto(
    servico_id: int, request: Request,
    foto: UploadFile = File(...), etapa: str = Form('durante'),
    legenda: str = Form(''), db: Session = Depends(sessao),
):
    user = obter_usuario(request, db)
    # Lock da tarefa impede que dois uploads concorrentes ignorem o limite.
    servico = (db.query(models.ServicoInterno)
               .filter(models.ServicoInterno.id == servico_id)
               .with_for_update().first())
    if not servico or not visivel(servico, user, db):
        raise HTTPException(404, detail='Serviço não encontrado.')
    if servico.status == STATUS_FECHADO:
        raise HTTPException(409, detail='Serviço encerrado. Fotos não podem ser acrescentadas.')
    if etapa not in ETAPAS_FOTOS:
        raise HTTPException(400, detail='Etapa da fotografia inválida.')
    if len(legenda.strip()) > 250:
        raise HTTPException(400, detail='Legenda muito longa (máximo 250 caracteres).')
    total = db.query(models.ServicoFoto).filter(models.ServicoFoto.servico_id == servico_id).count()
    if total >= MAX_FOTOS_SERVICO:
        raise HTTPException(409, detail=f'Limite de {MAX_FOTOS_SERVICO} fotos por serviço atingido.')
    if foto.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(415, detail='Envie JPG, PNG ou WebP.')
    bruto = await foto.read(MAX_FOTO_ENTRADA + 1)
    if not bruto or len(bruto) > MAX_FOTO_ENTRADA:
        raise HTTPException(413, detail='A foto deve ter no máximo 4 MB.')
    try:
        with Image.open(BytesIO(bruto)) as imagem:
            if imagem.format not in ('JPEG', 'PNG', 'WEBP'):
                raise HTTPException(415, detail='Formato de imagem inválido.')
            imagem = ImageOps.exif_transpose(imagem)
            imagem.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            imagem = imagem.convert('RGB')
            saida = BytesIO()
            imagem.save(saida, format='WEBP', quality=78, method=4)
            conteudo = saida.getvalue()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(415, detail='Imagem inválida ou corrompida.')
    if len(conteudo) > 2 * 1024 * 1024:
        raise HTTPException(413, detail='Imagem compactada muito grande.')
    registro = models.ServicoFoto(
        servico_id=servico_id, usuario_id=user.id, autor_nome=user.nome,
        etapa=etapa, legenda=legenda.strip(),
        nome_original=(foto.filename or 'foto')[:250],
        imagem=conteudo, tamanho_bytes=len(conteudo), criado_em=agora(),
    )
    db.add(registro)
    evento(db, servico, user, 'foto_anexada',
           f'Foto de {etapa} anexada.' + (f' {legenda.strip()}' if legenda.strip() else ''))
    servico.atualizado_em = agora()
    db.commit()
    db.refresh(registro)
    return _foto_info(registro)


@router.get('/{servico_id}/fotos/{foto_id}')
def visualizar_foto(servico_id: int, foto_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    obter_servico(db, servico_id, user)
    registro = (db.query(models.ServicoFoto)
                .filter(models.ServicoFoto.id == foto_id,
                        models.ServicoFoto.servico_id == servico_id).first())
    if not registro:
        raise HTTPException(404, detail='Foto não encontrada.')
    return Response(content=registro.imagem, media_type='image/webp', headers={
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f'inline; filename="servico-{servico_id}-foto-{foto_id}.webp"',
    })
