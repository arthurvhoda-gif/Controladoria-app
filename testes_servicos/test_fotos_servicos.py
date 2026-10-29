"""Teste local de foto no SQLite: acesso, persistência, validação e limite.
Nenhum acesso ao Neon/Render; dados falsos apenas.
"""
import asyncio
from io import BytesIO
from datetime import date, timedelta
import unittest
from PIL import Image
from fastapi import HTTPException, UploadFile
import test_servicos as fixture
api, models = fixture.api, fixture.models

class FotoSeguranca(unittest.TestCase):
    def setUp(self):
        self.base = fixture.ServicosTeste()
        self.base.setUp()
        self.db = self.base.db
        self.servico = self.base.criar()
    def tearDown(self):
        self.base.tearDown()
    def imagem(self, formato='PNG'):
        b = BytesIO()
        Image.new('RGB', (320,240), (20,80,150)).save(b, format=formato)
        return b.getvalue()
    def envia(self, uid, dados=None, nome='foto.png', tipo='image/png', etapa='antes'):
        if dados is None: dados = self.imagem()
        up = UploadFile(filename=nome, file=BytesIO(dados), headers={'content-type':tipo})
        return asyncio.run(api.adicionar_foto(self.servico['id'], self.base.req(uid),
                              foto=up, etapa=etapa, legenda='Antes do reparo', db=self.db))

    def test_envio_e_persistencia_e_historico(self):
        r = self.envia(2)
        self.assertEqual(r['etapa'], 'antes')
        self.assertEqual(len(api.listar_fotos(self.servico['id'],self.base.req(1),self.db)), 1)
        resposta = api.visualizar_foto(self.servico['id'],r['id'],self.base.req(2),self.db)
        self.assertEqual(resposta.media_type,'image/webp')
        self.assertTrue(resposta.body.startswith(b'RIFF'))
        self.assertEqual(len(api.historico(self.servico['id'],self.base.req(1),self.db)), 2)

    def test_outro_condominio_nao_ve_nem_envia(self):
        foto = self.envia(2)
        for fn in (lambda: self.envia(3),
                   lambda: api.listar_fotos(self.servico['id'], self.base.req(3), self.db),
                   lambda: api.visualizar_foto(self.servico['id'],foto['id'],self.base.req(3),self.db)):
            with self.assertRaises(HTTPException) as cm: fn()
            self.assertEqual(cm.exception.status_code, 404)

    def test_bloqueia_imagem_falsa_e_etapa_invalida(self):
        with self.assertRaises(HTTPException) as cm:
            self.envia(2,dados=b'nao e uma imagem')
        self.assertEqual(cm.exception.status_code,415)
        with self.assertRaises(HTTPException) as cm:
            self.envia(2,etapa='qualquer')
        self.assertEqual(cm.exception.status_code,400)

    def test_bloqueia_foto_apos_conclusao(self):
        s=self.servico
        self.base.req(2)
        for a,uid,msg in [('confirmar',2,''),('iniciar',2,''),('concluir',2,'Minha etapa concluída integralmente.'),('validar',1,'')]:
            api.atualizar(s['id'],api.ServicoAcao(acao=a,observacao=msg),self.base.req(uid),self.db)
        with self.assertRaises(HTTPException) as cm: self.envia(2)
        self.assertEqual(cm.exception.status_code,409)

    def test_limite_de_arquivo(self):
        with self.assertRaises(HTTPException) as cm: self.envia(2, dados=b'x' * (4 * 1024 * 1024 + 1))
        self.assertEqual(cm.exception.status_code,413)

if __name__=='__main__': unittest.main()
