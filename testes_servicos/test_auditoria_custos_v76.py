"""V7.6: auditoria das planilhas sem acessar dados privados ou a rede."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

MODULO = Path(__file__).resolve().parents[1] / "sincronizador" / "auditar_planilhas.py"
espec = importlib.util.spec_from_file_location("haize_auditoria_custos_v76", MODULO)
auditoria = importlib.util.module_from_spec(espec)
espec.loader.exec_module(auditoria)

HEAD = '<?xml version="1.0" encoding="UTF-8"?>'
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def linha(n, celulas):
    return '<row r="%d">%s</row>' % (n, ''.join(
        '<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % (k, n, v)
        if isinstance(v, str) else '<c r="%s%d"><v>%s</v></c>' % (k, n, v)
        for k, v in celulas.items()
    ))


def xlsm(arquivo, abas):
    nomes = list(abas)
    wb = HEAD + '<workbook xmlns="%s" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>%s</sheets></workbook>' % (
        MAIN, ''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (n, i, i) for i, n in enumerate(nomes, 1))
    )
    rel = HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % (
        ''.join('<Relationship Id="rId%d" Target="worksheets/sheet%d.xml"/>' % (i, i) for i in range(1, len(nomes)+1))
    )
    with ZipFile(arquivo, "w") as z:
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rel)
        for i, nome in enumerate(nomes, 1):
            xml = HEAD + '<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (MAIN, ''.join(abas[nome]))
            z.writestr("xl/worksheets/sheet%d.xml" % i, xml)


class AuditoriaCustosV76(unittest.TestCase):
    def test_leitura_e_comparacao_sem_alterar_origens(self):
        with tempfile.TemporaryDirectory() as pasta:
            root = Path(pasta)
            base = root / "BASE_DADOS_GERAL.xlsm"
            local = root / "ALFA.xlsm"
            xlsm(base, {
                "CONDOMINIOS": [linha(1, {"A":"Condominio", "B":"Arquivo"}), linha(2, {"A":"Alfa", "B":"ALFA.xlsm"})],
                "BASE_GERAL": [linha(1, {"A":"Descricao"}), linha(2, {"A":"Teste", "B":46000, "C":90.50, "D":"Jardinagem", "K":"Alfa", "L":"id-1"})],
                "BASE_PRAZOS": [linha(1, {"A":"Condominio"})],
            })
            xlsm(local, {"GASTOS": [linha(1, {"A":"Descricao"}), linha(2, {"A":"Teste", "B":46000, "C":90.50, "D":"Jardinagem", "L":"id-1"})]})
            antes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (base, local)]
            saida = root / "relatorios_local"
            resumo, divergencias = auditoria.auditar(root, saida)
            self.assertEqual(len(resumo), 1)
            self.assertEqual(resumo[0]["classificadas"], 1)
            self.assertEqual(resumo[0]["total_planilha"], "R$ 90,50")
            self.assertEqual(divergencias, [])
            self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in (base, local)], antes)
            self.assertEqual({p.name for p in saida.iterdir()},
                             {"RESUMO_DA_AUDITORIA.txt", "resumo_por_condominio.csv", "divergencias.csv"})

    def test_identifica_arquivo_ausente_sem_modificar_base(self):
        with tempfile.TemporaryDirectory() as pasta:
            root = Path(pasta)
            base = root / "BASE_DADOS_GERAL.xlsm"
            xlsm(base, {
                "CONDOMINIOS": [linha(1, {"A":"Condominio"}), linha(2, {"A":"Alfa", "B":"INEXISTENTE.xlsm"})],
                "BASE_GERAL": [linha(1, {"A":"Descricao"})],
                "BASE_PRAZOS": [linha(1, {"A":"Condominio"})],
            })
            antes = base.read_bytes()
            resumo, detalhes = auditoria.auditar(root, root / "relatorios")
            self.assertEqual(len(resumo), 1)
            self.assertTrue(any(a["tipo"] == "ARQUIVO_AUSENTE" for a in detalhes))
            self.assertEqual(base.read_bytes(), antes)

    def test_classificados_sem_id_sao_sinalizados(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta)
            xlsm(root / "BASE_DADOS_GERAL.xlsm", {
                "CONDOMINIOS":[linha(1, {"A":"Condominio"}), linha(2, {"A":"Alfa", "B":"ALFA.xlsm"})],
                "BASE_GERAL":[linha(1, {"A":"Descricao"})],
                "BASE_PRAZOS":[linha(1, {"A":"Condominio"})]
            })
            xlsm(root / "ALFA.xlsm", {"GASTOS":[linha(1, {"A":"Descricao"}), linha(2, {"A":"Reparo", "B":46000, "C":10, "D":"Manutencao"})]})
            resumo, detalhes=auditoria.auditar(root,root / "auditoria")
            self.assertTrue(any(d["tipo"] == "SEM_ID" for d in detalhes))
            self.assertEqual(resumo[0]["classificadas"],0)


if __name__=="__main__":
    unittest.main()
