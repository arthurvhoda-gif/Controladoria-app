# -*- coding: utf-8 -*-
"""Investigacao contabil de aumentos V8.0. Funcoes puras, sem rede/banco."""
from collections import defaultdict
from fractions import Fraction
import unicodedata


def chave_descricao(texto):
    s = unicodedata.normalize('NFKD', texto.casefold())
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).split())


def evidencia(r):
    return {'id': r.id_origem, 'data': r.data_original.isoformat(),
            'valor_centavos': r.valor_centavos, 'hash': r.hash_conteudo}


def _ordenar(rs):
    return sorted(rs, key=lambda r: (r.data_original, r.id_origem))


def investigar_aumento(registros, oportunidade, meses):
    """Explica aritmeticamente o impacto; nao atribui causa operacional.

    A mediana e representada por um mes observado, com desempate cronologico.
    A referencia trimestral e uma repeticao desse mes, nao o trimestre real.
    """
    meses = tuple(meses)
    if len(meses) != 6 or tuple(sorted(set(meses))) != meses:
        raise ValueError('Sao necessarias seis competencias ordenadas e distintas.')
    from datetime import date
    ds = [date.fromisoformat(m + '-01') for m in meses]
    if any(b.year*12+b.month != a.year*12+a.month+1 for a,b in zip(ds,ds[1:])):
        raise ValueError('Competencias nao consecutivas.')
    cid = oportunidade.condominio_id
    cat = oportunidade.categoria
    grupos = defaultdict(list)
    ids = set()
    for r in registros:
        mes = r.competencia.strftime('%Y-%m')
        if r.condominio_id != cid or r.categoria_chave != cat or mes not in meses:
            continue
        if r.id_origem in ids:
            raise ValueError('ID de origem repetido na investigacao.')
        ids.add(r.id_origem)
        if r.valor_centavos > 0:
            grupos[mes].append(r)
    totais = {m: sum(r.valor_centavos for r in grupos[m]) for m in meses}
    if any(v <= 0 for v in totais.values()):
        raise ValueError('Mes sem base positiva para investigacao.')
    mediana = sorted(totais[m] for m in meses[:3])[1]
    mes_base = min(m for m in meses[:3] if totais[m] == mediana)
    recentes = [r for m in meses[3:] for r in grupos[m]]
    anteriores = [r for m in meses[:3] for r in grupos[m]]
    total_recente = sum(r.valor_centavos for r in recentes)
    impacto = total_recente - 3*mediana
    aumentos = sum(totais[m]-mediana >= 10000 and (totais[m]-mediana)*100 >= 15*mediana for m in meses[3:])
    if (mediana != oportunidade.referencia_mensal_centavos or
        total_recente != oportunidade.total_recente_centavos or
        impacto != oportunidade.impacto_adicional_centavos or
        aumentos != oportunidade.meses_com_aumento or impacto <= 0 or aumentos < 2):
        raise ValueError('Oportunidade nao reconciliada com as evidencias.')
    base, atual = defaultdict(list), defaultdict(list)
    for r in grupos[mes_base]:
        base[chave_descricao(r.descricao)].append(r)
    for r in recentes:
        atual[chave_descricao(r.descricao)].append(r)
    vistos = {chave_descricao(r.descricao) for r in anteriores}
    linhas = []
    for k in sorted(set(base) | set(atual)):
        b, a = _ordenar(base[k]), _ordenar(atual[k])
        vb = sum(r.valor_centavos for r in b)
        va = sum(r.valor_centavos for r in a)
        delta = va - 3*vb
        # Decomposicao exata em centavos: quantidade de REGISTROS, nao de bens.
        # O residual e variacao de valor medio por registro, nao preco unitario.
        if b:
            efeito_frequencia = round(Fraction(vb, len(b)) * (len(a)-3*len(b)))
            efeito_valor = delta - efeito_frequencia
            efeito_sem_ref = 0
        else:
            efeito_frequencia = efeito_valor = 0
            efeito_sem_ref = delta
        if not b:
            status = 'nao_observado_nos_tres_meses_anteriores' if k not in vistos else 'ausente_no_mes_de_referencia'
        elif not a:
            status = 'ausente_no_trimestre_recente'
        else:
            status = 'descricao_presente_nos_dois_periodos'
        linhas.append({'descricao_normalizada': k, 'status': status,
            'registros_referencia': len(b), 'registros_recentes': len(a),
            'base_trimestral_centavos': 3*vb, 'recente_centavos': va,
            'contribuicao_centavos': delta,
            'efeito_frequencia_centavos': efeito_frequencia,
            'efeito_valor_medio_centavos': efeito_valor,
            'efeito_sem_referencia_centavos': efeito_sem_ref,
            'evidencias_referencia': [evidencia(r) for r in b],
            'evidencias_recentes': [evidencia(r) for r in a]})
    linhas.sort(key=lambda x: (-x['contribuicao_centavos'], x['descricao_normalizada']))
    pos = sum(max(0,x['contribuicao_centavos']) for x in linhas)
    neg = sum(min(0,x['contribuicao_centavos']) for x in linhas)
    resultado = {'condominio_id': cid, 'categoria': cat, 'competencias': list(meses),
        'mes_referencia': mes_base, 'totais_mensais_centavos': totais,
        'impacto_centavos': impacto, 'contribuicoes_positivas_centavos': pos,
        'compensacoes_centavos': neg, 'decomposicao': linhas,
        'estado': 'impacto_contabil_reconciliado_causa_operacional_nao_comprovada',
        'evidencias_tres_meses_anteriores': [evidencia(r) for r in _ordenar(anteriores)],
        'limites': ['Descricao igual nao comprova mesmo equipamento, fornecedor ou servico.',
                    'Frequencia significa numero de registros; valor medio nao e preco unitario.',
                    'Sem contratos, quantidades e ordens de servico, nao concluir causa nem economia.']}
    verificar_investigacao(resultado)
    return resultado


def verificar_investigacao(r):
    """Recalcula invariantes a partir das referencias, sem confiar nos subtotais."""
    def exigir(ok):
        if not ok:
            raise ValueError('Falha na verificacao independente da decomposicao.')
    meses = r['competencias']; base = r['mes_referencia']; linhas = r['decomposicao']
    anteriores = r['evidencias_tres_meses_anteriores']
    totais = {m: 0 for m in meses}
    ids = set()
    for e in anteriores:
        m = e['data'][:7]
        exigir(m in meses[:3] and e['id'] not in ids and e['valor_centavos'] > 0)
        ids.add(e['id']); totais[m] += e['valor_centavos']
    esperado = {e['id']: e for e in anteriores if e['data'][:7] == base}
    usado = set(); descricoes = set(); pos = neg = 0
    for x in linhas:
        b, a = x['evidencias_referencia'], x['evidencias_recentes']
        exigir(x['descricao_normalizada'] not in descricoes)
        descricoes.add(x['descricao_normalizada'])
        for e in b:
            exigir(e['id'] in esperado and esperado[e['id']] == e and e['id'] not in usado)
            usado.add(e['id'])
        for e in a:
            m = e['data'][:7]
            exigir(m in meses[3:] and e['id'] not in ids and e['valor_centavos'] > 0)
            ids.add(e['id']); totais[m] += e['valor_centavos']
        vb = sum(e['valor_centavos'] for e in b); va = sum(e['valor_centavos'] for e in a)
        delta = va-3*vb
        exigir(x['registros_referencia'] == len(b) and x['registros_recentes'] == len(a))
        exigir(x['base_trimestral_centavos'] == 3*vb and x['recente_centavos'] == va and x['contribuicao_centavos'] == delta)
        freq = round(Fraction(vb,len(b))*(len(a)-3*len(b))) if b else 0
        exigir(x['efeito_frequencia_centavos'] == freq and x['efeito_valor_medio_centavos'] == (delta-freq if b else 0) and x['efeito_sem_referencia_centavos'] == (0 if b else delta))
        pos += max(delta,0); neg += min(delta,0)
    exigir(usado == set(esperado))
    exigir(totais == r['totais_mensais_centavos'])
    mediana = sorted(totais[m] for m in meses[:3])[1]
    exigir(base == min(m for m in meses[:3] if totais[m] == mediana))
    exigir(pos == r['contribuicoes_positivas_centavos'] and neg == r['compensacoes_centavos'])
    exigir(pos+neg == r['impacto_centavos'] == sum(totais[m] for m in meses[3:])-3*mediana)
    return True
