# -*- coding: utf-8 -*-
"""Sincronização XLSM -> Haize (etapa 2).

Padrão: PRÉVIA LOCAL, SEM ACESSO À INTERNET.
Para importar no Render de TESTES: --enviar --api-url https://controladoria-api-teste.onrender.com
Requer HAIZE_SYNC_SECRET no ambiente somente em modo --enviar.
Não abre Excel, não executa macros, não modifica .xlsm.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import request, error

from auditar_planilhas import PASTA_PADRAO, extrair_base, extrair_condominio, br, canon


def verificar_mapeamento(pasta):
    base = pasta / "BASE_DADOS_GERAL.xlsm"
    if not base.is_file():
        raise FileNotFoundError(f"Base geral não encontrada: {base}")
    mapeamento, registros_base, _, _ = extrair_base(base)
    if len(mapeamento) != 10:
        raise ValueError(f"Esperava 10 condomínios na base, mas encontrei {len(mapeamento)}")
    nomes = [canon(n) for n, _ in mapeamento]
    arquivos = [a.casefold() for _, a in mapeamento]
    if len(set(nomes)) != 10 or len(set(arquivos)) != 10:
        raise ValueError("Condomínio ou arquivo duplicado na lista de origens.")
    for nome, arquivo in mapeamento:
        if not re.fullmatch(r"[^/\\<>:|?*]+\.xlsm", arquivo, re.IGNORECASE):
            raise ValueError(f"Nome de arquivo inválido na base para {nome}")
        if arquivo.casefold() in ('modelo.xlsm', 'base_dados_geral.xlsm'):
            raise ValueError("Arquivo de modelo/base não deve ser sincronizado.")
    return mapeamento, registros_base


def criar_snapshot(pasta, nome, arquivo):
    caminho = pasta / arquivo
    if not caminho.is_file():
        raise FileNotFoundError(f"Planilha de {nome} ausente: {caminho}")
    antes = caminho.stat()
    resultado = extrair_condominio(caminho, nome)
    depois = caminho.stat()
    if (antes.st_size, antes.st_mtime_ns) != (depois.st_size, depois.st_mtime_ns):
        raise ValueError(f"{arquivo} foi modificado durante a leitura. Salve e tente novamente.")
    erros = []
    for chave in ('sem_id', 'duplicados', 'datas_invalidas', 'valores_invalidos'):
        if resultado[chave]:
            erros.append(f"{chave}: {len(resultado[chave])}")
    if erros:
        raise ValueError(f"{arquivo}: problemas de leitura: " + ', '.join(erros))
    if not resultado['classificadas']:
        raise ValueError(f"{arquivo}: nenhum lançamento classificado. Sincronização vazia bloqueada.")
    despesas = [
        {'id_origem': item['id'], 'descricao': item['descricao'],
         'competencia': item['data'], 'categoria': item['categoria'],
         'valor': str(item['valor'])}
        for _, item in sorted(resultado['classificadas'].items())
    ]
    manutencoes = [
        {'chave': chave[:180], 'nome': manut.get('nome', chave)[:180],
         'periodicidade': manut['periodicidade'] or None,
         'ultima': manut['ultima'] or None, 'proxima': manut['proxima'] or None}
        for chave, manut in sorted(resultado['manutencoes'].items())
    ]
    for item in manutencoes:
        for data_nome in ('ultima', 'proxima'):
            if item[data_nome] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item[data_nome]):
                raise ValueError(f"{arquivo}: data inválida de manutenção: {item[data_nome]}")
    return {'arquivo': arquivo, 'condominio': nome,
            'lancamentos': despesas, 'manutencoes': manutencoes}, resultado


def validar_url_testes(url):
    url = (url or '').strip().rstrip('/')
    if url in ('http://127.0.0.1:8000', 'http://localhost:8000'):
        return url
    if url == 'https://controladoria-api-teste.onrender.com':
        return url
    raise ValueError('Por segurança, esta etapa permite envios apenas ao Render de TESTES ou localhost:8000.')


def aguardar_servidor(url, tentativas=3, timeout=150):
    """Acorda e confere o Render GRATUITO antes de enviar dados.

    Somente GET /status: esta função não envia nem altera lançamentos.
    """
    print('\nVerificando disponibilidade do Render de testes...')
    for tentativa in range(1, tentativas + 1):
        req = request.Request(url + '/status', headers={'Accept': 'application/json'}, method='GET')
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f'/status respondeu HTTP {resp.status}')
            print('Render de testes respondeu HTTP 200. Iniciando envio.')
            return
        except error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504):
                raise RuntimeError(f'/status respondeu HTTP {exc.code}; importação cancelada.') from None
            motivo = f'HTTP {exc.code}'
        except (error.URLError, OSError) as exc:
            motivo = str(exc)
        if tentativa == tentativas:
            raise RuntimeError(f'Render indisponível após {tentativas} verificações de /status: {motivo}')
        espera = 5 * tentativa
        print(f'  Render ainda não respondeu ({motivo}). Nova verificação em {espera}s...')
        time.sleep(espera)


def enviar(url, segredo, payload, tentativas=3, timeout=150):
    """Envia snapshot completo; reenvio é idempotente na API (chave arquivo+ID).

    Um timeout pode ocorrer após o servidor ter gravado os registros.
    Repetir o mesmo snapshot não cria duplicações, conforme validado no piloto.
    """
    dados = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    for tentativa in range(1, tentativas + 1):
        req = request.Request(
            url + '/custos/sincronizar', data=dados,
            headers={'Content-Type': 'application/json; charset=utf-8',
                     'X-Haize-Custos': segredo}, method='POST')
        try:
            with request.urlopen(req, timeout=timeout) as resposta:
                corpo = json.loads(resposta.read().decode('utf-8'))
            if corpo.get('status') != 'ok':
                raise RuntimeError(f"Servidor não confirmou importação: {corpo}")
            return corpo
        except error.HTTPError as exc:
            mensagem = exc.read(1000).decode('utf-8', 'replace')
            if exc.code not in (429, 502, 503, 504):
                raise RuntimeError(f"API respondeu HTTP {exc.code}: {mensagem}") from None
            motivo = f'HTTP {exc.code}: {mensagem}'
        except (error.URLError, OSError) as exc:
            motivo = str(exc)
        if tentativa == tentativas:
            raise RuntimeError(
                f"Falha ao sincronizar {payload['condominio']} após {tentativas} tentativas: {motivo}. "
                "Confira o Neon de TESTES antes de qualquer envio manual adicional.")
        espera = 5 * tentativa
        print(f"  {payload['condominio']}: tentativa {tentativa}/{tentativas} não confirmou "
              f"o envio ({motivo}). Tentando novamente em {espera}s...")
        time.sleep(espera)


def executar(args):
    pasta = Path(args.pasta)
    mapeamento, base = verificar_mapeamento(pasta)
    if args.somente:
        mapeamento = [(n, a) for n, a in mapeamento if canon(n) == canon(args.somente)]
        if not mapeamento:
            raise ValueError(f"Condomínio não encontrado na lista: {args.somente}")
    snapshots = []
    print('\n=== HAIZE - PREPARAÇÃO DE SINCRONIZAÇÃO DE CUSTOS ===\n')
    for nome, arquivo in mapeamento:
        snap, resultado = criar_snapshot(pasta, nome, arquivo)
        ids = set(resultado['classificadas'])
        ids_base = {uid for uid, item in base.items() if canon(item['condominio']) == canon(nome)}
        novidades = len(ids - ids_base)
        print(f"{nome}: {len(ids)} classificados | {br(resultado['total_classificado'])} | "
              f"novos em relação à base geral: {novidades}")
        snapshots.append(snap)
    print(f"\nCondomínios verificados: {len(snapshots)}")
    print(f"Lançamentos classificados: {sum(len(s['lancamentos']) for s in snapshots)}")
    if not args.enviar:
        print('\nMODO SIMULAÇÃO: nenhum dado foi enviado ao Render/Neon.')
        print('Nenhuma planilha foi alterada. Nenhuma macro foi executada.')
        return
    url = validar_url_testes(args.api_url)
    segredo = os.getenv('HAIZE_SYNC_SECRET', '').strip()
    if len(segredo) < 32:
        raise ValueError('HAIZE_SYNC_SECRET ausente ou curta. Configure apenas no CMD local, não no código.')
    print('\nENVIANDO APENAS PARA O RENDER DE TESTES: ' + url)
    aguardar_servidor(url)
    for snap in snapshots:
        resposta = enviar(url, segredo, snap)
        print(f"{snap['condominio']}: novos={resposta['novos']} "
              f"alterados={resposta['atualizados']} desativados={resposta['desativados']}")
    print('\nImportação de testes concluída. NENHUMA alteração na produção.')


def main():
    parser = argparse.ArgumentParser(description='Importação de custos XLSM, segura por padrão.')
    parser.add_argument('--pasta', default=str(PASTA_PADRAO))
    parser.add_argument('--somente', help='Nome de um condomínio para piloto')
    parser.add_argument('--enviar', action='store_true', help='Permite envio após validar chaves e API de testes')
    parser.add_argument('--api-url', default='', help='URL exata do Render de testes')
    args = parser.parse_args()
    try:
        executar(args)
    except Exception as exc:
        print(f'\n[ERRO] {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
