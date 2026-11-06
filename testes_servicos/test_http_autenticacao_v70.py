# -*- coding: utf-8 -*-
"""Integração HTTP real FastAPI com SQLite fictício isolado.

Sem Neon, Render, envio de e-mails ou WhatsApp. Diferente de testes que
chamam handlers diretamente, estes exercícios passam pelo middleware JWT
e pela matriz de autorização da API, com requisições HTTP de TestClient.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_servicos as fixture
import auth_utils
import main as api

models = fixture.models
SEGREDO_TESTE = "chave-unicamente-local-ci-nao-publicar-em-producao-2026"


class TesteHTTPV70(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AUTH_SECRET_KEY": SEGREDO_TESTE,
            "AUTOMATION_SECRET": "",
            "ENABLE_CHECKLIST_EMAILS": "false",
            "GAS_WEB_APP_URL": "",
            "HAIZE_SECRET": "",
        })
        self.env.start()
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome="Edificio Ficticio A"),
            models.Condominio(id=2, nome="Edificio Ficticio B"),
            models.Usuario(id=1, nome="Gestora", email="gestora@local.test",
                           senha=auth_utils.hash_password("SenhaSomenteParaTeste123"), perfil="Controladoria"),
            models.Usuario(id=2, nome="Ana", email="ana2@local.test", senha="hash-teste", perfil="Solicitante"),
            models.Usuario(id=3, nome="Ana", email="ana3@local.test", senha="hash-teste", perfil="Solicitante"),
            models.Usuario(id=4, nome="Zelador A", email="a@local.test", senha="hash-teste",
                           perfil="Checklist", condominio_id=1),
            models.Usuario(id=5, nome="Zelador B", email="b@local.test", senha="hash-teste",
                           perfil="Checklist", condominio_id=2),
            models.Usuario(id=6, nome="Financeiro", email="fin@local.test",
                           senha="hash-teste", perfil="Financeiro"),
            models.Solicitacao(id=10, numero="SOL-0010", condominio="Edificio Ficticio A",
                categoria="Manutencao", fornecedor="Ficticio", descricao="Pedido Ana 2",
                solicitante="Ana", solicitante_id=2, valor=100, status="Aprovação pendente"),
            models.Solicitacao(id=11, numero="SOL-0011", condominio="Edificio Ficticio A",
                categoria="Manutencao", fornecedor="Ficticio", descricao="Pedido Ana 3",
                solicitante="Ana", solicitante_id=3, valor=200, status="Aprovação pendente"),
            models.Solicitacao(id=12, numero="SOL-0012", condominio="Edificio Ficticio A",
                categoria="Manutencao", fornecedor="Ficticio", descricao="Pedido antigo",
                solicitante="Ana", solicitante_id=None, valor=200, status="Aprovação pendente"),
            models.ChecklistItem(id=20, condominio="Edificio Ficticio A", condominio_id=1,
                titulo="Vistoria A", frequencia="Diária"),
            models.ChecklistItem(id=21, condominio="Edificio Ficticio B", condominio_id=2,
                titulo="Vistoria B", frequencia="Diária"),
        ])
        self.db.commit()
        self.client = TestClient(api.app, raise_server_exceptions=True)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.env.stop()

    def auth(self, uid):
        user = self.db.get(models.Usuario, uid)
        return {"Authorization": "Bearer " + auth_utils.create_token(user)}

    def test_publico_versus_privado(self):
        self.assertEqual(self.client.get("/status").status_code, 200)
        self.assertEqual(self.client.get("/solicitacoes").status_code, 401)
        self.assertEqual(self.client.get("/usuarios").status_code, 401)

    def test_login_real_com_hash_e_token(self):
        res = self.client.post("/login", json={
            "email": "  GESTORA@LOCAL.TEST ", "senha": "SenhaSomenteParaTeste123"
        })
        self.assertEqual(res.status_code, 200, res.text)
        token = res.json()["access_token"]
        self.assertEqual(self.client.get("/usuarios/me",
            headers={"Authorization": "Bearer " + token}).json()["perfil"], "Controladoria")

    def test_login_senha_errada_nao_autentica(self):
        res = self.client.post("/login", json={
            "email": "gestora@local.test", "senha": "incorreta"
        })
        self.assertEqual(res.status_code, 401)

    def test_nomes_iguais_nao_vazam_pedidos(self):
        for uid, esperado in ((2, 10), (3, 11)):
            res = self.client.get("/solicitacoes", headers=self.auth(uid))
            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual([x["id"] for x in res.json()], [esperado])
        self.assertEqual(len(self.client.get("/solicitacoes", headers=self.auth(1)).json()), 3)

    def test_solicitante_nao_consulta_anexos_ou_historico_alheios(self):
        for path in ("/solicitacoes/11/anexos", "/solicitacoes/11/historico",
                     "/solicitacoes/12/anexos", "/solicitacoes/12/historico"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=self.auth(2)).status_code, 403)

    def test_zeladores_isolados_por_condominio(self):
        for uid, esperado in ((4, 20), (5, 21)):
            res = self.client.get("/checklists", headers=self.auth(uid))
            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual([x["id"] for x in res.json()], [esperado])
        self.assertEqual(self.client.get("/checklists", headers=self.auth(6)).status_code, 403)

    def test_financeiro_so_consulta_pagamentos(self):
        self.assertEqual(self.client.get("/financeiro/solicitacoes",
            headers=self.auth(6)).status_code, 200)
        res = self.client.post("/financeiro/solicitacoes/10/pagamentos",
            headers=self.auth(6), data={})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.client.get("/usuarios",
            headers=self.auth(6)).status_code, 403)

    def test_solicitante_nao_faz_pagamentos(self):
        self.assertEqual(self.client.get("/financeiro/solicitacoes",
            headers=self.auth(2)).status_code, 403)
        self.assertEqual(self.client.post("/financeiro/solicitacoes/10/pagamentos",
            headers=self.auth(2), data={}).status_code, 403)

    def test_token_forjado_rejeitado(self):
        self.assertEqual(self.client.get("/usuarios/me", headers={
            "Authorization": "Bearer abc.def.ghi"
        }).status_code, 401)

    def test_automacao_sem_chave_nunca_envia_ou_expõe(self):
        self.assertEqual(self.client.post("/automacoes/checklists/atrasos").status_code, 403)
        self.assertEqual(self.client.post("/automacoes/checklists/atrasos",
            headers={"X-Haize-Automation": "chave-invalida"}).status_code, 403)

    def test_rota_inexistente_nao_contorna_permissoes(self):
        self.assertEqual(self.client.get("/nao-existe", headers=self.auth(1)).status_code, 403)


if __name__ == "__main__":
    unittest.main()
