# -*- coding: utf-8 -*-
"""Homologacao integrada V7.3: React + FastAPI + PostgreSQL + Chromium REAIS.

Sem mock de API, sem dados privados e sem chamadas a Render/Vercel/Neon.
Back/frontend locais, PostgreSQL CI loopback e WhatsApp ENVIO DESATIVADO.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect

RAIZ = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:18773'
FRONTEND = 'http://127.0.0.1:4175'
SENHA = 'SenhaFicticiaDeTeste123'


def guardas():
    url = urlsplit(os.getenv('DATABASE_URL', ''))
    if (url.scheme not in ('postgresql', 'postgresql+psycopg2')
            or url.hostname not in ('127.0.0.1', 'localhost')
            or url.path != '/haize_v73_integracao'):
        raise RuntimeError('BLOQUEADO: homologacao exige Postgres local haize_v73_integracao.')
    if os.getenv('FRONTEND_ORIGINS') != FRONTEND:
        raise RuntimeError('BLOQUEADO: origem frontend de homologacao inesperada.')
    if os.getenv('ENABLE_CHECKLIST_EMAILS', '').lower() != 'false':
        raise RuntimeError('BLOQUEADO: emails devem ficar desativados.')
    if os.getenv('HAIZE_STORAGE_MODE', 'local') != 'local':
        raise RuntimeError('BLOQUEADO: nao usar armazenamento externo em homologacao.')


def consultar(method, caminho, *, token=None, dados=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    payload = None
    if dados is not None:
        payload = json.dumps(dados, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(API + caminho, data=payload, headers=headers, method=method)
    try:
        with urlopen(req, timeout=12) as resposta:
            corpo = resposta.read().decode('utf-8')
            return resposta.status, json.loads(corpo) if corpo else None
    except HTTPError as erro:
        corpo = erro.read().decode('utf-8')
        try:
            return erro.code, json.loads(corpo)
        except ValueError:
            return erro.code, corpo


def esperar_ativo(url, processo, rotulo):
    for _ in range(100):
        if processo.poll() is not None:
            raise RuntimeError(f'{rotulo} encerrou na inicializacao (code {processo.returncode}).')
        try:
            with urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f'{rotulo} nao respondeu no loopback.')


def encerrar(processo):
    if processo is None:
        return
    if processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=6)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=5)


def login_tela(pagina, email):
    pagina.goto(FRONTEND, wait_until='domcontentloaded')
    expect(pagina.locator('.login-screen')).to_be_visible()
    pagina.get_by_placeholder('nome@haize.com.br').fill(email)
    pagina.locator('input[type="password"]').fill(SENHA)
    pagina.get_by_role('button', name='Entrar na Plataforma').click()
    expect(pagina.locator('.sidebar-nav')).to_be_visible()
    expect(pagina.locator('.login-screen')).to_have_count(0)


def homologar(pagina):
    # Preparacao pelo backend VERDADEIRO; a interface consumira exatamente
    # os mesmos registros JWT, avisos, direitos e eventos no PostgreSQL real.
    status, gestor = consultar('POST', '/login', dados={
        'email': 'gestora@teste.local', 'senha': SENHA})
    assert status == 200, (status, gestor)
    token_gestor = gestor['access_token']
    status, alfa = consultar('POST', '/login', dados={
        'email': 'zelador.alfa@teste.local', 'senha': SENHA})
    assert status == 200, (status, alfa)
    token_alfa = alfa['access_token']
    status, beta = consultar('POST', '/login', dados={
        'email': 'zelador.beta@teste.local', 'senha': SENHA})
    assert status == 200, (status, beta)
    token_beta = beta['access_token']

    from datetime import date, timedelta
    status, criada = consultar('POST', '/servicos', token=token_gestor, dados={
        'condominio_id': 1, 'executores_ids': [2],
        'fiscalizadores_ids': [],
        'titulo': 'Inspecionar portão fictício',
        'descricao': 'Atividade de homologação integrada sem dados reais.',
        'prazo': (date.today() + timedelta(days=7)).isoformat(),
    })
    assert status == 201, (status, criada)
    sid = criada['id']

    status, avisos = consultar('GET', '/servicos/notificacoes', token=token_alfa)
    assert status == 200 and len(avisos) == 1 and avisos[0]['servico_id'] == sid
    aviso_id = avisos[0]['id']
    status, privacidade = consultar('GET', '/servicos/notificacoes', token=token_beta)
    assert status == 200 and privacidade == []
    status, negado = consultar('GET', f'/servicos/{sid}', token=token_beta)
    assert status == 404, (status, negado)
    print('REAL 1/5: FastAPI/JWT e isolamento de condominios aprovados.', flush=True)

    login_tela(pagina, 'zelador.alfa@teste.local')
    expect(pagina.locator('.notification-badge')).to_have_text('1')
    pagina.get_by_role('button', name='Ver alertas e notificações').click()
    expect(pagina.get_by_text('Tarefas e serviços (1)')).to_be_visible()
    bloco = pagina.locator('.alertas-checklist-lista').first
    expect(bloco).to_contain_text('Inspecionar portão fictício')
    bloco.locator('button').first.click()
    expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_be_visible()
    expect(pagina.locator('.notification-badge')).to_have_count(0)
    status, lidos = consultar('GET', '/servicos/notificacoes', token=token_alfa)
    assert status == 200 and any(a['id'] == aviso_id and a['lida'] for a in lidos)
    print('REAL 2/5: React abriu tarefa e API persistiu leitura do aviso.', flush=True)

    # A gaveta modal bloqueia cliques fora dela. Fechar antes do logout.
    pagina.get_by_role('button', name='Fechar detalhes do serviço').click()
    expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_have_count(0)
    pagina.get_by_role('button', name='Encerrar Sessão').click()
    expect(pagina.locator('.login-screen')).to_be_visible()
    login_tela(pagina, 'zelador.beta@teste.local')
    expect(pagina.locator('.notification-badge')).to_have_count(0)
    pagina.goto(f'{FRONTEND}/?servico={sid}', wait_until='domcontentloaded')
    expect(pagina.get_by_text('A tarefa do link não existe ou não está disponível para seu perfil.')).to_be_visible()
    expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_have_count(0)
    print('REAL 3/5: outra conta nao acessa alerta nem link profundo.', flush=True)

    # Revogacao simulada de cadastro pelo banco REAL, nao pelo mock. A API
    # precisa revalidar a permissao usando o registro de usuario atualizado.
    sys.path.insert(0, str(RAIZ / 'backend'))
    from database import SessionLocal
    import models
    with SessionLocal() as db:
        db.get(models.Usuario, 2).condominio_id = None
        db.commit()
    status, antigos = consultar('GET', '/servicos/notificacoes', token=token_alfa)
    assert status == 200 and antigos == [], (status, antigos)
    status, negar_leitura = consultar('POST', f'/servicos/notificacoes/{aviso_id}/ler', token=token_alfa)
    assert status == 404, (status, negar_leitura)
    status, negar_detalhe = consultar('GET', f'/servicos/{sid}', token=token_alfa)
    assert status == 404, (status, negar_detalhe)
    print('REAL 4/5: transferencia revogou acesso, aviso e leitura no backend.', flush=True)

    status, preferencias = consultar('GET', '/avisos-whatsapp/me', token=token_alfa)
    assert status == 200 and preferencias['envios_ativos'] is False
    status, fila = consultar('GET', '/avisos-whatsapp/fila/previas', token=token_gestor)
    assert status == 200 and fila['envios_ativos'] is False, (status, fila)
    print('REAL 5/5: WhatsApp permanece desativado com APIs e frontend reais.', flush=True)


def main():
    guardas()
    env = dict(os.environ)
    backend = frontend = None
    playwright = browser = contexto = None
    try:
        backend = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app',
             '--host', '127.0.0.1', '--port', '18773'],
            cwd=RAIZ / 'backend', env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        esperar_ativo(API + '/status', backend, 'FastAPI')
        frontend = subprocess.Popen(
            ['npm', 'run', 'preview', '--', '--host', '127.0.0.1',
             '--port', '4175', '--strictPort'],
            cwd=RAIZ / 'frontend', env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        esperar_ativo(FRONTEND, frontend, 'Vite Preview')
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        contexto = browser.new_context(
            locale='pt-BR', timezone_id='America/Sao_Paulo',
            service_workers='block', viewport={'width': 1365, 'height': 900},
        )
        pagina = contexto.new_page()
        pagina.set_default_timeout(16000)
        erros_js = []
        pagina.on('pageerror', lambda erro: erros_js.append(str(erro)))
        homologar(pagina)
        assert not erros_js, erros_js
        print('HOMOLOGACAO INTEGRADA V7.3: 5/5 APROVADOS — SEM MOCK, SEM ENVIO.', flush=True)
    finally:
        if contexto:
            contexto.close()
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        encerrar(frontend)
        encerrar(backend)


if __name__ == '__main__':
    main()
