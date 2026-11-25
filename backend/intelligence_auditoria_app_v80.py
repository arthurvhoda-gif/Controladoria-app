# -*- coding: utf-8 -*-
"""Auditoria independente dos resultados do app frente ao snapshot extraído.
Sem I/O; não certifica a completude do banco nem a correção dos documentos.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import unicodedata
from intelligence_auditoria_v80 import exigir, indexar, auditar_carteira_v80


def moeda(v):
    if v is None:
        return None
    d = Decimal(str(v))
    exigir(d.is_finite() and d >= 0, 'APP_VALOR')
    return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def chave(v):
    return ' '.join(unicodedata.normalize('NFC', v).casefold().split())


def campos(reg, esperado, codigo):
    exigir(all(k in reg and reg[k] == v for k,v in esperado.items()), codigo)


def auditar_app_v80(snapshot, central, carteira):
    """Audita todos os casos app, inclusive quando o central contém planilhas.
    Exige snapshot completo; nenhuma fonte ausente é interpretada como vazia.
    Cálculos separados dos três motores; texto livre não certificado.
    """
    exigir(central['versao']=='8.0-central-1' and central['data_referencia']==snapshot['data_referencia'], 'APP_REFERENCIA')
    exigir(all(central['fontes'][k]=='disponivel' for k in ('financeiro','compras','operacional')), 'APP_FONTES')
    exigir(central['economia_comprovada_centavos'] is None,'APP_ECONOMIA')
    hoje=date.fromisoformat(snapshot['data_referencia'])
    exigir(all(isinstance(snapshot.get(k),(list,tuple)) for k in ('solicitacoes','lancamentos','servicos','participantes','itens','execucoes')), 'APP_SNAPSHOT')
    cadastro=snapshot['condominios']; exigir(bool(cadastro),'APP_CADASTRO')
    sol=indexar(snapshot['solicitacoes'],lambda r:r['id']); livro=indexar(snapshot['lancamentos'],lambda r:r['id'])
    resultados=central['resultados']; f=resultados['financeiro']; c=resultados['compras']; o=resultados['operacional']
    pagamentos=defaultdict(list); estornos=defaultdict(list); refs=set(); decisoes={}
    for lid,l in livro.items():
        sid=l['solicitacao_id']; v=l['valor_centavos']; ref=l['estorno_de_id']
        exigir(sid in sol and type(v) is int and v>0,'APP_LIVRO')
        if l['tipo']=='pagamento':
            exigir(ref is None,'APP_PAGAMENTO'); pagamentos[sid].append(l)
        else:
            exigir(l['tipo']=='estorno' and ref in livro and ref not in refs,'APP_ESTORNO')
            p=livro[ref]; exigir(p['tipo']=='pagamento' and p['solicitacao_id']==sid and p['valor_centavos']==v,'APP_ESTORNO'); refs.add(ref); estornos[sid].append(l)
    fc=indexar(f['casos'],lambda x:x['solicitacao_id']); exigir(set(fc)==set(sol),'APP_COBERTURA_FIN')
    bruto=est=alertas=casos_alerta=0
    for sid,s in sol.items():
        cid=s['condominio_id']; exigir(cid is None or cid in cadastro,'APP_CADASTRO')
        a=moeda(s['valor_aprovado']); r=moeda(s['valor_realizado']) if s['status']=='Finalizada' else None
        b=sum(x['valor_centavos'] for x in pagamentos[sid]); e=sum(x['valor_centavos'] for x in estornos[sid]); p=b-e
        exigir(p>=0,'APP_LIQUIDO'); bruto+=b; est+=e
        x=fc[sid]; campos(x,dict(condominio_id=cid,status_atual=s['status'],aprovado_centavos_aproximado=a,realizado_centavos_aproximado=r,pagamentos_brutos_centavos=b,estornos_centavos=e,pago_liquido_centavos=p),'APP_VALORES_FIN')
        ev={l['id']:{k:l[k] for k in ('id','tipo','valor_centavos','estorno_de_id')} for l in pagamentos[sid]+estornos[sid]}
        exigir(indexar(x['evidencias'],lambda l:l['id'])==ev,'APP_EVIDENCIA_FIN')
        al={}
        if cid is None: al['condominio_nao_vinculado']=None
        if p>0 and s['status'] not in ('Aprovada','Em execução','Finalizada'): al['pagamento_em_status_nao_pagavel']=None
        if p>0 and not a: al['pagamento_sem_aprovacao_positiva']=None
        if a and p>a: al['pago_acima_do_aprovado']=p-a
        if s['status']=='Finalizada':
            if not r: al['realizado_nao_confirmado']=None
            if a and r and r>a: al['realizado_acima_do_aprovado']=r-a
            if r and p>r: al['pago_acima_do_realizado']=p-r
            if r and p<r: al['saldo_a_conciliar_com_realizado']=r-p
        exigir({k:v['diferenca_centavos'] for k,v in indexar(x['alertas'],lambda a:a['codigo']).items()}==al,'APP_ALERTAS_FIN')
        alertas+=len(al); casos_alerta+=bool(al)
        if al:
            v=max((al[k] for k in ('pago_acima_do_aprovado','pago_acima_do_realizado','realizado_acima_do_aprovado') if k in al),default=None)
            decisoes[f'solicitacao:{sid}']=(cid,1 if v is not None else 2,v,'maior_diferenca_da_solicitacao_nao_somavel' if v is not None else None)
    campos(f['totais'],dict(solicitacoes=len(sol),lancamentos=len(livro),casos_com_alertas=casos_alerta,alertas=alertas,pagamentos_brutos_centavos=bruto,estornos_centavos=est,pago_liquido_centavos=bruto-est),'APP_TOTAIS_FIN')
    # Compras: cobertura da coorte e todos os agrupamentos, inclusive sem sinal.
    inicio=hoje-timedelta(days=179); inc={}; exc={}; fora=nf=0
    for sid,s in sol.items():
        dia=datetime.strptime(s['data'],'%Y-%m-%d %H:%M:%S').date(); exigir(dia<=hoje,'APP_DATA_COMPRA')
        if dia<inicio: fora+=1; continue
        if s['status']!='Finalizada': nf+=1; continue
        cid=s['condominio_id']; cat,forn,desc=(chave(s[k]) for k in ('categoria','fornecedor','descricao')); a=moeda(s['valor_aprovado']); v=moeda(s['valor_realizado'])
        motivos=[m for ok,m in ((cid is None,'condominio_sem_vinculo'),(not cat,'categoria_ausente'),(not v,'realizado_sem_base_positiva')) if ok]
        if motivos: exc[sid]=dict(id=sid,motivos=motivos,realizado_centavos=v); continue
        inc[sid]=dict(id=sid,condominio_id=cid,data_criacao=dia.isoformat(),categoria=cat,rotulo_fornecedor=forn,descricao_chave=desc,realizado_centavos_aproximado=v,aprovado_centavos_aproximado=a)
    exigir(indexar(c['evidencias'],lambda x:x['id'])==inc and indexar(c['exclusoes'],lambda x:x['id'])==exc,'APP_COBERTURA_COMPRAS')
    campos(c,dict(inicio=inicio.isoformat(),data_referencia=hoje.isoformat()),'APP_JANELA_COMPRAS')
    def total(rs): return sum(r['realizado_centavos_aproximado'] for r in rs)
    campos(c['totais'],dict(solicitacoes_snapshot=len(sol),incluidas=len(inc),fora_da_janela=fora,nao_finalizadas_na_janela=nf,excluidas_por_cobertura=len(exc),total_realizado_centavos_aproximado=total(inc.values()),sem_rotulo_fornecedor=sum(not r['rotulo_fornecedor'] for r in inc.values()),sem_descricao=sum(not r['descricao_chave'] for r in inc.values())),'APP_TOTAIS_COMPRAS')
    cats=defaultdict(list); dem=defaultdict(list); orc={}
    for sid,r in inc.items():
        cats[r['condominio_id'],r['categoria']].append(r)
        if r['descricao_chave']: dem[r['categoria'],r['descricao_chave']].append(r)
        a=r['aprovado_centavos_aproximado']; v=r['realizado_centavos_aproximado']
        if not a or v>a:
            orc[sid]=dict(id=sid,condominio_id=r['condominio_id'],codigo='realizado_acima_aprovado' if a else 'aprovacao_sem_base_positiva',diferenca_centavos=v-a if a else None)
            # Financeiro completo já contém toda divergência de orçamento elegível.
            exigir(f'solicitacao:{sid}' in decisoes,'APP_ORCAMENTO_SEM_FIN')
    exigir(indexar(c['auditoria_orcamento'],lambda x:x['id'])==orc,'APP_ORCAMENTO')
    cc=indexar(c['concentracoes'],lambda x:(x['condominio_id'],x['categoria'])); exigir(set(cc)==set(cats),'APP_COBERTURA_CONCENTRACAO')
    for (cid,cat),rs in cats.items():
        t=total(rs); labels=defaultdict(list)
        for r in rs:
            if r['rotulo_fornecedor']: labels[r['rotulo_fornecedor']].append(r)
        rank=sorted([dict(rotulo=k,total_centavos=total(v),ids=sorted(r['id'] for r in v)) for k,v in labels.items()],key=lambda x:(-x['total_centavos'],x['rotulo']))
        maior=rank[0]['total_centavos'] if rank else 0; sinal=len(rs)>=3 and t>=100000 and maior*100>=70*t
        campos(cc[cid,cat],dict(total_centavos=t,sem_rotulo_centavos=t-sum(x['total_centavos'] for x in rank),quantidade=len(rs),ranking_rotulos=rank,participacao_lider_pontos_base=maior*10000//t if rank else None,sinal_concentracao=sinal,ids=sorted(r['id'] for r in rs)),'APP_CONCENTRACAO')
        if sinal: decisoes[f'concentracao:{cid}:{cat}']=(cid,3,t,'volume_realizado_aproximado')
    dd=indexar(c['demandas'],lambda x:(x['categoria'],x['descricao_chave'])); esperados=set()
    for (cat,desc),rs in dem.items():
        dias={r['data_criacao'] for r in rs}; meses={d[:7] for d in dias}; cids=sorted({r['condominio_id'] for r in rs}); rec=len(dias)>=3 and len(meses)>=2; part=len(cids)>=2
        if not (rec or part): continue
        k=(cat,desc); esperados.add(k); exigir(k in dd,'APP_DEMANDA_OMITIDA'); t=total(rs)
        campos(dd[k],dict(condominios=cids,datas_distintas=len(dias),meses_observados=len(meses),recorrente=rec,demanda_compartilhada_candidata=part,total_centavos=t,ids=sorted(r['id'] for r in rs)),'APP_DEMANDA')
        decisoes[f'demanda:{cat}:{desc}']=(None,3,t,'volume_realizado_aproximado')
    exigir(set(dd)==esperados,'APP_COBERTURA_DEMANDA')
    # Operação: recalcular estados por participantes e janelas de vistoria.
    ss=indexar(snapshot['servicos'],lambda x:x['id']); pp=indexar(snapshot['participantes'],lambda x:x['id']); ii=indexar(snapshot['itens'],lambda x:x['id']); ee=indexar(snapshot['execucoes'],lambda x:x['id'])
    ps=defaultdict(list); es=defaultdict(list); resumo=defaultdict(Counter); esperados={}
    for p in pp.values():
        exigir(p['servico_id'] in ss,'APP_PARTICIPANTE'); ps[p['servico_id']].append(p)
    for e in ee.values():
        exigir(e['item_id'] in ii,'APP_VISTORIA'); dt=datetime.fromisoformat(e['data_execucao']); exigir(dt.tzinfo is None and dt.date()<=hoje,'APP_DATA_VISTORIA'); es[e['item_id']].append((dt,e))
    etapas={'Aguardando ciência':'ciencia','Recebido':'inicio','Em andamento':'execucao','Aguardando fiscalização':'fiscalizacao','Aguardando validação':'validacao'}
    for sid,s in ss.items():
        cid=s['condominio_id']; exigir(cid in cadastro,'APP_CADASTRO'); cnt=resumo[cid]; cnt['servicos']+=1
        ex=[p['status'] for p in ps[sid] if p['papel']=='executor']; fi=[p['status'] for p in ps[sid] if p['papel']=='fiscalizador']; estado=s['status']; fechado=estado=='Concluído'
        if not ex: deriv=None
        elif all(x=='Finalizado' for x in ex): deriv='Aguardando fiscalização' if any(x!='Aprovado' for x in fi) else 'Aguardando validação'
        elif any(x in ('Finalizado','Em andamento') for x in ex): deriv='Em andamento'
        elif 'Aguardando ciência' in ex: deriv='Aguardando ciência'
        else: deriv='Recebido'
        div=deriv is not None and (deriv!='Aguardando validação' if fechado else deriv!=estado)
        dias=0 if fechado else max(0,(hoje-date.fromisoformat(s['prazo'])).days)
        if deriv is None: cnt['servicos_sem_base_participantes']+=1
        if not fechado: cnt['servicos_abertos']+=1; cnt['etapa_'+etapas[estado]]+=1
        if dias: cnt['servicos_atrasados']+=1
        if div: cnt['servicos_estado_divergente']+=1
        if dias or div or estado=='Aguardando validação':
            esperados['servico',sid]=dict(condominio_id=cid,estado=estado,etapa_registrada=etapas.get(estado),estado_derivado=deriv,divergencia_estado=div,prazo=s['prazo'],dias_atraso=dias,prioridade_registrada=s['prioridade'],evidencias_participantes=[{k:p[k] for k in ('id','papel','status')} for p in sorted(ps[sid],key=lambda x:x['id'])])
            decisoes[f'operacional:servico:{sid}']=(cid,1 if dias and s['prioridade'] in ('Alta','Urgente') else 2,None,None)
    janela=hoje-timedelta(days=89)
    for iid,i in ii.items():
        cid=i['condominio_id']; exigir(cid is None or cid in cadastro,'APP_CADASTRO'); cnt=resumo[cid]; cnt['itens_checklist']+=1
        if not es[iid]: cnt['itens_sem_vistoria']+=1; continue
        rs=sorted([(t,e) for t,e in es[iid] if t.date()>=janela],key=lambda x:(x[0],x[1]['id']))
        if not rs: cnt['itens_sem_vistoria_90d']+=1; continue
        ult=rs[-1][0]; ls=[e for t,e in rs if t==ult]; estados={e['status_conformidade']!='Conforme' for e in ls}
        def evid(xs): return [dict(id=e['id'],data=e['data_execucao'],status=e['status_conformidade']) for e in xs]
        if len(estados)>1:
            tipo='vistoria_estado_ambiguo'; cnt['itens_estado_ambiguo']+=1; x=dict(condominio_id=cid,evidencias=evid(ls))
        elif True in estados:
            tipo='vistoria'; n=len({t for t,e in rs if e['status_conformidade']!='Conforme'}); cnt['itens_ultimo_nao_conforme']+=1
            if n>=2: cnt['itens_nao_conformes_recorrentes']+=1
            x=dict(condominio_id=cid,recorrente=n>=2,ocorrencias_distintas_90d=n,ultima_vistoria=ult.isoformat(),evidencias=evid([e for t,e in rs]))
        else: continue
        esperados[tipo,iid]=x; decisoes[f'operacional:{tipo}:{iid}']=(cid,2,None,None)
    oc=indexar(o['casos'],lambda x:(x['tipo'],x['id'])); exigir(set(oc)==set(esperados),'APP_COBERTURA_OPERACAO')
    for k,x in esperados.items(): campos(oc[k],x,'APP_EVIDENCIA_OPERACAO')
    exigir(indexar(o['condominios'],lambda x:x['condominio_id'])=={cid:dict(condominio_id=cid,**c) for cid,c in resumo.items()},'APP_TOTAIS_OPERACAO')
    campos(o,dict(data_referencia=hoje.isoformat(),inicio_janela_vistorias=janela.isoformat()),'APP_JANELA_OPERACAO')
    ds=indexar([d for d in central['decisoes'] if d['origem']=='app'],lambda d:d['chave']); exigir(set(ds)==set(decisoes),'APP_COBERTURA_DECISOES')
    demandas_chaves=indexar(dd.values(),lambda x:f"demanda:{x['categoria']}:{x['descricao_chave']}")
    for k,d in ds.items():
        prefix=k.split(':',1)[0]
        if prefix=='solicitacao':
            sid=int(k.split(':')[1]); x=fc[sid]
            ref=dict(solicitacao_id=sid,lancamentos=[e['id'] for e in x['evidencias']],auditoria_compras_mesma_solicitacao=orc.get(sid))
        elif prefix=='concentracao':
            _,cid,cat=k.split(':',2); x=cc[int(cid),cat]
            ref=dict(ids=x['ids'],participacao_pontos_base=x['participacao_lider_pontos_base'])
        elif prefix=='demanda':
            # A categoria/descrição pode conter dois pontos: localizar pela chave integral.
            x=demandas_chaves[k]
            ref=dict(ids=x['ids'],condominios=x['condominios'])
        else:
            _,tipo,i=k.split(':'); x=oc[tipo,int(i)]
            ref=dict(tipo=tipo,id=int(i),dias_atraso=x.get('dias_atraso'),recorrente=x.get('recorrente'))
        exigir(d['referencias']==ref,'APP_REFERENCIAS_DECISAO')
        exigir((d['condominio_id'],d['prioridade'],d['valor_centavos'],d['natureza_valor'])==decisoes[k] and d['economia_comprovada_centavos'] is None,'APP_DECISAO')
    auditar_carteira_v80(central,carteira)
    return dict(estado='APROVADO_ESCOPO_SNAPSHOT_APP',solicitacoes=len(sol),lancamentos=len(livro),servicos=len(ss),vistorias=len(ee),decisoes=len(ds),pago_liquido_centavos=bruto-est,economia_comprovada_centavos=None)
