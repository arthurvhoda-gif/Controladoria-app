"""Testes V7.6: resumo agregado sem expor lancamentos individuais."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal

from test_auditoria_custos_v76 import xlsm, linha

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "sincronizador"

def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo

auditor = carregar("haize_auditor_v76", DIR / "auditar_planilhas.py")
diagnostico = carregar("haize_diagnostico_v76", DIR / "diagnosticar_pendencias_v76.py")


class DiagnosticoPendenciasV76(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp.name)
        nomes = ["Condominio %d" % i for i in range(1, 11)]
        mapping = [linha(1, {"A": "Condominio", "B": "Arquivo"})]
        for indice, nome in enumerate(nomes, 1):
            filename = "ORIGEM%d.xlsm" % indice
            mapping.append(linha(indice + 1, {"A": nome, "B": filename}))
            itens = [linha(1, {"A": "Descricao"})]
            if indice == 1:
                itens.append(linha(2, {"A": "Compativel", "B": 46000, "C": 50.25, "D": "Energia", "L": "id-ok"}))
                itens.append(linha(3, {"A": "Pendente antigo", "B": 45500, "C": 10.10, "D": "Limpeza", "L": "id-1"}))
                itens.append(linha(4, {"A": "Pendente novo", "B": 46000, "C": 20.30, "D": "Limpeza", "L": "id-2"}))
            xlsm(self.raiz / filename, {"GASTOS": itens})
        xlsm(self.raiz / "BASE_DADOS_GERAL.xlsm", {
            "CONDOMINIOS": mapping,
            "BASE_GERAL": [
                linha(1, {"A": "Descricao"}),
                linha(2, {"A": "Compativel", "B": 46000, "C": 50.25, "D": "Energia",
                          "K": "Condominio 1", "L": "id-ok"}),
            ],
            "BASE_PRAZOS": [linha(1, {"A": "Condominio"})]
        })

    def tearDown(self):
        self.temp.cleanup()

    def test_lista_apenas_somatorios_sem_id_ou_descricao(self):
        snapshot = {p.name: p.read_bytes() for p in self.raiz.iterdir()}
        grupos = diagnostico.analisar(self.raiz, auditor)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["condominio"], "Condominio 1")
        self.assertEqual(grupos[0]["quantidade"], 2)
        self.assertEqual(grupos[0]["valor"], Decimal("30.40"))
        self.assertTrue(grupos[0]["mais_antigo"] < grupos[0]["mais_recente"])
        self.assertNotIn("id-1", str(grupos))
        self.assertNotIn("Pendente antigo", str(grupos))
        self.assertEqual(snapshot, {p.name: p.read_bytes() for p in self.raiz.iterdir()})

    def test_falha_segura_sem_pasta(self):
        with self.assertRaises(FileNotFoundError):
            diagnostico.analisar(self.raiz / "nao-existe", auditor)


if __name__ == "__main__":
    unittest.main()
