# -*- coding: utf-8 -*-
"""Prova da demonstração local V7.3 com frontend/backend reais e SQLite falso.

Executa somente em loopback e intercepta QUALQUER pedido externo do navegador.
Não usa Neon, nem credenciais, nem provedores de e-mail ou WhatsApp.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

from iniciar_demo_local_v73 import (
    API, BASE, SITE, aguardar, ambiente_isolado, terminar,
)


def chamar(url, method='GET', payload=None, token=None):
    dados = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    pedido = Request(API + url, data=dados, headers=headers, method=method)
    try:
        with urlopen(pedido, timeout=10) as result:
            return result.status, json.loads(result.read())
    except HTTPError as erro:
        return erro.code, json.loads(erro.read())


def login(email):
    status, ret = chamar('/login', 'POST', {
        'email': email, 'senha': 'SenhaFicticiaDeTeste123',
    })
    assert status == 200, (status, ret)
    return ret['access_token']


def main():
    if os.environ.get('CI') != 'true':
        raise RuntimeError('Teste de homologação restrito ao CI: não usar dados locais.')
    with tempfile.TemporaryDirectory(prefix='haize_v73_demo_ci_') as temp:
        pasta = Path(temp).resolve()
        env = ambiente_isolado(pasta)
        assert env['DATABASE_URL'].startswith('sqlite:///')
        assert 'haize_v73_demo.sqlite3' in env['DATABASE_URL']
        assert env['HAIZE_STORAGE_MODE'] == 'local'
        assert env['ENABLE_CHECKLIST_EMAILS'] == 'false'
        assert env['GAS_WEB_APP_URL'] == ''
        assert env['RESEND_API_KEY'] == ''
        assert env['HAIZE_STORAGE_URL'] == ''
        assert env['AUTOMATION_SECRET'] == ''
        assert env['FRONTEND_PUBLIC_URL'] == SITE
        assert env['VITE_API_URL'] == API
        assert env['VITE_HAIZE_DEMO_V73'] == '1'

        backend = frontend = navegador = contexto = playwright = None
        try:
            with (pasta / 'api.log').open('w', encoding='utf-8') as l_api, \
                 (pasta / 'web.log').open('w', encoding='utf-8') as l_web:
                backend = subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn', 'demo_local_v73:app',
                     '--host', '127.0.0.1', '--port', '18774'],
                    cwd=BASE / 'backend', env=env, stdout=l_api,
                    stderr=subprocess.STDOUT,
                )
                aguardar(API + '/status', backend, 'Demo backend')
                frontend = subprocess.Popen(
                    ['npm', 'run', 'dev', '--', '--host', '127.0.0.1',
                     '--port', '5174', '--strictPort'],
                    cwd=BASE / 'frontend', env=env, stdout=l_web,
                    stderr=subprocess.STDOUT,
                )
                aguardar(SITE, frontend, 'Demo frontend')
                gestor = login('gestora.demo@local.test')
                alfa = login('zelador.alfa.demo@local.test')
                beta = login('zelador.beta.demo@local.test')
                codigo, servicos = chamar('/servicos', token=gestor)
                assert codigo == 200 and len(servicos) == 1, (codigo, servicos)
                sid = servicos[0]['id']
                codigo, avisos = chamar('/servicos/notificacoes', token=alfa)
                assert codigo == 200 and len(avisos) == 1
                assert avisos[0]['servico_id'] == sid
                assert chamar('/servicos/notificacoes', token=beta) == (200, [])
                assert chamar(f'/servicos/{sid}', token=beta)[0] == 404
                codigo, preferencias = chamar('/avisos-whatsapp/me', token=alfa)
                assert codigo == 200 and preferencias['envios_ativos'] is False
                print('DEMO 1/3: backend SQLite fictício, escopo e WhatsApp off.', flush=True)

                playwright = sync_playwright().start()
                navegador = playwright.chromium.launch(headless=True)
                contexto = navegador.new_context(service_workers='block',
                    viewport={'width': 1365, 'height': 900},
                    locale='pt-BR', timezone_id='America/Sao_Paulo')
                destinos_externos = []

                def evitar_externo(route):
                    url = route.request.url
                    if not url.startswith((API + '/', SITE + '/')):
                        destinos_externos.append(url)
                        route.abort()
                        return
                    route.continue_()

                contexto.route('**/*', evitar_externo)
                pagina = contexto.new_page()
                pagina.set_default_timeout(16000)
                erros_js = []
                pagina.on('pageerror', lambda e: erros_js.append(str(e)))
                pagina.goto(SITE, wait_until='domcontentloaded')
                expect(pagina.locator('.login-screen')).to_be_visible()
                expect(pagina.get_by_text('DEMONSTRAÇÃO LOCAL', exact=False)).to_be_visible()
                pagina.get_by_placeholder('nome@haize.com.br').fill(
                    'zelador.alfa.demo@local.test')
                pagina.locator('input[type=password]').fill(
                    'SenhaFicticiaDeTeste123')
                pagina.get_by_role('button', name='Entrar na Plataforma').click()
                expect(pagina.locator('.sidebar-nav')).to_be_visible()
                expect(pagina.locator('.notification-badge')).to_have_text('1')
                pagina.get_by_role('button', name='Ver alertas e notificações').click()
                expect(pagina.get_by_text('Verificar iluminação fictícia', exact=False)).to_be_visible()
                pagina.locator('.alertas-checklist-lista').first.locator('button').first.click()
                expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_be_visible()
                expect(pagina.locator('.notification-badge')).to_have_count(0)
                assert not erros_js, erros_js
                assert not destinos_externos, destinos_externos
                print('DEMO 2/3: navegador real abre e lê tarefa sem rede externa.', flush=True)

                # Fechar a gaveta antes do logout: o backdrop bloqueia cliques
                # fora do detalhe por acessibilidade e comportamento esperado.
                pagina.get_by_role('dialog', name=f'Serviço #{sid}').get_by_role('button', name='Fechar detalhes', exact=True).click()
                expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_have_count(0)
                pagina.get_by_role('button', name='Encerrar Sessão').click()
                expect(pagina.locator('.login-screen')).to_be_visible()
                pagina.get_by_placeholder('nome@haize.com.br').fill(
                    'zelador.beta.demo@local.test')
                pagina.locator('input[type=password]').fill(
                    'SenhaFicticiaDeTeste123')
                pagina.get_by_role('button', name='Entrar na Plataforma').click()
                expect(pagina.locator('.sidebar-nav')).to_be_visible()
                expect(pagina.locator('.notification-badge')).to_have_count(0)
                assert not erros_js, erros_js
                assert not destinos_externos, destinos_externos
                print('DEMO 3/3: mudança de conta preserva privacidade.', flush=True)
        except Exception:
            for nome in ('api.log', 'web.log'):
                arquivo = pasta / nome
                if arquivo.exists():
                    print(f'--- {nome} ---\n' +
                          '\n'.join(arquivo.read_text(encoding='utf-8',
                            errors='replace').splitlines()[-30:]), flush=True)
            raise
        finally:
            if contexto:
                contexto.close()
            if navegador:
                navegador.close()
            if playwright:
                playwright.stop()
            terminar(frontend)
            terminar(backend)
    print('DEMONSTRAÇÃO V7.3: 3/3 APROVADOS, sem API fictícia nem produção.', flush=True)


if __name__ == '__main__':
    main()
