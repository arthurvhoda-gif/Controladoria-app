
# -*- coding: utf-8 -*-
"""Testes dos relatorios privados HAIZE INTELLIGENCE."""

import sys
import unittest

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from custos_importacao_v77 import validar_lote

from intelligence_relatorio_v78 import (
    moeda,
    gerar_relatorio_privado_v78,
)


MAPA = {
    "ALFA FICTICIO": 1,
    "BETA FICTICIO": 2,
}


def gasto(
    identificador,
    valor="100.00",
    data="2026-04-10",
    categoria="LIMPEZA",
    condominio="ALFA FICTICIO",
):
    return {
        "id": identificador,
        "condominio": condominio,
        "descricao": "Despesa ficticia de teste",
        "data": data,
        "valor": valor,
        "categoria": categoria,
    }


def relatorio(registros, competencia="2026-04"):

    dados = validar_lote(registros, MAPA)

    return gerar_relatorio_privado_v78(
        dados,
        competencia,
    )


class TestesRelatorioIntelligenceV78(unittest.TestCase):

    def test_formatacao_monetaria(self):

        self.assertEqual(
            moeda(123456789),
            "R$ 1.234.567,89",
        )

    def test_formatacao_negativa(self):

        self.assertEqual(
            moeda(-1050),
            "-R$ 10,50",
        )

    def test_formatacao_zero(self):

        self.assertEqual(
            moeda(0),
            "R$ 0,00",
        )

    def test_identificacao_privada(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertIn(
            "HAIZE INTELLIGENCE",
            texto,
        )

        self.assertIn(
            "CONFIDENCIAL",
            texto,
        )

    def test_total_financeiro_exato(self):

        texto = relatorio([
            gasto("001", "100.05"),
            gasto("002", "200.10"),
            gasto("003", "-50.00"),
        ])

        self.assertIn(
            "Despesas positivas: R$ 300,15",
            texto,
        )

        self.assertIn(
            "Ajustes negativos: R$ 50,00",
            texto,
        )

        self.assertIn(
            "Saldo dos lancamentos: R$ 250,15",
            texto,
        )

    def test_isolamento_da_competencia(self):

        texto = relatorio([
            gasto("001", "100.00"),
            gasto(
                "002",
                "900.00",
                "2026-03-10",
            ),
        ])

        self.assertIn(
            "Despesas positivas: R$ 100,00",
            texto,
        )

        self.assertNotIn(
            "R$ 900,00",
            texto,
        )

    def test_rejeita_competencia_invalida(self):

        with self.assertRaises(ValueError):

            relatorio(
                [gasto("001")],
                "2026-13",
            )

    def test_rejeita_mes_sem_dados(self):

        with self.assertRaises(ValueError):

            relatorio(
                [gasto("001")],
                "2026-12",
            )

    def test_relatorio_sem_alertas(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertIn(
            "Total de alertas: 0",
            texto,
        )

    def test_relatorio_com_alerta(self):

        texto = relatorio([
            gasto("001", "100.00", "2026-01-10"),
            gasto("002", "110.00", "2026-02-10"),
            gasto("003", "90.00", "2026-03-10"),
            gasto("004", "600.00", "2026-04-10"),
        ])

        self.assertIn(
            "Total de alertas: 1",
            texto,
        )

        self.assertIn(
            "Aumento identificado: R$ 500,00",
            texto,
        )

    def test_separacao_dos_condominios(self):

        texto = relatorio([
            gasto("001", "100.00"),
            gasto(
                "002",
                "200.00",
                condominio="BETA FICTICIO",
            ),
        ])

        self.assertIn(
            "Condominio ID 1:",
            texto,
        )

        self.assertIn(
            "Condominio ID 2:",
            texto,
        )

    def test_ressalvas_obrigatorias(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertIn(
            "RESSALVAS DA ANALISE",
            texto,
        )

        self.assertIn(
            "A cobertura integral do mes precisa ser confirmada.",
            texto,
        )

    def test_nao_expoe_descricao_original(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertNotIn(
            "Despesa ficticia de teste",
            texto,
        )

    def test_resultado_reproduzivel(self):

        registros = [
            gasto("001", "100.00"),
            gasto("002", "200.00"),
        ]

        self.assertEqual(
            relatorio(registros),
            relatorio(list(reversed(registros))),
        )

    def test_limite_de_tamanho(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertLessEqual(
            len(texto),
            40000,
        )

    def test_recomendacoes_presentes(self):

        texto = relatorio([
            gasto("001"),
        ])

        self.assertIn(
            "RECOMENDACOES ESTRATEGICAS",
            texto,
        )


if __name__ == "__main__":
    unittest.main()
