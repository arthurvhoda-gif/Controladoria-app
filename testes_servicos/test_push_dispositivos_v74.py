"""V7.4: cadastro Web Push offline; SQLite ficticio, sem envio e sem rede."""
import base64
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import push_automatico as auto

from fastapi import HTTPException
import test_multiplos_participantes as base
import push_api as push

def url_key(bytes_):
    return base64.urlsafe_b64encode(bytes_).decode('ascii').rstrip('=')

CHAVE_PUBLICA = url_key(b'\x04' + bytes([2] * 64))
P256DH = url_key(b'\x04' + bytes([3] * 64))
AUTH = url_key(bytes([4] * 16))


class PushDispositivosV74(unittest.TestCase):
    def setUp(self):
        self.fixture = base.MultiplosParticipantesTeste()
        self.fixture.setUp()
        self.db = self.fixture.db
        self.ambiente = patch.dict(os.environ, {'VAPID_PUBLIC_KEY': CHAVE_PUBLICA})
        self.ambiente.start()

    def tearDown(self):
        self.ambiente.stop()
        self.fixture.tearDown()

    def req(self, uid):
        return self.fixture.req(uid)

    def dados(self, n=1, host='fcm.googleapis.com'):
        return push.RegistroPush(
            endpoint=f'https://{host}/fcm/send/subscricao-ficticia-{n:04d}',
            keys=push.ChavesPush(p256dh=P256DH, auth=AUTH),
        )

    def test_rota_config_requer_configuracao_correta_e_indica_automaticos(self):
        # A rota real precisa apontar ao endpoint autenticado, nao ao helper interno.
        rotas = [rota for rota in push.router.routes
                 if getattr(rota, 'path', None) == '/push/config'
                 and 'GET' in getattr(rota, 'methods', set())]
        self.assertEqual(len(rotas), 1)
        self.assertIs(rotas[0].endpoint, push.configuracao)
        self.assertFalse(push.configuracao(self.req(2), self.db)['envios_ativos'])
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'true',
            'PUSH_TESTS_ENABLED': 'true',
            'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32)),
        }):
            configuracao = push.configuracao(self.req(2), self.db)
            self.assertTrue(configuracao['envios_ativos'])
            self.assertTrue(configuracao['registro_disponivel'])
            self.assertTrue(configuracao['teste_disponivel'])
        with patch.dict(os.environ, {'PUSH_AUTO_DISPATCH_ENABLED': 'false'}):
            self.assertFalse(push.configuracao(self.req(2), self.db)['envios_ativos'])

    def test_registro_e_listagem_sem_expor_token(self):
        self.assertTrue(push.configuracao(self.req(2), self.db)['registro_disponivel'])
        self.assertFalse(push.configuracao(self.req(2), self.db)['envios_ativos'])
        self.assertTrue(push.registrar(self.dados(), self.req(2), self.db)['registrado'])
        self.assertEqual(push.meus_dispositivos(self.req(2), self.db)['total'], 1)
        self.assertNotIn('endpoint', push.meus_dispositivos(self.req(2), self.db))
        self.assertEqual(push.meus_dispositivos(self.req(3), self.db)['total'], 0)
        # Idempotente, inclusive nas atualizacoes de assinatura.
        push.registrar(self.dados(), self.req(2), self.db)
        self.assertEqual(push.meus_dispositivos(self.req(2), self.db)['total'], 1)

    def test_troca_de_conta_reassocia_sem_vazar_avisos(self):
        d = self.dados()
        push.registrar(d, self.req(2), self.db)
        push.registrar(d, self.req(3), self.db)
        self.assertEqual(push.meus_dispositivos(self.req(2), self.db)['total'], 0)
        self.assertEqual(push.meus_dispositivos(self.req(3), self.db)['total'], 1)
        # A conta antiga nao pode excluir o aparelho de outra conta.
        push.revogar(push.RemocaoPush(endpoint=d.endpoint), self.req(2), self.db)
        self.assertEqual(push.meus_dispositivos(self.req(3), self.db)['total'], 1)
        push.revogar(push.RemocaoPush(endpoint=d.endpoint), self.req(3), self.db)
        self.assertEqual(push.meus_dispositivos(self.req(3), self.db)['total'], 0)

    def test_destinos_internos_e_chaves_invalidas_negados(self):
        for endpoint in [
            'http://fcm.googleapis.com/fcm/send/fake-token',
            'https://127.0.0.1/push/subscription',
            'https://example.com/fcm/send/fake-token',
            'https://fcm.googleapis.com.evil.example/fcm/send/fake',
            'https://fcm.googleapis.com:8443/fcm/send/fake-token',
        ]:
            with self.subTest(endpoint=endpoint), self.assertRaises(HTTPException) as cm:
                push.registrar(push.RegistroPush(endpoint=endpoint, keys=self.dados().keys), self.req(2), self.db)
            self.assertEqual(cm.exception.status_code, 422)
        chaves = push.ChavesPush(p256dh=url_key(bytes([3] * 65)), auth=AUTH)
        with self.assertRaises(HTTPException) as cm:
            push.registrar(push.RegistroPush(endpoint=self.dados().endpoint, keys=chaves), self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 422)

    def test_limite_5_aparelhos(self):
        for n in range(5):
            push.registrar(self.dados(n), self.req(2), self.db)
        with self.assertRaises(HTTPException) as cm:
            push.registrar(self.dados(10), self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertEqual(push.meus_dispositivos(self.req(2), self.db)['total'], 5)

    def test_sem_chave_o_registro_permanece_desativado(self):
        with patch.dict(os.environ, {'VAPID_PUBLIC_KEY': ''}):
            self.assertFalse(push.configuracao(self.req(1), self.db)['registro_disponivel'])
            with self.assertRaises(HTTPException) as cm:
                push.registrar(self.dados(), self.req(2), self.db)
            self.assertEqual(cm.exception.status_code, 503)
        self.assertEqual(push.meus_dispositivos(self.req(2), self.db)['total'], 0)


    def test_teste_desativado_nao_atinge_a_rede(self):
        d = self.dados()
        push.registrar(d, self.req(2), self.db)
        with patch('push_api.webpush') as envio:
            with self.assertRaises(HTTPException) as cm:
                push.enviar_teste_manual(self.req(2), self.db)
        self.assertEqual(cm.exception.status_code, 503)
        envio.assert_not_called()

    def test_envio_so_propria_conta_limite_e_payload(self):
        push.registrar(self.dados(1), self.req(2), self.db)
        push.registrar(self.dados(2, host='web.push.apple.com'), self.req(2), self.db)
        push.registrar(self.dados(3), self.req(3), self.db)
        with patch.dict(os.environ, {
            'PUSH_TESTS_ENABLED': 'true',
            'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32)),
        }), patch('push_api.webpush') as envio:
            self.assertTrue(push.configuracao(self.req(2), self.db)['teste_disponivel'])
            resposta = push.enviar_teste_manual(self.req(2), self.db)
            self.assertEqual(resposta['aceitos_pelo_provedor'], 2)
            self.assertFalse(resposta['entrega_no_celular_confirmada'])
            self.assertEqual(envio.call_count, 2)
            argumentos = [c.kwargs for c in envio.call_args_list]
            self.assertTrue(all('haize-teste-v1' in a['data'] for a in argumentos))
            self.assertTrue(all('subscricao-ficticia-0003' not in a['subscription_info']['endpoint'] for a in argumentos))
            with self.assertRaises(HTTPException) as cm:
                push.enviar_teste_manual(self.req(2), self.db)
            self.assertEqual(cm.exception.status_code, 429)
            self.assertEqual(envio.call_count, 2)

    def test_sem_dispositivos_nao_consume_cota(self):
        with patch.dict(os.environ, {
            'PUSH_TESTS_ENABLED': 'true', 'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32))
        }), patch('push_api.webpush') as envio:
            with self.assertRaises(HTTPException) as cm:
                push.enviar_teste_manual(self.req(6), self.db)
            self.assertEqual(cm.exception.status_code, 409)
            self.assertEqual(self.db.query(base.models.PushTesteControle).count(), 0)
            envio.assert_not_called()


    def test_fila_automatica_totalmente_desligada_sem_flags(self):
        from datetime import date, timedelta
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(), self.req(2), self.db)
        criar(ServicoNovo(
            condominio_id=1, executores_ids=[2], titulo='Tarefa de exemplo',
            descricao='Verificar portas do elevador ficticio.',
            prazo=date.today() + timedelta(days=2),
        ), self.req(1), self.db)
        self.assertEqual(self.db.query(base.models.PushAvisoFila).count(), 0)
        with patch('push_automatico.webpush') as sender:
            self.assertFalse(auto.processar_fila()['ativo'])
            sender.assert_not_called()

    def test_enfileira_transacional_por_dispositivo_sem_despachar(self):
        from datetime import date, timedelta
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)
        push.registrar(self.dados(2), self.req(2), self.db)
        push.registrar(self.dados(3), self.req(3), self.db)
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'false',
        }), patch('push_automatico.webpush') as sender:
            s = criar(ServicoNovo(
                condominio_id=1, executores_ids=[2], titulo='Tarefa de exemplo',
                descricao='Revisao ficticia do elevador.',
                prazo=date.today() + timedelta(days=2),
            ), self.req(1), self.db)
            fila = self.db.query(base.models.PushAvisoFila).all()
            self.assertEqual(len(fila), 2)
            self.assertTrue(all(x.usuario_id == 2 for x in fila))
            self.assertTrue(all(x.servico_id == s['id'] for x in fila))
            self.assertTrue(all(x.evento_id is not None for x in fila))
            self.assertFalse(auto.processar_fila()['ativo'])
            sender.assert_not_called()

    def test_despacho_respeita_condominio_e_transferencia_do_dispositivo(self):
        from datetime import date, timedelta
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'false',
        }):
            criar(ServicoNovo(
                condominio_id=1, executores_ids=[2], titulo='Tarefa de exemplo',
                descricao='Revisao ficticia do elevador.',
                prazo=date.today() + timedelta(days=2),
            ), self.req(1), self.db)
        item = self.db.query(base.models.PushAvisoFila).first()
        self.assertEqual(item.usuario_id, 2)
        self.assertIsNotNone(auto._pode_despachar(self.db, item))
        self.db.get(base.models.Usuario, 2).condominio_id = 2
        self.db.commit()
        self.assertIsNone(auto._pode_despachar(self.db, item))
        self.db.get(base.models.Usuario, 2).condominio_id = 1
        self.db.commit()
        push.registrar(self.dados(1), self.req(3), self.db)
        self.assertIsNone(auto._pode_despachar(self.db, item))

    def test_falha_em_criacao_reverte_fila_e_aviso(self):
        from datetime import date, timedelta
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)
        with patch.dict(os.environ, {'PUSH_AUTO_QUEUE_ENABLED': 'true'}):
            with patch.object(self.db, 'commit', side_effect=RuntimeError('falha transacional ficticia')):
                with self.assertRaises(RuntimeError):
                    criar(ServicoNovo(
                        condominio_id=1, executores_ids=[2], titulo='Tarefa ficticia',
                        descricao='Teste de rollback da fila.',
                        prazo=date.today() + timedelta(days=2),
                    ), self.req(1), self.db)
            self.db.rollback()
        self.assertEqual(self.db.query(base.models.PushAvisoFila).count(), 0)


    def test_despacho_automatico_de_tarefa_para_executor_e_fiscal_sem_beta(self):
        from datetime import date, timedelta
        import json
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)  # Android Alfa
        push.registrar(self.dados(2, host='web.push.apple.com'), self.req(1), self.db)  # iPhone Gestora
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'false',
            'PUSH_TESTS_ENABLED': 'true',
            'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32)),
        }):
            tarefa = criar(ServicoNovo(
                condominio_id=1, executores_ids=[2], fiscalizadores_ids=[1],
                titulo='Inspecionar portao de testes',
                descricao='Validacao de evento de tarefa no ambiente ficticio.',
                prazo=date.today() + timedelta(days=2),
            ), self.req(1), self.db)
            self.assertEqual(self.db.query(base.models.PushAvisoFila).count(), 2)
            with patch.dict(os.environ, {'PUSH_AUTO_DISPATCH_ENABLED': 'true'}):
                with patch.object(auto, 'SessionLocal', base.fixture.stub.SessionLocal), \
                     patch('push_automatico.webpush') as enviar:
                    resultado = auto.processar_fila()
                    self.assertEqual(resultado['processados'], 2)
                    self.assertEqual(resultado['aceitos'], 2)
                    self.assertEqual(enviar.call_count, 2)
                    payloads = [json.loads(x.kwargs['data']) for x in enviar.call_args_list]
                    self.assertEqual({x['tipo'] for x in payloads}, {'haize-servico-v1'})
                    self.assertEqual({x['servico_id'] for x in payloads}, {tarefa['id']})
                    self.assertEqual(len({x['evento_id'] for x in payloads}), 1)
                    destinos = [x.kwargs['subscription_info']['endpoint'] for x in enviar.call_args_list]
                    self.assertTrue(any('fcm.googleapis.com' in x for x in destinos))
                    self.assertTrue(any('web.push.apple.com' in x for x in destinos))
                    self.assertTrue(all('subscricao-ficticia-0003' not in x for x in destinos))
                    self.assertEqual(auto.processar_fila()['processados'], 0)
                    self.assertEqual(enviar.call_count, 2)
            self.assertEqual({x.status for x in self.db.query(base.models.PushAvisoFila).all()}, {'aceito'})

    def test_despacho_descarta_aviso_se_usuario_mudou_de_condominio(self):
        from datetime import date, timedelta
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'false',
            'PUSH_TESTS_ENABLED': 'true',
            'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32)),
        }):
            criar(ServicoNovo(
                condominio_id=1, executores_ids=[2],
                titulo='Inspecionar portao de testes',
                descricao='Validacao de evento de tarefa no ambiente ficticio.',
                prazo=date.today() + timedelta(days=2),
            ), self.req(1), self.db)
            self.db.get(base.models.Usuario, 2).condominio_id = 2
            self.db.commit()
            with patch.dict(os.environ, {'PUSH_AUTO_DISPATCH_ENABLED': 'true'}):
                with patch.object(auto, 'SessionLocal', base.fixture.stub.SessionLocal), \
                     patch('push_automatico.webpush') as enviar:
                    resultado = auto.processar_fila()
                    self.assertEqual(resultado['processados'], 1)
                    self.assertEqual(resultado['descartados'], 1)
                    enviar.assert_not_called()
            self.assertEqual(self.db.query(base.models.PushAvisoFila).first().status, 'descartado')

    def test_despacho_falha_controlada_sem_duplicar_e_reenvia_apos_intervalo(self):
        from datetime import date, timedelta, datetime, timezone
        from servicos_api import ServicoNovo, criar
        push.registrar(self.dados(1), self.req(2), self.db)
        with patch.dict(os.environ, {
            'PUSH_AUTO_QUEUE_ENABLED': 'true',
            'PUSH_AUTO_DISPATCH_ENABLED': 'false',
            'PUSH_TESTS_ENABLED': 'true',
            'VAPID_PRIVATE_KEY': url_key(bytes([9] * 32)),
        }):
            criar(ServicoNovo(
                condominio_id=1, executores_ids=[2],
                titulo='Inspecionar portao de testes',
                descricao='Validacao de evento de tarefa no ambiente ficticio.',
                prazo=date.today() + timedelta(days=2),
            ), self.req(1), self.db)
            with patch.dict(os.environ, {'PUSH_AUTO_DISPATCH_ENABLED': 'true'}):
                with patch.object(auto, 'SessionLocal', base.fixture.stub.SessionLocal), \
                     patch('push_automatico.webpush', side_effect=TimeoutError('ficticio')):
                    resultado = auto.processar_fila()
                    self.assertEqual(resultado['falhas'], 1)
                    self.assertEqual(auto.processar_fila()['processados'], 0)
                item = self.db.query(base.models.PushAvisoFila).first()
                self.assertEqual(item.tentativas, 1)
                item.atualizado_em = datetime(2020, 1, 1, tzinfo=timezone.utc)
                self.db.commit()
                with patch.object(auto, 'SessionLocal', base.fixture.stub.SessionLocal), \
                     patch('push_automatico.webpush') as enviar:
                    resultado = auto.processar_fila()
                    self.assertEqual(resultado['aceitos'], 1)
                    self.assertEqual(enviar.call_count, 1)

if __name__ == '__main__':
    unittest.main()
