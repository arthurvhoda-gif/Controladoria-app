# -*- coding: utf-8 -*-
"""V7.3 — conferência transacional e conservadora da fila de WhatsApp.

SOMENTE LEITURA, SEM DESPACHANTE. Adquire bloqueios PostgreSQL sobre fila,
titular da conta, preferência e serviço; nunca altera status, cria mensagens,
consulta provedor nem autoriza envio.

Esta conferência é uma fotografia transitória. Mesmo uma resposta sem
impedimentos NÃO deve ser usada para disparar mensagens; uma integração
futura exigirá o processo completo de reserva, cobrança, idempotência e
callbacks aprovados, num fluxo transacional próprio.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from whatsapp_historico import avaliar_historico
from whatsapp_validade import avaliar_vigencia
from servicos_api import pessoa_visivel, visivel

TIPOS = frozenset({
    'nova_tarefa', 'designacao_fiscal', 'pronto_fiscalizacao',
    'devolucao', 'validacao_final', 'servico_validado',
})
PAPEIS = {
    'nova_tarefa': 'executor',
    'devolucao': 'executor',
    'designacao_fiscal': 'fiscalizador',
    'pronto_fiscalizacao': 'fiscalizador',
}
MAX_EVENTOS_CONFERENCIA = 10000


def verificar_fila_transacional(db: Session, fila_id: int):
    """Analisa, com locks em uma única sessão, sem realizar qualquer escrita.

    CHECK do usuário precede CHECK das preferências, na mesma ordem utilizada
    por contato_bloqueado_para_edicao(). Isso evita consentimento baseado em
    telefone revogado durante a verificação, no PostgreSQL.
    """
    fila = (
        db.query(models.FilaWhatsApp)
        .filter(models.FilaWhatsApp.id == fila_id)
        .with_for_update()
        .one_or_none()
    )
    if fila is None:
        raise HTTPException(404, detail='Aviso preparado não encontrado.')

    impedimentos = []
    pendencias = []

    def impedir(texto):
        impedimentos.append(texto)

    def revisar(texto):
        pendencias.append(texto)

    if fila.status != 'preparada':
        impedir('Fila não está preparada: item cancelado ou em estado desconhecido.')

    destinatario = (
        db.query(models.Usuario)
        .filter(models.Usuario.id == fila.usuario_id)
        .with_for_update()
        .one_or_none()
    )
    if destinatario is None:
        impedir('Destinatário não existe mais.')
    preferencia = (
        db.query(models.PreferenciaWhatsApp)
        .filter(models.PreferenciaWhatsApp.usuario_id == fila.usuario_id)
        .with_for_update()
        .one_or_none()
    )
    if not preferencia or not preferencia.telefone or not preferencia.consentimento:
        impedir('Sem número cadastrado e autorização individual válidos.')
    elif preferencia.consentido_em is None:
        revisar('Autorização antiga sem data auditável; não comprova opt-in.')

    aviso = db.get(models.ServicoAviso, fila.aviso_id)
    servico = (
        db.query(models.ServicoInterno)
        .filter(models.ServicoInterno.id == fila.servico_id)
        .with_for_update()
        .one_or_none()
    )
    if aviso is None or servico is None:
        impedir('Referência de aviso ou serviço ausente.')
    elif (aviso.id != fila.aviso_id or aviso.usuario_id != fila.usuario_id or
          aviso.servico_id != fila.servico_id):
        impedir('Fila e aviso pertencem a destinatários ou serviços diferentes.')

    if aviso and aviso.tipo_evento not in TIPOS:
        revisar('Aviso legado ou de tipo desconhecido; classificação textual não é suficiente.')
    if aviso and (type(aviso.evento_id) is not int or aviso.evento_id <= 0):
        revisar('Aviso sem evento de origem identificado.')
    if servico and destinatario:
        if not visivel(servico, destinatario, db):
            impedir('Destinatário perdeu acesso atual ao serviço ou condomínio.')
        if destinatario.perfil not in ('Controladoria', 'Checklist', 'Solicitante'):
            impedir('Perfil do destinatário não recebe tarefas internas.')

    if preferencia and preferencia.telefone:
        total_telefone = db.query(func.count(models.PreferenciaWhatsApp.usuario_id)).filter(
            models.PreferenciaWhatsApp.telefone == preferencia.telefone
        ).scalar()
        if total_telefone != 1:
            impedir('Número de WhatsApp repetido entre cadastros; envio bloqueado.')
    else:
        total_telefone = None

    # A restrição UNIQUE do aviso existe em bases migradas; verificar também
    # múltiplas filas distintas para mesmo destinatário e mesmo evento.
    if aviso:
        total_fila = db.query(func.count(models.FilaWhatsApp.id)).filter(
            models.FilaWhatsApp.aviso_id == aviso.id
        ).scalar()
        if total_fila != 1:
            impedir('Aviso presente mais de uma vez na fila.')
        if type(aviso.evento_id) is int and aviso.evento_id > 0:
            total_ciclo = (
                db.query(func.count(models.FilaWhatsApp.id))
                .join(models.ServicoAviso,
                      models.FilaWhatsApp.aviso_id == models.ServicoAviso.id)
                .filter(
                    models.ServicoAviso.evento_id == aviso.evento_id,
                    models.ServicoAviso.usuario_id == aviso.usuario_id,
                    models.ServicoAviso.tipo_evento == aviso.tipo_evento,
                ).scalar()
            )
            if total_ciclo != 1:
                impedir('Existem múltiplos avisos do mesmo evento ao destinatário.')

    participante = None
    diagnostico_atual = 'revisar'
    diagnostico_historico = 'revisar'
    if aviso and servico and destinatario and aviso.tipo_evento in TIPOS:
        papel_esperado = PAPEIS.get(aviso.tipo_evento)
        if papel_esperado is not None:
            participante = db.query(models.ServicoParticipante).filter(
                models.ServicoParticipante.servico_id == servico.id,
                models.ServicoParticipante.usuario_id == destinatario.id,
                models.ServicoParticipante.papel == papel_esperado,
            ).with_for_update().one_or_none()
            if participante is None:
                impedir('Destinatário não tem designação atual no papel exigido.')
        elif aviso.tipo_evento == 'servico_validado':
            participante = db.query(models.ServicoParticipante).filter(
                models.ServicoParticipante.servico_id == servico.id,
                models.ServicoParticipante.usuario_id == destinatario.id,
            ).with_for_update().one_or_none()
            if participante is None:
                impedir('Notificação de encerramento sem participação atual.')
        elif aviso.tipo_evento == 'validacao_final':
            if (destinatario.id != servico.criador_id or
                    destinatario.perfil != 'Controladoria'):
                impedir('Validação final endereçada a destinatário sem essa atribuição.')

        if participante and not pessoa_visivel(participante, servico, destinatario):
            impedir('Participação não autoriza visualizar o serviço neste condomínio.')

        estado = avaliar_vigencia(
            aviso.tipo_evento, servico.status,
            papel=participante.papel if participante else None,
            status_participante=participante.status if participante else None,
            destinatario_eh_criador=servico.criador_id == destinatario.id,
        )
        diagnostico_atual = estado['situacao']
        if diagnostico_atual == 'possivelmente_desatualizado':
            impedir('Aviso superado pelo estado atual da tarefa.')
        elif diagnostico_atual != 'coerente':
            revisar('Estado atual não comprova a necessidade do aviso.')

        registros = (
            db.query(models.ServicoEvento)
            .filter(models.ServicoEvento.servico_id == servico.id)
            .order_by(models.ServicoEvento.id.asc())
            .limit(MAX_EVENTOS_CONFERENCIA + 1)
            .all()
        )
        if len(registros) > MAX_EVENTOS_CONFERENCIA:
            revisar('Histórico longo demais para conferência integral; revisão obrigatória.')
        else:
            eventos = [{
                'id': e.id, 'servico_id': e.servico_id,
                'acao': e.acao, 'autor_id': e.autor_id,
            } for e in registros]
            historico = avaliar_historico(
                tipo=aviso.tipo_evento, evento_origem_id=aviso.evento_id,
                destinatario_id=destinatario.id, servico_id=servico.id,
                eventos=eventos,
            )
            diagnostico_historico = historico['situacao']
            if diagnostico_historico == 'superado':
                impedir('Evento de origem superado no histórico da tarefa.')
            elif diagnostico_historico != 'nao_comprovado':
                revisar('Histórico não comprova a vigência do evento.')

    # Não há campo de "usuário ativo" nem comprovação do provedor sobre
    # linha WhatsApp ativa. Não presumir nenhum desses dados como True.
    revisar('Atividade da conta e do número no provedor não comprovadas.')
    revisar('Despacho oficial e política de custos não estão habilitados.')

    instante = datetime.now(timezone.utc).isoformat()
    return {
        'fila_id': fila.id,
        'servico_id': fila.servico_id,
        'status_fila': fila.status,
        'situacao': 'impedido' if impedimentos else 'revisar',
        'impedimentos': impedimentos,
        'pendencias': pendencias,
        'diagnostico_atual': diagnostico_atual,
        'diagnostico_historico': diagnostico_historico,
        'validado_em': instante,
        'conferencia_transacional': True,
        'envio_autorizado': False,
        'envios_ativos': False,
    }
