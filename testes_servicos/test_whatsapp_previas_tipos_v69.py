import os
import unittest
from unittest.mock import patch
import test_multiplos_participantes as base
import whatsapp_alertas as wa
from whatsapp_mensagens import preparar_previa_whatsapp

class PreviaTiposV69Teste(unittest.TestCase):
    def previa(self, **alt):
        d = dict(servico_id=2, titulo='Teste', mensagem_aviso='Nova tarefa para executar: Teste', frontend_public_url='http://127.0.0.1:5173')
        d.update(alt)
        return preparar_previa_whatsapp(**d)
    def test_explicito_prevalece(self):
        self.assertEqual(self.previa(tipo_evento='devolucao')['evento'], 'devolucao')
    def test_seis_tipos(self):
        for t in ('nova_tarefa', 'designacao_fiscal', 'pronto_fiscalizacao', 'devolucao', 'validacao_final', 'servico_validado'):
            r = self.previa(tipo_evento=t, mensagem_aviso='Texto alterado')
            self.assertEqual(r['evento'], t)
            self.assertIn('no aplicativo', r['mensagem'])
    def test_legado(self):
        self.assertEqual(self.previa(tipo_evento=None), self.previa())
        self.assertEqual(self.previa()['evento'], 'nova_tarefa')
    def test_tipo_invalido(self):
        for t in ('', 'desconhecido', True, 7, [], {}):
            self.assertEqual(self.previa(tipo_evento=t)['evento'], 'atualizacao')

class PreviaTiposIntegradaV69Teste(unittest.TestCase):
    def setUp(self):
        self.c = base.MultiplosParticipantesTeste()
        self.c.setUp()
        self.db = self.c.db
        wa.salvar_numero_admin(2, wa.NumeroAdministrado(numero='43999990002'), self.c.req(1), self.db)
        wa.salvar_preferencias(wa.PreferenciaEntrada(receber_alertas=True), self.c.req(2), self.db)
        s = self.c.novo(execs=[2], fisc=[])
        self.aviso = self.db.query(base.models.ServicoAviso).filter_by(servico_id=s['id'], usuario_id=2).one()
    def tearDown(self):
        self.c.tearDown()
    def consultar(self):
        antes = [(f.id, f.status) for f in self.db.query(base.models.FilaWhatsApp).all()]
        with patch.dict(os.environ, {'FRONTEND_PUBLIC_URL': 'http://127.0.0.1:5173'}):
            r = wa.listar_previas_fila(self.c.req(1), self.db)
        self.assertFalse(r['envios_ativos'])
        item = r['previa'][0]
        self.assertIs(item['diagnostico_preenvio']['envio_autorizado'], False)
        self.assertEqual(antes, [(f.id, f.status) for f in self.db.query(base.models.FilaWhatsApp).all()])
        return item
    def test_tipo_gravado(self):
        self.aviso.mensagem = 'Texto sem prefixo'
        self.db.commit()
        self.assertEqual(self.consultar()['evento'], 'nova_tarefa')
    def test_legado_preservado(self):
        self.aviso.tipo_evento = None
        self.db.commit()
        self.assertEqual(self.consultar()['evento'], 'nova_tarefa')
        self.db.refresh(self.aviso)
        self.assertIsNone(self.aviso.tipo_evento)
    def test_tipo_invalido_revisar(self):
        self.aviso.tipo_evento = 'desconhecido'
        self.db.commit()
        r = self.consultar()
        self.assertEqual(r['evento'], 'atualizacao')
        self.assertEqual(r['diagnostico_preenvio']['situacao'], 'revisar')
    def test_origem_incompativel(self):
        self.aviso.tipo_evento = 'devolucao'
        self.db.commit()
        self.assertEqual(self.consultar()['diagnostico_historico']['situacao'], 'revisar')
