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
    pagina.get_by_role('dialog', name=f'Serviço #{sid}').get_by_role('button', name='Fechar detalhes', exact=True).click()
    expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_have_count(0)
    pagina.get_by_role('button', name='Encerrar Sessão').click()
    expect(pagina.locator('.login-screen')).to_be_visible()
    respostas_sessao = []
    def observar_revalidacao(res):
        if res.url.endswith('/usuarios/me'):
            respostas_sessao.append(res.status)
    pagina.on('response', observar_revalidacao)
    login_tela(pagina, 'zelador.beta@teste.local')
    expect(pagina.locator('.notification-badge')).to_have_count(0)
    pagina.wait_for_function("""() => {
        try {
            const conta = JSON.parse(sessionStorage.getItem('usuarioControladoria'));
            return conta && conta.email === 'zelador.beta@teste.local' && !!conta.token
        } catch { return false }
    }""", timeout=5000)
    # Reiniciar IMEDIATAMENTE após o login: exercita a corrida entre
    # navegação e revalidação de perfil sem acrescentar espera artificial.
    antes_da_navegacao = pagina.evaluate("""() => {
        const raw = sessionStorage.getItem('usuarioControladoria');
        if (!raw) return {existe: false};
        const conta = JSON.parse(raw);
        return {existe: true, email_correto: conta.email === 'zelador.beta@teste.local'};
    }""")
    print('DIAGNOSTICO SESSAO ANTES DE LINK (FICTICIO): ' +
          json.dumps({'estado': antes_da_navegacao, 'revalidacoes': respostas_sessao},
                     ensure_ascii=False), flush=True)
    # Instrumentação de CI: caso o feedback falhe em corrida de sessão,
    # registrar apenas códigos HTTP e estado visual fictício (sem token).
    respostas_link = []
    def registrar_resposta_link(res):
        if f'/servicos/{sid}' in res.url:
            respostas_link.append({
                'status': res.status, 'metodo': res.request.method,
            })
    pagina.on('response', registrar_resposta_link)
    pagina.goto(f'{FRONTEND}/?servico={sid}', wait_until='domcontentloaded')
    try:
        expect(pagina.get_by_text(
            'A tarefa do link não existe ou não está disponível para seu perfil.'
        )).to_be_visible(timeout=11000)
    except AssertionError:
        estado_visual = pagina.evaluate("""() => ({
            tela: location.pathname + location.search,
            sessao_existente: !!sessionStorage.getItem('usuarioControladoria'),
            central: !!document.querySelector('[aria-label="Central de Serviços"]'),
            avisos: [...document.querySelectorAll('[role="alert"]')]
                .map(e => e.innerText.slice(0, 250)),
            carregando: [...document.querySelectorAll('[role="status"]')]
                .map(e => e.innerText.slice(0, 140)).slice(0, 5),
            titulos: [...document.querySelectorAll('h1,h2,h3')]
                .map(e => e.innerText.slice(0, 90)).slice(0, 8)
        })""")
        print('DIAGNOSTICO LINK PROTEGIDO (DADOS FICTICIOS): ' +
              json.dumps({'api': respostas_link, 'tela': estado_visual},
                         ensure_ascii=False), flush=True)
        raise
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



def homologar_mobile(browser):
    """Simula tela e toque de celular real, usando a API e o PostgreSQL reais.

    Mobile Playwright valida layout e comportamento, não substitui teste
    físico em aparelhos Android/iOS.
    """
    from datetime import date, timedelta
    status, gestor = consultar('POST', '/login', dados={
        'email': 'gestora@teste.local', 'senha': SENHA,
    })
    assert status == 200
    token_gestor = gestor['access_token']
    status, beta = consultar('POST', '/login', dados={
        'email': 'zelador.beta@teste.local', 'senha': SENHA,
    })
    assert status == 200
    token_beta = beta['access_token']

    status, criada = consultar('POST', '/servicos', token=token_gestor, dados={
        'condominio_id': 2, 'executores_ids': [3],
        'fiscalizadores_ids': [],
        'titulo': 'Inspecionar bombas fictícias no celular',
        'descricao': 'Fluxo mobile com notificação persistente e API real.',
        'prazo': (date.today() + timedelta(days=7)).isoformat(),
    })
    assert status == 201, (status, criada)
    sid = criada['id']
    status, avisos = consultar('GET', '/servicos/notificacoes', token=token_beta)
    assert status == 200 and len(avisos) == 1 and avisos[0]['servico_id'] == sid
    aviso_id = avisos[0]['id']

    with browser.new_context(
        viewport={'width': 390, 'height': 844},
        device_scale_factor=2, is_mobile=True, has_touch=True,
        locale='pt-BR', timezone_id='America/Sao_Paulo',
        service_workers='block',
    ) as contexto:
        pagina = contexto.new_page()
        pagina.set_default_timeout(16000)
        erros = []
        pagina.on('pageerror', lambda e: erros.append(str(e)))
        pagina.goto(FRONTEND, wait_until='domcontentloaded')
        expect(pagina.locator('.login-screen')).to_be_visible()
        pagina.get_by_placeholder('nome@haize.com.br').fill('zelador.beta@teste.local')
        pagina.locator('input[type="password"]').fill(SENHA)
        pagina.get_by_role('button', name='Entrar na Plataforma').click()
        expect(pagina.locator('.login-screen')).to_have_count(0)
        expect(pagina.locator('.notification-badge')).to_have_text('1')
        print('MOBILE 1/4: login e contador real em viewport touch 390px.', flush=True)

        pagina.get_by_role('button', name='Ver alertas e notificações').click()
        expect(pagina.get_by_text('Tarefas e serviços (1)')).to_be_visible()
        bloco = pagina.locator('.alertas-checklist-lista').first
        expect(bloco).to_contain_text('Inspecionar bombas fictícias')
        bloco.locator('button').first.click()
        expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_be_visible()
        expect(pagina.locator('.notification-badge')).to_have_count(0)
        status, atualizados = consultar('GET', '/servicos/notificacoes', token=token_beta)
        assert status == 200 and any(a['id'] == aviso_id and a['lida'] for a in atualizados)
        print('MOBILE 2/4: toque no sino e leitura persistida na API.', flush=True)

        pagina.get_by_role('dialog', name=f'Serviço #{sid}').get_by_role(
            'button', name='Fechar detalhes', exact=True).click()
        expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_have_count(0)
        pagina.get_by_role('button', name='Abrir menu de navegação').click()
        expect(pagina.locator('.sidebar-nav').get_by_role(
            'button', name='Minhas Tarefas')).to_be_visible()
        pagina.locator('.sidebar-nav').get_by_role(
            'button', name='Minhas Tarefas').click()
        expect(pagina.get_by_role('heading', name='Visão geral dos serviços')).to_be_visible()
        # Nenhum dado de outro condomínio deve aparecer na listagem.
        expect(pagina.get_by_text('Inspecionar portão fictício')).to_have_count(0)
        expect(pagina.get_by_text('Inspecionar bombas fictícias', exact=False)).to_be_visible()
        print('MOBILE 3/4: menu touch, tarefas e isolamento de condomínios.', flush=True)

        pagina.goto(f'{FRONTEND}/?servico={sid}', wait_until='domcontentloaded')
        expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}')).to_be_visible()
        pagina.wait_for_function("() => !location.search.includes('servico=')")
        expect(pagina.get_by_role('dialog', name=f'Serviço #{sid}').get_by_role(
            'heading', name='Inspecionar bombas fictícias no celular')).to_be_visible()
        # O documento deve caber no telefone sem rolagem horizontal geral.
        largura = pagina.evaluate("""() => ({
            visivel: document.documentElement.clientWidth,
            conteudo: document.documentElement.scrollWidth
        })""")
        if largura['conteudo'] > largura['visivel'] + 2:
            extrapolam = pagina.evaluate("""() => [...document.querySelectorAll('*')]
                .map(el => {
                  const r = el.getBoundingClientRect();
                  return { tag: el.tagName, css: String(el.className).slice(0, 75),
                           x: Math.round(r.left), direita: Math.round(r.right),
                           largura: Math.round(r.width) };
                })
                .filter(r => r.direita > window.innerWidth + 2 || r.x < -2)
                .sort((a,b) => b.direita - a.direita).slice(0, 14)""")
            arvores = pagina.evaluate("""() => {
              const sel = ['html', 'body', '.app', '.main-content', '.topbar',
                '.topbar-actions', '.page', '.haize-servicos', '.hs-v4-drawer',
                '.hs-v4-drawer-scroll', '.hs-v4-drawer-bar', '.hs-v3-detail-inner'];
              return sel.map(css => {
                const el = document.querySelector(css);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {css, client: el.clientWidth, scroll: el.scrollWidth,
                  x: Math.round(r.left), direita: Math.round(r.right),
                  overflow: getComputedStyle(el).overflowX};
              }).filter(Boolean);
            }""")
            print('MOBILE DIMENSÕES: ' + json.dumps(arvores, ensure_ascii=False), flush=True)
            print('MOBILE DIAGNÓSTICO DE OVERFLOW: ' +
                  json.dumps(extrapolam, ensure_ascii=False), flush=True)
        assert largura['conteudo'] <= largura['visivel'] + 2, largura
        assert not erros, erros
        print('MOBILE 4/4: link profundo, gaveta e viewport sem overflow.', flush=True)

    print('HOMOLOGACAO MOBILE V7.3: 4/4 APROVADOS com frontend e API reais.', flush=True)


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
        homologar_mobile(browser)
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
