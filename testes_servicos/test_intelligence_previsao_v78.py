
# -*- coding: utf-8 -*-

import sys
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "backend"),
)

from custos_importacao_v77 import validar_lote

from intelligence_previsao_v78 import (
    ErroPrevisao,
    prever_despesas_v78,
)


MAPA = {
    "ALFA FICTICIO": 1,
    "BETA FICTICIO": 2,
}

MESES = [
    f"2026-{i:02d}"
    for i in range(1, 7)
]


def preparar(valores, condominio="ALFA FICTICIO"):

    return [
        {
            "id": f"REG-{i}",
            "condominio": condominio,
            "descricao": "Despesa ficticia",
            "data": f"2026-{i:02d}-10",
            "valor": str(valor),
            "categoria": "LIMPEZA",
        }
        for i, valor in enumerate(valores, 1)
    ]


def prever(registros, fechados=MESES):

    return prever_despesas_v78(
        validar_lote(registros, MAPA),
        1,
        "2026-06",
        fechados,
    )


class TestesPrevisaoV78(unittest.TestCase):

    def test_despesas_constantes(self):

        resultado = prever(
            preparar([100] * 6)
        )

        self.assertEqual(
            resultado.previsao_centavos,
            10000,
        )

        self.assertEqual(
            resultado.erro_medio_centavos,
            0,
        )

    def test_proxima_competencia(self):

        resultado = prever(
            preparar([100] * 6)
        )

        self.assertEqual(
            resultado.competencia_prevista,
            "2026-07",
        )

    def test_escolhe_metodo_de_menor_erro(self):

        resultado = prever(
            preparar([
                100, 200, 300,
                400, 500, 600,
            ])
        )

        self.assertEqual(
            resultado.metodo,
            "ultimo_mes",
        )

        self.assertEqual(
            resultado.previsao_centavos,
            60000,
        )

    def test_mediana_resiste_a_pico_atipico(self):

        resultado = prever(
            preparar([
                100, 100, 400,
                100, 100, 100,
            ])
        )

        self.assertEqual(
            resultado.metodo,
            "mediana_3_meses",
        )

    def test_bloqueia_historico_insuficiente(self):

        with self.assertRaises(ErroPrevisao):

            prever(
                preparar([100, 200, 300])
            )

    def test_bloqueia_mes_nao_fechado(self):

        with self.assertRaises(ErroPrevisao):

            prever(
                preparar([100] * 6),
                MESES[:5],
            )

    def test_isolamento_por_condominio(self):

        registros = preparar([100] * 6)

        registros += preparar(
            [900] * 6,
            "BETA FICTICIO",
        )

        resultado = prever(registros)

        self.assertEqual(
            resultado.previsao_centavos,
            10000,
        )

    def test_cenarios_de_variacao(self):

        resultado = prever(
            preparar([
                100, 200, 300,
                400, 500, 600,
            ])
        )

        self.assertEqual(
            resultado.cenario_inferior_centavos,
            50000,
        )

        self.assertEqual(
            resultado.cenario_superior_centavos,
            70000,
        )


if __name__ == "__main__":
    unittest.main()
