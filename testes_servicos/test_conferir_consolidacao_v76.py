"""V7.6: conferencia por agregados de despesas ausentes com planilhas ficticias."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from test_auditoria_custos_v76 import linha, xlsm

ROOT = Path(__file__).resolve().parents[1]

def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo

mod = carregar("haize_conferencia_v76", ROOT / "sincronizador" / "conferir_consolidacao_v76.py")
aud = carregar("haize_auditoria_v76", ROOT / "sincronizador" / "auditar_planilhas.py")

class ConferenciaConsolidacaoV76(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        mapa = [linha(1, {"A": "Condominio", "B": "Arquivo"})]
        base = [linha(1, {"A": "Descricao"})]
        for i in range(1, 11):
            nome, arquivo = "Condominio %d" % i, "ORIGEM%d.xlsm" % i
            mapa.append(linha(i + 1, {"A": nome, "B": arquivo}))
            linhas = [linha(1, {"A": "Descricao"})]
            if i == 1:
                # So 1 unidade da base pode ser usada como candidata exata.
                base.extend([
                    linha(2, {"A": "Limpeza", "B": 46200, "C": 10, "D": "Servicos",
                              "K": nome, "L": "id-na-base"}),
                    linha(3, {"A": "Energia", "B": 46190, "C": 55, "D": "Energia",
                              "K": nome, "L": "id-outro"}),
                ])
                linhas.extend([
                    linha(2, {"A": "Limpeza", "B": 46200, "C": 10, "D": "Servicos", "L": "id-novo-1"}),
                    linha(3, {"A": "Limpeza", "B": 46200, "C": 10, "D": "Servicos", "L": "id-novo-2"}),
                    linha(4, {"A": "Energia Diferente", "B": 46190, "C": 55, "D": "Energia", "L": "id-novo-3"}),
                    linha(5, {"A": "Gas", "B": 46200, "C": 7.50, "D": "Gas", "L": "id-novo-4"}),
                ])
            xlsm(self.p / arquivo, {"GASTOS": linhas})
        xlsm(self.p / "BASE_DADOS_GERAL.xlsm", {
            "CONDOMINIOS": mapa,
            "BASE_GERAL": base,
            "BASE_PRAZOS": [linha(1, {"A": "Condominio"})],
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_capacidade_de_correspondencia_uma_a_uma_e_arquivos_intactos(self):
        orig = {f.name: f.read_bytes() for f in self.p.iterdir()}
        grupos = mod.analisar(self.p, aud)
        self.assertEqual(len(grupos), 1)
        g = grupos[0]
        self.assertEqual(g["quantidade"], 4)
        self.assertEqual(g["classificacoes"]["Possivel duplicata com outro ID"], 1)
        self.assertEqual(g["classificacoes"]["Mesmo valor e competencia"], 1)
        self.assertEqual(g["classificacoes"]["Sem correspondencia identificada"], 2)
        self.assertEqual(g["meses_na_base"], {list(g["meses_faltantes"])[0]:1, list(g["meses_faltantes"])[1]:1} if len(g["meses_faltantes"])>1 else {list(g["meses_faltantes"])[0]:2})
        self.assertEqual(orig, {f.name: f.read_bytes() for f in self.p.iterdir()})

    def test_pasta_inexistente_falha(self):
        with self.assertRaises(FileNotFoundError):
            mod.analisar(self.p / "ausente", aud)

if __name__ == "__main__":
    unittest.main()
