# -*- coding: utf-8 -*-
"""Ciclo integrado de homologacao. Nao escreve, conecta ou envia dados.
Dados reais locais e app ficticio: sem vinculos, sem soma entre fontes.
"""
from copy import deepcopy
from datetime import date
from intelligence_central_v80 import executar_central_v80
from intelligence_auditoria_v80 import auditar_local_v80, auditar_carteira_v80, exigir
from intelligence_auditoria_app_v80 import auditar_app_v80
from intelligence_prescritiva_v80 import priorizar_v80

FICTICIOS = {'Condominio Ficticio Alfa', 'Condominio Ficticio Beta'}
APP_FONTES = ('financeiro','operacional','compras')

def executar_ciclo_v80(*, registros, agenda, nomes, sem_aba, competencia, snapshot, limite=5):
    """Audita os dois escopos e so entao devolve a carteira.
    Nenhuma escrita ou envio. A agenda pode ter cobertura parcial explicita.
    """
    exigir(isinstance(snapshot,dict) and isinstance(snapshot.get('condominios'),dict)
           and len(snapshot['condominios'])==2 and set(snapshot['condominios'].values())==FICTICIOS,'CICLO_APP_NAO_FICTICIO')
    exigir(all(isinstance(snapshot.get(k),(list,tuple)) for k in ('solicitacoes','lancamentos','servicos','participantes','itens','execucoes')),'CICLO_APP_INCOMPLETO')
    exigir(isinstance(nomes,dict) and len(nomes)==10 and not set(nomes.values()) & FICTICIOS,'CICLO_CADASTRO_LOCAL')
    exigir(isinstance(sem_aba,list) and len(set(sem_aba))==len(sem_aba) and set(sem_aba)<=set(nomes),'CICLO_COBERTURA_AGENDA')
    exigir(isinstance(agenda,(list,tuple)) and all(a['condominio_id'] in nomes and a['condominio_id'] not in sem_aba for a in agenda),'CICLO_AGENDA')
    dia=snapshot['data_referencia']; hoje=date.fromisoformat(dia)
    exigir(hoje.isoformat()==dia and competencia<dia[:7],'CICLO_COMPETENCIA_NAO_ENCERRADA')
    ag=None if len(sem_aba)==len(nomes) else agenda
    kwargs=dict(data_referencia=dia,competencia=competencia,historico=registros,agenda=ag,nomes_locais=nomes,simulacao=True)
    local=executar_central_v80(**kwargs)
    local['lancamentos_validados']=len(registros)
    central=executar_central_v80(**kwargs,snapshot_app=snapshot)
    if sem_aba and ag is not None:
        local['fontes']['agenda']=central['fontes']['agenda']='parcial_sem_aba_em_alguns_condominios'
    # Conferencia de que a integracao nao mudou a investigacao local.
    exigir(not central['contextos'],'CICLO_VINCULO_INDEVIDO')
    exigir({k:v for k,v in central['resultados'].items() if k not in APP_FONTES}==local['resultados'],'CICLO_RESULTADO_LOCAL_DIVERGENTE')
    exigir([d for d in central['decisoes'] if d['origem']=='planilhas']==local['decisoes'],'CICLO_DECISAO_LOCAL_DIVERGENTE')
    exigir(all(central['fontes'][k]==local['fontes'][k] for k in ('historico','agenda')),'CICLO_FONTES_LOCAIS')
    al=auditar_local_v80(local,registros,ag)
    carteira=priorizar_v80(central,limite)
    aa=auditar_app_v80(snapshot,central,carteira)
    auditar_carteira_v80(central,carteira)
    exigir(al['estado']=='APROVADO_ESCOPO_LOCAL_SIMULADO' and aa['estado']=='APROVADO_ESCOPO_SNAPSHOT_APP','CICLO_AUDITORIA')
    exigir(al['decisoes']+aa['decisoes']==len(central['decisoes'])==carteira['total_casos'],'CICLO_COBERTURA')
    exigir(central['economia_comprovada_centavos'] is None,'CICLO_ECONOMIA')
    return dict(versao='8.0-executor-homologacao-1',estado='APROVADO_HOMOLOGACAO_MISTA',
                central=central,carteira=carteira,auditoria_local=al,auditoria_app=aa,
                local_para_memoria=local,nomes_locais=deepcopy(nomes),nomes_app=deepcopy(snapshot['condominios']),
                limites=['Planilhas reais, cobertura mensal nao confirmada; app exclusivamente ficticio.',
                         'Sem vinculos entre os cadastros, sem somar valores de origens distintas.',
                         'Auditorias nao certificam causas, documentos, completude mensal ou economia.',
                         'Sem envio, sem alteracoes ao app, sem agendamento e sem memoria integrada.'])
