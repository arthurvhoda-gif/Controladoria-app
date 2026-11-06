# -*- coding: utf-8 -*-
"""V7.0 - Integração dos uploads reais sem banco externo.

Exercita handlers FastAPI diretamente com SQLite em memória, arquivos
temporários e fila de e-mail desativada. Não lê Neon/Render/GAS.
"""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException, UploadFile

import test_servicos as fixture
import main as api

models = fixture.models


class UploadsEndpointsV70(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(fixture.stub.engine)
        models.Base.metadata.create_all(fixture.stub.engine)
        self.db = fixture.stub.SessionLocal()
        self.db.add_all([
            models.Condominio(id=1, nome="Condomínio Fictício A"),
            models.Condominio(id=2, nome="Condomínio Fictício B"),
            models.Usuario(id=1, nome="Controladoria", email="gestor@teste.local", senha="x", perfil="Controladoria"),
            models.Usuario(id=2, nome="Zelador", email="zelador@teste.local", senha="x", perfil="Checklist", condominio_id=1),
            models.Usuario(id=3, nome="Outro", email="outro@teste.local", senha="x", perfil="Checklist", condominio_id=2),
            models.Solicitacao(
                id=10, numero="SOL-0010", condominio="Condomínio Fictício A",
                condominio_id=1, categoria="Manutenção", fornecedor="Fictício",
                descricao="Pedido de teste", solicitante="Controladoria", solicitante_id=1,
            ),
            models.ChecklistItem(id=20, condominio="Condomínio Fictício A", condominio_id=1,
                                 titulo="Testar portão", frequencia="Diária"),
        ])
        self.db.commit()
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(api, "UPLOAD_DIR", self.temp.name),
            patch.object(api, "FOTOS_CHECKLIST_DIR", str(Path(self.temp.name) / "checklists")),
            patch.object(api, "ENVIO_AUTOMATICO_CHECKLIST", False),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.db.close()
        self.temp.cleanup()

    def req(self, uid=1, perfil="Controladoria", condominio_id=None):
        return SimpleNamespace(state=SimpleNamespace(
            auth_user_id=uid,
            auth_user_role=perfil,
            auth_user_name=f"Usuário fictício {uid}",
            auth_condominio_id=condominio_id,
        ))

    def enviar_anexo(self, nome, bytes_pdf=b"%PDF-1.7\nDocumento fictício", request=None):
        arq = UploadFile(filename=nome, file=io.BytesIO(bytes_pdf))
        return api.upload_anexo_solicitacao(
            10, request or self.req(), arq, "Orçamento", "Usuário", self.db
        )

    def test_anexo_real_salvo_e_baixavel_com_nome_legivel(self):
        anexo = self.enviar_anexo("../../../../pedido.pdf")
        caminho = Path(anexo.caminho)
        self.assertEqual(anexo.nome_arquivo, "pedido.pdf")
        self.assertEqual(caminho.parent, Path(self.temp.name).resolve())
        self.assertNotIn("pedido", caminho.name)
        self.assertEqual(caminho.read_bytes(), b"%PDF-1.7\nDocumento fictício")
        baixado = api.download_anexo(anexo.id, self.req(), self.db)
        self.assertEqual(baixado.filename, "pedido.pdf")
        self.assertTrue(Path(baixado.path).is_file())
        self.assertEqual(self.db.query(models.HistoricoSolicitacao).count(), 1)

    def test_anexo_negado_para_solicitante_de_outra_conta(self):
        with self.assertRaises(HTTPException) as erro:
            self.enviar_anexo("documento.pdf", request=self.req(9, "Solicitante"))
        self.assertEqual(erro.exception.status_code, 403)
        self.assertEqual(self.db.query(models.Anexo).count(), 0)

    def test_foto_real_preserva_execucao_e_isolamento_por_condominio(self):
        entrada = UploadFile(filename="..\\..\\fachada.png", file=io.BytesIO(b"foto de teste"))
        retorno = api.executar_checklist(
            20, self.req(2, "Checklist", 1), BackgroundTasks(),
            responsavel="Zelador", status_conformidade="Não Conforme",
            observacao="Foto usada apenas no teste", foto=entrada, db=self.db
        )
        self.assertEqual(retorno["envio_relatorio"], "desativado")
        registro = self.db.query(models.ChecklistExecucao).filter_by(item_id=20).one()
        self.assertEqual(registro.nome_foto, "fachada.png")
        self.assertEqual(Path(registro.caminho_foto).parent, (Path(self.temp.name) / "checklists").resolve())
        self.assertEqual(Path(registro.caminho_foto).read_bytes(), b"foto de teste")
        foto = api.ver_foto_execucao(registro.id, self.req(2, "Checklist", 1), self.db)
        self.assertTrue(Path(foto.path).is_file())
        with self.assertRaises(HTTPException) as erro:
            api.ver_foto_execucao(registro.id, self.req(3, "Checklist", 2), self.db)
        self.assertEqual(erro.exception.status_code, 404)

    def test_foto_condominio_diferente_nao_grava(self):
        entrada = UploadFile(filename="foto.jpg", file=io.BytesIO(b"teste"))
        with self.assertRaises(HTTPException) as erro:
            api.executar_checklist(
                20, self.req(3, "Checklist", 2), BackgroundTasks(), responsavel="Outro",
                status_conformidade="Conforme", foto=entrada, db=self.db
            )
        self.assertEqual(erro.exception.status_code, 404)
        self.assertEqual(self.db.query(models.ChecklistExecucao).count(), 0)

    def test_legado_com_caminho_antigo_continua_baixavel(self):
        caminho = Path(self.temp.name) / "10_abcd_documento-antigo.pdf"
        caminho.write_bytes(b"%PDF-1.4\nlegado")
        antigo = models.Anexo(
            solicitacao_id=10, nome_arquivo="documento-antigo.pdf", caminho=str(caminho),
            tipo="Orçamento", responsavel="Teste"
        )
        self.db.add(antigo)
        self.db.commit()
        retorno = api.download_anexo(antigo.id, self.req(), self.db)
        self.assertEqual(retorno.filename, "documento-antigo.pdf")
        self.assertEqual(retorno.path, str(caminho))
        self.assertEqual(caminho.read_bytes(), b"%PDF-1.4\nlegado")


if __name__ == "__main__":
    unittest.main()
