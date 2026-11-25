# -*- coding: utf-8 -*-
"""Reconciliação privada de solicitações e livro financeiro V8.0.

Função pura sobre um snapshot atual (não reconstrói períodos históricos).
Adaptador SQLite exclusivamente em memória, para homologação fictícia.
Não importa main, não cria tabelas, não envia dados e não acessa produção.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3

STATUS_PAGAVEIS = frozenset(('Aprovada', 'Em execução', 'Finalizada'))
MAX_CENTAVOS = 99_999_999_999_999
LIMITE_SOLICITACOES = 50_000
LIMITE_LANCAMENTOS = 200_000


class ErroReconciliacao(ValueError):
    """Snapshot inválido: não emitir conclusões financeiras a partir dele."""


def _id(valor):
    if type(valor) is not int or valor <= 0:
        raise ErroReconciliacao('Identificador inválido.')
    return valor


def _valor_livro(valor):
    if type(valor) is not int or not 0 < valor <= MAX_CENTAVOS:
        raise ErroReconciliacao('Valor inválido no livro financeiro.')
    return valor


def _valor_legado(valor):
    # Colunas Float do aplicativo são aproximações, não valores pagos.
    # Zero/NULL não confirmam uma aprovação ou realização positiva.
    if valor is None:
        return None
    if type(valor) not in (int, float, str, Decimal):
        raise ErroReconciliacao('Valor legado inválido.')
    try:
        d = Decimal(str(valor))
        if not d.is_finite() or d < 0 or d > Decimal(MAX_CENTAVOS) / 100:
            raise ErroReconciliacao('Valor legado fora do limite.')
        return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise ErroReconciliacao('Valor legado inválido.') from exc


def _indexar(linhas, limite):
    if not isinstance(linhas, (list, tuple)) or len(linhas) > limite:
        raise ErroReconciliacao('Snapshot fora dos limites de homologação.')
    indice = {}
    for linha in linhas:
        if not isinstance(linha, dict):
            raise ErroReconciliacao('Registro inválido.')
        chave = _id(linha.get('id'))
        if chave in indice:
            raise ErroReconciliacao('ID duplicado no snapshot.')
        indice[chave] = linha
    return indice


def reconciliar_financeiro_v80(solicitacoes, lancamentos):
    """Reconcilia o livro completo e valores atuais de cada solicitação.

    Recusa lotes estruturalmente inconsistentes. Alertas são independentes,
    podem se sobrepor e nunca são somados como economia. Não calcula atrasos
    de pagamento sem vencimentos nem classifica estorno como economia.
    """
    sol = _indexar(solicitacoes, LIMITE_SOLICITACOES)
    livro = _indexar(lancamentos, LIMITE_LANCAMENTOS)
    grupos = defaultdict(list)
    estornados = set()
    metadados = {}
    for sid, s in sol.items():
        if not {'condominio_id', 'status', 'valor_aprovado', 'valor_realizado'} <= s.keys():
            raise ErroReconciliacao('Campos obrigatórios ausentes na solicitação.')
        cid = s['condominio_id']
        if cid is not None:
            _id(cid)
        status = s['status']
        if not isinstance(status, str) or not status.strip():
            raise ErroReconciliacao('Status inválido.')
        metadados[sid] = (cid, status, _valor_legado(s['valor_aprovado']),
                          _valor_legado(s['valor_realizado']) if status == 'Finalizada' else None)
    for lid, lan in livro.items():
        if not {'solicitacao_id', 'tipo', 'valor_centavos', 'estorno_de_id'} <= lan.keys():
            raise ErroReconciliacao('Campos obrigatórios ausentes no livro.')
        sid = _id(lan['solicitacao_id'])
        if sid not in sol:
            raise ErroReconciliacao('Lançamento sem solicitação correspondente.')
        valor = _valor_livro(lan['valor_centavos'])
        ref = lan['estorno_de_id']
        if lan['tipo'] == 'pagamento':
            if ref is not None:
                raise ErroReconciliacao('Pagamento com referência de estorno.')
        elif lan['tipo'] == 'estorno':
            original = livro.get(_id(ref))
            if (original is None or original.get('tipo') != 'pagamento'
                or original.get('solicitacao_id') != sid
                or original.get('valor_centavos') != valor or ref in estornados):
                raise ErroReconciliacao('Estorno sem vínculo íntegro e único.')
            estornados.add(ref)
        else:
            raise ErroReconciliacao('Tipo de lançamento desconhecido.')
        grupos[sid].append({'id': lid, 'tipo': lan['tipo'], 'valor_centavos': valor,
                            'estorno_de_id': ref})
    casos = []
    for sid in sorted(sol):
        cid, status, aprovado, realizado = metadados[sid]
        evidencias = sorted(grupos[sid], key=lambda x: x['id'])
        bruto = sum(x['valor_centavos'] for x in evidencias if x['tipo'] == 'pagamento')
        estorno = sum(x['valor_centavos'] for x in evidencias if x['tipo'] == 'estorno')
        liquido = bruto - estorno
        if liquido < 0:
            raise ErroReconciliacao('Livro líquido negativo.')
        alertas = []
        def alerta(codigo, valor, acao):
            alertas.append({'codigo': codigo, 'diferenca_centavos': valor, 'acao': acao})
        if cid is None:
            alerta('condominio_nao_vinculado', None, 'Regularizar o vínculo antes de atribuir valores a um condomínio.')
        if liquido > 0 and status not in STATUS_PAGAVEIS:
            alerta('pagamento_em_status_nao_pagavel', None, 'Conciliar o status atual com o histórico de aprovação e estornos; não presumir o status na data do pagamento.')
        if liquido > 0 and not aprovado:
            alerta('pagamento_sem_aprovacao_positiva', None, 'Confirmar o valor aprovado no histórico; não calcular excedente sobre base desconhecida.')
        if aprovado and liquido > aprovado:
            alerta('pago_acima_do_aprovado', liquido-aprovado, 'Comparar comprovantes e autorização complementar; se confirmado, solicitar regularização ou estorno autorizado.')
        if status == 'Finalizada':
            if not realizado:
                alerta('realizado_nao_confirmado', None, 'Confirmar o valor final antes de comparar com pagamentos.')
            if aprovado and realizado and realizado > aprovado:
                alerta('realizado_acima_do_aprovado', realizado-aprovado, 'Verificar aprovação de escopo adicional ou alteração de orçamento.')
            if realizado and liquido > realizado:
                alerta('pago_acima_do_realizado', liquido-realizado, 'Conciliar comprovantes com o valor final e eventuais créditos.')
            if realizado and liquido < realizado:
                alerta('saldo_a_conciliar_com_realizado', realizado-liquido, 'Conferir parcelas, créditos e vencimentos; diferença não comprova atraso.')
        casos.append({'solicitacao_id': sid, 'condominio_id': cid, 'status_atual': status,
                      'aprovado_centavos_aproximado': aprovado,
                      'realizado_centavos_aproximado': realizado,
                      'pagamentos_brutos_centavos': bruto, 'estornos_centavos': estorno,
                      'pago_liquido_centavos': liquido, 'evidencias': evidencias, 'alertas': alertas})
    totais = {'solicitacoes': len(casos), 'lancamentos': len(livro),
              'casos_com_alertas': sum(bool(c['alertas']) for c in casos),
              'alertas': sum(len(c['alertas']) for c in casos),
              'pagamentos_brutos_centavos': sum(c['pagamentos_brutos_centavos'] for c in casos),
              'estornos_centavos': sum(c['estornos_centavos'] for c in casos),
              'pago_liquido_centavos': sum(c['pago_liquido_centavos'] for c in casos)}
    if (totais['pagamentos_brutos_centavos'] != sum(l['valor_centavos'] for l in livro.values() if l['tipo'] == 'pagamento')
        or totais['estornos_centavos'] != sum(l['valor_centavos'] for l in livro.values() if l['tipo'] == 'estorno')
        or totais['pago_liquido_centavos'] != totais['pagamentos_brutos_centavos'] - totais['estornos_centavos']):
        raise ErroReconciliacao('Falha na conferência global do livro.')
    return {'escopo': 'snapshot_atual_compras_financeiro', 'totais': totais, 'casos': casos,
            'ressalvas': ['Valores aprovados/realizados são campos legados aproximados.',
                          'Alertas podem se sobrepor. Não somar como prejuízo ou economia.',
                          'Sem vencimentos e histórico de autorizações, não concluir atraso ou pagamento indevido.',
                          'Não misturar o livro financeiro com despesas das planilhas.']}


def ensaiar_fonte_sqlite_v80(conexao):
    """Consulta colunas reais do schema em SQLite em memória, sem escrita.

    A conexão é fornecida pelo teste, com dados fictícios já confirmados.
    Rejeita arquivos de banco, conexões com anexos e transações pendentes.
    """
    if not isinstance(conexao, sqlite3.Connection) or conexao.in_transaction:
        raise ErroReconciliacao('Conexão de ensaio inválida ou com transação pendente.')
    bancos = conexao.execute('PRAGMA database_list').fetchall()
    if len(bancos) != 1 or tuple(bancos[0])[1:] != ('main', ''):
        raise ErroReconciliacao('Somente SQLite em memória, sem anexos.')
    def consultar(sql, limite):
        cursor = conexao.execute(sql, (limite+1,))
        colunas = [c[0] for c in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    try:
        conexao.execute('BEGIN')
        solicitacoes = consultar('SELECT id, condominio_id, status, valor_aprovado, valor_realizado FROM solicitacoes ORDER BY id LIMIT ?', LIMITE_SOLICITACOES)
        lancamentos = consultar('SELECT id, solicitacao_id, tipo, valor_centavos, estorno_de_id FROM financeiro_lancamentos ORDER BY id LIMIT ?', LIMITE_LANCAMENTOS)
        return reconciliar_financeiro_v80(solicitacoes, lancamentos)
    finally:
        if conexao.in_transaction:
            conexao.rollback()
