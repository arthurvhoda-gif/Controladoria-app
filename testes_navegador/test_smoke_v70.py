# -*- coding: utf-8 -*-
"""Regressão real em Chromium usando apenas API simulada.

Não acessa Neon, Render, Vercel, WhatsApp, Gmail, nem dados de usuários reais.
Cada cenário abre contexto isolado e as respostas são totalmente fictícias.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from urllib.request import urlopen
from urllib.error import URLError

from playwright.sync_api import sync_playwright, expect

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"
BASE = "http://127.0.0.1:4174"
API = "https://api.haize.test"

USUARIOS = {
    "admin@teste.local": dict(id=1, nome="Gestora Teste", email="admin@teste.local", perfil="Controladoria", condominio_id=None),
    "zelador@teste.local": dict(id=2, nome="Zelador Teste", email="zelador@teste.local", perfil="Checklist", condominio_id=1),
    "compras@teste.local": dict(id=3, nome="Solicitante Teste", email="compras@teste.local", perfil="Solicitante", condominio_id=None),
    "fin@teste.local": dict(id=4, nome="Financeiro Teste", email="fin@teste.local", perfil="Financeiro", condominio_id=None),
}

PEDIDOS = [
    {
        "id": i,
        "numero": f"SOL-{i:04d}",
        "condominio": "Condomínio Fictício A",
        "condominio_id": 1,
        "categoria": "Manutenção",
        "fornecedor": "Fornecedor Fictício",
        "descricao": "Pedido especialmente identificável" if i == 1 else f"Compra simulada número {i}",
        "valor": 100.0 + i,
        "valor_aprovado": 0.0,
        "valor_realizado": 0.0,
        "status": "Aprovação pendente",
        "solicitante": "Solicitante Teste",
        "solicitante_id": 3,
        "data": f"2026-10-{(i % 28)+1:02d} 10:00:00",
    }
    for i in range(1, 16)
]

FINANCEIRO = {
    "solicitacoes": [
        {
            "solicitacao_id": 15,
            "numero": "SOL-0015",
            "condominio": "Condomínio Fictício A",
            "categoria": "Manutenção",
            "fornecedor": "Fornecedor Fictício",
            "descricao": "Pagamento de teste",
            "status": "Aprovada",
            "pago_centavos": 15000,
            "excedente_centavos": 0,
            "alerta_sobrepagamento": False,
        }
    ],
    "limite": 100,
}

DETALHE_FINANCEIRO = {
    "resumo": {
        "numero": "SOL-0015",
        "condominio": "Condomínio Fictício A",
        "descricao": "Pagamento de teste",
        "solicitado_centavos": 20000,
        "aprovado_centavos": 20000,
        "realizado_centavos": 15000,
        "pago_centavos": 15000,
        "saldo_centavos": 5000,
        "excedente_centavos": 0,
        "alerta_sobrepagamento": False,
        "solicitante_id": 3,
        "pagamento_permitido": True,
    },
    "lancamentos": [],
}


class HaizeNavegadorV70(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ)
        env["VITE_API_URL"] = API
        cls.servidor = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "4174", "--strictPort"],
            cwd=FRONTEND,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(80):
            if cls.servidor.poll() is not None:
                raise RuntimeError("Vite encerrou antes da inicialização.")
            try:
                with urlopen(BASE, timeout=1) as res:
                    if res.status == 200:
                        break
            except (URLError, TimeoutError, OSError):
                time.sleep(0.25)
        else:
            cls.servidor.terminate()
            raise RuntimeError("Vite não iniciou na porta de testes.")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.servidor.terminate()
        try:
            cls.servidor.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.servidor.kill()

    def setUp(self):
        self.contexto = self.browser.new_context(
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            service_workers="block",
            viewport={"width": 1440, "height": 900},
        )
        self.page = self.contexto.new_page()
        self.page.set_default_timeout(12000)
        self.usuario = USUARIOS["admin@teste.local"]
        self.sessao_invalida = False
        self.erros_js = []
        self.page.on("pageerror", lambda erro: self.erros_js.append(str(erro)))
        self.page.route(API + "/**", self.responder_api)

    def tearDown(self):
        try:
            self.assertEqual(self.erros_js, [], "Exceções JavaScript no navegador")
        finally:
            self.contexto.close()

    def responder_api(self, rota):
        request = rota.request
        caminho = request.url.removeprefix(API).split("?")[0]
        metodo = request.method
        status = 200
        if caminho == "/login" and metodo == "POST":
            dados = json.loads(request.post_data or "{}")
            usuario = USUARIOS.get(dados.get("email", "").lower())
            if not usuario:
                status, resposta = 401, {"detail": "Credenciais de teste inválidas"}
            else:
                self.usuario = usuario
                resposta = {"usuario": usuario, "access_token": "token-ficticio-" + str(usuario["id"])}
        elif caminho == "/usuarios/me":
            status = 401 if self.sessao_invalida else 200
            resposta = {"detail": "Sessão expirada"} if status == 401 else self.usuario
        elif caminho == "/solicitacoes":
            resposta = PEDIDOS if self.usuario["perfil"] != "Checklist" else []
        elif caminho == "/condominios":
            resposta = [{"id": 1, "nome": "Condomínio Fictício A", "cnpj": None, "codigo": "TESTE"}]
        elif caminho in {"/categorias", "/fornecedores", "/checklists", "/usuarios"}:
            resposta = []
        elif caminho == "/checklists/alertas":
            resposta = {"alertas": []}
        elif caminho in {"/servicos", "/servicos/notificacoes", "/servicos/responsaveis"}:
            resposta = []
        elif caminho == "/financeiro/solicitacoes":
            resposta = FINANCEIRO
        elif caminho == "/financeiro/solicitacoes/15/lancamentos":
            resposta = DETALHE_FINANCEIRO
        elif caminho == "/avisos-whatsapp/admin/usuarios":
            resposta = [
                {**u, "numero": None, "receber_alertas": False, "condominio_nome": "Condomínio Fictício A"}
                for u in USUARIOS.values()
            ]
        elif caminho == "/avisos-whatsapp/fila/previas":
            resposta = {"previa": [], "envios_ativos": False}
        elif caminho == "/status":
            resposta = {"status": "online"}
        else:
            # Rota não simulada: não acesse serviços reais e exponha o erro na UI.
            status, resposta = 404, {"detail": f"Rota ausente na simulação: {caminho}"}
        rota.fulfill(status=status, content_type="application/json", body=json.dumps(resposta, ensure_ascii=False))

    def login(self, email="admin@teste.local"):
        self.page.goto(BASE, wait_until="domcontentloaded")
        expect(self.page.locator(".login-screen")).to_be_visible()
        self.page.get_by_placeholder("nome@haize.com.br").fill(email)
        self.page.locator('input[type="password"]').fill("SenhaFicticiaDeTeste123")
        self.page.get_by_role("button", name="Entrar na Plataforma").click()
        expect(self.page.locator(".sidebar-nav")).to_be_visible()
        expect(self.page.locator(".login-screen")).to_have_count(0)

    def menu(self, nome):
        self.page.locator(".sidebar-nav").get_by_role("button", name=nome, exact=True).click()

    def test_01_login_e_termino_da_sessao(self):
        self.login()
        self.menu("Solicitações")
        expect(self.page.locator(".central-solicitacao-linha")).to_have_count(10)
        self.page.get_by_role("button", name="Encerrar Sessão").click()
        expect(self.page.locator(".login-screen")).to_be_visible()
        self.assertIsNone(self.page.evaluate("sessionStorage.getItem('usuarioControladoria')"))

    def test_02_solicitacoes_paginacao_e_filtros(self):
        self.login("compras@teste.local")
        self.menu("Solicitações")
        expect(self.page.locator(".central-solicitacao-linha")).to_have_count(10)
        self.page.locator(".cadastro-paginacao, .central-paginacao").last.get_by_role("button", name="Próxima").click()
        expect(self.page.locator(".central-solicitacao-linha")).to_have_count(5)
        self.page.get_by_role("searchbox", name="Pesquisar solicitações").fill("especialmente identificável")
        expect(self.page.locator(".central-solicitacao-linha")).to_have_count(1)
        expect(self.page.get_by_role("button", name="Abrir solicitação SOL-0001")).to_be_visible()
        self.assertEqual(self.page.locator(".sidebar-nav").get_by_role("button", name="Contatos WhatsApp").count(), 0)

    def test_03_zelador_so_ve_checklist_e_tarefas(self):
        self.login("zelador@teste.local")
        nav = self.page.locator(".sidebar-nav")
        expect(nav.get_by_role("button", name="Checklist Predial")).to_be_visible()
        expect(nav.get_by_role("button", name="Minhas Tarefas")).to_be_visible()
        self.assertEqual(nav.get_by_role("button", name="Central Financeira").count(), 0)
        self.assertEqual(nav.get_by_role("button", name="Contatos WhatsApp").count(), 0)
        self.menu("Minhas Tarefas")
        expect(self.page.get_by_role("heading", name="Visão geral dos serviços")).to_be_visible()
        self.menu("Checklist Predial")
        expect(self.page.locator(".page-checklist")).to_be_visible()

    def test_04_financeiro_consulta_sem_poder_registrar(self):
        self.login("fin@teste.local")
        nav = self.page.locator(".sidebar-nav")
        expect(nav.get_by_role("button", name="Central Financeira")).to_be_visible()
        self.assertEqual(nav.get_by_role("button", name="Contatos WhatsApp").count(), 0)
        self.assertEqual(nav.get_by_role("button", name="Checklist Predial").count(), 0)
        expect(self.page.locator(".fin-root")).to_be_visible()
        self.page.locator(".fin-linha").first.click()
        expect(self.page.get_by_text("Acesso somente para consulta", exact=False)).to_be_visible()
        self.assertEqual(self.page.get_by_role("button", name="Registrar pagamento auditado").count(), 0)
        self.assertEqual(self.page.get_by_role("button", name="Cadastrar Financeiro").count(), 0)

    def test_05_controladoria_acessa_servicos_financeiro_e_whatsapp(self):
        self.login()
        self.menu("Serviços Internos")
        expect(self.page.get_by_role("heading", name="Visão geral dos serviços")).to_be_visible()
        self.menu("Central Financeira")
        expect(self.page.locator(".fin-root")).to_be_visible()
        expect(self.page.get_by_role("button", name="Cadastrar Financeiro")).to_be_visible()
        self.menu("Contatos WhatsApp")
        expect(self.page.locator(".wa-admin")).to_be_visible()
        expect(self.page.get_by_text("Cadastros existentes")).to_be_visible()
        self.page.get_by_role("button", name="Exibir prévias").click()
        expect(self.page.get_by_text("Nenhuma notificação preparada no momento.")).to_be_visible()

    def test_06_sessao_rejeitada_retorna_ao_login(self):
        self.sessao_invalida = True
        self.page.add_init_script(
            """sessionStorage.setItem('usuarioControladoria', JSON.stringify({
                id: 1, nome: 'Gestora Teste', email: 'admin@teste.local',
                perfil: 'Controladoria', token: 'token-expirado'
            }))"""
        )
        self.page.goto(BASE, wait_until="domcontentloaded")
        expect(self.page.locator(".login-screen")).to_be_visible()
        self.assertIsNone(self.page.evaluate("sessionStorage.getItem('usuarioControladoria')"))


if __name__ == "__main__":
    unittest.main()
