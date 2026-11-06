# -*- coding: utf-8 -*-
"""Inventário sem exposição de caminho ou dados pessoais."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inventariar_arquivos_v70 import resumir


class TestInventarioV70(unittest.TestCase):
    def test_agrega_presente_e_ausente_sem_divulgar_caminhos(self):
        with TemporaryDirectory() as tmp:
            existe = Path(tmp) / "foto-de-teste.png"
            existe.write_bytes(b"teste")
            r = resumir([str(existe), str(Path(tmp) / "perdido.pdf"), None, ""])
            self.assertEqual(r, {"total": 4, "presentes": 1, "ausentes": 1, "sem_caminho": 2})
            self.assertNotIn(str(existe), str(r))

    def test_sem_documentos_tem_contagem_zero(self):
        self.assertEqual(resumir([]), {"total": 0, "presentes": 0, "ausentes": 0, "sem_caminho": 0})

    def test_nao_le_arquivo_somente_existencia(self):
        vistos = []
        r = resumir(["arquivo-ficticio.pdf"], existe=lambda caminho: vistos.append(caminho) or True)
        self.assertEqual(vistos, ["arquivo-ficticio.pdf"])
        self.assertEqual(r["presentes"], 1)

    def test_excecao_na_consulta_nao_interrompe_inventario(self):
        def consulta(_):
            raise OSError("arquivo inacessivel")
        self.assertEqual(resumir(["arquivo"], existe=consulta)["ausentes"], 1)


if __name__ == "__main__":
    unittest.main()
