# -*- coding: utf-8 -*-
"""V7.0: teste de uploads sem Neon, Render, emails ou arquivos persistentes."""
import io
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import HTTPException, UploadFile

from arquivos_seguros import (
    nome_exibicao_seguro, salvar_upload_local, BLOCO_BYTES,
    MAX_ANEXO_SOLICITACAO, MAX_FOTO_CHECKLIST,
)


class ArquivosSegurosV70(unittest.TestCase):
    def test_nome_visivel_preserva_texto_sem_diretorios(self):
        self.assertEqual(nome_exibicao_seguro("C:\\temporario\\Orçamento 2026.pdf"), "Orçamento 2026.pdf")
        self.assertEqual(nome_exibicao_seguro("../../relatorio.pdf"), "relatorio.pdf")
        self.assertEqual(nome_exibicao_seguro("..\\..\\segredo.txt"), "segredo.txt")
        self.assertEqual(nome_exibicao_seguro("bom\x00nome.pdf"), "bomnome.pdf")

    def test_nomes_vazios_bloqueados(self):
        for nome in (None, "", ".", "..", "/"):
            with self.subTest(nome=nome), self.assertRaises(HTTPException):
                nome_exibicao_seguro(nome)

    def test_upload_nome_e_path_nao_dependem_do_cliente(self):
        with tempfile.TemporaryDirectory() as pasta:
            upload = UploadFile(filename="../../dados-confidenciais.pdf", file=io.BytesIO(b"%PDF-1.7\nTeste"))
            nome, caminho = salvar_upload_local(upload, pasta, "sol_9", 100)
            self.assertEqual(nome, "dados-confidenciais.pdf")
            self.assertEqual(Path(caminho).parent, Path(pasta).resolve())
            self.assertTrue(Path(caminho).name.startswith("sol_9_"))
            self.assertNotIn("confidenciais", Path(caminho).name)
            self.assertEqual(Path(caminho).read_bytes(), b"%PDF-1.7\nTeste")

    def test_upload_com_limite_apaga_arquivo_parcial(self):
        with tempfile.TemporaryDirectory() as pasta:
            upload = UploadFile(filename="grande.pdf", file=io.BytesIO(b"x" * (BLOCO_BYTES + 10)))
            with self.assertRaises(HTTPException) as erro:
                salvar_upload_local(upload, pasta, "sol_9", BLOCO_BYTES)
            self.assertEqual(erro.exception.status_code, 413)
            self.assertEqual(list(Path(pasta).iterdir()), [])

    def test_upload_vazio_sem_residuo(self):
        with tempfile.TemporaryDirectory() as pasta:
            upload = UploadFile(filename="foto.png", file=io.BytesIO())
            with self.assertRaises(HTTPException) as erro:
                salvar_upload_local(upload, pasta, "chk_4", 10)
            self.assertEqual(erro.exception.status_code, 400)
            self.assertEqual(list(Path(pasta).iterdir()), [])

    def test_prefixo_apenas_interno(self):
        with tempfile.TemporaryDirectory() as pasta:
            upload = UploadFile(filename="ok.pdf", file=io.BytesIO(b"teste"))
            with self.assertRaises(ValueError):
                salvar_upload_local(upload, pasta, "../../malicioso", 10)

    def test_limites_conforme_entradas_aceitas(self):
        self.assertEqual(MAX_ANEXO_SOLICITACAO, 10 * 1024 * 1024)
        self.assertEqual(MAX_FOTO_CHECKLIST, 20 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
