# -*- coding: utf-8 -*-
"""Triagem executiva e comparação de cenários explícitos. Sem I/O.
Não estima benefícios a partir de alertas nem autoriza intervenções.
"""
from collections import defaultdict

TEMAS = {
    'historico': ('custos', 'Validar documentos e escopo das maiores contribuições antes de decidir sobre cortes.'),
    'recorrencia': ('custos', 'Identificar ativo e natureza dos registros recorrentes antes de propor mudança.'),
    'agenda': ('manutencao', 'Confirmar execução documentada e programar atividades pendentes por prazo.'),
    'solicitacao': ('financeiro', 'Conciliar autorização, valor final e comprovantes antes de regularizar divergências.'),
    'operacional': ('operacao', 'Tratar o gargalo ou não conformidade com evidências, sem atribuir culpa automaticamente.'),
    'concentracao': ('fornecedores', 'Confirmar identidade e escopo; obter propostas comparáveis.'),
    'demanda': ('fornecedores', 'Avaliar programação e cotação conjunta após validar especificações e quantidades.'),
}
FONTES = {'historico','agenda','financeiro','operacional','compras'}


def priorizar_v80(central, limite=5):
    """Agrupa por espaço de IDs, condomínio e tema. Nunca descarta P1.
    Limite é meta de grupos, não teto de urgências. Valores não são somados.
    """
    if type(limite) is not int or not 1 <= limite <= 100:
        raise ValueError('Limite executivo inválido.')
    if not isinstance(central,dict) or central.get('versao') != '8.0-central-1':
        raise ValueError('Versão central inválida.')
    fontes=central.get('fontes'); ds=central.get('decisoes')
    if not isinstance(fontes,dict) or set(fontes)!=FONTES or any(not isinstance(v,str) or not v for v in fontes.values()):
        raise ValueError('Mapa de fontes incompleto.')
    if not isinstance(ds,list) or len(ds)>200000:
        raise ValueError('Lista de decisões inválida.')
    if central.get('economia_comprovada_centavos') is not None:
        raise ValueError('Economia não verificável neste fluxo.')
    grupos=defaultdict(list); vistos=set()
    for d in ds:
        if not isinstance(d,dict): raise ValueError('Decisão inválida.')
        k=d.get('chave'); o=d.get('origem'); cid=d.get('condominio_id'); p=d.get('prioridade')
        if not isinstance(k,str) or not k or k in vistos or ':' not in k:
            raise ValueError('Chave inválida ou duplicada.')
        prefixo=k.split(':',1)[0]
        if prefixo not in TEMAS or o != ('planilhas' if prefixo in ('historico','recorrencia','agenda') else 'app'):
            raise ValueError('Origem ou tipo de decisão inconsistente.')
        if cid is not None and (type(cid) is not int or cid<=0): raise ValueError('Condomínio inválido.')
        if type(p) is not int or p not in (1,2,3): raise ValueError('Prioridade inválida.')
        if not isinstance(d.get('acao'),str) or not d['acao'].strip() or not isinstance(d.get('fato'),str) or not isinstance(d.get('referencias'),dict) or not isinstance(d.get('hipoteses_nao_comprovadas'),list):
            raise ValueError('Decisão sem suporte mínimo.')
        v=d.get('valor_centavos'); n=d.get('natureza_valor')
        if v is not None and (type(v) is not int or v<0 or not isinstance(n,str) or not n):
            raise ValueError('Valor sem natureza válida.')
        if d.get('economia_comprovada_centavos') is not None: raise ValueError('Economia não verificável.')
        fontes_necessarias={'historico':('historico',),'recorrencia':('historico','agenda'),'agenda':('agenda',),'solicitacao':('financeiro','compras'),'operacional':('operacional',),'concentracao':('compras',),'demanda':('compras',)}[prefixo]
        if (any(fontes[f]=='indisponivel' for f in fontes_necessarias) if prefixo=='recorrencia' else all(fontes[f]=='indisponivel' for f in fontes_necessarias)): raise ValueError('Decisão sem fonte disponível.')
        vistos.add(k); grupos[(o,cid,TEMAS[prefixo][0])].append(d)
    carteira=[]
    for (o,cid,tema),rs in grupos.items():
        rs=sorted(rs,key=lambda d:(d['prioridade'],d['chave']))
        valores=defaultdict(list)
        for d in rs:
            if d.get('valor_centavos') is not None: valores[d['natureza_valor']].append(d['valor_centavos'])
        carteira.append({'origem':o,'condominio_id':cid,'tema':tema,'prioridade':rs[0]['prioridade'],
            'quantidade_casos':len(rs),'casos_p1':sum(d['prioridade']==1 for d in rs),
            'chaves':[d['chave'] for d in rs], 'acoes':[{'chave':d['chave'],'prioridade':d['prioridade'],'acao':d['acao'],'fato':d['fato']} for d in rs],
            'maiores_valores_por_natureza':{k:max(v) for k,v in sorted(valores.items())},
            'economia_comprovada_centavos':None})
    # Entre temas distintos, valores não comparáveis não decidem ranking.
    carteira.sort(key=lambda g:(g['prioridade'],-g['casos_p1'],-g['quantidade_casos'],g['origem'],g['condominio_id'] is None,g['condominio_id'] or 0,g['tema']))
    selecionados=[g for i,g in enumerate(carteira) if i<limite or g['prioridade']==1]
    pendentes=[g for i,g in enumerate(carteira) if i>=limite and g['prioridade']!=1]
    if sum(g['quantidade_casos'] for g in carteira)!=len(ds) or any(g['prioridade']==1 for g in pendentes):
        raise ValueError('Falha de cobertura executiva.')
    return {'versao':'8.0-prescritiva-1','fontes':dict(fontes),'total_casos':len(ds),'total_grupos':len(carteira),
            'executivo':selecionados,'fila':pendentes,'total_p1':sum(d['prioridade']==1 for d in ds),
            'limite_alvo':limite,'economia_comprovada_centavos':None,
            'limites':['P1 é prioridade de triagem, não risco crítico comprovado. Todos os casos P1 permanecem no executivo.',
            'Agrupamento por condomínio e tema não estabelece vínculo causal. Quantidades não medem risco.',
            'Valores por natureza são máximos individuais, não somas nem economias. Fontes indisponíveis permanecem desconhecidas.',
            'Fila de prioridades menores preservada integralmente; nenhuma intervenção é autorizada.']}


CENARIOS=('pessimista','base','otimista')
MAX=99_999_999_999_999

def _dinheiro(v):
    if type(v) is not int or not 0<=v<=MAX: raise ValueError('Valor em centavos inválido.')
    return v


def comparar_alternativas_v80(alternativas, horizonte_meses, *, restricoes_confirmadas=False):
    """Compara fluxos incrementais nominais frente a não agir (zero).
    Cada cenário tem custo inicial, custo mensal adicional e benefício mensal
    incremental, todos fornecidos explicitamente. Sem probabilidades, desconto,
    impostos ou valor residual implícitos. Não recomenda execução automática.
    """
    if type(horizonte_meses) is not int or not 1<=horizonte_meses<=120 or type(restricoes_confirmadas) is not bool:
        raise ValueError('Horizonte ou restrições inválidos.')
    if not isinstance(alternativas,(list,tuple)) or not 1<=len(alternativas)<=50:
        raise ValueError('Alternativas inválidas.')
    linhas=[]; vistos=set()
    for a in alternativas:
        if not isinstance(a,dict): raise ValueError('Alternativa inválida.')
        nome=a.get('id')
        if not isinstance(nome,str) or not nome.strip() or nome=='nao_agir' or nome in vistos: raise ValueError('ID inválido ou duplicado.')
        vistos.add(nome)
        ev=a.get('evidencia'); cs=a.get('cenarios')
        if not isinstance(ev,str) or not ev.strip() or not isinstance(cs,dict) or set(cs)!=set(CENARIOS):
            raise ValueError('Cenários completos e origem das premissas obrigatórios.')
        resultados={}
        for c in CENARIOS:
            s=cs[c]
            if not isinstance(s,dict) or set(s)!={'investimento','custo_mensal','beneficio_mensal'}: raise ValueError('Premissas financeiras incompletas.')
            inv,custo,ben=(_dinheiro(s[k]) for k in ('investimento','custo_mensal','beneficio_mensal'))
            mensal=ben-custo; saldo=mensal*horizonte_meses-inv
            payback=(0 if inv==0 and mensal>=0 else (inv+mensal-1)//mensal if mensal>0 else None)
            resultados[c]={'premissas':dict(s),'saldo_incremental_centavos':saldo,'payback_meses':payback if payback is not None and payback<=horizonte_meses else None}
        saldos=[resultados[c]['saldo_incremental_centavos'] for c in CENARIOS]
        if saldos!=sorted(saldos): raise ValueError('Cenários fora da ordem pessimista/base/otimista.')
        linhas.append({'id':nome,'evidencia':ev,'cenarios':resultados})
    linhas.sort(key=lambda a:a['id'])
    def saldos(a): return [a['cenarios'][c]['saldo_incremental_centavos'] for c in CENARIOS]
    robustas=[]
    for a in linhas:
        x=saldos(a)
        # Estritamente superior a não agir em todos os cenários e a todas as
        # demais alternativas em cada cenário correspondente. Empate não decide.
        if min(x)>0 and all(all(u>v for u,v in zip(x,saldos(b))) for b in linhas if b is not a): robustas.append(a['id'])
    indicacao=robustas[0] if len(robustas)==1 and restricoes_confirmadas else None
    return {'horizonte_meses':horizonte_meses,'alternativas':linhas,'referencia_nao_agir_centavos':0,
            'dominantes_financeiras':robustas,'alternativa_para_avaliacao_humana':indicacao,
            'restricoes_confirmadas_pelo_fornecedor_das_premissas':restricoes_confirmadas,
            'economia_comprovada_centavos':None,'limites':['Simulação nominal incremental, não previsão nem economia comprovada.',
            'Benefícios e custos são premissas externas; não inferidos de aumentos históricos.',
            'Restrições técnicas, legais, contratuais e de segurança exigem confirmação externa; não autoriza execução.',
            'Cenários sem probabilidades, sem desconto e sem valor residual.']}
