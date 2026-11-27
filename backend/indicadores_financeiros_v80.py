# -*- coding: utf-8 -*-
"""Indicadores financeiros em centavos; sem I/O."""
FORMAS = ('pix', 'boleto', 'transferencia', 'credito', 'debito', 'dinheiro', 'outros')


def indicadores_pagamento(aprovado, realizado, pago):
    if type(pago) is not int or any(v is not None and (type(v) is not int or v < 0) for v in (aprovado, realizado)):
        raise ValueError('Valores monetarios invalidos')
    saldo = max(0, realizado-pago) if realizado is not None else None
    excedente_final = max(0, pago-realizado) if realizado is not None else None
    economia = aprovado-realizado if aprovado is not None and realizado is not None else None
    if realizado is None:
        progresso = None
        situacao = 'valor_final_indefinido'
    else:
        progresso = min(10000, max(0, pago*10000//realizado)) if realizado else 10000
        situacao = 'divergencia_financeira' if pago > realizado else 'quitado' if pago == realizado else 'parcial' if pago > 0 else 'pendente'
    if aprovado is not None and pago > aprovado:
        situacao = 'sobrepagamento'
    return dict(saldo_a_pagar_centavos=saldo, excedente_realizado_centavos=excedente_final,
                diferenca_orcamento_centavos=economia, progresso_pagamento_pontos_base=progresso,
                situacao_pagamento=situacao)
