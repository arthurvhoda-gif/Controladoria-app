# -*- coding: utf-8 -*-
"""Homologação local do núcleo central. Sem rede, e-mail ou acesso a banco."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

from intelligence_ensaio_v80 import REPO, assinatura
from auditar_planilhas import extrair_base, extrair_condominio, canon, LeitorXlsm, texto, data_excel
from custos_importacao_v77 import validar_lote
from intelligence_central_v80 import executar_central_v80
from intelligence_relatorio_v78 import moeda


def executar(args):
    pasta=args.planilhas.resolve(strict=True); saida=args.saida.resolve()
    if saida.is_relative_to(pasta) or saida.is_relative_to(REPO):
        raise ValueError('Saída deve ficar fora do repositório e das planilhas.')
    base=(pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    if base.parent!=pasta: raise ValueError('Cadastro fora da pasta.')
    hb=assinatura(base); mapa,_,_,_=extrair_base(base)
    arquivos=[(pasta/a).resolve(strict=True) for _,a in mapa]
    if len(mapa)!=10 or len({canon(n) for n,_ in mapa})!=10 or len(set(arquivos))!=10 or any(a.parent!=pasta or a==base or a.suffix.lower()!='.xlsm' for a in arquivos):
        raise ValueError('Cadastro ou arquivos inválidos.')
    hashes={a:assinatura(a) for a in arquivos}; registros=[]; agenda=[]; sem_aba=[]; nao_classificados=0
    nomes={i:n for i,(n,_) in enumerate(mapa,1)}
    for i,((n,_),a) in enumerate(zip(mapa,arquivos),1):
        f=extrair_condominio(a,n)
        if any(f[k] for k in ('sem_id','duplicados','datas_invalidas','valores_invalidos')):
            raise ValueError('Problemas de integridade nas origens.')
        registros.extend(f['classificadas'].values()); nao_classificados+=f['pendentes']
        leitor=LeitorXlsm(a)
        try:
            if 'PRAZOS' not in leitor.abas:
                sem_aba.append(i); continue
            for linha,d in leitor.linhas('PRAZOS',{'A','B','C','D'}):
                if linha<=1 or not texto(d.get('A')): continue
                agenda.append({'condominio_id':i,'linha':linha,'nome':texto(d['A']),'periodicidade':texto(d.get('B')),'ultima':data_excel(d.get('C')),'proxima':data_excel(d.get('D'))})
        finally: leitor.fechar()
    if assinatura(base)!=hb or any(assinatura(a)!=h for a,h in hashes.items()):
        raise ValueError('Planilhas alteradas durante a leitura.')
    dados=validar_lote(registros,{n:i for i,n in nomes.items()})
    r=executar_central_v80(data_referencia=date.today().isoformat(),competencia=args.competencia,historico=dados,
                          agenda=agenda if len(sem_aba)<len(nomes) else None,nomes_locais=nomes,simulacao=True)
    if sem_aba and len(sem_aba)<len(nomes): r['fontes']['agenda']='parcial_sem_aba_em_alguns_condominios'
    r.update({'execucao':uuid.uuid4().hex,'utc':datetime.now(timezone.utc).isoformat(),
              'nomes_locais':nomes,'hash_cadastro':hb,'arquivos':[{'condominio_id':i,'arquivo':a.name,'sha256':hashes[a]} for i,a in enumerate(arquivos,1)],
              'sem_aba_prazos':sem_aba,'lancamentos_validados':len(dados),'nao_classificados_excluidos':nao_classificados})
    hist=r['resultados']['historico']; impacto=sum(c['impacto_centavos'] for c in hist['casos'])
    linhas=['HAIZE INTELLIGENCE V8.0 | PARECER CENTRAL PRIVADO','SIMULAÇÃO - COBERTURA MENSAL NÃO CONFIRMADA',
            f'Competência financeira: {args.competencia}; referência da agenda: {r["data_referencia"]}',
            'Fontes: '+', '.join(f'{k}={v}' for k,v in r['fontes'].items()),
            f'Condomínios sem aba PRAZOS: {len(sem_aba)}',f'Impacto histórico reconciliado: {moeda(impacto)} (não economia)',
            f'Categorias avaliadas: {hist["categorias_avaliadas"]}; sem base: {hist["categorias_sem_base"]}',
            f'Decisões/candidatos: {len(r["decisoes"])} (podem compartilhar evidências)','',
            'PRIMEIRAS 30 PRIORIDADES; TODAS AS EVIDÊNCIAS CONSTAM NO JSON']
    for d in r['decisoes'][:30]:
        nome=nomes.get(d['condominio_id'],'Sem vínculo')
        linhas.extend([f'P{d["prioridade"]} | {nome} | {d["chave"]}',d['fato'],d['acao']])
        if d['valor_centavos'] is not None: linhas.append(f'{moeda(d["valor_centavos"])} | {d["natureza_valor"]}')
        linhas.extend(['Limites: '+' '.join(d['hipoteses_nao_comprovadas']),''])
    linhas.extend(['LIMITES',*r['limites'],'Fontes do aplicativo não conectadas neste ensaio. Não emitir parecer de ausência de risco.','CONFIDENCIAL - SEM ENVIO'])
    saida.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix='.central-',dir=saida)); destino=saida/('central_'+r['execucao'])
    try:
        (tmp/'PARECER_CENTRAL.txt').write_text('\n'.join(linhas),encoding='utf-8')
        (tmp/'EVIDENCIAS_CENTRAL.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.rename(destino)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise
    print('ENSAIO CENTRAL V8.0 - SEM ENVIO'); print('Lancamentos validados:',len(dados)); print('Casos historicos reconciliados:',len(hist['casos'])); print('Impacto historico observado:',moeda(impacto))
    print('Linhas de agenda:',len(agenda)); print('Condominios sem aba PRAZOS:',len(sem_aba)); print('Decisoes/candidatos:',len(r['decisoes']))
    for k,v in r['fontes'].items(): print(k+':',v)
    print('Pasta privada:',destino)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--competencia',required=True); p.add_argument('--simulacao',action='store_true',required=True)
    p.add_argument('--planilhas',type=Path,default=Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS'); p.add_argument('--saida',type=Path,default=Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA')
    try: executar(p.parse_args())
    except Exception as e: print(f'EXECUCAO BLOQUEADA ({type(e).__name__}): {e}',file=sys.stderr); return 1
    return 0

if __name__=='__main__': sys.exit(main())
