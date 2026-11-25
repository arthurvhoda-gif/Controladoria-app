# -*- coding: utf-8 -*-
"""Investigação operacional de snapshot atual, sem banco, rede ou escrita.

Datas de checklist são locais (São Paulo). O chamador deve fornecer uma
extração completa e consistente na data de referência. Não reconstrói o passado.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

NOVO = 'Aguardando ciência'
CIENTE = 'Recebido'
EXECUCAO = 'Em andamento'
FISCALIZACAO = 'Aguardando fiscalização'
VALIDACAO = 'Aguardando validação'
FECHADO = 'Concluído'
FINALIZADO = 'Finalizado'
APROVADO = 'Aprovado'
ESTADOS = (NOVO, CIENTE, EXECUCAO, FISCALIZACAO, VALIDACAO, FECHADO)
ETAPAS = {NOVO: 'ciencia', CIENTE: 'inicio', EXECUCAO: 'execucao',
          FISCALIZACAO: 'fiscalizacao', VALIDACAO: 'validacao'}
ACOES = {'ciencia': 'Confirmar recebimento e disponibilidade de execução.',
         'inicio': 'Definir início e remover impedimentos de execução.',
         'execucao': 'Priorizar conclusão e verificar impedimentos registrados.',
         'fiscalizacao': 'Priorizar fiscalização e conferir evidências de execução.',
         'validacao': 'Priorizar decisão de validação da Controladoria.'}

class ErroOperacional(ValueError):
    pass


def _id(v):
    if type(v) is not int or v <= 0:
        raise ErroOperacional('Identificador inválido.')
    return v


def _indice(linhas, campos):
    if not isinstance(linhas, (tuple, list)) or len(linhas) > 200_000:
        raise ErroOperacional('Snapshot inválido ou fora do limite.')
    idx = {}
    for r in linhas:
        if not isinstance(r, dict) or not set(campos) <= r.keys():
            raise ErroOperacional('Campos obrigatórios ausentes.')
        k = _id(r['id'])
        if k in idx:
            raise ErroOperacional('ID duplicado na fonte.')
        idx[k] = r
    return idx


def _data(v):
    try:
        if type(v) is not str or len(v) != 10:
            raise ValueError()
        d = date.fromisoformat(v)
        if d.isoformat() != v:
            raise ValueError()
        return d
    except ValueError as e:
        raise ErroOperacional('Data inválida.') from e


def _instante(v):
    try:
        if type(v) is not str or len(v) < 19:
            raise ValueError()
        t = datetime.fromisoformat(v)
        if t.tzinfo is not None:
            raise ValueError()
        return t
    except ValueError as e:
        raise ErroOperacional('Data de vistoria local inválida.') from e


def _derivar(ps):
    ex = [p['status'] for p in ps if p['papel'] == 'executor']
    fi = [p['status'] for p in ps if p['papel'] == 'fiscalizador']
    if not ex:
        return None
    if not all(s == FINALIZADO for s in ex):
        if any(s in (EXECUCAO, FINALIZADO) for s in ex):
            return EXECUCAO
        return CIENTE if all(s != NOVO for s in ex) else NOVO
    return FISCALIZACAO if fi and not all(s == APROVADO for s in fi) else VALIDACAO


def investigar_operacao_v80(servicos, participantes, itens, execucoes, data_referencia):
    """Recebe dados projetados das quatro tabelas, com IDs reais da mesma extração.

    Sem histórico de transições não mede tempo em cada etapa nem atraso de
    serviços concluídos. Recorrência: >=2 registros não conformes do mesmo
    item nos últimos 90 dias, com último registro não conforme.
    """
    hoje = _data(data_referencia)
    inicio = hoje - timedelta(days=89)
    ss = _indice(servicos, ('id','condominio_id','status','prazo','prioridade'))
    pp = _indice(participantes, ('id','servico_id','papel','status'))
    ii = _indice(itens, ('id','condominio_id'))
    ee = _indice(execucoes, ('id','item_id','status_conformidade','data_execucao'))
    por_servico = defaultdict(list)
    por_item = defaultdict(list)
    for p in pp.values():
        if _id(p['servico_id']) not in ss:
            raise ErroOperacional('Participante sem serviço.')
        papel = p['papel']
        permitidos = { 'executor': (NOVO,CIENTE,EXECUCAO,FINALIZADO),
                       'fiscalizador': (NOVO,CIENTE,APROVADO) }
        if papel not in permitidos or p['status'] not in permitidos[papel]:
            raise ErroOperacional('Papel ou estado de participante inválido.')
        por_servico[p['servico_id']].append(p)
    for e in ee.values():
        if _id(e['item_id']) not in ii:
            raise ErroOperacional('Vistoria sem item correspondente.')
        t = _instante(e['data_execucao'])
        if t.date() > hoje:
            raise ErroOperacional('Vistoria posterior ao snapshot.')
        if e['status_conformidade'] not in ('Conforme','Não Conforme','Não conforme'):
            raise ErroOperacional('Estado de vistoria desconhecido.')
        por_item[e['item_id']].append((t,e))
    casos = []
    resumo = defaultdict(Counter)
    for sid,s in sorted(ss.items()):
        cid = _id(s['condominio_id']); prazo = _data(s['prazo'])
        estado = s['status']; prioridade = s['prioridade']
        if estado not in ESTADOS or prioridade not in ('Baixa','Normal','Alta','Urgente'):
            raise ErroOperacional('Estado ou prioridade de serviço desconhecido.')
        resumo[cid]['servicos'] += 1
        ps = sorted(por_servico[sid], key=lambda p:p['id'])
        derivado = _derivar(ps)
        divergente = (estado != FECHADO and derivado is not None and estado != derivado) or (estado == FECHADO and derivado not in (None, VALIDACAO))
        if derivado is None:
            resumo[cid]['servicos_sem_base_participantes'] += 1
        atraso = estado != FECHADO and prazo < hoje
        if estado != FECHADO:
            resumo[cid]['servicos_abertos'] += 1
            resumo[cid]['etapa_'+ETAPAS[estado]] += 1
        if atraso:
            resumo[cid]['servicos_atrasados'] += 1
        if divergente:
            resumo[cid]['servicos_estado_divergente'] += 1
        if atraso or divergente or estado == VALIDACAO:
            etapa = ETAPAS.get(estado)
            casos.append({'tipo':'servico','condominio_id':cid,'id':sid,
                'estado':estado,'etapa_registrada':etapa,'estado_derivado':derivado,
                'divergencia_estado':divergente,'prazo':prazo.isoformat(),
                'dias_atraso':(hoje-prazo).days if atraso else 0,
                'prioridade_registrada':prioridade,
                'evidencias_participantes':[{'id':p['id'],'papel':p['papel'],'status':p['status']} for p in ps],
                'acao':'Reconciliar estados antes de decidir.' if divergente else ACOES[etapa]})
    for iid,item in sorted(ii.items()):
        cid = item['condominio_id']
        if cid is not None:
            _id(cid)
        resumo[cid]['itens_checklist'] += 1
        hist = sorted(por_item[iid],key=lambda x:(x[0],x[1]['id']))
        if not hist:
            resumo[cid]['itens_sem_vistoria'] += 1
            continue
        janela = [(t,e) for t,e in hist if t.date() >= inicio]
        if not janela:
            resumo[cid]['itens_sem_vistoria_90d'] += 1
            continue
        ult = janela[-1][0]
        simultaneos = [e for t,e in janela if t == ult]
        estados = {e['status_conformidade'] != 'Conforme' for e in simultaneos}
        if len(estados) != 1:
            resumo[cid]['itens_estado_ambiguo'] += 1
            casos.append({'tipo':'vistoria_estado_ambiguo','condominio_id':cid,'id':iid,
                'evidencias':[{'id':e['id'],'data':e['data_execucao'],'status':e['status_conformidade']} for e in simultaneos],
                'acao':'Reconciliar registros simultâneos antes de concluir.'})
            continue
        ncs = [(t,e) for t,e in janela if e['status_conformidade'] != 'Conforme']
        if not next(iter(estados)):
            continue
        # Registros simultâneos não contam como eventos distintos de recorrência.
        ocorrencias = len({t for t,e in ncs})
        recorrente = ocorrencias >= 2
        resumo[cid]['itens_ultimo_nao_conforme'] += 1
        if recorrente:
            resumo[cid]['itens_nao_conformes_recorrentes'] += 1
        casos.append({'tipo':'vistoria','condominio_id':cid,'id':iid,
            'recorrente':recorrente,'ocorrencias_distintas_90d':ocorrencias,
            'ultima_vistoria':ult.isoformat(),'evidencias':[{'id':e['id'],'data':e['data_execucao'],'status':e['status_conformidade']} for t,e in janela],
            'acao':'Priorizar diagnóstico técnico do item e avaliar recorrência.' if recorrente else 'Priorizar tratamento da não conformidade registrada.'})
    # Não somar serviços e vistorias como se fossem eventos independentes de risco.
    return {'data_referencia':hoje.isoformat(),'inicio_janela_vistorias':inicio.isoformat(),
            'condominios':[{'condominio_id':cid,**dict(sorted(c.items()))} for cid,c in sorted(resumo.items(),key=lambda x:(x[0] is None,x[0] or 0))],
            'casos':casos,'limites':['Snapshot atual; cobertura e data de extração dependem da fonte.',
            'Ausência de vistoria não comprova atraso sem agenda individual.',
            'Recorrência de registros não comprova falhas técnicas distintas.',
            'Sem vínculo explícito, não atribuir despesas a serviços ou vistorias.',
            'Sem histórico de transições, não estimar tempo em etapa ou atraso de serviço concluído.']}
