# -*- coding: utf-8 -*-
"""Homologacao V7.2: adaptador real das rotas, com Google simulado.
Nenhum acesso a Drive, Neon, Render ou e-mails neste teste.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException, UploadFile
import test_servicos as fixture
import main as api
import armazenamento_drive_v72 as drive

models = fixture.models


class IntegracaoV72(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome='Condominio A'),
            models.Condominio(id=2, nome='Condominio B'),
            models.Usuario(id=1, nome='Gestor', email='gestor@teste.local', senha='x', perfil='Controladoria'),
            models.Usuario(id=2, nome='Zelador A', email='zelador@teste.local', senha='x', perfil='Checklist', condominio_id=1),
            models.Usuario(id=3, nome='Zelador B', email='outro@teste.local', senha='x', perfil='Checklist', condominio_id=2),
            models.Usuario(id=4, nome='Outro solicitante', email='solicitante@teste.local', senha='x', perfil='Solicitante'),
            models.Solicitacao(id=10, numero='SOL-0010', condominio='Condominio A', condominio_id=1,
                               categoria='Manutencao', fornecedor='Ficticio', descricao='Teste',
                               solicitante='Gestor', solicitante_id=1),
            models.ChecklistItem(id=20, condominio='Condominio A', condominio_id=1,
                                 titulo='Testar portao', frequencia='Diaria'),
        ])
        self.db.commit()
        self.tmp = tempfile.TemporaryDirectory()
        self.fs = {}
        self.calls = []
        self.patches = [
            patch.dict(os.environ, {'HAIZE_STORAGE_MODE': 'drive_v72'}, clear=False),
            patch.object(api, 'UPLOAD_DIR', self.tmp.name),
            patch.object(api, 'FOTOS_CHECKLIST_DIR', str(Path(self.tmp.name) / 'checklists')),
            patch.object(api, 'ENVIO_AUTOMATICO_CHECKLIST', False),
            patch.object(drive, '_enviar', side_effect=self.fake_google),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.db.close()
        self.tmp.cleanup()

    def req(self, uid, papel, cid=None):
        return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid,
            auth_user_role=papel, auth_user_name=f'Teste {uid}', auth_condominio_id=cid))

    def fake_google(self, dados):
        self.calls.append(dados['op'])
        chave = dados['key']
        if dados['op'] == 'put':
            bruto = base64.b64decode(dados['data'])
            if len(bruto) != dados['size'] or hashlib.sha256(bruto).hexdigest() != dados['sha256']:
                raise HTTPException(503)
            if chave in self.fs and self.fs[chave] != bruto:
                raise HTTPException(503)
            repetido = chave in self.fs
            self.fs[chave] = bruto
            return {'ok': True, 'key': chave, 'sha256': dados['sha256'],
                    'size': len(bruto), 'repeated': repetido}
        if dados['op'] == 'get':
            if chave not in self.fs:
                raise HTTPException(404)
            bruto = self.fs[chave]
            return {'ok': True, 'key': chave, 'sha256': hashlib.sha256(bruto).hexdigest(),
                    'size': len(bruto), 'data': base64.b64encode(bruto).decode('ascii')}
        raise AssertionError('Operacao desconhecida')

    def test_compra_roundtrip_e_permissao_antes_do_drive(self):
        conteudo = b'%PDF-1.7\nDocumento ficticio'
        anexo = api.upload_anexo_solicitacao(
            10, self.req(1, 'Controladoria'),
            UploadFile(filename='../../evidencia.pdf', file=io.BytesIO(conteudo)),
            'Orcamento', 'Gestor', self.db)
        self.assertRegex(anexo.caminho, r'^drive-v72:[a-f0-9]{32}$')
        self.assertFalse(any(Path(self.tmp.name).iterdir()))
        retorno = api.download_anexo(anexo.id, self.req(1, 'Controladoria'), self.db)
        self.assertEqual(retorno.body, conteudo)
        self.assertIn('attachment', retorno.headers['content-disposition'])
        qtd = len(self.calls)
        with self.assertRaises(HTTPException) as erro:
            api.download_anexo(anexo.id, self.req(4, 'Solicitante'), self.db)
        self.assertEqual(erro.exception.status_code, 403)
        self.assertEqual(qtd, len(self.calls))
        self.assertEqual(self.db.query(models.HistoricoSolicitacao).count(), 1)

    def test_checklist_roundtrip_e_isolamento_condominio(self):
        bruto = b'\x89PNG\r\n\x1a\n' + b'foto-ficticia'
        api.executar_checklist(20, self.req(2, 'Checklist', 1), BackgroundTasks(),
             responsavel='Zelador', status_conformidade='Nao Conforme',
             observacao='Testes', foto=UploadFile(filename='fachada.png', file=io.BytesIO(bruto)), db=self.db)
        exe = self.db.query(models.ChecklistExecucao).filter_by(item_id=20).one()
        self.assertTrue(exe.caminho_foto.startswith(drive.PREFIXO))
        res = api.ver_foto_execucao(exe.id, self.req(2, 'Checklist', 1), self.db)
        self.assertEqual(res.body, bruto)
        self.assertEqual(res.media_type, 'image/png')
        qtd = len(self.calls)
        with self.assertRaises(HTTPException) as erro:
            api.ver_foto_execucao(exe.id, self.req(3, 'Checklist', 2), self.db)
        self.assertEqual(erro.exception.status_code, 404)
        self.assertEqual(qtd, len(self.calls))

    def test_arquivos_legados_permanecem_legiveis(self):
        caminho = Path(self.tmp.name) / 'legado.pdf'
        caminho.write_bytes(b'PDF LEGADO')
        anexo = models.Anexo(solicitacao_id=10, nome_arquivo='legado.pdf', caminho=str(caminho),
                             tipo='Orcamento', responsavel='Gestor')
        self.db.add(anexo)
        self.db.commit()
        resposta = api.download_anexo(anexo.id, self.req(1, 'Controladoria'), self.db)
        self.assertEqual(resposta.path, str(caminho))
        self.assertEqual(self.calls, [])

    def test_falha_google_nao_grava_registro_falso(self):
        with patch.object(drive, '_enviar', side_effect=HTTPException(503)):
            with self.assertRaises(HTTPException) as erro:
                api.upload_anexo_solicitacao(10, self.req(1, 'Controladoria'),
                   UploadFile(filename='novo.pdf', file=io.BytesIO(b'conteudo')),
                   'Orcamento', 'Gestor', self.db)
        self.assertEqual(erro.exception.status_code, 503)
        self.assertEqual(self.db.query(models.Anexo).count(), 0)

    def test_retorno_corrompido_nao_entregue(self):
        with patch.object(drive, '_enviar', return_value={'key': 'a'*32, 'size': 4,
                           'sha256': '0'*64, 'data': 'YQ==', 'ok': True}):
            with self.assertRaises(HTTPException) as erro:
                drive._baixar_drive('drive-v72:' + 'a'*32)
        self.assertEqual(erro.exception.status_code, 503)

    def test_limite_e_modo_errado_fecham_acesso(self):
        with self.assertRaises(HTTPException) as erro:
            drive.salvar_upload_haize(UploadFile(filename='foto.jpg', file=io.BytesIO(b'xxxx')),
                                     self.tmp.name, 'foto', 3)
        self.assertEqual(erro.exception.status_code, 413)
        with patch.dict(os.environ, {'HAIZE_STORAGE_MODE':'errado'}):
            with self.assertRaises(HTTPException) as erro:
                drive.salvar_upload_haize(UploadFile(filename='foto.jpg', file=io.BytesIO(b'xx')),
                                         self.tmp.name, 'foto', 100)
        self.assertEqual(erro.exception.status_code, 503)


class ProtocoloV72(unittest.TestCase):
    def test_hmac_usa_payload_exato_e_nao_expoe_segredo(self):
        segredo = 'a'*64
        url = 'https://script.google.com/macros/s/ABCdef-123_/exec'
        class FakeResposta:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limite): return b'{"ok":true,"version":1}'
        class FakeOpener:
            def open(self, req, timeout):
                e = json.loads(req.data.decode('utf-8'))
                self_o.assertEqual(e['signature'], hmac.new(segredo.encode(), e['payload'].encode(), hashlib.sha256).hexdigest())
                self_o.assertEqual(json.loads(e['payload'])['op'], 'ping')
                self_o.assertNotIn(segredo, req.full_url)
                return FakeResposta()
        self_o = self
        with patch.dict(os.environ, {'HAIZE_STORAGE_URL':url, 'HAIZE_STORAGE_SECRET':segredo}):
            with patch.object(drive.urlrequest, 'build_opener', return_value=FakeOpener()):
                self.assertEqual(drive._enviar({'op': 'ping'})['ok'], True)

    def test_url_insegura_recusada_antes_de_requisicao(self):
        with patch.dict(os.environ, {'HAIZE_STORAGE_URL':'https://example.org/macros/s/x/exec',
                                     'HAIZE_STORAGE_SECRET':'a'*64}):
            with self.assertRaises(HTTPException) as erro:
                drive._enviar({'op':'ping'})
        self.assertEqual(erro.exception.status_code, 503)


if __name__ == '__main__':
    unittest.main()
