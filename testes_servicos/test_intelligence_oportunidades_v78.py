
# -*- coding: utf-8 -*-

import sys
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "backend"),
)

from custos_importacao_v77 import validar_lote

from intelligence_oportunidades_v78 import (
    ErroOportunidades,
    identificar_oportunidades_v78,
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
    categoria="LIMPEZA",
    condominio="ALFA FICTICIO",
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


def analisar(registros, fechados=MESES):

    return identificar_oportunidades_v78(
        validar_lote(registros, MAPA),
        1,
        "2026-06",
        fechados,
    )


class TestesOportunidadesV78(unittest.TestCase):

    def test_custos_estaveis(self):

        resultado = analisar(
            preparar([100] * 6)
        )

        self.assertEqual(
            resultado.oportunidades,
            (),
        )

    def test_aumento_persistente(self):

        resultado = analisar(
            preparar([
                100, 100, 100,
                250, 260, 100,
            ])
        )

        self.assertEqual(
            len(resultado.oportunidades),
            1,
        )

        oportunidade = resultado.oportunidades[0]

        self.assertEqual(
            oportunidade.impacto_adicional_centavos,
            31000,
        )

        self.assertEqual(
            oportunidade.meses_com_aumento,
            2,
        )

    def test_pico_isolado_nao_e_persistente(self):

        resultado = analisar(
            preparar([
                100, 100, 100,
                600, 100, 100,
            ])
        )

        self.assertEqual(
            resultado.oportunidades,
            (),
        )

    def test_historico_incompleto(self):

        resultado = analisar(
            preparar([100, 100, 100, 400])
        )

        self.assertEqual(
            resultado.categorias_sem_base,
            1,
        )

        self.assertEqual(
            resultado.oportunidades,
            (),
        )

    def test_ajustes_negativos_nao_sao_economia(self):

        resultado = analisar(
            preparar([
                100, 100, 100,
                -500, 100, 100,
            ])
        )

        self.assertEqual(
            resultado.oportunidades,
            (),
        )

    def test_isolamento_por_condominio(self):

        registros = preparar([100] * 6)

        registros += preparar(
            [
                100, 100, 100,
                900, 900, 900,
            ],
            condominio="BETA FICTICIO",
        )

        resultado = analisar(registros)

        self.assertEqual(
            resultado.oportunidades,
            (),
        )

    def test_rejeita_mes_nao_fechado(self):

        with self.assertRaises(ErroOportunidades):

            analisar(
                preparar([100] * 6),
                MESES[:5],
            )

    def test_prioriza_maior_impacto(self):

        registros = preparar([
            100, 100, 100,
            300, 300, 300,
        ])

        registros += preparar(
            [
                100, 100, 100,
                900, 900, 900,
            ],
            categoria="MANUTENCAO",
        )

        resultado = analisar(registros)

        self.assertEqual(
            len(resultado.oportunidades),
            2,
        )

        self.assertEqual(
            resultado.oportunidades[0].categoria,
            "manutencao",
        )

        self.assertEqual(
            resultado.oportunidades[0].prioridade,
            "ALTA",
        )


if __name__ == "__main__":
    unittest.main()
