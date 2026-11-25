# -*- coding: utf-8 -*-
"""Reabre as fontes originais para auditar o ensaio central local. Sem rede."""
import argparse
from pathlib import Path
import json
import hashlib
import sys
import tempfile
import os
from intelligence_ensaio_v80 import REPO, assinatura
from auditar_planilhas import extrair_base, extrair_condominio, canon, LeitorXlsm, texto, data_excel
from custos_importacao_v77 import validar_lote
from intelligence_central_v80 import executar_central_v80
from intelligence_prescritiva_v80 import priorizar_v80
from intelligence_auditoria_v80 import auditar_local_v80, auditar_carteira_v80, exigir


def executar(arquivo,pasta):
    raiz=(Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA').resolve(strict=True)
    origem=arquivo.resolve(strict=True); pasta=pasta.resolve(strict=True)
    exigir(not raiz.is_relative_to(REPO) and not raiz.is_relative_to(pasta) and origem.is_relative_to(raiz) and origem.name=='EVIDENCIAS_CENTRAL.json','CAMINHO')
    with origem.open('rb') as f: raw=f.read(100_000_001)
    exigir(0<len(raw)<=100_000_000,'TAMANHO')
    def pares(ps):
        d={}
        for k,v in ps:
            exigir(k not in d,'JSON_DUPLICADO'); d[k]=v
        return d
    c=json.loads(raw,object_pairs_hook=pares)
    base=(pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    exigir(base.parent==pasta and assinatura(base)==c['hash_cadastro'],'CADASTRO_ALTERADO')
    mapa,_,_,_=extrair_base(base); arquivos=[(pasta/a).resolve(strict=True) for _,a in mapa]
    exigir(len(mapa)==10 and len({canon(n) for n,_ in mapa})==10 and len(set(arquivos))==10 and all(a.parent==pasta and a!=base and a.suffix.lower()=='.xlsm' for a in arquivos),'CADASTRO')
    nomes={i:n for i,(n,_) in enumerate(mapa,1)}
    exigir({str(i):n for i,n in nomes.items()}==c['nomes_locais'],'MAPA_ALTERADO')
    manifesto=[{'condominio_id':i,'arquivo':a.name,'sha256':assinatura(a)} for i,a in enumerate(arquivos,1)]
    exigir(manifesto==c['arquivos'],'PLANILHAS_ALTERADAS')
    registros=[]; agenda=[]; sem_aba=[]; pendentes=0
    for i,a in enumerate(arquivos,1):
        f=extrair_condominio(a,nomes[i]); exigir(not any(f[k] for k in ('sem_id','duplicados','datas_invalidas','valores_invalidos')),'INTEGRIDADE_ORIGEM')
        registros.extend(f['classificadas'].values()); pendentes+=f['pendentes']
        leitor=LeitorXlsm(a)
        try:
            if 'PRAZOS' not in leitor.abas: sem_aba.append(i); continue
            for linha,d in leitor.linhas('PRAZOS',{'A','B','C','D'}):
                if linha<=1 or not texto(d.get('A')): continue
                agenda.append({'condominio_id':i,'linha':linha,'nome':texto(d['A']),'periodicidade':texto(d.get('B')),'ultima':data_excel(d.get('C')),'proxima':data_excel(d.get('D'))})
        finally: leitor.fechar()
    exigir(assinatura(base)==c['hash_cadastro'] and all(assinatura(a)==m['sha256'] for a,m in zip(arquivos,manifesto)),'ORIGEM_MUDOU_DURANTE_LEITURA')
    exigir(sem_aba==c['sem_aba_prazos'] and pendentes==c['nao_classificados_excluidos'],'COBERTURA_ORIGEM')
    dados=validar_lote(registros,{n:i for i,n in nomes.items()}); ag=agenda if len(sem_aba)<len(nomes) else None
    r=auditar_local_v80(c,dados,ag)
    # Reprodução adicional para conferir textos, relações e metadados: não independente.
    novo=executar_central_v80(data_referencia=c['data_referencia'],competencia=c['competencia'],historico=dados,agenda=ag,nomes_locais=nomes,simulacao=True)
    if sem_aba and ag is not None: novo['fontes']['agenda']='parcial_sem_aba_em_alguns_condominios'
    exigir(all(c.get(k)==v for k,v in novo.items()),'REPRODUCAO_CENTRAL_DIVERGENTE')
    carteira=priorizar_v80(c); auditar_carteira_v80(c,carteira)
    r.update({'sha256_relatorio':hashlib.sha256(raw).hexdigest(),'execucao_central':c['execucao'],'competencia':c['competencia'],'fontes':c['fontes'],'grupos_executivos':len(carteira['executivo']),'p1_preservados':carteira['total_p1'],'limites':['Escopo local simulado; não valida completude mensal nem causas operacionais.','Carteira regenerada para ensaio; não verifica um email ou relatório já enviado.','Reprodução textual usa o mesmo motor; auditoria matemática separada.']})
    destino=origem.parent/'AUDITORIA_V80.json'
    fd,tmp=tempfile.mkstemp(prefix='.auditoria-',dir=origem.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,indent=2)
        os.replace(tmp,destino)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    print(r['estado']); print('Casos historicos auditados:',r['casos_historicos']); print('Decisoes auditadas:',r['decisoes']); print('P1 preservados:',r['p1_preservados']); print('Relatorio privado:',destino)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--evidencias',required=True,type=Path); p.add_argument('--planilhas',type=Path,default=Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS'); a=p.parse_args()
    try: executar(a.evidencias,a.planilhas)
    except Exception as e:
        print('AUDITORIA BLOQUEADA:',type(e).__name__,str(e) if type(e).__name__=='ErroAuditoria' else 'Verificar origem e estrutura.',file=sys.stderr); sys.exit(1)
