# -*- coding: utf-8 -*-
"""Vincula o diagnóstico de cobertura à mesma extração financeira.
Não confirma fechamento nem transforma valores brutos em economia.
"""
from collections import Counter
from datetime import date


def exigir(ok, codigo):
    if not ok:
        raise ValueError(codigo)


def conferir_cobertura(cobertura, manifesto, nomes, registros, referencia):
    exigir(type(referencia) is date and cobertura['referencia']==referencia.isoformat(), 'COBERTURA_REFERENCIA_DIVERGENTE')
    exigir(cobertura['versao']=='8.0-cobertura-1' and cobertura['economia_comprovada_centavos'] is None, 'COBERTURA_ESCOPO')
    exigir(cobertura['nomes']==nomes, 'COBERTURA_CADASTRO_DIVERGENTE')
    exigir(cobertura['manifesto']=={k:manifesto[k] for k in ('hash_cadastro','arquivos')}, 'COBERTURA_ARQUIVOS_DIVERGENTES')
    c=cobertura['totais']['classificado']; n=cobertura['totais']['nao_classificado']
    exigir(c['registros']==len(registros)==manifesto['lancamentos_validados'] and n['registros']==manifesto['nao_classificados_excluidos'], 'COBERTURA_CONTAGEM_DIVERGENTE')
    vals=[r.valor_centavos for r in registros]
    exigir(all(type(v) is int for v in vals), 'COBERTURA_VALOR_INVALIDO')
    exigir(c['positivos_centavos']==sum(v for v in vals if v>0) and c['negativos_centavos']==sum(v for v in vals if v<0) and c['positivos']==sum(v>0 for v in vals) and c['negativos']==sum(v<0 for v in vals) and c['zeros']==sum(v==0 for v in vals) and c['valor_invalido']==0, 'COBERTURA_VALORES_DIVERGENTES')
    exigir(Counter(r.condominio_id for r in registros)==Counter({cid:sum(x['registros'] for x in cobertura['mensal'] if x['condominio_id']==cid and x['classificacao']=='classificado') for cid in nomes}), 'COBERTURA_CONTAGEM_CONDOMINIO')
    return cobertura


def linhas_cobertura(c):
    a=c['totais']['classificado']; b=c['totais']['nao_classificado']
    def moeda(v):
        sinal='-' if v<0 else ''; inteiro,frac=divmod(abs(v),100)
        return sinal+'R$ '+f'{inteiro:,}'.replace(',','.')+f',{frac:02d}'
    linhas=['COBERTURA FINANCEIRA - PLANILHAS REAIS, SEM FECHAMENTO CONFIRMADO',
            f"Classificados: {a['registros']} registros | positivos brutos: {moeda(a['positivos_centavos'])}",
            f"Nao classificados: {b['registros']} registros | positivos brutos: {moeda(b['positivos_centavos'])}",
            f"Mes anterior ({c['competencia_anterior']}): {sum(x['competencia_anterior_sem_positivo_classificado'] for x in c['cobertura'])} de {len(c['cobertura'])} condominios sem valores positivos classificados.",
            f"Sinais temporais: {len(c['sinais'])} | grupos candidatos a duplicidade: {len(c['candidatos_duplicidade'])}",
            f"Datas invalidas: {c['datas_invalidas']} | futuras: {c['datas_futuras']}"]
    for x in c['cobertura']:
        linhas.append(f"{c['nomes'][x['condominio_id']]}: ultimo mes positivo classificado {x['ultimo_mes_classificado_positivo'] or 'nao observado'}")
    for s in c['sinais']:
        linhas.append(f"Sinal {s['mes']}: {moeda(s['positivos_nao_classificados_centavos'])} versus mediana observada {moeda(s['mediana_tres_meses_centavos'])}.")
        grupos=[x for x in c['concentracoes'] if x['mes']==s['mes']]
        if grupos:
            g=max(grupos,key=lambda x:x['positivos_nao_classificados_centavos'])
            linhas.append(f"Maior concentracao: {c['nomes'][g['condominio_id']]} | {moeda(g['positivos_nao_classificados_centavos'])}")
    linhas.extend(['Nao somar com pagamentos do app. Nao comprova despesa liquida, duplicidade ou economia.','Detalhes e referencias: COBERTURA_FINANCEIRA.json.',''])
    return linhas
