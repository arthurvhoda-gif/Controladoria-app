"""V7.5: Web Push de tarefas, fila segura e recuperacao oportunista.

Enfileiramento e despacho exigem flags independentes; ao despachar, usuario,
condominio e dispositivo sao revalidados. Uma thread daemon recupera falhas
a cada minuto enquanto a instancia esta ativa. Em hospedagem gratuita, uma
instancia adormecida nao executa o recuperador: nao prometer entrega 24/7.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread

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
INTERVALO_RECUPERACAO_SEGUNDOS = 60
_RECUPERADOR_PARAR = Event()
_RECUPERADOR_LOCK = Lock()
_recuperador_thread = None
logger = logging.getLogger('haize.push.recuperacao')


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
                        data=json.dumps({
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


def _executar_recuperacao_periodica():
    """Verifica fila existente, sem criar notificacoes nem expor assinaturas."""
    if not despacho_habilitado():
        return
    try:
        # Uma unica iteracao e limitada a 10 avisos (processar_fila).
        processar_fila()
    except Exception:
        # Falha do banco/provedor nao deve derrubar a API ou vazar endpoints.
        logger.warning('Falha ao recuperar fila Push; sera reavaliada no proximo ciclo.')


def _ciclo_recuperacao():
    """Primeiro ciclo no startup e, depois, a cada minuto enquanto vivo."""
    while not _RECUPERADOR_PARAR.is_set():
        _executar_recuperacao_periodica()
        if _RECUPERADOR_PARAR.wait(INTERVALO_RECUPERACAO_SEGUNDOS):
            break


def iniciar_recuperador():
    """Ativa somente se a fila e o despacho estiverem explicitamente ativos."""
    global _recuperador_thread
    if not despacho_habilitado():
        return False
    with _RECUPERADOR_LOCK:
        if _recuperador_thread is not None and _recuperador_thread.is_alive():
            return True
        _RECUPERADOR_PARAR.clear()
        _recuperador_thread = Thread(
            target=_ciclo_recuperacao, name='haize-push-retry', daemon=True
        )
        _recuperador_thread.start()
    return True


def parar_recuperador():
    """Permite encerramento limpo no shutdown, sem bloquear o servidor."""
    _RECUPERADOR_PARAR.set()
