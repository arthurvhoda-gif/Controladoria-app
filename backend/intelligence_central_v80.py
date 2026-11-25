# -*- coding: utf-8 -*-
"""Orquestração privada V8.0: sem rede, escrita, banco ou envio.
IDs locais de planilhas e IDs do app pertencem a espaços distintos.
"""
from collections import defaultdict
from datetime import date
from custos_importacao_v77 import chave_nome
from intelligence_previsao_v78 import interpretar_mes, deslocar_mes
from intelligence_motor_v78 import analisar_historico_privado
from intelligence_oportunidades_v78 import identificar_oportunidades_v78
from intelligence_investigacao_v80 import investigar_aumento, verificar_investigacao
from intelligence_manutencao_v80 import investigar_manutencao_v80
from intelligence_reconciliacao_v80 import reconciliar_financeiro_v80
from intelligence_operacional_v80 import investigar_operacao_v80
from intelligence_compras_v80 import investigar_compras_v80


def _id(v):
    if type(v) is not int or v <= 0:
        raise ValueError('ID inválido no cadastro.')
    return v


def _cadastro(nomes):
    if not isinstance(nomes, dict) or not nomes:
        raise ValueError('Cadastro explícito obrigatório.')
    normalizados = set()
    for cid,nome in nomes.items():
        _id(cid)
        k = chave_nome(nome)
        if not k or k in normalizados:
            raise ValueError('Nome ausente ou ambíguo no cadastro.')
        normalizados.add(k)


def executar_central_v80(*, data_referencia, competencia, historico=None,
                         agenda=None, nomes_locais=None, fechamentos=None,
                         simulacao=False, snapshot_app=None, vinculos=None):
    """Executa núcleos com dados explícitos. None significa fonte indisponível.

    Snapshot do app deve ser atual, completo e consistente (extração ainda
    externa). Vínculos local->app são fornecidos explicitamente, nunca inferidos.
    Fechamentos confirmados por condomínio; simulação é sempre rotulada.
    """
    hoje = date.fromisoformat(data_referencia)
    if hoje.isoformat()!=data_referencia or type(simulacao) is not bool:
        raise ValueError('Data ou modo inválido.')
    ref = interpretar_mes(competencia)
    if ref>hoje.replace(day=1):
        raise ValueError('Competência futura.')
    meses = [deslocar_mes(ref,i).strftime('%Y-%m') for i in range(-5,1)]
    fontes = {k:'indisponivel' for k in ('historico','agenda','financeiro','operacional','compras')}
    resultados = {}; decisoes = []; contextos=[]
    locais = nomes_locais if nomes_locais is not None else {}
    if historico is not None or agenda is not None or locais:
        _cadastro(locais)
    app = {}
    if snapshot_app is not None:
        if not isinstance(snapshot_app,dict) or snapshot_app.get('data_referencia')!=data_referencia:
            raise ValueError('Snapshot ausente ou de outra data.')
        app = snapshot_app.get('condominios')
        _cadastro(app)
    mapa = {} if vinculos is None else vinculos
    if not isinstance(mapa,dict) or any(type(k) is not int or type(v) is not int or k not in locais or v not in app for k,v in mapa.items()) or len(set(mapa.values()))!=len(mapa):
        raise ValueError('Vínculos explícitos inválidos ou não bijetivos.')
    # Um vínculo confirmado exige ainda nomes compatíveis; renomeações precisam de revisão.
    if any(chave_nome(locais[k])!=chave_nome(app[v]) for k,v in mapa.items()):
        raise ValueError('Vínculo diverge do cadastro de nomes.')

    def caso(chave, origem, cid, nivel, fato, acao, referencias, limites, valor=None, natureza=None):
        if cid is not None:
            _id(cid)
            cadastro = locais if origem=='planilhas' else app
            if cid not in cadastro:
                raise ValueError('Condomínio sem cadastro na fonte.')
        decisoes.append(dict(chave=chave,origem=origem,condominio_id=cid,prioridade=nivel,
            fato=fato,acao=acao,referencias=referencias,hipoteses_nao_comprovadas=limites,
            valor_centavos=valor,natureza_valor=natureza,economia_comprovada_centavos=None))

    if historico is not None:
        analisar_historico_privado(historico)
        if any(r.condominio_id not in locais for r in historico):
            raise ValueError('Histórico fora do cadastro local.')
        if fechamentos is not None and (not isinstance(fechamentos,dict) or any(type(k) is not int or k not in locais for k in fechamentos)):
            raise ValueError('Fechamentos inválidos.')
        confirmados={}
        for k,vs in (fechamentos or {}).items():
            if not isinstance(vs,(list,tuple,set,frozenset)) or any(interpretar_mes(v)>ref for v in vs):
                raise ValueError('Fechamentos inválidos ou posteriores.')
            confirmados[k]=set(vs)
        if simulacao and confirmados:
            raise ValueError('Não misturar fechamento confirmado com simulação.')
        hist=tuple(r for r in historico if r.competencia<=ref and r.data_original<=hoje)
        if not hist:
            raise ValueError('Histórico sem registros até referência.')
        fontes['historico']='simulacao_cobertura_nao_confirmada' if simulacao else 'disponivel_fechamentos_explicitos'
        investigacoes=[]; sem_fechamento=[]; avaliadas=sem_base=0
        for cid in sorted(locais):
            if not simulacao and not set(meses)<=confirmados.get(cid,set()):
                sem_fechamento.append(cid); continue
            r=identificar_oportunidades_v78(hist,cid,competencia,meses)
            avaliadas+=r.categorias_avaliadas; sem_base+=r.categorias_sem_base
            for o in r.oportunidades:
                c=investigar_aumento(hist,o,meses); verificar_investigacao(c)
                investigacoes.append(c)
                caso(f'historico:{cid}:{o.categoria}', 'planilhas',cid,2 if simulacao else 1,
                    'Aumento contábil reconciliado frente à referência histórica.',
                    'Priorizar validação do escopo e documentos das maiores contribuições; não autorizar corte sem causa comprovada.',
                    {'categoria':o.categoria,'competencias':meses},
                    ['Reajuste, alteração de quantidade ou escopo e falha operacional não confirmados.'],
                    c['impacto_centavos'],'impacto_adicional_historico_simulado' if simulacao else 'impacto_adicional_historico')
        resultados['historico']={'casos':investigacoes,'categorias_avaliadas':avaliadas,'categorias_sem_base':sem_base,'sem_fechamento':sem_fechamento}
        if agenda is not None:
            if any(not isinstance(r,dict) or r.get('condominio_id') not in locais or type(r.get('condominio_id')) is not int for r in agenda):
                raise ValueError('Agenda fora do cadastro local.')
            m=investigar_manutencao_v80(historico,agenda,data_referencia,competencia,['manutencao condominio'])
            fontes['agenda']='disponivel_datas_registradas'; resultados['manutencao']=m
            for a in m['agenda']:
                if a['estado']=='prazo_futuro': continue
                cid=a['condominio_id']; linha=a['evidencia']['linha']
                caso(f'agenda:{cid}:{linha}','planilhas',cid,1 if a['estado']=='prazo_registrado_vencido' else 2,
                    a['estado'],a['acao'],{'linha':linha,'nome':a['nome'],'proxima':a['evidencia']['proxima']},
                    ['Prazo registrado não comprova execução ou falta de execução.'])
            for r in m['recorrencias']:
                # A mesma despesa pode estar em uma decomposição contábil. A interseção é
                # evidência reutilizada, não confirmação independente nem novo impacto.
                ids={(e['id'],e['hash']) for e in r['evidencias']}
                relacionadas=[]
                for c in investigacoes:
                    if c['condominio_id']!=r['condominio_id'] or c['categoria']!=r['categoria']: continue
                    ev={(e['id'],e['hash']) for x in c['decomposicao'] for e in x['evidencias_recentes']}
                    if ids & ev: relacionadas.append({'caso':f"historico:{c['condominio_id']}:{c['categoria']}",'registros_em_comum':len(ids&ev),'independente':False})
                caso(f"recorrencia:{r['condominio_id']}:{r['categoria']}:{r['descricao']}",'planilhas',r['condominio_id'],3,
                    'Descrição de manutenção recorrente, sem identificação inequívoca de ativo.',r['acao'],
                    {'ids':[e['id'] for e in r['evidencias']],'relacoes_mesma_fonte':relacionadas},
                    ['Pode ser manutenção preventiva regular; não comprova falha repetida.'],r['total_centavos'],'gasto_observado_nao_adicional')
    elif agenda is not None:
        raise ValueError('Módulo de manutenção requer histórico validado.')

    if snapshot_app is not None:
        # Um grupo parcialmente extraído é rejeitado, não substituído por lista vazia.
        def grupo(*keys):
            vs=[snapshot_app.get(k) for k in keys]
            if all(v is None for v in vs): return None
            if any(not isinstance(v,(list,tuple)) for v in vs):
                raise ValueError('Grupo de fontes incompleto.')
            return vs
        sol=snapshot_app.get('solicitacoes'); livro=snapshot_app.get('lancamentos')
        if sol is not None and not isinstance(sol,(list,tuple)):
            raise ValueError('Solicitações inválidas.')
        if livro is not None and sol is None: raise ValueError('Livro sem solicitações.')
        if sol is not None:
            for s in sol:
                if not isinstance(s,dict) or (s.get('condominio_id') is not None and (type(s['condominio_id']) is not int or s['condominio_id'] not in app)):
                    raise ValueError('Solicitação fora do cadastro.')
            compra=investigar_compras_v80(sol,data_referencia); resultados['compras']=compra; fontes['compras']='disponivel'
            auditoria={a['id']:a for a in compra['auditoria_orcamento']}
            finance_ids=set()
            if livro is not None:
                if not isinstance(livro,(list,tuple)): raise ValueError('Livro inválido.')
                fin=reconciliar_financeiro_v80(sol,livro); resultados['financeiro']=fin; fontes['financeiro']='disponivel'
                for c in fin['casos']:
                    sid=c['solicitacao_id']; al=c['alertas']
                    if not al: continue
                    finance_ids.add(sid)
                    codigos=[a['codigo'] for a in al]
                    relevantes=[a for a in al if a['codigo'] in ('pago_acima_do_aprovado','pago_acima_do_realizado','realizado_acima_do_aprovado')]
                    # Maior diferença sinalizada por solicitação, não soma de alertas sobrepostos.
                    valor=max((a['diferenca_centavos'] for a in relevantes),default=None)
                    caso(f'solicitacao:{sid}','app',c['condominio_id'],1 if relevantes else 2,
                        '; '.join(codigos),' '.join(dict.fromkeys(a['acao'] for a in al)),
                        {'solicitacao_id':sid,'lancamentos':[e['id'] for e in c['evidencias']], 'auditoria_compras_mesma_solicitacao':auditoria.get(sid)},
                        ['Escopo adicional, autorizações, parcelas ou créditos podem explicar divergências.'],valor,'maior_diferenca_da_solicitacao_nao_somavel' if valor is not None else None)
            for sid,a in sorted(auditoria.items()):
                if sid in finance_ids: continue
                caso(f'solicitacao:{sid}','app',a['condominio_id'],2,a['codigo'],
                     'Conciliar valor aprovado, realizado e autorização de alterações.',{'solicitacao_id':sid},
                     ['Aumento de escopo ou aprovação complementar não confirmados.'],a['diferenca_centavos'],'diferenca_orcamentaria_aproximada')
            for c in compra['concentracoes']:
                if not c['sinal_concentracao']: continue
                caso(f"concentracao:{c['condominio_id']}:{c['categoria']}",'app',c['condominio_id'],3,
                     'Concentração por rótulo de fornecedor.',c['acao'],{'ids':c['ids'],'participacao_pontos_base':c['participacao_lider_pontos_base']},
                     ['Identidade jurídica, preços unitários e alternativas não comprovados.'],c['total_centavos'],'volume_realizado_aproximado')
            for d in compra['demandas']:
                caso(f"demanda:{d['categoria']}:{d['descricao_chave']}",'app',None,3,
                    'Demanda recorrente ou compartilhada candidata.',d['acao'],{'ids':d['ids'],'condominios':d['condominios']},
                    ['Descrições semelhantes não garantem equivalência de escopo.'],d['total_centavos'],'volume_realizado_aproximado')
        oper=grupo('servicos','participantes','itens','execucoes')
        if oper is not None:
            o=investigar_operacao_v80(*oper,data_referencia); resultados['operacional']=o; fontes['operacional']='disponivel'
            for r in o['condominios']:
                if r['condominio_id'] is not None and r['condominio_id'] not in app: raise ValueError('Operação fora do cadastro.')
            for c in o['casos']:
                nivel=1 if c.get('dias_atraso',0)>0 and c.get('prioridade_registrada') in ('Alta','Urgente') else 2
                caso(f"operacional:{c['tipo']}:{c['id']}",'app',c['condominio_id'],nivel,
                     c.get('estado',c['tipo']),c['acao'],{'tipo':c['tipo'],'id':c['id'],'dias_atraso':c.get('dias_atraso'),'recorrente':c.get('recorrente')},
                     ['Não atribuir culpa ou custo sem vínculo e evidência técnica.'])

    # Contextos do mesmo condomínio só existem mediante mapeamento explícito.
    por=defaultdict(list)
    for d in decisoes:
        por[(d['origem'],d['condominio_id'])].append(d['chave'])
    for l,a in sorted(mapa.items()):
        if por['planilhas',l] and por['app',a]:
            contextos.append({'local_id':l,'app_id':a,'casos_planilhas':sorted(por['planilhas',l]),'casos_app':sorted(por['app',a]),
                'estado':'contexto_mesmo_condominio_sem_vinculo_causal','acao':'Cruzar documentos ou IDs de ativo/serviço quando disponíveis; datas e escopos podem diferir.'})
    if len({d['chave'] for d in decisoes})!=len(decisoes): raise ValueError('Chaves de decisão repetidas.')
    decisoes.sort(key=lambda d:(d['prioridade'],d['origem'],d['natureza_valor'] or '',-(d['valor_centavos'] or 0),d['chave']))
    return {'versao':'8.0-central-1','data_referencia':data_referencia,'competencia':competencia,'simulacao':simulacao,
            'fontes':fontes,'resultados':resultados,'decisoes':decisoes,'contextos':contextos,
            'economia_comprovada_centavos':None,'limites':['Não somar valores de naturezas distintas ou alertas sobrepostos.',
            'Prioridades são regras de triagem, não probabilidades de risco.', 'Ausência de fonte não significa ausência de problemas.',
            'Sem documentos/ativos/contratos vinculados, hipóteses operacionais permanecem não comprovadas.']}
