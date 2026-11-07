# -*- coding: utf-8 -*-
"""V7.3 - HTTP real FastAPI + JWT, com banco SQLite descartavel ficticio.

Sem Neon/Render/Drive/email/WhatsApp. Testa middleware e isolamento real.
"""
import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_servicos as fixture
import auth_utils
import main as app
import models

SEGREDO_TESTE = 'chave-para-integ-http-v73-apenas-teste-local-2026'


class HTTPNotificacoesV73(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'AUTH_SECRET_KEY': SEGREDO_TESTE,
            'AUTOMATION_SECRET': '',
            'GAS_WEB_APP_URL': '',
            'HAIZE_SECRET': '',
            'ENABLE_CHECKLIST_EMAILS': 'false',
            'FRONTEND_PUBLIC_URL': 'http://127.0.0.1:5173',
        })
        self.env.start()
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome='Condominio A'),
            models.Condominio(id=2, nome='Condominio B'),
            models.Usuario(id=1, nome='Gestora', email='gestora@fake.local',
                           senha='hash-teste', perfil='Controladoria'),
            models.Usuario(id=2, nome='Zelador A', email='a@fake.local',
                           senha='hash-teste', perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Zelador B', email='b@fake.local',
                           senha='hash-teste', perfil='Checklist', condominio_id=2),
            models.Usuario(id=4, nome='Solicitante', email='c@fake.local',
                           senha='hash-teste', perfil='Solicitante'),
        ])
        self.db.commit()
        self.client = TestClient(app.app, raise_server_exceptions=True)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.env.stop()

    def auth(self, uid):
        return {'Authorization': 'Bearer ' + auth_utils.create_token(
            self.db.get(models.Usuario, uid))}

    def criar_tarefa(self, condominio_id=1, executor=2):
        resposta = self.client.post('/servicos', headers=self.auth(1), json={
            'condominio_id': condominio_id, 'executores_ids': [executor],
            'fiscalizadores_ids': [],
            'titulo': 'Verificar equipamento', 'descricao': 'Inspecao interna de teste',
            'prazo': (date.today() + timedelta(days=7)).isoformat(),
        })
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()['id']

    def test_http_jwt_aviso_privado_e_leitura(self):
        servico_id = self.criar_tarefa()
        self.assertEqual(self.client.get('/servicos/notificacoes').status_code, 401)
        self.assertEqual(self.client.get('/servicos/notificacoes',
                                         headers=self.auth(3)).json(), [])
        res = self.client.get('/servicos/notificacoes', headers=self.auth(2))
        self.assertEqual(res.status_code, 200, res.text)
        avisos = res.json()
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['servico_id'], servico_id)
        id_aviso = avisos[0]['id']
        self.assertFalse(avisos[0]['lida'])
        self.assertEqual(self.client.post(f'/servicos/notificacoes/{id_aviso}/ler',
                                          headers=self.auth(3)).status_code, 404)
        ok = self.client.post(f'/servicos/notificacoes/{id_aviso}/ler',
                              headers=self.auth(2))
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertTrue(self.client.get('/servicos/notificacoes',
                                        headers=self.auth(2)).json()[0]['lida'])

    def test_http_transferencia_revoga_aviso_e_link(self):
        sid = self.criar_tarefa()
        id_aviso = self.client.get('/servicos/notificacoes',
                                   headers=self.auth(2)).json()[0]['id']
        usuario = self.db.get(models.Usuario, 2)
        usuario.condominio_id = 2
        self.db.commit()
        self.assertEqual(self.client.get('/servicos/notificacoes',
                                         headers=self.auth(2)).json(), [])
        self.assertEqual(self.client.post(f'/servicos/notificacoes/{id_aviso}/ler',
                                          headers=self.auth(2)).status_code, 404)
        self.assertEqual(self.client.get(f'/servicos/{sid}',
                                         headers=self.auth(2)).status_code, 404)
        self.assertEqual(self.client.get(f'/servicos/{sid}',
                                         headers=self.auth(1)).status_code, 200)

    def test_http_prazos_respeita_perfil_e_condominio(self):
        self.db.add_all([
            models.ServicoInterno(
                id=80, condominio_id=1, condominio_nome='Condominio A',
                responsavel_id=2, responsavel_nome='Zelador A', criador_id=1,
                criador_nome='Gestora', titulo='Prazo A',
                descricao='Atividade vencida', status='Em andamento',
                prazo=date.today() - timedelta(days=3),
            ),
            models.ServicoInterno(
                id=81, condominio_id=2, condominio_nome='Condominio B',
                responsavel_id=3, responsavel_nome='Zelador B', criador_id=1,
                criador_nome='Gestora', titulo='Prazo B',
                descricao='Atividade vencida', status='Em andamento',
                prazo=date.today() - timedelta(days=2),
            ),
        ])
        self.db.commit()
        self.assertEqual(self.client.get('/servicos/alertas-prazos').status_code, 401)
        self.assertEqual(self.client.get('/servicos/alertas-prazos',
                                         headers=self.auth(4)).json()['total'], 0)
        self.assertEqual(self.client.get('/servicos/alertas-prazos',
                                         headers=self.auth(2)).json()['alertas'][0]['servico_id'], 80)
        self.assertEqual(self.client.get('/servicos/alertas-prazos',
                                         headers=self.auth(3)).json()['alertas'][0]['servico_id'], 81)
        self.assertEqual(self.client.get('/servicos/alertas-prazos',
                                         headers=self.auth(1)).json()['total'], 2)

    def test_http_consentimento_e_historico_protegido(self):
        telefone = self.client.put('/avisos-whatsapp/admin/usuarios/2/numero',
             headers=self.auth(1), json={'numero': '(43) 99999-1111'})
        self.assertEqual(telefone.status_code, 200, telefone.text)
        self.assertEqual(telefone.json()['numero'], '+5543999991111')
        self.assertEqual(self.client.get('/avisos-whatsapp/admin/usuarios/2/auditoria',
                                         headers=self.auth(2)).status_code, 403)
        self.assertEqual(self.client.put('/avisos-whatsapp/me', headers=self.auth(2),
                                         json={'receber_alertas': True}).status_code, 409)
        autorizado = self.client.put('/avisos-whatsapp/me', headers=self.auth(2),
             json={'receber_alertas': True, 'numero_confirmado': '+5543999991111'})
        self.assertEqual(autorizado.status_code, 200, autorizado.text)
        self.assertTrue(autorizado.json()['receber_alertas'])
        logs = self.client.get('/avisos-whatsapp/admin/usuarios/2/auditoria',
                               headers=self.auth(1))
        self.assertEqual(logs.status_code, 200, logs.text)
        historico = logs.json()['historico']
        self.assertEqual({x['tipo'] for x in historico},
                         {'numero_atualizado', 'concedido'})
        self.assertNotIn('+5543999991111', logs.text)

    def test_http_troca_numero_anula_optin_antigo(self):
        self.client.put('/avisos-whatsapp/admin/usuarios/2/numero',
                        headers=self.auth(1), json={'numero': '(43) 99999-1111'})
        self.client.put('/avisos-whatsapp/me', headers=self.auth(2),
                        json={'receber_alertas': True,
                              'numero_confirmado': '+5543999991111'})
        alteracao = self.client.put('/avisos-whatsapp/admin/usuarios/2/numero',
                                   headers=self.auth(1), json={'numero': '(43) 98888-2222'})
        self.assertEqual(alteracao.status_code, 200, alteracao.text)
        self.assertFalse(alteracao.json()['receber_alertas'])
        antigo = self.client.put('/avisos-whatsapp/me', headers=self.auth(2),
                  json={'receber_alertas': True,
                        'numero_confirmado': '+5543999991111'})
        self.assertEqual(antigo.status_code, 409)
        atual = self.client.get('/avisos-whatsapp/me', headers=self.auth(2))
        self.assertEqual(atual.status_code, 200)
        self.assertFalse(atual.json()['receber_alertas'])
        self.assertEqual(atual.json()['numero'], '+5543988882222')


if __name__ == '__main__':
    unittest.main()
