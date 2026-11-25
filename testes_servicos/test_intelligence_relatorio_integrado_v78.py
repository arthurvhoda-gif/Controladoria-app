
# -*- coding: utf-8 -*-

import sys
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "backend"),
)

from custos_importacao_v77 import validar_lote

from intelligence_relatorio_integrado_v78 import (
    gerar_relatorio_integrado_v78,
)


MAPA = {
    "ALFA FICTICIO": 1,
    "BETA FICTICIO": 2,
}

MESES = [
    f"2026-{i:02d}"
    for i in range(1, 7)
]


def preparar(
    valores,
    condominio="ALFA FICTICIO",
    categoria="LIMPEZA",
):

    return [
        {
            "id": f"{categoria}-{i}",
            "condominio": condominio,
            "descricao": "Despesa ficticia",
            "data": f"2026-{i:02d}-10",
            "valor": str(valor),
            "categoria": categoria,
        }
        for i, valor in enumerate(valores, 1)
    ]


def gerar(registros, fechamentos=None):

    if fechamentos is None:
        fechamentos = {1: MESES}

    return gerar_relatorio_integrado_v78(
        validar_lote(registros, MAPA),
        "2026-06",
        fechamentos,
    )


class TestesRelatorioIntegradoV78(unittest.TestCase):

    def test_relatorio_completo(self):

        texto = gerar(
            preparar([100] * 6)
        )

        for secao in (
            "RESUMO FINANCEIRO",
            "ALERTAS DE VARIACAO",
            "INTELIGENCIA PREDITIVA",
            "OPORTUNIDADES DE REDUCAO DE CUSTOS",
            "LIMITACOES E PLANO DE ACAO",
        ):
            self.assertIn(secao, texto)

    def test_integra_previsao_financeira(self):

        texto = gerar(
            preparar([100] * 6)
        )

        self.assertIn(
            "Despesa estimada: R$ 100,00",
            texto,
        )

        self.assertIn(
            "Competencia prevista: 2026-07",
            texto,
        )

    def test_integra_oportunidades(self):

        texto = gerar(
            preparar([
                100, 100, 100,
                250, 260, 100,
            ])
        )

        self.assertIn(
            "Oportunidades identificadas: 1",
            texto,
        )

        self.assertIn(
            "Impacto adicional identificado: R$ 310,00",
            texto,
        )

    def test_sem_fechamento_confirmado(self):

        texto = gerar(
            preparar([100] * 6),
            {},
        )

        self.assertIn(
            "Fechamento mensal nao confirmado",
            texto,
        )

        self.assertNotIn(
            "Despesa estimada:",
            texto,
        )

    def test_historico_insuficiente(self):

        texto = gerar(
            preparar([100] * 6),
            {1: MESES[1:]},
        )

        self.assertIn(
            "Historico insuficiente para previsao.",
            texto,
        )

    def test_fechamentos_independentes(self):

        registros = preparar([100] * 6)

        registros += preparar(
            [900] * 6,
            "BETA FICTICIO",
        )

        texto = gerar(
            registros,
            {1: MESES},
        )

        self.assertIn(
            "Condominios sem previsao: 1",
            texto,
        )

        self.assertEqual(
            texto.count("Despesa estimada:"),
            1,
        )

    def test_ignora_dados_posteriores(self):

        dados = preparar([100] * 6)

        futuro = preparar(
            [100, 100, 100, 100, 100, 100, 9000]
        )

        self.assertEqual(
            gerar(dados),
            gerar(futuro),
        )

    def test_rejeita_fechamento_futuro(self):

        with self.assertRaises(ValueError):

            gerar(
                preparar([100] * 6),
                {1: MESES + ["2026-07"]},
            )

    def test_rejeita_condominio_invalido(self):

        with self.assertRaises(ValueError):

            gerar(
                preparar([100] * 6),
                {999: MESES},
            )

    def test_confidencialidade_e_ressalvas(self):

        texto = gerar(
            preparar([100] * 6)
        )

        self.assertIn(
            "CONFIDENCIAL",
            texto,
        )

        self.assertIn(
            "nao representa economia",
            texto,
        )

        self.assertNotIn(
            "Despesa ficticia",
            texto,
        )

        self.assertLessEqual(
            len(texto),
            40000,
        )


if __name__ == "__main__":
    unittest.main()
