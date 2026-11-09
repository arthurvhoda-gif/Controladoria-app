"""V7.5: Web Push de eventos de tarefas, com fila segura e gatilhos desligados.

A fila somente e gravada quando PUSH_AUTO_QUEUE_ENABLED=true.
Nenhum pedido HTTP externo e feito sem PUSH_AUTO_DISPATCH_ENABLED=true.
Tanto dispositivos quanto avisos passam por nova autorizacao no despacho.
O processamento e oportunista apos commit; nao substituir por garantia
de entrega em segundo plano sem gatilho cron gratuito e monitoramento.
"""
import os
from datetime import datetime, timedelta, timezone

from pywebpush import webpush, WebPushException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from push_api import _validar_endpoint, _modo_teste_habilitado


TIPOS_PERMITIDOS = frozenset({
    'nova_tarefa', 'designacao_fiscal', 'pronto_fiscalizacao',
    'devolucao', 'validacao_final', 'servico_validado',
})
LIMITE_BATCH = 10
MAX_TENTATIVAS = 3
ESPERA_RETRY = timedelta(minutes=2)


def fila_habilitada():
    return os.getenv('PUSH_AUTO_QUEUE_ENABLED', '').strip() == 'true'


def despacho_habilitado():
    return (
        fila_habilitada()
        and os.getenv('PUSH_AUTO_DISPATCH_ENABLED', '').strip() == 'true'
        and _modo_teste_habilitado()
    )


def enfileirar_aviso(db: Session, aviso: models.ServicoAviso):
    """Enfileira na MESMA transacao que o aviso de servico.

    Nao escreve fila para mensagens legadas sem evento/tipo explicitos.
    A ausenca de aparelhos instalados nao cria pendencias retroativas.
    """
    if (not fila_habilitada() or aviso.tipo_evento not in TIPOS_PERMITIDOS
            or aviso.evento_id is None):
        return 0
    db.flush()
    aparelhos = db.query(models.PushDispositivo.id).filter(
        models.PushDispositivo.usuario_id == aviso.usuario_id
    ).limit(5).all()
    for (aparelho_id,) in aparelhos:
        db.add(models.PushAvisoFila(
            aviso_id=aviso.id, dispositivo_id=aparelho_id,
            usuario_id=aviso.usuario_id, servico_id=aviso.servico_id,
            evento_id=aviso.evento_id, tipo_evento=aviso.tipo_evento,
            status='pendente', tentativas=0,
        ))
    return len(aparelhos)


def _pode_despachar(db: Session, item: models.PushAvisoFila):
    """Verifica acesso ATUAL, inclusive transferencia de aparelho e condominio."""
    from servicos_api import _avisos_visiveis
    usuario = db.get(models.Usuario, item.usuario_id)
    aparelho = db.get(models.PushDispositivo, item.dispositivo_id)
    if not usuario or not aparelho or aparelho.usuario_id != item.usuario_id:
        return None
    aviso = _avisos_visiveis(db, usuario).filter(
        models.ServicoAviso.id == item.aviso_id,
    ).first()
    if (not aviso or aviso.servico_id != item.servico_id
            or aviso.evento_id is None or aviso.evento_id != item.evento_id
            or aviso.tipo_evento != item.tipo_evento
            or item.tipo_evento not in TIPOS_PERMITIDOS):
        return None
    return aparelho


def processar_fila(limite=LIMITE_BATCH):
    """Tenta entregar pendencias elegiveis; nao roda caso gate esteja off.

    Contrato conservador: um item por aviso+dispositivo; sem expor chaves
    em logs e sem disparar avisos antigos quando fila nao estava habilitada.
    O aceite do provedor nao prova exibicao no celular.
    """
    if not despacho_habilitado():
        return {'ativo': False, 'processados': 0, 'aceitos': 0, 'falhas': 0, 'descartados': 0}
    agora = datetime.now(timezone.utc)
    total = min(max(int(limite), 1), LIMITE_BATCH)
    resumo = {'ativo': True, 'processados': 0, 'aceitos': 0, 'falhas': 0, 'descartados': 0}
    for _ in range(total):
        with SessionLocal() as db:
            # skip_locked no Postgres previne dois workers simultaneos
            # processarem o mesmo aviso. Stale reclamado apos 2 minutos.
            antigos = agora - ESPERA_RETRY
            item = db.query(models.PushAvisoFila).filter(or_(
                models.PushAvisoFila.status == 'pendente',
                and_(models.PushAvisoFila.status.in_(['falha', 'processando']),
                     models.PushAvisoFila.tentativas < MAX_TENTATIVAS,
                     models.PushAvisoFila.atualizado_em <= antigos),
            )).order_by(models.PushAvisoFila.id.asc()).with_for_update(skip_locked=True).first()
            if item is None:
                break
            item.status = 'processando'
            item.tentativas += 1
            item.atualizado_em = datetime.now(timezone.utc)
            db.commit()
            item_id = item.id

            # Reconsulta apos commit para verificar autorizacao vigente.
            item = db.get(models.PushAvisoFila, item_id)
            if item is None:
                continue
            aparelho = _pode_despachar(db, item)
            if aparelho is None:
                item.status = 'descartado'
                resumo['descartados'] += 1
            else:
                try:
                    _validar_endpoint(aparelho.endpoint)
                    webpush(
                        subscription_info={
                            'endpoint': aparelho.endpoint,
                            'keys': {'p256dh': aparelho.p256dh, 'auth': aparelho.chave_auth},
                        },
                        data=__import__('json').dumps({
                            'tipo': 'haize-servico-v1',
                            'servico_id': item.servico_id,
                            'evento_id': item.evento_id,
                        }),
                        vapid_private_key=os.getenv('VAPID_PRIVATE_KEY', '').strip(),
                        vapid_claims={'sub': 'mailto:app1haize@gmail.com'},
                        ttl=300, timeout=6,
                    )
                    item.status = 'aceito'
                    resumo['aceitos'] += 1
                except WebPushException as erro:
                    item.status = 'falha'
                    resumo['falhas'] += 1
                    if erro.status_code in (404, 410):
                        # O endpoint nao e mais valido. Cascade remove itens.
                        db.delete(aparelho)
                except Exception:
                    # Erros nao incluem credenciais nem endpoint.
                    item.status = 'falha'
                    resumo['falhas'] += 1
            item.atualizado_em = datetime.now(timezone.utc)
            db.commit()
            resumo['processados'] += 1
    return resumo
