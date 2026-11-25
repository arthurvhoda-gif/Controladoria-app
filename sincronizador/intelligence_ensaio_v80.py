# -*- coding: utf-8 -*-
"""Ensaio investigativo V8.0: leitura local, sem rede, sem email, sem banco."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'backend'))
from auditar_planilhas import extrair_base, extrair_condominio, canon
from custos_importacao_v77 import validar_lote
from intelligence_motor_v78 import analisar_historico_privado
from intelligence_previsao_v78 import interpretar_mes, deslocar_mes
from intelligence_oportunidades_v78 import identificar_oportunidades_v78
from intelligence_relatorio_v78 import moeda
from intelligence_investigacao_v80 import investigar_aumento, verificar_investigacao


def assinatura(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def executar(args):
    referencia = interpretar_mes(args.competencia)
    meses = [deslocar_mes(referencia,i).strftime('%Y-%m') for i in range(-5,1)]
    pasta = args.planilhas.resolve(strict=True)
    saida = args.saida.resolve()
    if saida.is_relative_to(pasta) or saida.is_relative_to(REPO):
        raise ValueError('Saida deve ficar fora do repositorio e das planilhas.')
    base = (pasta/'BASE_DADOS_GERAL.xlsm').resolve(strict=True)
    if base.parent != pasta:
        raise ValueError('Base fora da pasta autorizada.')
    hb = assinatura(base)
    m,_,_,_ = extrair_base(base)
    if len(m)!=10 or len({canon(n) for n,_ in m})!=10:
        raise ValueError('Cadastro deve conter dez condominios distintos.')
    arquivos = [(pasta/a).resolve(strict=True) for _,a in m]
    if len(set(arquivos))!=10 or any(a.parent!=pasta or a==base or a.suffix.lower()!='.xlsm' for a in arquivos):
        raise ValueError('Arquivos de origem invalidos.')
    hashes = {a:assinatura(a) for a in arquivos}
    fontes = [extrair_condominio(a,n) for (n,_),a in zip(m,arquivos)]
    if any(f[k] for f in fontes for k in ('sem_id','duplicados','datas_invalidas','valores_invalidos')):
        raise ValueError('Problemas de integridade nas origens.')
    if assinatura(base)!=hb or any(assinatura(a)!=h for a,h in hashes.items()):
        raise ValueError('Planilhas alteradas durante a leitura. Execucao bloqueada.')
    mapa = {n:i for i,(n,_) in enumerate(m,1)}
    nomes = {i:n for n,i in mapa.items()}
    dados = validar_lote([r for f in fontes for r in f['classificadas'].values()],mapa)
    hist = tuple(r for r in dados if r.competencia<=referencia)
    analisar_historico_privado(hist)
    casos=[]; avaliadas=sem_base=0
    for cid in sorted(nomes):
        resultado=identificar_oportunidades_v78(hist,cid,args.competencia,meses)
        avaliadas+=resultado.categorias_avaliadas; sem_base+=resultado.categorias_sem_base
        for o in resultado.oportunidades:
            caso=investigar_aumento(hist,o,meses)
            verificar_investigacao(caso)
            caso['condominio']=nomes[cid]
            casos.append(caso)
    casos.sort(key=lambda c:(-c['impacto_centavos'],c['condominio_id'],c['categoria']))
    impacto=sum(c['impacto_centavos'] for c in casos)
    run_id=uuid.uuid4().hex
    pacote={'versao':'8.0-investigacao-1','execucao':run_id,'utc':datetime.now(timezone.utc).isoformat(),
        'modo':'SIMULACAO - COBERTURA NAO CONFIRMADA','competencia':args.competencia,
        'fonte':'planilhas individuais GASTOS; base geral apenas cadastro', 'hash_cadastro':hb,
        'fontes':[{'condominio':n,'arquivo':a.name,'sha256':hashes[a]} for (n,_),a in zip(m,arquivos)],
        'lancamentos_historico_total':len(dados),'lancamentos_ate_competencia':len(hist),
        'nao_classificados_excluidos':sum(f['pendentes'] for f in fontes),'categorias_avaliadas':avaliadas,
        'categorias_sem_base':sem_base,'impacto_total_centavos':impacto,'casos':casos}
    linhas=['HAIZE INTELLIGENCE V8.0 | PARECER INVESTIGATIVO LOCAL',f'Execucao: {run_id}',f'Competencia: {args.competencia}',
        'SIMULACAO - cobertura mensal nao confirmada. Fechamentos assumidos apenas para ensaio.',
        'Dados classificados das planilhas individuais. Sem integracao com contratos, compras, servicos ou pagamentos.',
        'Aumentos de despesas nao equivalem a perdas, irregularidades ou economias comprovadas.','',
        f'Casos reconciliados: {len(casos)} | impacto observado: {moeda(impacto)}',
        f'Categorias avaliadas: {avaliadas} | sem base: {sem_base}', '']
    for i,c in enumerate(casos,1):
        linhas.extend([f'{i:02d} | {c["condominio"]} | {c["categoria"].upper()}',
            f'Impacto: {moeda(c["impacto_centavos"])} | mes de referencia: {c["mes_referencia"]}',
            f'Contribuicoes positivas: {moeda(c["contribuicoes_positivas_centavos"])} | compensacoes: {moeda(c["compensacoes_centavos"])}',
            'Principais contribuicoes por descricao (nao provas de causa):'])
        for x in [x for x in c['decomposicao'] if x['contribuicao_centavos']>0][:5]:
            desc=' '.join(x['descricao_normalizada'].split())[:140]
            linhas.extend([f'  {desc}: +{moeda(x["contribuicao_centavos"])}',
                f'    Registros: {x["registros_referencia"]} no mes de referencia vs {x["registros_recentes"]} no trimestre recente.',
                f'    Efeitos: frequencia {moeda(x["efeito_frequencia_centavos"])}; valor medio {moeda(x["efeito_valor_medio_centavos"])}; sem referencia {moeda(x["efeito_sem_referencia_centavos"])}.',
                '    Estado: '+x['status']])
        linhas.extend(['Conclusao: aumento contabil reconciliado; causa operacional ainda nao comprovada.',
            'Proxima investigacao do sistema: cruzar documentos, contratos, compras e servicos relacionados quando as fontes forem integradas.',
            'Decisao segura agora: nao autorizar corte ou renegociacao apenas com este sinal.',''])
    linhas.extend(['METODO: trimestre recente menos tres vezes o mes que representa a mediana anterior.',
        'Frequencia e contagem de registros, nao quantidade de bens. Valor medio nao e preco unitario.',
        'JSON local inclui todos os grupos, compensacoes, IDs, datas, valores e hashes para rastreabilidade.',
        'CONFIDENCIAL. Nenhum email enviado.'])
    saida.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.ensaio-',dir=saida))
    destino=saida/f'{args.competencia}_{run_id}'
    try:
        (tmp/'PARECER_INVESTIGATIVO.txt').write_text('\n'.join(linhas),encoding='utf-8')
        (tmp/'EVIDENCIAS_E_MEMORIA.json').write_text(json.dumps(pacote,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.rename(destino)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True)
        raise
    print('ENSAIO V8.0 CONCLUIDO - SEM ENVIO')
    print('Lancamentos validados:',len(dados))
    print('Casos reconciliados:',len(casos))
    print('Categorias avaliadas:',avaliadas)
    print('Categorias sem base:',sem_base)
    print('Impacto observado:',moeda(impacto))
    print('Pasta privada:',destino)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--competencia',required=True)
    p.add_argument('--simulacao',action='store_true',required=True)
    p.add_argument('--planilhas',type=Path,default=Path.home()/'Music'/'Sistema_Rateio'/'CONDOMÍNIOS')
    p.add_argument('--saida',type=Path,default=Path.home()/'Documents'/'HAIZE_INTELLIGENCE_V80_PRIVADA')
    try:
        executar(p.parse_args())
    except Exception as e:
        print(f'EXECUCAO BLOQUEADA ({type(e).__name__}): {e}',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
