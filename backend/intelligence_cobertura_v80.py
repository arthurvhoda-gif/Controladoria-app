# -*- coding: utf-8 -*-
"""Diagnóstico de cobertura de linhas da planilha. Não confirma despesas, fechamento ou economia."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
import unicodedata


def chave(x):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(x or '')) if not unicodedata.combining(c)).casefold().split())


def mes_anterior(d):
    return date(d.year - (d.month == 1), 12 if d.month == 1 else d.month-1, 1).isoformat()[:7]


def mes_valido(x):
    try:
        d=date.fromisoformat(x)
        return d.isoformat()[:7] if d.isoformat()==x else None
    except (TypeError,ValueError):
        return None


def valor_centavos(x):
    if not isinstance(x,Decimal) or not x.is_finite(): return None
    return int((x*100).to_integral_value(rounding=ROUND_HALF_UP))


def novo_grupo():
    return dict(registros=0, positivos=0, positivos_centavos=0, negativos=0, negativos_centavos=0, zeros=0, valor_invalido=0)


def somar(g,v):
    g['registros']+=1
    if v is None: g['valor_invalido']+=1
    elif v>0: g['positivos']+=1; g['positivos_centavos']+=v
    elif v<0: g['negativos']+=1; g['negativos_centavos']+=v
    else: g['zeros']+=1


def diagnosticar_cobertura_v80(nomes, linhas, referencia):
    """Linhas elegíveis de GASTOS, conforme regra do importador existente.
    Não classifica, não deduplica e não soma com livro de pagamentos do app.
    """
    if type(referencia) is not date or not isinstance(nomes,dict) or not nomes or any(type(k) is not int or k<=0 or not chave(v) for k,v in nomes.items()) or len({chave(v) for v in nomes.values()})!=len(nomes):
        raise ValueError('COBERTURA_CADASTRO')
    limite=mes_anterior(referencia)
    grupos=defaultdict(novo_grupo); total=defaultdict(novo_grupo)
    dup=defaultdict(list); maiores=defaultdict(list); vistos=set()
    datas_invalidas=0; futuras=0
    for r in linhas:
        cid=r['condominio_id']; l=r['linha']; k=(cid,l)
        if type(cid) is not int or cid not in nomes or type(l) is not int or l<2 or k in vistos or not chave(r['descricao']): raise ValueError('COBERTURA_LINHA')
        vistos.add(k)
        dt=r['data']; mes=mes_valido(dt)
        if mes is None: datas_invalidas+=1; mes='DATA_INVALIDA'
        elif date.fromisoformat(dt)>referencia: futuras+=1; mes='DATA_FUTURA'
        status='nao_classificado' if chave(r['categoria']) in ('','nao classificado') else 'classificado'
        v=valor_centavos(r['valor'])
        somar(grupos[cid,mes,status],v); somar(total[status],v)
        if mes not in ('DATA_INVALIDA','DATA_FUTURA') and v is not None and v>0:
            dup[cid,dt,chave(r['descricao']),v].append(l)
            if status=='nao_classificado': maiores[cid,mes].append((v,l))
    mensal=[]; por_mes=defaultdict(int); por_cond_mes=defaultdict(int)
    for (cid,mes,s),g in sorted(grupos.items()):
        mensal.append(dict(condominio_id=cid,mes=mes,classificacao=s,**g))
        if s=='nao_classificado' and mes not in ('DATA_INVALIDA','DATA_FUTURA'):
            por_mes[mes]+=g['positivos_centavos']; por_cond_mes[cid,mes]+=g['positivos_centavos']
    cobertura=[]
    for cid in sorted(nomes):
        def ultimo(s):
            ms=[m for (i,m,t),g in grupos.items() if i==cid and t==s and m<=limite and mes_valido(m+'-01') and g['positivos']>0]
            return max(ms,default=None)
        c=ultimo('classificado'); nc=ultimo('nao_classificado')
        cobertura.append(dict(condominio_id=cid,ultimo_mes_classificado_positivo=c,ultimo_mes_nao_classificado_positivo=nc,competencia_anterior_sem_positivo_classificado=c!=limite))
    concentracoes=[]
    for (cid,mes),v in sorted(por_cond_mes.items()):
        t=por_mes[mes]
        if t>0:
            concentracoes.append(dict(condominio_id=cid,mes=mes,positivos_nao_classificados_centavos=v,total_mes_centavos=t,participacao_pontos_base=v*10000//t,maiores_linhas=[dict(linha=l,valor_centavos=a) for a,l in sorted(maiores[cid,mes],key=lambda x:(-x[0],x[1]))[:3]]))
    # Regra de triagem transparente: mês anterior ao atual, três meses
    # consecutivos com valores positivos observados; não presume completude.
    sinais=[]
    for mes,v in sorted(por_mes.items()):
        if mes>limite: continue
        d=date.fromisoformat(mes+'-01'); anteriores=[]
        for _ in range(3):
            m=mes_anterior(d); anteriores.append(m); d=date.fromisoformat(m+'-01')
        if all(por_mes.get(m,0)>0 for m in anteriores):
            base=median(por_mes[m] for m in anteriores)
            if v>=2*base:
                sinais.append(dict(mes=mes,positivos_nao_classificados_centavos=v,mediana_tres_meses_centavos=base,meses_base=sorted(anteriores),regra='pelo_menos_duas_vezes_mediana_observada'))
    candidatos=[dict(condominio_id=cid,data=dt,valor_centavos=v,linhas=sorted(ls)) for (cid,dt,desc,v),ls in sorted(dup.items()) if len(ls)>1]
    return dict(versao='8.0-cobertura-1',referencia=referencia.isoformat(),competencia_anterior=limite,nomes=dict(nomes),totais={s:total[s] for s in ('classificado','nao_classificado')},mensal=mensal,cobertura=cobertura,concentracoes=concentracoes,sinais=sinais,candidatos_duplicidade=candidatos,datas_invalidas=datas_invalidas,datas_futuras=futuras,economia_comprovada_centavos=None,limites=['Valores positivos brutos de linhas, nao total contabil confirmado.','Duplicidade candidata exige mesma data, descricao normalizada e valor no mesmo condominio; nao confirma duplicidade.','Sem fechamento confirmado; ausencia de registros nao equivale a gasto zero.','Dados do mes corrente sao parciais; datas invalidas ou futuras ficam fora das tendencias.','Leitura de valores armazenados no XLSM, sem recalcular formulas.'])
