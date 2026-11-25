# -*- coding: utf-8 -*-
"""Análise de compras por coorte de criação, sobre snapshot atual.
Sem rede, banco, escrita, inferência de identidade ou preços unitários.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import unicodedata

MAX = 99_999_999_999_999

class ErroCompras(ValueError):
    pass


def _id(v):
    if type(v) is not int or v <= 0:
        raise ErroCompras('ID inválido.')
    return v


def _chave(v):
    if not isinstance(v, str) or len(v) > 10000:
        raise ErroCompras('Campo textual inválido.')
    return ' '.join(unicodedata.normalize('NFC', v).casefold().split())


def _centavos(v):
    if v is None:
        return None
    if type(v) not in (int, float, str, Decimal):
        raise ErroCompras('Valor legado inválido.')
    try:
        d = Decimal(str(v))
        if not d.is_finite() or not 0 <= d <= Decimal(MAX)/100:
            raise ErroCompras('Valor legado fora dos limites.')
        return int((d*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, OverflowError) as exc:
        raise ErroCompras('Valor legado inválido.') from exc


def _dia(v):
    try:
        if type(v) is not str or len(v)!=10:
            raise ValueError()
        d=date.fromisoformat(v)
        if d.isoformat()!=v:
            raise ValueError()
        return d
    except ValueError as exc:
        raise ErroCompras('Data inválida.') from exc


def _criacao(v):
    try:
        if type(v) is not str or len(v)!=19:
            raise ValueError()
        d=datetime.strptime(v,'%Y-%m-%d %H:%M:%S')
        if d.strftime('%Y-%m-%d %H:%M:%S')!=v:
            raise ValueError()
        return d.date()
    except ValueError as exc:
        raise ErroCompras('Data de criação inválida.') from exc


def investigar_compras_v80(solicitacoes, data_referencia, dias=180):
    """Considera solicitações hoje finalizadas e criadas na janela inclusiva.

    Valores realizados legados positivos: aproximação, não desembolso.
    Concentração por rótulo, não identidade jurídica. Agrupamentos textuais
    são pistas de planejamento, nunca prova de equivalência de escopo.
    """
    hoje=_dia(data_referencia)
    if type(dias) is not int or not 1<=dias<=366:
        raise ErroCompras('Janela inválida.')
    inicio=hoje-timedelta(days=dias-1)
    if not isinstance(solicitacoes,(list,tuple)) or len(solicitacoes)>50000:
        raise ErroCompras('Snapshot inválido.')
    vistos=set(); incluidos=[]; excluidos=[]; fora=0; nao_finalizados=0
    campos={'id','condominio_id','status','data','categoria','fornecedor','descricao','valor_aprovado','valor_realizado'}
    for r in solicitacoes:
        if not isinstance(r,dict) or not campos<=r.keys():
            raise ErroCompras('Campos obrigatórios ausentes.')
        sid=_id(r['id'])
        if sid in vistos:
            raise ErroCompras('ID repetido.')
        vistos.add(sid)
        cid=r['condominio_id']
        if cid is not None: _id(cid)
        criacao=_criacao(r['data'])
        if criacao>hoje: raise ErroCompras('Criação posterior à extração.')
        if not isinstance(r['status'],str) or not r['status'].strip():
            raise ErroCompras('Status inválido.')
        if criacao<inicio:
            fora+=1; continue
        if r['status']!='Finalizada':
            nao_finalizados+=1; continue
        cat, forn, desc=(_chave(r[k]) for k in ('categoria','fornecedor','descricao'))
        realizado=_centavos(r['valor_realizado']); aprovado=_centavos(r['valor_aprovado'])
        motivos=[]
        if cid is None: motivos.append('condominio_sem_vinculo')
        if not cat: motivos.append('categoria_ausente')
        if not realizado: motivos.append('realizado_sem_base_positiva')
        if motivos:
            excluidos.append({'id':sid,'motivos':motivos,'realizado_centavos':realizado}); continue
        incluidos.append({'id':sid,'condominio_id':cid,'data_criacao':criacao.isoformat(),
                          'categoria':cat,'rotulo_fornecedor':forn,'descricao_chave':desc,
                          'realizado_centavos_aproximado':realizado,'aprovado_centavos_aproximado':aprovado})
    incluidos.sort(key=lambda r:r['id']); excluidos.sort(key=lambda r:r['id'])
    grupos=defaultdict(list); demandas=defaultdict(list)
    for r in incluidos:
        grupos[(r['condominio_id'],r['categoria'])].append(r)
        if r['descricao_chave']:
            demandas[(r['categoria'],r['descricao_chave'])].append(r)
    concentracoes=[]
    for (cid,cat),rs in sorted(grupos.items()):
        total=sum(r['realizado_centavos_aproximado'] for r in rs)
        rotulos=defaultdict(list)
        for r in rs:
            if r['rotulo_fornecedor']: rotulos[r['rotulo_fornecedor']].append(r)
        ranking=[{'rotulo':k,'total_centavos':sum(r['realizado_centavos_aproximado'] for r in v),
                  'ids':[r['id'] for r in v]} for k,v in rotulos.items()]
        ranking.sort(key=lambda x:(-x['total_centavos'],x['rotulo']))
        conhecido=sum(x['total_centavos'] for x in ranking)
        # Denominador inclui rótulos desconhecidos: não inflar a concentração.
        maior=ranking[0]['total_centavos'] if ranking else 0
        sinal=len(rs)>=3 and total>=100000 and maior*100>=70*total
        concentracoes.append({'condominio_id':cid,'categoria':cat,'total_centavos':total,
            'sem_rotulo_centavos':total-conhecido,'quantidade':len(rs),'ranking_rotulos':ranking,
            'participacao_lider_pontos_base':maior*10000//total if ranking else None,
            'sinal_concentracao':sinal,'ids':[r['id'] for r in rs],
            'acao':'Avaliar condições e alternativas de fornecimento após confirmar identidades e escopos.' if sinal else None})
    recorrencias=[]
    for (cat,desc),rs in sorted(demandas.items()):
        datas={r['data_criacao'] for r in rs}; cids={r['condominio_id'] for r in rs}
        meses={d[:7] for d in datas}
        recorrente=len(datas)>=3 and len(meses)>=2
        compartilhada=len(cids)>=2
        if not (recorrente or compartilhada): continue
        recorrencias.append({'categoria':cat,'descricao_chave':desc,'condominios':sorted(cids),
            'datas_distintas':len(datas),'meses_observados':len(meses),'recorrente':recorrente,
            'demanda_compartilhada_candidata':compartilhada,
            'total_centavos':sum(r['realizado_centavos_aproximado'] for r in rs),
            'ids':[r['id'] for r in rs],
            'acao':'Avaliar calendário de demanda e cotação conjunta somente após validar especificações, quantidades, condições e contratos.'})
    recorrencias.sort(key=lambda r:(-r['total_centavos'],r['categoria'],r['descricao_chave']))
    auditoria=[]
    for r in incluidos:
        a=r['aprovado_centavos_aproximado']; v=r['realizado_centavos_aproximado']
        if not a or v>a:
            auditoria.append({'id':r['id'],'condominio_id':r['condominio_id'],
                'codigo':'aprovacao_sem_base_positiva' if not a else 'realizado_acima_aprovado',
                'diferenca_centavos':v-a if a else None})
    total=sum(r['realizado_centavos_aproximado'] for r in incluidos)
    if total!=sum(g['total_centavos'] for g in concentracoes):
        raise ErroCompras('Falha na reconciliação dos grupos.')
    if len(incluidos)+len(excluidos)+fora+nao_finalizados!=len(vistos):
        raise ErroCompras('Falha na reconciliação da cobertura.')
    return {'escopo':'snapshot_atual_coorte_criacao','inicio':inicio.isoformat(),'data_referencia':hoje.isoformat(),
        'totais':{'solicitacoes_snapshot':len(vistos),'incluidas':len(incluidos),'fora_da_janela':fora,
                  'nao_finalizadas_na_janela':nao_finalizados,'excluidas_por_cobertura':len(excluidos),
                  'total_realizado_centavos_aproximado':total,
                  'sem_rotulo_fornecedor':sum(not r['rotulo_fornecedor'] for r in incluidos),
                  'sem_descricao':sum(not r['descricao_chave'] for r in incluidos)},
        'concentracoes':concentracoes,'demandas':recorrencias,'auditoria_orcamento':auditoria,
        'evidencias':incluidos,'exclusoes':excluidos,
        'limites':['Coorte pela criação, com estado atual; não é série histórica de conclusão ou pagamento.',
                   'Rótulo de fornecedor não identifica pessoa jurídica. Descrição igual não prova equivalência.',
                   'Sem quantidade e preço unitário não há comparação de preço nem estimativa de economia.',
                   'Grupos de demanda, concentração e orçamento podem se sobrepor: não somar impactos.',
                   'Valores realizados legados aproximados; não somar a pagamentos ou despesas das planilhas.']}
