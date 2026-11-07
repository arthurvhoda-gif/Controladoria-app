# -*- coding: utf-8 -*-
"""Inicia a V7.3 localmente com banco temporário e SEM serviços externos.

Compatível com Windows; não usa Neon, Render, Vercel, WhatsApp, Resend nem
credenciais existentes. O script de produção permanece inalterado.
"""
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

BASE = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:18774'
SITE = 'http://127.0.0.1:5174'


def ambiente_isolado(pasta: Path):
    # Lista positiva: não herdar DATABASE_URL, tokens nem variáveis da produção.
    permitidas = {
        'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'USERPROFILE',
        'APPDATA', 'LOCALAPPDATA', 'HOMEDRIVE', 'HOMEPATH', 'HOME',
        'TEMP', 'TMP', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'LANG',
        'PYTHONIOENCODING', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE',
        'NODE_EXTRA_CA_CERTS', 'NPM_CONFIG_CACHE',
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in permitidas}
    arquivo = pasta / 'haize_v73_demo.sqlite3'
    env.update({
        'DATABASE_URL': 'sqlite:///' + arquivo.as_posix(),
        'HAIZE_DEMO_LOCAL_V73': '1',
        'HAIZE_DEMO_TEMP_DIR': str(pasta),
        'HAIZE_DEMO_DB_FILE': str(arquivo),
        'AUTH_SECRET_KEY': secrets.token_urlsafe(48),
        'FRONTEND_ORIGINS': SITE,
        'FRONTEND_PUBLIC_URL': SITE,
        'VITE_API_URL': API,
        'VITE_HAIZE_DEMO_V73': '1',
        'ENABLE_CHECKLIST_EMAILS': 'false',
        'GAS_WEB_APP_URL': '',
        'HAIZE_SECRET': '',
        'AUTOMATION_SECRET': '',
        'HAIZE_STORAGE_MODE': 'local',
        'HAIZE_STORAGE_URL': '',
        'HAIZE_STORAGE_SECRET': '',
        'RESEND_API_KEY': '',
        'HAIZE_ATRASOS_ENVIO_ATIVO': 'NAO',
        'PYTHONNOUSERSITE': '1',
    })
    return env


def aguardar(url, proc, rotulo):
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(f'{rotulo} terminou antes de iniciar.')
        try:
            with urlopen(url, timeout=1) as resposta:
                if resposta.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(.2)
    raise RuntimeError(f'{rotulo} não respondeu em localhost.')


def terminar(proc):
    if proc is None or proc.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def python_da_venv(venv):
    return venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def garantir_dependencias():
    pasta_venv = BASE / '.venv_demo_v73'
    exe = python_da_venv(pasta_venv)
    if not exe.exists():
        print('Criando ambiente Python isolado para a demonstracao...', flush=True)
        subprocess.run([sys.executable, '-m', 'venv', str(pasta_venv)], check=True)
    resultado = subprocess.run(
        [str(exe), '-c',
         'import fastapi, sqlalchemy, uvicorn, jwt, reportlab, argon2, PIL, multipart'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if resultado.returncode:
        print('Instalando dependencias Python do projeto no ambiente isolado...',
              flush=True)
        subprocess.run([str(exe), '-m', 'pip', 'install', '-r',
                        str(BASE / 'backend/requirements.txt')], check=True)
    if not (BASE / 'frontend/node_modules/.bin/vite.cmd').exists() and os.name == 'nt':
        print('Instalando dependencias do frontend conforme package-lock...', flush=True)
        subprocess.run(['npm.cmd', 'ci'], cwd=BASE / 'frontend', check=True)
    elif not (BASE / 'frontend/node_modules/.bin/vite').exists() and os.name != 'nt':
        subprocess.run(['npm', 'ci'], cwd=BASE / 'frontend', check=True)
    return exe


def ultimas_linhas(arquivo: Path):
    try:
        return '\n'.join(arquivo.read_text(encoding='utf-8', errors='replace').splitlines()[-22:])
    except OSError:
        return '(log indisponivel)'


def main():
    print('HAIZE V7.3 - DEMONSTRACAO LOCAL COM DADOS FICTICIOS', flush=True)
    print('Nenhum servico externo ou banco de producao sera utilizado.', flush=True)
    exe = garantir_dependencias()
    with tempfile.TemporaryDirectory(prefix='haize_v73_demo_') as temporario:
        pasta = Path(temporario).resolve()
        env = ambiente_isolado(pasta)
        backend = frontend = None
        try:
            with (pasta / 'backend.log').open('w', encoding='utf-8') as log_api, \
                 (pasta / 'frontend.log').open('w', encoding='utf-8') as log_site:
                backend = subprocess.Popen(
                    [str(exe), '-m', 'uvicorn', 'demo_local_v73:app',
                     '--host', '127.0.0.1', '--port', '18774'],
                    cwd=BASE / 'backend', env=env,
                    stdout=log_api, stderr=subprocess.STDOUT,
                )
                aguardar(API + '/status', backend, 'Backend da demonstracao')
                frontend = subprocess.Popen(
                    ['npm.cmd' if os.name == 'nt' else 'npm',
                     'run', 'dev', '--', '--host', '127.0.0.1',
                     '--port', '5174', '--strictPort'],
                    cwd=BASE / 'frontend', env=env,
                    stdout=log_site, stderr=subprocess.STDOUT,
                )
                aguardar(SITE, frontend, 'Frontend da demonstracao')
                print('\nAplicativo ficticio: ' + SITE, flush=True)
                print('Controladoria: gestora.demo@local.test', flush=True)
                print('Zelador Alfa: zelador.alfa.demo@local.test', flush=True)
                print('Zelador Beta: zelador.beta.demo@local.test', flush=True)
                print('Senha de demonstracao: SenhaFicticiaDeTeste123', flush=True)
                print('\nFeche com Ctrl+C. Os dados temporarios serao apagados.', flush=True)
                webbrowser.open(SITE)
                while backend.poll() is None and frontend.poll() is None:
                    time.sleep(.5)
                raise RuntimeError('Um dos servidores foi encerrado inesperadamente.')
        except KeyboardInterrupt:
            print('\nEncerrando demonstracao...', flush=True)
        except Exception:
            print('\nErro ao abrir a demonstracao. Log do backend:', flush=True)
            print(ultimas_linhas(pasta / 'backend.log'), flush=True)
            print('\nLog do frontend:', flush=True)
            print(ultimas_linhas(pasta / 'frontend.log'), flush=True)
            raise
        finally:
            terminar(frontend)
            terminar(backend)


if __name__ == '__main__':
    main()
