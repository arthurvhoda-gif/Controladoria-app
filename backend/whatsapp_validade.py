"""Diagnóstico OFFLINE de vigência de avisos da Central de Serviços (V6.4).

Função PURA: não consulta banco, não grava status, não cancela mensagens,
não faz chamadas de rede e não envia WhatsApp.

IMPORTANTE: o mesmo status pode reaparecer depois de uma devolução. Por isso
um aviso que parece coerente com os estados ATUAIS não é necessariamente
o aviso mais recente. Sem um identificador do evento/ciclo de origem, não
se deve decidir envio nem cancelamento automático com base neste resultado.
"""

STATUS_NOVO = 'Aguardando ciência'
STATUS_CIENTE = 'Recebido'
STATUS_EXECUCAO = 'Em andamento'
STATUS_FISCALIZACAO = 'Aguardando fiscalização'
STATUS_VALIDACAO = 'Aguardando validação'
STATUS_FECHADO = 'Concluído'
STATUS_EXEC_CONCLUIDO = 'Finalizado'
STATUS_FISC_APROVADO = 'Aprovado'

# Resultado possível: coerente, possivelmente_desatualizado, informativo, revisar.
# Nenhuma dessas classificações autoriza um envio automático.
def avaliar_vigencia(evento, status_servico, *, papel=None,
                     status_participante=None, destinatario_eh_criador=False):
    """Avalia indícios atuais; NÃO determina historicamente a validade do aviso.

    Retorna dict com situacao e motivo, exclusivamente para diagnóstico.
    Dados ausentes ou contraditórios retornam 'revisar' (falha conservadora).
    """
    def resultado(situacao, motivo):
        return {'situacao': situacao, 'motivo': motivo}

    if not isinstance(evento, str) or not isinstance(status_servico, str):
        return resultado('revisar', 'Dados do aviso ou da tarefa insuficientes.')

    if evento == 'servico_validado':
        if status_servico == STATUS_FECHADO:
            return resultado('informativo', 'Encerramento: comunicação histórica, sem ação do destinatário.')
        return resultado('revisar', 'Aviso de encerramento com tarefa não encerrada.')

    if evento == 'validacao_final':
        if not destinatario_eh_criador:
            return resultado('revisar', 'Verificar quem é o destinatário da validação final.')
        if status_servico == STATUS_VALIDACAO:
            return resultado('coerente', 'Tarefa aguarda validação final; confirmar evento/ciclo antes de enviar.')
        return resultado('possivelmente_desatualizado', 'Tarefa não está aguardando validação final.')

    if evento not in ('nova_tarefa', 'designacao_fiscal', 'pronto_fiscalizacao', 'devolucao'):
        return resultado('revisar', 'Evento desconhecido ou não classificado.')
    if not papel or not status_participante:
        return resultado('revisar', 'Participação individual indisponível; pode ser serviço legado.')

    papel_esperado = 'fiscalizador' if evento in ('designacao_fiscal', 'pronto_fiscalizacao') else 'executor'
    if papel != papel_esperado:
        return resultado('revisar', 'O papel do destinatário não corresponde ao tipo de aviso.')

    if evento in ('nova_tarefa', 'designacao_fiscal'):
        if status_participante == STATUS_NOVO and status_servico != STATUS_FECHADO:
            return resultado('coerente', 'Destinatário ainda não confirmou ciência.')
        return resultado('possivelmente_desatualizado', 'Ciência possivelmente já confirmada ou tarefa encerrada.')

    if evento == 'pronto_fiscalizacao':
        if status_servico == STATUS_FISCALIZACAO and status_participante in (STATUS_NOVO, STATUS_CIENTE):
            return resultado('coerente', 'Tarefa aguarda fiscalização e destinatário não aprovou ainda.')
        return resultado('possivelmente_desatualizado', 'Tarefa ou fiscalizador não estão pendentes de fiscalização.')

    if evento == 'devolucao':
        if status_servico == STATUS_EXECUCAO and status_participante == STATUS_EXECUCAO:
            return resultado('coerente', 'Executor está na etapa de ajustes/execução.')
        return resultado('possivelmente_desatualizado', 'Executor ou tarefa já mudou da etapa de ajustes.')

    return resultado('revisar', 'Não foi possível classificar.')
