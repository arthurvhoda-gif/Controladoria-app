"""V7.4: cadastro Web Push offline; SQLite ficticio, sem envio e sem rede."""
import base64
import os
import unittest
from unittest.mock import patch

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

if __name__ == '__main__':
    unittest.main()
