# -*- coding: utf-8 -*-
"""Auditoria independente de evidências locais V8.0 (simulação).
Não certifica cobertura, execução de manutenção ou causa operacional.
"""
from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction
import unicodedata

class ErroAuditoria(ValueError):
    pass


def exigir(ok, codigo):
    if not ok:
        raise ErroAuditoria(codigo)


def chave(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c)).split())


def meses_seis(competencia):
    d=date.fromisoformat(competencia+'-01'); n=d.year*12+d.month-1
    return [f'{i//12:04d}-{i%12+1:02d}' for i in range(n-5,n+1)]


def ev(r):
    return {'id':r.id_origem,'data':r.data_original.isoformat(),'valor_centavos':r.valor_centavos,'hash':r.hash_conteudo}


def indexar(rs, key):
    d={}
    for r in rs:
        k=key(r); exigir(k not in d,'DUPLICIDADE'); d[k]=r
    return d


def conferir_evidencias(xs, rs):
    exigir(indexar(xs,lambda e:e['id'])==indexar([ev(r) for r in rs],lambda e:e['id']),'EVIDENCIAS_DIVERGENTES')


def auditar_local_v80(central, registros, agenda):
    """Recebe registros reextraídos das fontes, não do relatório auditado.
    Restrito ao ensaio local; recusa fontes do aplicativo nesta fase.
    Recalcula regras de triagem e cada contribuição sem chamar os motores.
    """
    exigir(central['versao']=='8.0-central-1' and central['simulacao'] is True,'ESCOPO')
    fontes=central['fontes']
    exigir(set(fontes)=={'historico','agenda','financeiro','operacional','compras'} and fontes['historico']=='simulacao_cobertura_nao_confirmada' and all(fontes[k]=='indisponivel' for k in ('financeiro','operacional','compras')),'FONTES')
    exigir(central.get('economia_comprovada_centavos') is None and not central['contextos'],'ECONOMIA_OU_CONTEXTO')
    hoje=date.fromisoformat(central['data_referencia']); meses=meses_seis(central['competencia'])
    exigir(meses[-1]<=hoje.strftime('%Y-%m'),'DATA')
    indexar(registros,lambda r:(r.condominio_id,r.id_origem))
    exigir(len(registros)==central['lancamentos_validados'],'COBERTURA_LANCAMENTOS')
    grupos=defaultdict(list)
    for r in registros:
        if r.data_original<=hoje and r.competencia.strftime('%Y-%m') in meses:
            grupo=grupos[r.condominio_id,r.categoria_chave]
            if r.valor_centavos>0: grupo.append(r)
    esperados={}; avaliadas=sem_base=0; decisoes={}; impacto=0
    for (cid,cat),rs in grupos.items():
        por={m:[r for r in rs if r.competencia.strftime('%Y-%m')==m] for m in meses}
        totais={m:sum(r.valor_centavos for r in por[m]) for m in meses}
        if not all(totais.values()): sem_base+=1; continue
        avaliadas+=1; med=sorted(totais[m] for m in meses[:3])[1]
        delta=sum(totais[m] for m in meses[3:])-3*med
        if delta<=0 or sum(totais[m]-med>=10000 and (totais[m]-med)*100>=15*med for m in meses[3:])<2: continue
        base=min(m for m in meses[:3] if totais[m]==med)
        esperados[cid,cat]=(por,totais,base,delta)
    hist=central['resultados']['historico']
    exigir(hist['categorias_avaliadas']==avaliadas and hist['categorias_sem_base']==sem_base and hist['sem_fechamento']==[],'COBERTURA_CATEGORIAS')
    casos=indexar(hist['casos'],lambda c:(c['condominio_id'],c['categoria']))
    exigir(set(casos)==set(esperados),'COBERTURA_CASOS_HISTORICOS')
    for (cid,cat),c in casos.items():
        por,totais,base,delta=esperados[cid,cat]
        exigir(c['competencias']==meses and c['totais_mensais_centavos']==totais and c['mes_referencia']==base and c['impacto_centavos']==delta,'IMPACTO_HISTORICO')
        anteriores=[r for m in meses[:3] for r in por[m]]; recentes=[r for m in meses[3:] for r in por[m]]
        conferir_evidencias(c['evidencias_tres_meses_anteriores'],anteriores)
        bs=defaultdict(list); ats=defaultdict(list)
        for r in por[base]: bs[chave(r.descricao)].append(r)
        for r in recentes: ats[chave(r.descricao)].append(r)
        linhas=indexar(c['decomposicao'],lambda x:x['descricao_normalizada'])
        exigir(set(linhas)==set(bs)|set(ats),'COBERTURA_DESCRICOES')
        pos=neg=0
        for desc,x in linhas.items():
            b,a=bs[desc],ats[desc]; conferir_evidencias(x['evidencias_referencia'],b); conferir_evidencias(x['evidencias_recentes'],a)
            vb=sum(r.valor_centavos for r in b); va=sum(r.valor_centavos for r in a); dif=va-3*vb
            freq=round(Fraction(vb*(len(a)-3*len(b)),len(b))) if b else 0
            campos={'registros_referencia':len(b),'registros_recentes':len(a),'base_trimestral_centavos':3*vb,'recente_centavos':va,'contribuicao_centavos':dif,'efeito_frequencia_centavos':freq,'efeito_valor_medio_centavos':dif-freq if b else 0,'efeito_sem_referencia_centavos':0 if b else dif}
            exigir(all(x[k]==v for k,v in campos.items()),'DECOMPOSICAO')
            pos+=max(0,dif); neg+=min(0,dif)
        exigir(pos==c['contribuicoes_positivas_centavos'] and neg==c['compensacoes_centavos'] and pos+neg==delta,'RECONCILIACAO')
        decisoes[f'historico:{cid}:{cat}']=(cid,2,delta,'impacto_adicional_historico_simulado'); impacto+=delta
    if agenda is None:
        exigir(fontes['agenda']=='indisponivel' and 'manutencao' not in central['resultados'],'AGENDA_AUSENTE')
    else:
        exigir(fontes['agenda'] in ('disponivel_datas_registradas','parcial_sem_aba_em_alguns_condominios'),'AGENDA_FONTE')
        m=central['resultados']['manutencao']; original=indexar(agenda,lambda r:(r['condominio_id'],r['linha']))
        rel=indexar(m['agenda'],lambda r:(r['condominio_id'],r['evidencia']['linha']))
        exigir(set(original)==set(rel),'COBERTURA_AGENDA')
        nomes=Counter((r['condominio_id'],chave(r['nome'])) for r in agenda)
        def data(s):
            if s in ('',None): return None,False
            try:
                d=date.fromisoformat(s); return (d,False) if d.isoformat()==s else (None,True)
            except (ValueError,TypeError): return None,True
        for (cid,linha),r in original.items():
            u,ui=data(r['ultima']); p,pi=data(r['proxima']); dias=None
            if nomes[cid,chave(r['nome'])]>1: estado='identificacao_ambigua'
            elif ui or pi or (u and u>hoje) or (u and p and p<=u): estado='datas_inconsistentes'
            elif p is None: estado='sem_proxima_data'
            else:
                dias=(p-hoje).days; estado='prazo_registrado_vencido' if dias<0 else 'prazo_em_30_dias' if dias<=30 else 'prazo_futuro'
            x=rel[cid,linha]; exigir(x['evidencia']==r and x['nome']==chave(r['nome']) and x['estado']==estado and x['dias_ate_prazo']==dias,'AGENDA_DIVERGENTE')
            if estado!='prazo_futuro': decisoes[f'agenda:{cid}:{linha}']=(cid,1 if dias is not None and dias<0 else 2,None,None)
        exigir(dict(Counter(r['estado'] for r in rel.values()))==m['contagem_agenda'],'CONTAGEM_AGENDA')
        rec=defaultdict(list)
        for (cid,cat),rs in grupos.items():
            if cat=='manutencao condominio':
                for r in rs: rec[cid,cat,chave(r.descricao)].append(r)
        rec={k:rs for k,rs in rec.items() if len({r.data_original for r in rs})>=3 and len({r.competencia for r in rs})>=2}
        rr=indexar(m['recorrencias'],lambda r:(r['condominio_id'],r['categoria'],r['descricao']))
        exigir(set(rr)==set(rec),'COBERTURA_RECORRENCIAS')
        for (cid,cat,desc),rs in rec.items():
            x=rr[cid,cat,desc]; conferir_evidencias(x['evidencias'],rs); v=sum(r.valor_centavos for r in rs)
            exigir(x['total_centavos']==v and x['registros']==len(rs) and x['datas_distintas']==len({r.data_original for r in rs}) and x['meses_observados']==len({r.competencia for r in rs}),'RECORRENCIA_DIVERGENTE')
            decisoes[f'recorrencia:{cid}:{cat}:{desc}']=(cid,3,v,'gasto_observado_nao_adicional')
        exigir(m['total_recorrencias_centavos']==sum(r['total_centavos'] for r in rr.values()),'TOTAL_RECORRENCIAS')
    ds=indexar(central['decisoes'],lambda d:d['chave']); exigir(set(ds)==set(decisoes),'COBERTURA_DECISOES')
    for k,d in ds.items():
        exigir((d['condominio_id'],d['prioridade'],d['valor_centavos'],d['natureza_valor'])==decisoes[k] and d['origem']=='planilhas' and d.get('economia_comprovada_centavos') is None,'DECISAO_DIVERGENTE')
    return {'estado':'APROVADO_ESCOPO_LOCAL_SIMULADO','casos_historicos':len(casos),'impacto_historico_centavos':impacto,'decisoes':len(ds),'linhas_agenda':len(agenda or []),'economia_comprovada_centavos':None}


def auditar_carteira_v80(central, carteira):
    ds=indexar(central['decisoes'],lambda d:d['chave']); grupos=carteira['executivo']+carteira['fila']; vistos=set()
    exigir(carteira['fontes']==central['fontes'] and carteira['economia_comprovada_centavos'] is None,'CARTEIRA_FONTES')
    temas={'historico':'custos','recorrencia':'custos','agenda':'manutencao','solicitacao':'financeiro','operacional':'operacao','concentracao':'fornecedores','demanda':'fornecedores'}
    ident=set()
    for g in grupos:
        ks=g['chaves']; exigir(bool(ks) and not (set(ks)&vistos) and len(set(ks))==len(ks) and set(ks)<=set(ds),'CARTEIRA_COBERTURA')
        rs=[ds[k] for k in ks]; grupo=(g['origem'],g['condominio_id'],g['tema']); exigir(grupo not in ident,'CARTEIRA_GRUPO_DUPLICADO'); ident.add(grupo)
        exigir(all((d['origem'],d['condominio_id'],temas[d['chave'].split(':')[0]])==grupo for d in rs),'CARTEIRA_GRUPO')
        exigir(g['prioridade']==min(d['prioridade'] for d in rs) and g['casos_p1']==sum(d['prioridade']==1 for d in rs) and g['quantidade_casos']==len(rs),'CARTEIRA_PRIORIDADE')
        exigir(g['economia_comprovada_centavos'] is None,'CARTEIRA_ECONOMIA')
        ac=indexar(g['acoes'],lambda a:a['chave']); exigir(set(ac)==set(ks) and all(all(ac[k][f]==ds[k][f] for f in ('acao','fato','prioridade')) for k in ks),'CARTEIRA_ACOES')
        valores=defaultdict(list)
        for d in rs:
            if d['valor_centavos'] is not None: valores[d['natureza_valor']].append(d['valor_centavos'])
        exigir(g['maiores_valores_por_natureza']=={k:max(v) for k,v in valores.items()},'CARTEIRA_VALORES')
        vistos.update(ks)
    exigir(vistos==set(ds) and carteira['total_casos']==len(ds) and carteira['total_grupos']==len(grupos) and carteira['total_p1']==sum(d['prioridade']==1 for d in ds.values()),'CARTEIRA_TOTAIS')
    exigir(all(g['prioridade']!=1 for g in carteira['fila']),'CARTEIRA_P1_OMITIDO')
    return True
