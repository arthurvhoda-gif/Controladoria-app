# -*- coding: utf-8 -*-
"""V6.7: SIMULADOR puro e conservador de pré-envio; NUNCA AUTORIZA ENVIOS.

Esta função não consulta banco, não bloqueia/cancela itens reais e não envia.
As informações precisam ser obtidas de uma leitura confiável e ATUAL da
mesma transação quando uma implementação futura for desenhada.

`nao_comprovado` do histórico NÃO prova que o aviso continua vigente.
Mesmo quando todas as entradas parecem regulares, a saída é apenas
`pendente_de_validacao_operacional` com `envio_autorizado=False`.
Não conectar este módulo a um despachante real de WhatsApp.
"""

SITUACOES = frozenset({
    "impedido", "revisar", "pendente_de_validacao_operacional",
})


def avaliar_preenvio(*, status_fila, consentimento, telefone_ativo,
                     usuario_ativo, destinatario_autorizado,
                     vinculos_consistentes, evento_origem_id,
                     diagnostico_atual, diagnostico_historico,
                     duplicidade_detectada):
    """Somente triagem. Nenhum resultado autoriza disparo de mensagem.

    Parâmetros booleanos são evidências fornecidas pelo chamador, NÃO
    verificações executadas aqui. Uma futura integração terá de validar
    identidade, escopo, preferências e deduplicação de forma atômica no DB.

    `vinculos_consistentes` significa que aviso, fila, destinatário,
    serviço e evento de origem foram conferidos quanto à integridade.
    """
    def resposta(situacao, motivo):
        return {"situacao": situacao, "motivo": motivo,
                "envio_autorizado": False}

    if status_fila not in ("preparada", "cancelada"):
        return resposta("revisar", "Status de fila desconhecido ou ausente.")
    if status_fila == "cancelada":
        return resposta("impedido", "Aviso já cancelado; não reconsiderar envio.")

    valores = {
        "consentimento": consentimento,
        "telefone_ativo": telefone_ativo,
        "usuario_ativo": usuario_ativo,
        "destinatario_autorizado": destinatario_autorizado,
        "vinculos_consistentes": vinculos_consistentes,
        "duplicidade_detectada": duplicidade_detectada,
    }
    # Primeiro, rejeitar entradas de tipo invalido. None representa
    # verificacao INDISPONIVEL (nunca uma aprovacao presumida).
    if any(valor is not None and type(valor) is not bool for valor in valores.values()):
        return resposta("revisar", "Uma verificação obrigatória tem tipo inválido.")

    # Um bloqueio COMPROVADO deve continuar visivel mesmo quando outras
    # verificacoes ainda nao estao disponiveis. Nunca libera para envio.
    for campo, motivo in (
        ("consentimento", "Sem consentimento individual ativo."),
        ("telefone_ativo", "Telefone não está ativo ou cadastrado."),
        ("usuario_ativo", "Usuário de destino não está ativo."),
        ("destinatario_autorizado", "Destinatário sem acesso atual à tarefa."),
        ("vinculos_consistentes", "Vínculos de fila, aviso, tarefa ou evento inconsistentes."),
    ):
        if valores[campo] is False:
            return resposta("impedido", motivo)
    if duplicidade_detectada is True:
        return resposta("impedido", "Possível duplicidade detectada para este aviso/evento.")

    if diagnostico_historico == "superado":
        return resposta("impedido", "Histórico indica aviso superado por acontecimento posterior.")
    if diagnostico_atual == "possivelmente_desatualizado":
        return resposta("impedido", "Situação atual sugere aviso ultrapassado.")

    if type(evento_origem_id) is not int or evento_origem_id <= 0:
        return resposta("revisar", "Aviso sem evento de origem válido; pode ser legado.")
    if diagnostico_historico not in ("superado", "nao_comprovado", "revisar", "informativo"):
        return resposta("revisar", "Diagnóstico histórico ausente ou desconhecido.")
    if diagnostico_atual not in ("coerente", "possivelmente_desatualizado", "revisar", "informativo"):
        return resposta("revisar", "Diagnóstico atual ausente ou desconhecido.")
    if diagnostico_historico in ("revisar", "informativo"):
        return resposta("revisar", "Histórico não permite conclusão operacional segura.")
    if diagnostico_atual != "coerente":
        return resposta("revisar", "Situação atual não comprova necessidade de ação.")

    # Sem verificacoes confiaveis, exigir revisao — NUNCA inventar True.
    ausentes = [nome for nome, valor in valores.items() if valor is None]
    if ausentes:
        return resposta("revisar", "Verificações não comprovadas: " +
                        ", ".join(ausentes) + ". Nenhum envio autorizado.")

    # 'nao_comprovado' + 'coerente': apenas passou por filtros de triagem;
    # NÃO significa aptidão, autorização ou liberação para disparar.
    return resposta(
        "pendente_de_validacao_operacional",
        "Nenhum impedimento detectado na simulação; envio NÃO autorizado. "
        "Exige nova verificação transacional, política de prazo e "
        "controles do provedor em uma etapa futura.",
    )
