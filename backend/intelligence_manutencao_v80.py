# -*- coding: utf-8 -*-
"""Investigacao de planejamento e recorrencia, sem efeitos externos."""
from collections import defaultdict, Counter
from datetime import date, timedelta
from custos_importacao_v77 import chave_nome
from intelligence_motor_v78 import analisar_historico_privado


def _data(s):
    if not isinstance(s, str) or len(s) != 10:
        raise ValueError('Data invalida.')
    d = date.fromisoformat(s)
    if d.isoformat() != s:
        raise ValueError('Data invalida.')
    return d


def _opcional(s):
    if s in ('', None):
        return None, 'ausente'
    try:
        return _data(s), 'valida'
    except (ValueError, TypeError):
        return None, 'invalida'


def investigar_manutencao_v80(registros, prazos, data_referencia, competencia, categorias):
    """Datas de agenda atuais e despesas ate competencia sao eixos distintos.

    Recorrencia descritiva: >=3 datas distintas em >=2 competencias, nos
    seis meses ate a competencia. Nao identifica ativos por texto.
    """
    hoje = _data(data_referencia)
    fim = _data(competencia + '-01')
    if fim > hoje.replace(day=1):
        raise ValueError('Competencia futura.')
    idx = fim.year * 12 + fim.month - 1 - 5
    ano, mes = divmod(idx, 12)
    inicio = date(ano, mes + 1, 1)
    analisar_historico_privado(registros)
    if not isinstance(categorias, (list, tuple, set, frozenset)) or not categorias or any(not isinstance(c,str) or not chave_nome(c) for c in categorias):
        raise ValueError('Categorias de manutencao explicitas obrigatorias.')
    cats = {chave_nome(c) for c in categorias}
    if not isinstance(prazos,(list,tuple)) or len(prazos)>50000:
        raise ValueError('Agenda invalida.')
    grupos = defaultdict(list)
    chaves = set()
    for r in prazos:
        if not isinstance(r,dict) or not {'condominio_id','linha','nome','periodicidade','ultima','proxima'} <= r.keys():
            raise ValueError('Campos de agenda ausentes.')
        cid, linha = r['condominio_id'], r['linha']
        if type(cid) is not int or cid<=0 or type(linha) is not int or linha<=1 or (cid,linha) in chaves:
            raise ValueError('Identificador de agenda invalido ou duplicado.')
        chaves.add((cid,linha))
        if not isinstance(r['nome'],str) or not chave_nome(r['nome']) or not isinstance(r['periodicidade'],str):
            raise ValueError('Nome ou periodicidade invalida.')
        grupos[(cid,chave_nome(r['nome']))].append(r)
    agenda=[]; cont=Counter()
    for (cid,nome),rs in sorted(grupos.items()):
        for r in sorted(rs,key=lambda x:x['linha']):
            ultima,u = _opcional(r['ultima']); proxima,p = _opcional(r['proxima'])
            dias = None
            if len(rs)>1:
                estado='identificacao_ambigua'; acao='Identificar separadamente as atividades antes de decidir.'
            elif u=='invalida' or p=='invalida' or (ultima and ultima>hoje) or (ultima and proxima and proxima<=ultima):
                estado='datas_inconsistentes'; acao='Corrigir ou confirmar datas de agenda antes de priorizar.'
            elif proxima is None:
                estado='sem_proxima_data'; acao='Obter proxima data documentada; nao presumir atraso.'
            else:
                dias=(proxima-hoje).days
                if dias<0:
                    estado='prazo_registrado_vencido'; acao='Confirmar execucao ou priorizar agendamento; prazo vencido nao prova servico nao realizado.'
                elif dias<=30:
                    estado='prazo_em_30_dias'; acao='Priorizar planejamento da atividade e confirmar disponibilidade.'
                else:
                    estado='prazo_futuro'; acao='Acompanhar planejamento.'
            cont[estado]+=1
            agenda.append({'condominio_id':cid,'nome':nome,'estado':estado,'dias_ate_prazo':dias,'evidencia':dict(r),'acao':acao})
    agenda.sort(key=lambda x:(x['dias_ate_prazo'] is None,x['dias_ate_prazo'] or 0,x['condominio_id'],x['nome'],x['evidencia']['linha']))
    despesas=defaultdict(list)
    for r in registros:
        if inicio<=r.competencia<=fim and r.data_original<=hoje and r.categoria_chave in cats and r.valor_centavos>0:
            despesas[(r.condominio_id,r.categoria_chave,chave_nome(r.descricao))].append(r)
    recorrencias=[]
    for (cid,cat,desc),rs in sorted(despesas.items()):
        datas={r.data_original for r in rs}; meses={r.competencia for r in rs}
        if len(datas)<3 or len(meses)<2:
            continue
        evidencia=[{'id':r.id_origem,'data':r.data_original.isoformat(),'valor_centavos':r.valor_centavos,'hash':r.hash_conteudo} for r in sorted(rs,key=lambda r:(r.data_original,r.id_origem))]
        recorrencias.append({'condominio_id':cid,'categoria':cat,'descricao':desc,'registros':len(rs),'datas_distintas':len(datas),'meses_observados':len(meses),'total_centavos':sum(e['valor_centavos'] for e in evidencia),'evidencias':evidencia,'estado':'recorrencia_de_descricao_nao_de_ativo','acao':'Identificar ativo e natureza dos gastos; avaliar plano preventivo somente com evidencias tecnicas.'})
    recorrencias.sort(key=lambda r:(-r['total_centavos'],r['condominio_id'],r['categoria'],r['descricao']))
    return {'data_agenda':hoje.isoformat(),'competencia_financeira':competencia,'inicio_financeiro':inicio.isoformat(),'categorias':sorted(cats),'agenda':agenda,'contagem_agenda':dict(sorted(cont.items())),'recorrencias':recorrencias,'total_recorrencias_centavos':sum(r['total_centavos'] for r in recorrencias),'limites':['Agenda lida de valores salvos; formulas nao recalculadas.','Prazo vencido nao comprova falta de execucao. Periodicidade textual nao recalcula datas.','Descricoes iguais nao identificam equipamento nem falha tecnica.','Totais de recorrencia sao gastos observados, nao economia nem impacto adicional. Nao somar aos alertas anteriores.','Cobertura financeira mensal nao confirmada. Nenhum corte de manutencao ou substituicao recomendado sem avaliacao tecnica.']}
