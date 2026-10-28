"""Central de serviços: fluxo auditável e isolado das solicitações de compra.

Notificações desta versão são internas ao aplicativo. Integração WhatsApp exige
implantação separada de API oficial, opt-in e política de envio.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from database import SessionLocal

router = APIRouter(prefix='/servicos', tags=['Serviços internos'])

STATUS_NOVO = 'Aguardando ciência'
STATUS_CIENTE = 'Recebido'
STATUS_EXECUCAO = 'Em andamento'
STATUS_VALIDACAO = 'Aguardando validação'
STATUS_FECHADO = 'Concluído'
PRIORIDADES = ('Baixa', 'Normal', 'Alta', 'Urgente')


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
    responsavel_id: int = Field(gt=0)
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


def visivel(servico, user):
    if user.perfil == 'Controladoria':
        return True
    if servico.responsavel_id != user.id:
        return False
    if user.perfil == 'Checklist':
        return user.condominio_id is not None and servico.condominio_id == user.condominio_id
    return user.perfil == 'Solicitante'


def obter_servico(db: Session, id_servico: int, user):
    servico = db.get(models.ServicoInterno, id_servico)
    if not servico or not visivel(servico, user):
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


def serializar(servico):
    return {
        'id': servico.id, 'condominio_id': servico.condominio_id,
        'condominio': servico.condominio_nome,
        'responsavel_id': servico.responsavel_id,
        'responsavel': servico.responsavel_nome,
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
    if user.perfil == 'Checklist':
        if not user.condominio_id:
            return []
        query = query.filter(models.ServicoInterno.responsavel_id == user.id,
                             models.ServicoInterno.condominio_id == user.condominio_id)
    elif user.perfil != 'Controladoria':
        query = query.filter(models.ServicoInterno.responsavel_id == user.id)
    return [serializar(s) for s in query.order_by(models.ServicoInterno.id.desc()).limit(500).all()]


@router.post('', status_code=201)
def criar(dados: ServicoNovo, request: Request, db: Session = Depends(sessao)):
    autor = obter_usuario(request, db)
    if autor.perfil != 'Controladoria':
        raise HTTPException(403, detail='Somente Controladoria pode criar serviços.')
    cond = db.get(models.Condominio, dados.condominio_id)
    destino = db.get(models.Usuario, dados.responsavel_id)
    if not cond:
        raise HTTPException(400, detail='Condomínio inválido.')
    if not destino or destino.perfil not in ('Checklist', 'Solicitante', 'Controladoria'):
        raise HTTPException(400, detail='Responsável inválido.')
    if destino.perfil == 'Checklist' and destino.condominio_id != cond.id:
        raise HTTPException(400, detail='Zelador não está vinculado ao condomínio escolhido.')
    if dados.prazo < hoje():
        raise HTTPException(400, detail='O prazo não pode estar no passado.')
    if len(dados.titulo.strip()) < 4 or len(dados.descricao.strip()) < 5:
        raise HTTPException(400, detail='Título ou descrição inválida.')
    servico = models.ServicoInterno(
        condominio_id=cond.id, condominio_nome=cond.nome,
        responsavel_id=destino.id, responsavel_nome=destino.nome,
        criador_id=autor.id, criador_nome=autor.nome,
        titulo=dados.titulo.strip(), descricao=dados.descricao.strip(),
        prioridade=dados.prioridade, prazo=dados.prazo,
        status=STATUS_NOVO, criado_em=agora(), atualizado_em=agora(),
    )
    db.add(servico)
    db.flush()
    evento(db, servico, autor, 'criado', 'Serviço atribuído a ' + destino.nome)
    notificar(db, destino.id, servico, f'Nova tarefa: {servico.titulo}')
    db.commit()
    db.refresh(servico)
    return serializar(servico)


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
    aviso = db.query(models.ServicoAviso).filter(models.ServicoAviso.id == aviso_id,
                    models.ServicoAviso.usuario_id == user.id).first()
    if not aviso:
        raise HTTPException(404, detail='Aviso não encontrado.')
    if aviso.lida_em is None:
        aviso.lida_em = agora()
        db.commit()
    return {'ok': True}


@router.get('/{servico_id}')
def detalhes(servico_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    return serializar(obter_servico(db, servico_id, user))


@router.get('/{servico_id}/historico')
def historico(servico_id: int, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    obter_servico(db, servico_id, user)
    eventos = db.query(models.ServicoEvento).filter(models.ServicoEvento.servico_id == servico_id).order_by(models.ServicoEvento.id.asc()).all()
    return [{'id': e.id, 'acao': e.acao, 'autor': e.autor_nome,
             'observacao': e.observacao, 'data': e.criado_em.isoformat()} for e in eventos]


@router.post('/{servico_id}/acoes')
def atualizar(servico_id: int, dados: ServicoAcao, request: Request, db: Session = Depends(sessao)):
    user = obter_usuario(request, db)
    # Bloqueia a linha durante a transição, evitando duas atualizações concorrentes.
    servico = db.query(models.ServicoInterno).filter(
        models.ServicoInterno.id == servico_id
    ).with_for_update().first()
    if not servico or not visivel(servico, user):
        raise HTTPException(404, detail='Serviço não encontrado.')
    papel_gestor = user.perfil == 'Controladoria'
    regras = {
        'confirmar': (STATUS_NOVO, STATUS_CIENTE, not papel_gestor or user.id == servico.responsavel_id),
        'iniciar': (STATUS_CIENTE, STATUS_EXECUCAO, user.id == servico.responsavel_id),
        'concluir': (STATUS_EXECUCAO, STATUS_VALIDACAO, user.id == servico.responsavel_id),
        'validar': (STATUS_VALIDACAO, STATUS_FECHADO, papel_gestor),
        'devolver': (STATUS_VALIDACAO, STATUS_EXECUCAO, papel_gestor),
    }
    antes, depois, autorizado = regras[dados.acao]
    if not autorizado:
        raise HTTPException(403, detail='Você não pode executar esta ação.')
    if servico.status != antes:
        raise HTTPException(409, detail=f'Ação indisponível: status atual é {servico.status}.')
    observacao = dados.observacao.strip()
    if dados.acao in ('concluir', 'devolver') and len(observacao) < 10:
        raise HTTPException(400, detail='Informe uma observação com pelo menos 10 caracteres.')
    servico.status = depois
    servico.atualizado_em = agora()
    evento(db, servico, user, dados.acao, observacao)
    if dados.acao == 'concluir':
        notificar(db, servico.criador_id, servico, f'Serviço aguardando validação: {servico.titulo}')
    if dados.acao == 'devolver':
        notificar(db, servico.responsavel_id, servico, f'Serviço devolvido para ajustes: {servico.titulo}')
    if dados.acao == 'validar':
        notificar(db, servico.responsavel_id, servico, f'Serviço validado: {servico.titulo}')
    db.commit()
    db.refresh(servico)
    return serializar(servico)
