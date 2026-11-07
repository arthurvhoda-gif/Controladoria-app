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
from tempfile import TemporaryDirectory
from zipfile import ZipFile
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
        "fornecedor": '=HYPERLINK("https://exemplo-invalido.test","Clique")' if i == 2 else "Fornecedor Fictício",
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
        self.avisos_servicos_ficticios = []
        self.servicos_ficticios = []
        self.pessoas_servicos_ficticios = []
        self.atrasos_servicos_ficticios = []
        self.falha_consulta_servicos = False
        self.detalhe_servico_revogado = False
        self.lista_servicos_indisponivel = False
        self.link_servico_indisponivel = False
        self.consultas_detalhe_servico = 0
        self.telefone_whatsapp_ficticio = '+5543999991111'
        self.ultimo_consentimento_ficticio = None
        self.consentimento_whatsapp_ficticio = False
        self.leituras_avisos_ficticios = []
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
        elif caminho == "/servicos/notificacoes":
            if self.falha_consulta_servicos:
                status, resposta = 403, {"detail": "Permissões alteradas. Faça nova consulta."}
            else:
                # Simula o filtro por destinatário aplicado pela API real.
                resposta = [a for a in self.avisos_servicos_ficticios
                            if a.get("destinatario_id", self.usuario["id"]) == self.usuario["id"]]
        elif caminho == "/servicos/alertas-prazos":
            if self.falha_consulta_servicos:
                status, resposta = 403, {"detail": "Permissões alteradas. Faça nova consulta."}
            else:
                resposta = {"total": len(self.atrasos_servicos_ficticios),
                           "alertas": self.atrasos_servicos_ficticios, "limite": 100}
        elif caminho.startswith("/servicos/notificacoes/") and caminho.endswith("/ler") and metodo == "POST":
            try:
                aviso_id = int(caminho.split("/")[3])
                aviso = next(a for a in self.avisos_servicos_ficticios if a["id"] == aviso_id)
                aviso["lida"] = True
                self.leituras_avisos_ficticios.append(aviso_id)
                resposta = {"ok": True}
            except (ValueError, StopIteration):
                status, resposta = 404, {"detail": "Aviso não encontrado."}
        elif caminho == "/servicos/17":
            self.consultas_detalhe_servico += 1
            if self.link_servico_indisponivel:
                status, resposta = 503, {"detail": "Falha temporária na rede de teste"}
            elif self.detalhe_servico_revogado:
                status, resposta = 404, {"detail": "Serviço não encontrado."}
            else:
                resposta = {
                    "id": 17, "titulo": "Verificar iluminação fictícia",
                    "descricao": "Conferência de teste da iluminação comum",
                    "condominio": "Condomínio Fictício A", "prioridade": "Normal",
                    "prazo": "2026-12-05", "status": "Aguardando ciência",
                    "criador": "Gestora Teste", "responsavel": "Zelador Teste",
                    "atrasado": False, "executores": [], "fiscalizadores": [],
                    "acoes_disponiveis": [],
                }
        elif caminho in ("/servicos/17/historico", "/servicos/17/fotos",
                           "/servicos/18/historico", "/servicos/18/fotos"):
            resposta = []
        elif caminho == "/servicos/responsaveis":
            resposta = self.pessoas_servicos_ficticios
        elif caminho == "/servicos":
            if metodo == "POST":
                dados = json.loads(request.post_data or "{}")
                resposta = {
                    "id": 18, "titulo": dados["titulo"],
                    "descricao": dados["descricao"],
                    "condominio_id": dados["condominio_id"],
                    "condominio": "Condomínio Fictício A",
                    "prioridade": dados["prioridade"], "prazo": dados["prazo"],
                    "status": "Aguardando ciência", "criador": "Gestora Teste",
                    "responsavel": "Gestora Teste", "atrasado": False,
                    "executores": [{"usuario_id": 1, "nome": "Gestora Teste",
                                   "status": "Aguardando ciência"}],
                    "fiscalizadores": [], "acoes_disponiveis": [],
                }
                self.servicos_ficticios.append(resposta)
                self.avisos_servicos_ficticios.append({
                    "id": 701, "servico_id": 18, "destinatario_id": 1,
                    "mensagem": "Nova tarefa criada na Controladoria",
                    "lida": False, "criada_em": "2026-11-07T11:40:00",
                })
                status = 201
            elif self.lista_servicos_indisponivel:
                status, resposta = 503, {"detail": "Serviços temporariamente indisponíveis"}
            else:
                resposta = [item for item in self.servicos_ficticios
                            if not (self.detalhe_servico_revogado and item["id"] == 17)]
        elif caminho == "/financeiro/solicitacoes":
            resposta = FINANCEIRO
        elif caminho == "/financeiro/solicitacoes/15/lancamentos":
            resposta = DETALHE_FINANCEIRO
        elif caminho == "/avisos-whatsapp/admin/usuarios":
            resposta = [
                {**u, "numero": None, "receber_alertas": False, "condominio_nome": "Condomínio Fictício A"}
                for u in USUARIOS.values()
            ]
        elif caminho.startswith("/avisos-whatsapp/admin/usuarios/") and caminho.endswith("/auditoria"):
            resposta = {"usuario_id": int(caminho.split("/")[4]), "historico": [
                {"tipo": "concedido", "origem": "usuario", "alterado_por_id": 2,
                 "telefone_final": "1234", "criado_em": "2026-11-07T08:00:00"},
                {"tipo": "numero_atualizado", "origem": "controladoria", "alterado_por_id": 1,
                 "telefone_anterior_final": None, "telefone_novo_final": "1234",
                 "criado_em": "2026-11-07T07:00:00"}
            ], "limite": 100}
        elif caminho == "/avisos-whatsapp/me":
            if metodo == "PUT":
                dados = json.loads(request.post_data or "{}")
                self.ultimo_consentimento_ficticio = dados
                if (dados.get("receber_alertas") and
                        dados.get("numero_confirmado") != self.telefone_whatsapp_ficticio):
                    status, resposta = 409, {"detail": "Telefone alterado pela Controladoria. Reabra a tela."}
                else:
                    self.consentimento_whatsapp_ficticio = bool(dados.get("receber_alertas"))
                    resposta = {"numero": self.telefone_whatsapp_ficticio,
                               "receber_alertas": self.consentimento_whatsapp_ficticio,
                               "envios_ativos": False}
            else:
                resposta = {"numero": self.telefone_whatsapp_ficticio,
                           "receber_alertas": self.consentimento_whatsapp_ficticio,
                           "envios_ativos": False}
        elif caminho == "/avisos-whatsapp/fila/previas":
            resposta = {"previa": [], "envios_ativos": False}
        elif caminho == "/status":
            resposta = {"status": "online"}
        else:
            # Rota não simulada: não acesse serviços reais e exponha o erro na UI.
            status, resposta = 404, {"detail": f"Rota ausente na simulação: {caminho}"}
        rota.fulfill(status=status, content_type="application/json", body=json.dumps(resposta, ensure_ascii=False))

    def login(self, email="admin@teste.local", caminho=""):
        self.page.goto(BASE + caminho, wait_until="domcontentloaded")
        expect(self.page.locator(".login-screen")).to_be_visible()
        self.page.get_by_placeholder("nome@haize.com.br").fill(email)
        self.page.locator('input[type="password"]').fill("SenhaFicticiaDeTeste123")
        self.page.get_by_role("button", name="Entrar na Plataforma").click()
        expect(self.page.locator(".sidebar-nav")).to_be_visible()
        expect(self.page.locator(".login-screen")).to_have_count(0)

    def menu(self, nome):
        # O contador de pendências pode acrescentar um número ao nome acessível.
        self.page.locator(".sidebar-nav").get_by_role("button", name=nome, exact=False).click()

    def test_08_aviso_de_tarefa_no_sino_global_abre_detalhe_e_confirma_leitura(self):
        self.avisos_servicos_ficticios = [{
            "id": 501, "servico_id": 17,
            "mensagem": "Nova tarefa para executar: Verificar iluminação fictícia",
            "lida": False, "criada_em": "2026-11-07T11:00:00",
        }]
        self.login("zelador@teste.local")
        sino = self.page.get_by_role("button", name="Ver alertas e notificações")
        expect(self.page.locator(".notification-badge")).to_have_text("1")
        sino.click()
        expect(self.page.get_by_text("Tarefas e serviços (1)")).to_be_visible()
        bloco = self.page.locator(".alertas-checklist-lista").first
        expect(bloco).to_contain_text("Verificar iluminação fictícia")
        bloco.locator("button").first.click()
        expect(self.page.get_by_role("heading", name="Central de Serviços")).to_be_visible()
        expect(self.page.get_by_role("dialog", name="Serviço #17")).to_be_visible()
        self.page.wait_for_function(
            "() => document.querySelector('.notification-badge') === null"
        )
        self.assertEqual(self.leituras_avisos_ficticios, [501])

    def test_09_servico_atrasado_no_sino_sem_criar_aviso_de_whatsapp(self):
        self.atrasos_servicos_ficticios = [{
            "servico_id": 17, "titulo": "Verificar iluminação fictícia",
            "condominio": "Condomínio Fictício A", "prazo": "2026-10-30",
            "dias_atraso": 8,
        }]
        self.login("zelador@teste.local")
        expect(self.page.locator(".notification-badge")).to_have_text("1")
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text("Serviços em atraso (1)")).to_be_visible()
        self.page.locator(".alertas-checklist-lista").first.locator("button").first.click()
        expect(self.page.get_by_role("dialog", name="Serviço #17")).to_be_visible()
        self.assertEqual(self.leituras_avisos_ficticios, [])

    def test_10_api_revogada_limpa_avisos_antigos_do_sino(self):
        self.avisos_servicos_ficticios = [{
            "id": 501, "servico_id": 17,
            "mensagem": "Nova tarefa para executar: Verificar iluminação fictícia",
            "lida": False, "criada_em": "2026-11-07T11:00:00",
        }]
        self.atrasos_servicos_ficticios = [{
            "servico_id": 17, "titulo": "Verificar iluminação fictícia",
            "condominio": "Condomínio Fictício A", "prazo": "2026-10-30",
            "dias_atraso": 8,
        }]
        self.login("zelador@teste.local")
        expect(self.page.locator(".notification-badge")).to_have_text("2")
        self.falha_consulta_servicos = True
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text("Não foi possível atualizar as notificações de tarefas.")).to_be_visible()
        expect(self.page.get_by_text("Não foi possível atualizar os serviços em atraso.")).to_be_visible()
        expect(self.page.locator(".notification-badge")).to_have_count(0)

    def test_11_controladoria_ve_historico_whatsapp_sem_numero_completo(self):
        self.login()
        self.menu("Contatos WhatsApp")
        expect(self.page.get_by_role("heading", name="Contatos para notificações")).to_be_visible()
        zelador = self.page.locator(".wa-admin-user").filter(has_text="Zelador Teste")
        zelador.get_by_role("button", name="Ver histórico").click()
        expect(zelador.get_by_text("Autorização concedida pela pessoa")).to_be_visible()
        expect(zelador.get_by_text("Número atualizado pela Controladoria")).to_be_visible()
        expect(zelador.locator(".wa-admin-auditoria")).to_contain_text("1234")
        self.assertNotIn("+554399991234", zelador.locator(".wa-admin-auditoria").inner_text())

    def test_12_optin_envia_apenas_o_numero_que_usuario_viu(self):
        self.login("zelador@teste.local")
        self.page.get_by_role("button", name="Avisos pelo WhatsApp").click()
        modal = self.page.get_by_role("dialog", name="Avisos pelo WhatsApp")
        expect(modal).to_contain_text('+5543999991111')
        modal.get_by_role("checkbox").check()
        modal.get_by_role("button", name="Salvar preferências").click()
        expect(modal.get_by_text("Preferências salvas.", exact=False)).to_be_visible()
        self.assertEqual(self.ultimo_consentimento_ficticio, {
            "receber_alertas": True, "numero_confirmado": '+5543999991111'
        })
        self.assertTrue(self.consentimento_whatsapp_ficticio)

    def test_13_troca_telefone_enquanto_modal_aberto_bloqueia_optin(self):
        self.login("zelador@teste.local")
        self.page.get_by_role("button", name="Avisos pelo WhatsApp").click()
        modal = self.page.get_by_role("dialog", name="Avisos pelo WhatsApp")
        expect(modal).to_contain_text('+5543999991111')
        # A Controladoria altera o número no servidor antes de salvar.
        self.telefone_whatsapp_ficticio = '+5543988882222'
        modal.get_by_role("checkbox").check()
        modal.get_by_role("button", name="Salvar preferências").click()
        expect(modal.get_by_role("alert")).to_contain_text("Telefone alterado pela Controladoria")
        self.assertEqual(self.ultimo_consentimento_ficticio['numero_confirmado'], '+5543999991111')
        self.assertFalse(self.consentimento_whatsapp_ficticio)

    def test_14_nao_pede_permissao_sem_clique_e_nao_promete_push_remoto(self):
        self.page.add_init_script("""
          window.__permRequestCount = 0;
          class LocalNotification {
            static permission = 'default';
            static requestPermission() {
              window.__permRequestCount += 1;
              LocalNotification.permission = 'granted';
              return Promise.resolve('granted');
            }
            constructor() {}
          }
          Object.defineProperty(window, 'Notification', {
            configurable: true, value: LocalNotification,
          });
        """)
        self.login("zelador@teste.local")
        self.assertEqual(self.page.evaluate("window.__permRequestCount"), 0)
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text(
            "Avisos internos disponíveis enquanto o aplicativo estiver aberto."
        )).to_be_visible()
        self.assertEqual(self.page.get_by_text("Notificações Push ativas").count(), 0)
        self.page.get_by_role("button", name="Ativar aviso no navegador").click()
        self.page.wait_for_function("() => window.__permRequestCount === 1")
        expect(self.page.get_by_text(
            "Avisos locais permitidos enquanto o aplicativo estiver aberto."
        )).to_be_visible()

    def test_15_apenas_aviso_novo_gera_notificacao_local_uma_vez(self):
        self.page.add_init_script("""
          window.__avisosNativos = [];
          class LocalNotification {
            static permission = 'granted';
            constructor(titulo, opcoes) {
              window.__avisosNativos.push({titulo, corpo: opcoes?.body});
            }
          }
          Object.defineProperty(window, 'Notification', {
            configurable: true, value: LocalNotification,
          });
        """)
        self.avisos_servicos_ficticios = [{
            "id": 501, "servico_id": 17,
            "mensagem": "Aviso antigo de tarefa fictícia",
            "lida": False, "criada_em": "2026-11-06T11:00:00",
        }]
        self.login("zelador@teste.local")
        expect(self.page.locator(".notification-badge")).to_have_text("1")
        # O primeiro carregamento define a referência, sem alarme de mensagens antigas.
        self.assertEqual(self.page.evaluate("window.__avisosNativos"), [])
        self.avisos_servicos_ficticios.append({
            "id": 502, "servico_id": 17,
            "mensagem": "Nova atividade fictícia",
            "lida": False, "criada_em": "2026-11-07T11:30:00",
        })
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.locator(".notification-badge")).to_have_text("2")
        self.page.wait_for_function("() => window.__avisosNativos.length === 1")
        novo = self.page.evaluate("window.__avisosNativos[0]")
        self.assertIn("Controladoria Haize", novo["titulo"])
        self.assertNotIn("Nova atividade fictícia", novo["corpo"])
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        self.page.wait_for_timeout(150)
        self.assertEqual(len(self.page.evaluate("window.__avisosNativos")), 1)

    def test_16_troca_de_conta_limpa_avisos_do_usuario_anterior(self):
        self.avisos_servicos_ficticios = [
            {"id": 601, "servico_id": 17, "destinatario_id": 2,
             "mensagem": "Tarefa PRIVADA Zelador A",
             "lida": False, "criada_em": "2026-11-07T11:30:00"},
            {"id": 602, "servico_id": 17, "destinatario_id": 3,
             "mensagem": "Tarefa PRIVADA Colaborador",
             "lida": False, "criada_em": "2026-11-07T11:40:00"},
        ]
        self.login("zelador@teste.local")
        expect(self.page.locator(".notification-badge")).to_have_text("1")
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text("Tarefa PRIVADA Zelador A")).to_be_visible()
        self.assertEqual(self.page.get_by_text("Tarefa PRIVADA Colaborador").count(), 0)
        self.page.get_by_role("button", name="Encerrar Sessão").click()
        expect(self.page.locator(".login-screen")).to_be_visible()
        self.login("compras@teste.local")
        # Solicitante também tem 15 solicitações fictícias na central; validar
        # o subtotal de TAREFAS, não o total agregado do sino.
        expect(self.page.locator(".notification-badge")).to_be_visible()
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text("Tarefas e serviços (1)")).to_be_visible()
        expect(self.page.get_by_text("Tarefa PRIVADA Colaborador")).to_be_visible()
        self.assertEqual(self.page.get_by_text("Tarefa PRIVADA Zelador A").count(), 0)

    def test_17_criar_servico_atualiza_sino_sem_f5(self):
        self.pessoas_servicos_ficticios = [
            {"id": 1, "nome": "Gestora Teste", "perfil": "Controladoria",
             "condominio_id": None}
        ]
        self.login()
        self.menu("Serviços Internos")
        self.page.get_by_role("button", name="Novo serviço").first.click()
        modal = self.page.get_by_role("dialog", name="Criar solicitação de serviço")
        modal.locator("#hs-v3-titulo").fill("Revisar quadro elétrico")
        modal.locator("#hs-v3-condominio").select_option("1")
        modal.locator("#hs-v3-prazo").fill(
            (__import__("datetime").date.today() +
             __import__("datetime").timedelta(days=30)).isoformat()
        )
        modal.locator("#hs-v3-descricao").fill("Inspecionar quadro elétrico das áreas comuns")
        modal.locator(".hs-v3-people-list[aria-label='Escolher executores'] input[type=checkbox]").first.check()
        modal.get_by_role("button", name="Criar serviço", exact=False).click()
        expect(self.page.get_by_role("dialog", name="Serviço #18")).to_be_visible()
        self.page.get_by_role("button", name="Fechar detalhes do serviço").click()
        self.page.get_by_role("button", name="Ver alertas e notificações").click()
        expect(self.page.get_by_text("Tarefas e serviços (1)")).to_be_visible()
        expect(self.page.get_by_text("Nova tarefa criada na Controladoria")).to_be_visible()

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
        self.page.locator(".central-paginacao").get_by_role("button", name="Próxima").click()
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

    def test_07_exportacao_excel_preserva_duas_abas_e_formulas(self):
        self.login()
        self.menu("Análises & Rateio")
        botao = self.page.get_by_role("button", name="Exportar Excel")
        expect(botao).to_be_enabled()
        # Exercita a biblioteca ExcelJS REAL no Chromium, não um mock.
        with self.page.expect_download(timeout=45000) as evento:
            botao.click()
        arquivo = evento.value
        self.assertTrue(arquivo.suggested_filename.endswith(".xlsx"))
        with TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "relatorio.xlsx"
            arquivo.save_as(caminho)
            with ZipFile(caminho) as pacote:
                self.assertIsNone(pacote.testzip(), "Arquivo XLSX inválido")
                nomes = set(pacote.namelist())
                self.assertIn("xl/workbook.xml", nomes)
                self.assertIn("xl/worksheets/sheet1.xml", nomes)
                self.assertIn("xl/worksheets/sheet2.xml", nomes)
                self.assertIn("xl/styles.xml", nomes)
                workbook = pacote.read("xl/workbook.xml").decode("utf-8")
                self.assertIn("Resumo por Condomínio", workbook)
                self.assertIn("Extrato de Solicitações", workbook)
                extrato = pacote.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("SUM(F5:F", extrato)
                self.assertIn("SUM(G5:G", extrato)
                # Fornecedor controlado pelo usuário é texto literal, nunca
                # fórmula executável, mesmo começando com '='.
                strings = pacote.read("xl/sharedStrings.xml").decode("utf-8") if "xl/sharedStrings.xml" in nomes else extrato
                self.assertIn("HYPERLINK", strings)
                import re
                formulas = re.findall(r"<f(?: [^>]*)?>(.*?)</f>", extrato)
                self.assertTrue(formulas, "Fórmulas consolidadas precisam existir")
                self.assertFalse(any("HYPERLINK" in formula for formula in formulas))
                resumo = pacote.read("xl/worksheets/sheet1.xml").decode("utf-8")
                self.assertIn("mergeCell", resumo)
                estilos = pacote.read("xl/styles.xml").decode("utf-8")
                self.assertIn("numFmt", estilos)
        expect(self.page.get_by_text("Relatório Executivo Excel (.xlsx) gerado com sucesso!")).to_be_visible()

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
