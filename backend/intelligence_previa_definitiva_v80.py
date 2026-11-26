# -*- coding: utf-8 -*-
"""Prévia local real, com histórico explicitamente exploratório. Sem rede ou envio."""
from datetime import date
from collections import defaultdict
from intelligence_cobertura_ciclo_v80 import conferir_cobertura, linhas_cobertura


def exigir(ok, codigo):
    if not ok:
        raise ValueError(codigo)


def mes_num(d):
    return d.year * 12 + d.month - 1


def mes_texto(n):
    return f'{n//12:04d}-{n%12+1:02d}'


def escolher_competencia(registros, nomes, hoje):
    """Maximiza condomínios com positivo em cada um dos seis meses.
    Empate: janela mais recente. Nenhum dado confirma fechamento.
    """
    exigir(type(hoje) is date and isinstance(nomes, dict) and nomes, 'PREVIA_CADASTRO')
    por = defaultdict(set)
    anterior = mes_num(hoje)-1
    for r in registros:
        exigir(r.condominio_id in nomes and type(r.data_original) is date and type(r.competencia) is date and r.competencia == r.data_original.replace(day=1), 'PREVIA_REGISTRO')
        m = mes_num(r.competencia)
        if m <= anterior and r.data_original <= hoje and r.valor_centavos > 0:
            por[m].add(r.condominio_id)
    opcoes = []
    for m in sorted(por):
        ids = set(nomes)
        for j in range(m-5,m+1):
            ids &= por.get(j,set())
        if ids:
            opcoes.append((len(ids),m,sorted(ids)))
    ultimo = max(por, default=None)
    if opcoes:
        _,m,ids = max(opcoes,key=lambda t:(t[0],t[1]))
    else:
        m,ids = None,[]
    return dict(competencia=mes_texto(m) if m is not None else None,
                janela=[mes_texto(j) for j in range(m-5,m+1)] if m is not None else [],
                condominios_com_positivo_em_seis_meses=ids,
                condominios_sem_positivo_em_algum_mes=sorted(set(nomes)-set(ids)),
                ultimo_mes_calendario_encerrado=mes_texto(anterior),
                ultimo_mes_positivo_observado=mes_texto(ultimo) if ultimo is not None else None,
                fechamento_confirmado=False,
                regra='maior cobertura de seis meses; empate pela mais recente')


def gerar_previa(*,registros,agenda,nomes,sem_aba,manifesto,cobertura,hoje):
    exigir(isinstance(nomes,dict) and len(nomes)==10 and not any('ficticio' in n.casefold() or 'fictício' in n.casefold() for n in nomes.values()),'PREVIA_CADASTRO_LOCAL')
    exigir(isinstance(sem_aba,list) and len(set(sem_aba))==len(sem_aba) and set(sem_aba)<=set(nomes) and all(a['condominio_id'] in nomes and a['condominio_id'] not in sem_aba for a in agenda),'PREVIA_AGENDA')
    conferir_cobertura(cobertura,manifesto,nomes,registros,hoje)
    selecao=escolher_competencia(registros,nomes,hoje)
    r=dict(versao='8.0-previa-local-1',estado='PREVIA_COBERTURA_SEM_BASE_HISTORICA',referencia=hoje.isoformat(),selecao=selecao,nomes=nomes,manifesto=manifesto,cobertura=cobertura,central=None,carteira=None,auditoria=None,app_definitivo='indisponivel_nao_publicado',economia_comprovada_centavos=None,envio_autorizado=False)
    if selecao['competencia'] is None:
        return r
    from intelligence_central_v80 import executar_central_v80
    from intelligence_auditoria_v80 import auditar_local_v80,auditar_carteira_v80
    from intelligence_prescritiva_v80 import priorizar_v80
    ag=None if len(sem_aba)==len(nomes) else agenda
    c=executar_central_v80(data_referencia=hoje.isoformat(),competencia=selecao['competencia'],historico=registros,agenda=ag,nomes_locais=nomes,simulacao=True)
    c['lancamentos_validados']=len(registros)
    if sem_aba and ag is not None: c['fontes']['agenda']='parcial_sem_aba_em_alguns_condominios'
    exigir(all(c['fontes'][k]=='indisponivel' for k in ('financeiro','operacional','compras')) and not c['contextos'] and all(d['origem']=='planilhas' for d in c['decisoes']),'PREVIA_FONTE_APP')
    a=auditar_local_v80(c,registros,ag); p=priorizar_v80(c)
    exigir(a['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and auditar_carteira_v80(c,p) is True and a['decisoes']==p['total_casos']==len(c['decisoes']),'PREVIA_AUDITORIA')
    r.update(estado='PREVIA_LOCAL_AUDITADA',central=c,carteira=p,auditoria=a)
    return r


def moeda(v):
    sinal='-' if v<0 else ''; a,b=divmod(abs(v),100)
    return sinal+'R$ '+f'{a:,}'.replace(',','.')+f',{b:02d}'


def parecer(r):
    exigir(r['envio_autorizado'] is False and r['economia_comprovada_centavos'] is None,'PREVIA_ENVIO')
    s=r['selecao']; nomes=r['nomes']; p=r['carteira']; c=r['central']
    ls=['HAIZE INTELLIGENCE V8.0 | PREVIA EXECUTIVA PRIVADA','PLANILHAS REAIS - ANALISE EXPLORATORIA SEM FECHAMENTO CONFIRMADO','SEM ENVIO | APP DEFINITIVO INDISPONIVEL | NENHUM DADO FICTICIO DO APP',f"Referencia: {r['referencia']}",f"Ultimo mes calendario encerrado: {s['ultimo_mes_calendario_encerrado']}",f"Ultimo mes positivo classificado observado: {s['ultimo_mes_positivo_observado'] or 'nenhum'}",f"Competencia historica selecionada: {s['competencia'] or 'sem base de seis meses'}",f"Regra: {s['regra']}",f"Condominios com positivo em cada mes da janela: {len(s['condominios_com_positivo_em_seis_meses'])}/{len(nomes)}",'Presenca de dados nao confirma cobertura mensal nem fechamento.','']
    if s['condominios_sem_positivo_em_algum_mes']:
        ls.append('Sem positivo em algum mes da janela: '+', '.join(nomes[i] for i in s['condominios_sem_positivo_em_algum_mes']))
    ls.extend(linhas_cobertura(r['cobertura']))
    ls.extend(['ACOES DE QUALIDADE DOS DADOS','Atualizar competencias ausentes e confirmar fechamento; revisar classificacoes com documentos de origem.','Conferir concentracoes e candidatos a duplicidade antes de qualquer correcao.',''])
    if p is None:
        ls.append('Sem janela elegivel de seis meses: historico e agenda nao auditados neste ciclo.')
    else:
        ls.extend([f"Auditoria: {r['auditoria']['estado']}",f"Categorias avaliadas: {c['resultados']['historico']['categorias_avaliadas']} | sem base: {c['resultados']['historico']['categorias_sem_base']}",f"Impacto adicional historico exploratorio: {moeda(r['auditoria']['impacto_historico_centavos'])} (nao economia)",f"Candidatos: {p['total_casos']} | P1: {p['total_p1']} | grupos na fila: {len(p['fila'])}",'PRIORIDADES EXECUTIVAS'])
        ds={d['chave']:d for d in c['decisoes']}
        for g in p['executivo']:
            ls.append(f"P{g['prioridade']} | {nomes[g['condominio_id']]} | {g['tema']}")
            for k in g['chaves']:
                d=ds[k]; ls.extend([f"  {k}: {d['fato']}",f"  Acao: {d['acao']}"])
                if d['valor_centavos'] is not None: ls.append(f"  {moeda(d['valor_centavos'])} | {d['natureza_valor']}")
                ls.append('  Limites: '+' '.join(d['hipoteses_nao_comprovadas']))
        ls.extend(['Fila integral e evidencias em PREVIA_AUDITADA.json.','']+c['limites'])
    ls.extend(['Sem economia comprovada. Sem acesso ao banco definitivo, sem conclusoes sobre compras, pagamentos ou servicos do app.','CONFIDENCIAL - NAO ENVIADO'])
    return '\n'.join(ls)+'\n'
