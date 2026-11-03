# -*- coding: utf-8 -*-
"""Analise historica conservadora V6.6 - SOMENTE LEITURA.

Nao permite envio nem cancelamento. 'nao_comprovado' nao comprova vigencia.
Necessita historico COMPLETO da tarefa e evento de origem rastreado.
"""

ORIGENS = {
    "nova_tarefa": {"criado"},
    "designacao_fiscal": {"criado"},
    "pronto_fiscalizacao": {"concluir"},
    "devolucao": {"devolver"},
    "validacao_final": {"concluir", "fiscalizar"},
    "servico_validado": {"validar"},
}
ACOES_CONHECIDAS = {"criado", "confirmar", "iniciar", "concluir", "fiscalizar", "devolver", "validar"}


def resultado(situacao, motivo, evento_superador=None):
    return {"situacao": situacao, "motivo": motivo, "evento_superador": evento_superador}


def avaliar_historico(*, tipo, evento_origem_id, destinatario_id, servico_id, eventos):
    """Diagnostico parcial conservador, sem qualquer decisao de envio.

    `eventos` deve conter historico COMPLETO do servico, do mesmo banco e
    ordenado logicamente por IDs. Resultados nao comprovam entrega nem
    permitem envio. Ausencia de evidencias nao significa que aviso e atual.
    """
    if tipo not in ORIGENS:
        return resultado("revisar", "Tipo de aviso desconhecido.")
    if not all(type(x) is int and x > 0 for x in (evento_origem_id, destinatario_id, servico_id)):
        return resultado("revisar", "Identificadores ausentes ou invalidos; aviso legado pode nao ter origem.")
    if not isinstance(eventos, (list, tuple)) or not eventos:
        return resultado("revisar", "Historico ausente ou incompleto.")

    ids = set()
    for ev in eventos:
        if (not isinstance(ev, dict) or
                type(ev.get("id")) is not int or ev["id"] <= 0 or ev["id"] in ids or
                type(ev.get("servico_id")) is not int or ev["servico_id"] != servico_id or
                not isinstance(ev.get("acao"), str) or not ev["acao"] or
                (ev.get("autor_id") is not None and
                 (type(ev["autor_id"]) is not int or ev["autor_id"] <= 0))):
            return resultado("revisar", "Historico inconsistente; nao inferir vigencia.")
        ids.add(ev["id"])

    origem = next((ev for ev in eventos if ev["id"] == evento_origem_id), None)
    if origem is None:
        return resultado("revisar", "Evento de origem nao encontrado no historico.")
    if origem["acao"] not in ORIGENS[tipo]:
        return resultado("revisar", "A acao do evento de origem nao corresponde ao tipo do aviso.")
    if tipo == "servico_validado":
        return resultado("informativo", "Aviso historico de encerramento; revisar criterios antes de envio.")

    posteriores = sorted((ev for ev in eventos if ev["id"] > evento_origem_id), key=lambda ev: ev["id"])

    for ev in posteriores:
        acao = ev["acao"]
        autor = ev["autor_id"]
        causa = None
        if tipo in ("nova_tarefa", "designacao_fiscal"):
            if autor == destinatario_id and acao == "confirmar":
                causa = "O destinatario confirmou ciencia apos a origem."
            elif tipo == "nova_tarefa" and autor == destinatario_id and acao in ("iniciar", "concluir"):
                causa = "O executor avancou a tarefa apos a designacao."
            elif tipo == "designacao_fiscal" and autor == destinatario_id and acao == "fiscalizar":
                causa = "O fiscalizador ja fiscalizou apos a designacao."
        elif tipo == "devolucao":
            if autor == destinatario_id and acao == "concluir":
                causa = "O executor concluiu os ajustes apos esta devolucao."
        elif tipo == "pronto_fiscalizacao":
            if acao == "devolver":
                causa = "Houve devolucao posterior a este aviso de fiscalizacao."
            elif autor == destinatario_id and acao == "fiscalizar":
                causa = "Este fiscalizador ja avaliou a etapa correspondente."
        elif tipo == "validacao_final":
            if acao in ("validar", "devolver"):
                causa = "O ciclo foi validado ou devolvido apos este aviso."
        if causa:
            return resultado("superado", causa, ev["id"])

    # Historico sem evento decisivo nao prova que o destinatario ainda precisa agir.
    if any(ev["acao"] not in ACOES_CONHECIDAS for ev in posteriores):
        return resultado("revisar", "Existem acoes desconhecidas posteriores; analise manual necessaria.")
    if any(ev["autor_id"] is None and ev["acao"] in ("confirmar", "iniciar", "concluir", "fiscalizar") for ev in posteriores):
        return resultado("revisar", "Autor de uma acao posterior indisponivel; analise manual necessaria.")
    return resultado("nao_comprovado", "Nenhum evento posterior decisivo identificado; nao autoriza envio.")
