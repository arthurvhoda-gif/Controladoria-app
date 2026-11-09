#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pacote determinístico para REVISÃO DE HOMOLOGAÇÃO V7.3, nunca deploy.

Somente código de backend explicitamente permitido, SQL de migração,
documentação e frontend compilado com URL local no ambiente descartável.
Nunca inclui SQLite de legado, fotos, caches, .env, segredos ou uploads.

Não publica artefatos em serviços, não faz rede e não escreve no repositório.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

BASE = Path(__file__).resolve().parents[1]
BACKEND_PERMITIDO = (
    'armazenamento_drive_v72.py',
    'arquivos_seguros.py',
    'auth_utils.py',
    'database.py',
    'empresas.py',
    'financeiro_api.py',
    'main.py',
    'models.py',
    'schemas.py',
    'servicos_api.py',
    'usuarios_pendencias.py',
    'whatsapp_alertas.py',
    'whatsapp_historico.py',
    'whatsapp_mensagens.py',
    'whatsapp_preenvio.py',
    'whatsapp_validade.py',
    'whatsapp_verificacao_transacional.py',
    'requirements.txt',
)
OUTROS_PERMITIDOS = (
    'migracoes/v73_whatsapp_telefone_unico.sql',
    'docs/V73_LIBERACAO_CONTROLADA.md',
    'docs/NOTIFICACOES_V73_PLANO_DE_FECHAMENTO.md',
    'docs/DEMONSTRACAO_LOCAL_NOTIFICACOES_V73.md',
)
SUFIXOS_SITE = {'.html', '.js', '.css', '.json', '.png',
                '.ico', '.svg', '.webmanifest', '.woff', '.woff2'}


def versao_git():
    return subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=BASE, text=True,
    ).strip()


def arquivos_permitidos():
    obrigatorios = [
        *(Path('backend') / nome for nome in BACKEND_PERMITIDO),
        *(Path(nome) for nome in OUTROS_PERMITIDOS),
    ]
    site = BASE / 'frontend' / 'dist'
    if not (site / 'index.html').is_file():
        raise RuntimeError('Frontend não compilado; execute npm run build antes.')
    for f in site.rglob('*'):
        if not f.is_file():
            continue
        rel = f.relative_to(BASE)
        if f.suffix not in SUFIXOS_SITE:
            raise RuntimeError('Arquivo não previsto no frontend compilado: ' + rel.as_posix())
        obrigatorios.append(rel)

    permitidos = {}
    for rel in sorted(obrigatorios, key=lambda p: p.as_posix()):
        destino = (BASE / rel)
        # Symlinks e arquivos que escapem da pasta do projeto são proibidos.
        if (not destino.is_file() or destino.is_symlink()
                or not destino.resolve().is_relative_to(BASE.resolve())):
            raise RuntimeError('Arquivo obrigatório ausente ou inseguro: ' + rel.as_posix())
        nome = rel.as_posix()
        if (nome in permitidos or '/__pycache__/' in nome or
                nome.endswith(('.db', '.sqlite', '.sqlite3', '.pyc',
                                '.env', '.pem', '.key', '.map'))):
            raise RuntimeError('Arquivo duplicado ou sensível bloqueado: ' + nome)
        permitidos[nome] = destino.read_bytes()

    if not any(k.startswith('frontend/dist/assets/') for k in permitidos):
        raise RuntimeError('Build do frontend sem assets.')
    assert not any('demo_local_v73.py' in n for n in permitidos)
    assert not any('controladoria.db' in n for n in permitidos)
    return permitidos


def zipinfo(nome):
    info = ZipInfo(nome, date_time=(2024, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def gerar(destino):
    arquivos = arquivos_permitidos()
    manifesto = {
        'tipo': 'candidato_homologacao_nao_implantar',
        'versao': 'v73-notificacoes',
        'commit': versao_git(),
        'envio_whatsapp_ativado': False,
        'pronto_para_producao': False,
        'observacao': (
            'Frontend compilado contra API local descartável; reconstruir '
            'com endpoint próprio e homologado antes de qualquer implantação.'
        ),
        'arquivos': {
            nome: {'sha256': hashlib.sha256(conteudo).hexdigest(),
                   'bytes': len(conteudo)}
            for nome, conteudo in arquivos.items()
        },
    }
    arquivos['MANIFESTO_HOMOLOGACAO_V73.json'] = (
        json.dumps(manifesto, indent=2, ensure_ascii=False, sort_keys=True)
        + '\n'
    ).encode('utf-8')
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destino, 'w', compression=ZIP_DEFLATED, compresslevel=9) as z:
        for nome, conteudo in sorted(arquivos.items()):
            z.writestr(zipinfo(nome), conteudo)
    return hashlib.sha256(destino.read_bytes()).hexdigest(), manifesto


def verificar_zip(caminho):
    with ZipFile(caminho) as z:
        nomes = z.namelist()
        if nomes != sorted(nomes) or len(nomes) != len(set(nomes)):
            raise RuntimeError('Arquivo de homologação contém nomes duplicados ou fora de ordem.')
        manifest = json.loads(z.read('MANIFESTO_HOMOLOGACAO_V73.json'))
        if manifest['pronto_para_producao'] or manifest['envio_whatsapp_ativado']:
            raise RuntimeError('Pacote sugere implantação ou WhatsApp ativo.')
        if set(nomes) != {'MANIFESTO_HOMOLOGACAO_V73.json', *manifest['arquivos']}:
            raise RuntimeError('Lista de arquivos não confere com o manifesto.')
        for nome, dados in manifest['arquivos'].items():
            if hashlib.sha256(z.read(nome)).hexdigest() != dados['sha256']:
                raise RuntimeError('Integridade inválida: ' + nome)
        return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verificar-ci', action='store_true',
                        help='gera duas cópias efêmeras e confere SHA-256 e conteúdo')
    parser.add_argument('--saida', type=Path)
    args = parser.parse_args()

    if args.verificar_ci and os.environ.get('CI') != 'true':
        raise SystemExit('Verificação CI restrita ao ambiente temporário da automação.')
    if not args.verificar_ci and not args.saida:
        parser.error('Use --saida ou --verificar-ci.')
    if args.verificar_ci:
        with tempfile.TemporaryDirectory(prefix='haize_v73_pacote_ci_') as pasta:
            a = Path(pasta) / 'a.zip'
            b = Path(pasta) / 'b.zip'
            h1, m = gerar(a)
            h2, _ = gerar(b)
            if h1 != h2 or a.read_bytes() != b.read_bytes():
                raise RuntimeError('Pacote não reproduzível no mesmo código.')
            verificar_zip(a)
            print('V7.3: pacote determinístico de homologação aprovado; '
                  f'{len(m["arquivos"])} arquivos permitidos; hash SHA256={h1}.')
    else:
        if args.saida.resolve().is_relative_to(BASE.resolve()):
            raise SystemExit('BLOQUEADO: salvar pacote somente fora do repositório.')
        h, m = gerar(args.saida)
        verificar_zip(args.saida)
        print(f'Pacote V7.3 de HOMOLOGAÇÃO (não produção): '
              f'{len(m["arquivos"])} arquivos, SHA256={h}')


if __name__ == '__main__':
    main()
