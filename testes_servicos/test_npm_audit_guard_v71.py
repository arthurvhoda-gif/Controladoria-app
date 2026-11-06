# -*- coding: utf-8 -*-
"""Testes da barreira npm da V7.1 sem rede nem acesso ao aplicativo real."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resumir_npm_audit_v70 as auditoria


class TesteAuditoriaDependenciasV71(unittest.TestCase):
    def executar(self, severidades, exigir_sem_altas=True):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "npm-audit.json"
            path.write_text(json.dumps({
                "metadata": {"vulnerabilities": {
                    "critical": severidades.get("critical", 0),
                    "high": severidades.get("high", 0),
                    "moderate": severidades.get("moderate", 0),
                    "low": severidades.get("low", 0),
                }},
                "vulnerabilities": {}
            }), encoding="utf8")
            args = ["resumir_npm_audit_v70.py", str(path)]
            if exigir_sem_altas:
                args.append("--fail-high")
            buf = StringIO()
            with patch.object(sys, "argv", args), redirect_stdout(buf):
                try:
                    auditoria.main()
                    return 0, buf.getvalue()
                except SystemExit as exc:
                    return 1, buf.getvalue() + str(exc)

    def test_zero_altas_aprovado(self):
        codigo, saida = self.executar({"moderate": 9, "low": 2})
        self.assertEqual(codigo, 0)
        self.assertIn("moderate=9", saida)

    def test_uma_alta_bloqueada(self):
        codigo, saida = self.executar({"high": 1})
        self.assertEqual(codigo, 1)
        self.assertIn("BLOQUEADO", saida)

    def test_uma_critica_bloqueada(self):
        codigo, saida = self.executar({"critical": 1})
        self.assertEqual(codigo, 1)
        self.assertIn("BLOQUEADO", saida)

    def test_modo_somente_inventario_permanece_compativel(self):
        codigo, saida = self.executar({"high": 1}, exigir_sem_altas=False)
        self.assertEqual(codigo, 0)
        self.assertIn("warning", saida)


if __name__ == "__main__":
    unittest.main()
