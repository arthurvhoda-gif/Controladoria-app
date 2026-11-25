# -*- coding: utf-8 -*-
"""Ensaio privado de manutencao: somente leitura de planilhas, sem rede."""
import argparse, json, sys, tempfile, shutil, uuid
from pathlib import Path
from datetime import date
from auditar_planilhas import LeitorXlsm, data_excel, texto, extrair_base, extrair_condominio, canon
from intelligence_ensaio_v80 import assinatura, REPO
from custos_importacao_v77 import validar_lote
from intelligence_manutencao_v80 import investigar_manutencao_v80
from intelligence_relatorio_v78 import moeda


def executar(args):
    pasta=args.planilhas.resolve(strict=True); saida=args.saida.resolve()
    if saida.is_relative_to(pasta) or saida.is_relative_to(REPO):
        raise ValueError('Saida deve ficar fora do repositorio e das planilhas.')
    base=(pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    if base.parent!=pasta: raise ValueError('Cadastro fora da pasta.')
    hb=assinatura(base); mapa,_,_,_=extrair_base(base)
    arquivos=[(pasta/a).resolve(strict=True) for _,a in mapa]
    if len(mapa)!=10 or len({canon(n) for n,_ in mapa})!=10 or len(set(arquivos))!=10 or any(a.parent!=pasta or a==base or a.suffix.lower()!='.xlsm' for a in arquivos):
        raise ValueError('Cadastro ou arquivos invalidos.')
    hashes={a:assinatura(a) for a in arquivos}; registros=[]; agenda=[]; sem_aba=[]; nao_classificados=0
    nomes={i:n for i,(n,_) in enumerate(mapa,1)}
    for i,((n,_),a) in enumerate(zip(mapa,arquivos),1):
        fonte=extrair_condominio(a,n)
        if any(fonte[k] for k in ('sem_id','duplicados','datas_invalidas','valores_invalidos')): raise ValueError('Problemas de integridade nas origens.')
        registros.extend(fonte['classificadas'].values()); nao_classificados+=fonte['pendentes']
        leitor=LeitorXlsm(a)
        try:
            if 'PRAZOS' not in leitor.abas:
                sem_aba.append(i); continue
            for linha,d in leitor.linhas('PRAZOS',{'A','B','C','D'}):
                if linha<=1 or not texto(d.get('A')): continue
                agenda.append({'condominio_id':i,'linha':linha,'nome':texto(d['A']),'periodicidade':texto(d.get('B')),'ultima':data_excel(d.get('C')),'proxima':data_excel(d.get('D'))})
        finally: leitor.fechar()
    if assinatura(base)!=hb or any(assinatura(a)!=h for a,h in hashes.items()): raise ValueError('Planilhas alteradas durante a leitura.')
    dados=validar_lote(registros,{n:i for i,n in nomes.items()})
    resultado=investigar_manutencao_v80(dados,agenda,args.data_referencia,args.competencia,args.categoria or ['manutencao condominio'])
    resultado.update({'modo':'HOMOLOGACAO LOCAL - SEM ENVIO','nomes_temporarios':nomes,'fontes':[{'condominio_id':i,'arquivo':a.name,'sha256':hashes[a]} for i,a in enumerate(arquivos,1)],'hash_cadastro':hb,'sem_aba_prazos':sem_aba,'lancamentos_validados':len(dados),'nao_classificados':nao_classificados})
    linhas=['HAIZE INTELLIGENCE | MANUTENCAO | HOMOLOGACAO PRIVADA',f'Data da agenda: {args.data_referencia}; competencia financeira: {args.competencia}','Categorias financeiras: '+', '.join(resultado['categorias']),'', 'AGENDA REGISTRADA']
    for x in resultado['agenda']:
        if x['estado']=='prazo_futuro': continue
        linhas.append(f'{nomes[x["condominio_id"]]} | {x["nome"]} | {x["estado"]} | {x["evidencia"]["proxima"]} | {x["acao"]}')
    linhas.append('\nRECORRENCIAS FINANCEIRAS (nao identificam ativos)')
    for x in resultado['recorrencias']:
        linhas.append(f'{nomes[x["condominio_id"]]} | {x["descricao"]} | {x["registros"]} registros | {moeda(x["total_centavos"])} | {x["acao"]}')
    linhas.extend(['','LIMITACOES',*resultado['limites'],f'Condominios sem aba PRAZOS: {len(sem_aba)}'])
    saida.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix='.manutencao-',dir=saida)); destino=saida/('manutencao_'+uuid.uuid4().hex)
    try:
        (tmp/'PARECER_MANUTENCAO.txt').write_text('\n'.join(linhas),encoding='utf-8')
        (tmp/'EVIDENCIAS_MANUTENCAO.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.rename(destino)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise
    print('ENSAIO MANUTENCAO V8.0 - SEM ENVIO'); print('Lancamentos validados:',len(dados)); print('Linhas de agenda:',len(agenda)); print('Condominios sem aba PRAZOS:',len(sem_aba))
    for k,v in resultado['contagem_agenda'].items(): print(k+':',v)
    print('Recorrencias descritivas:',len(resultado['recorrencias'])); print('Gastos observados nas recorrencias:',moeda(resultado['total_recorrencias_centavos'])); print('Pasta privada:',destino)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--competencia',required=True); p.add_argument('--data-referencia',default=date.today().isoformat()); p.add_argument('--simulacao',action='store_true',required=True); p.add_argument('--categoria',action='append'); p.add_argument('--planilhas',type=Path,default=Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS'); p.add_argument('--saida',type=Path,default=Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA')
    try: executar(p.parse_args())
    except Exception as e: print(f'EXECUCAO BLOQUEADA ({type(e).__name__}): {e}',file=sys.stderr); return 1
    return 0

if __name__=='__main__': sys.exit(main())
