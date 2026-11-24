
# -*- coding: utf-8 -*-
"""
HAIZE INTELLIGENCE V7.8
Testes da fonte histórica privada.

Todos os dados são fictícios.
Nenhum acesso ao banco de produção.
Nenhum envio de e-mail.
"""

import os
import sys
import unittest

from pathlib import Path
from datetime import date

BACKEND = Path(__file__).resolve().parents[1] / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, select, update, func
from sqlalchemy.orm import Session

import models

from custos_historicos_v77 import (
    CustoHistoricoV77,
    CustoImportacaoLoteV77,
    CustoHistoricoEventoV77,
)

from custos_servico_v77 import (
    ensaiar_aplicacao_sqlite_v77,
)

from intelligence_fonte_v78 import (
    ErroFonteIntelligence,
    carregar_historico_validado_v78,
    analisar_fonte_historica_v78,
)


MAPA = {
    "ALFA FICTICIO": 1,
    "BETA FICTICIO": 2,
}


def gasto(
    identificador,
    valor="100.00",
    data="2026-01-10",
    categoria="LIMPEZA",
    condominio="ALFA FICTICIO",
):
    return {
        "id": identificador,
        "condominio": condominio,
        "descricao": "Despesa ficticia de homologacao",
        "data": data,
        "valor": valor,
        "categoria": categoria,
    }


class TestesFonteIntelligenceV78(unittest.TestCase):

    def setUp(self):

        self.engine = create_engine(
            "sqlite:///:memory:"
        )

        tabelas = (
            models.Condominio.__table__,
            CustoImportacaoLoteV77.__table__,
            CustoHistoricoV77.__table__,
            CustoHistoricoEventoV77.__table__,
        )

        for tabela in tabelas:
            tabela.create(self.engine)

        with Session(self.engine) as sessao:

            sessao.add_all([
                models.Condominio(
                    id=1,
                    nome="ALFA FICTICIO",
                ),
                models.Condominio(
                    id=2,
                    nome="BETA FICTICIO",
                ),
            ])

            sessao.commit()

    def tearDown(self):

        self.engine.dispose()

    def inserir(self, registros):

        with Session(self.engine) as sessao:

            ensaiar_aplicacao_sqlite_v77(
                sessao,
                registros,
                MAPA,
            )

            sessao.commit()

    def test_carregamento_historico_validado(self):

        self.inserir([
            gasto("001", "100.05"),
            gasto("002", "200.10"),
        ])

        with Session(self.engine) as sessao:

            dados = carregar_historico_validado_v78(
                sessao,
                MAPA,
            )

            self.assertEqual(len(dados), 2)

            self.assertEqual(
                sum(r.valor_centavos for r in dados),
                30015,
            )

    def test_integracao_com_motor_intelligence(self):

        self.inserir([
            gasto("001", "100.05"),
            gasto("002", "200.10"),
            gasto("003", "-50.00"),
        ])

        with Session(self.engine) as sessao:

            resultado = analisar_fonte_historica_v78(
                sessao,
                MAPA,
            )

            self.assertEqual(
                resultado.lancamentos,
                3,
            )

            self.assertEqual(
                resultado.despesas_positivas_centavos,
                30015,
            )

            self.assertEqual(
                resultado.ajustes_negativos_centavos,
                5000,
            )

            self.assertEqual(
                resultado.saldo_centavos,
                25015,
            )

    def test_isolamento_por_condominio(self):

        self.inserir([
            gasto("001", "100.00"),
            gasto(
                "001",
                "300.00",
                condominio="BETA FICTICIO",
            ),
        ])

        with Session(self.engine) as sessao:

            dados = carregar_historico_validado_v78(
                sessao,
                {"ALFA FICTICIO": 1},
            )

            self.assertEqual(len(dados), 1)

            self.assertEqual(
                dados[0].condominio_id,
                1,
            )

            self.assertEqual(
                dados[0].valor_centavos,
                10000,
            )

    def test_rejeita_condominio_inexistente(self):

        with Session(self.engine) as sessao:

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    {"GAMA FICTICIO": 999},
                )

    def test_rejeita_nome_e_id_incompativeis(self):

        with Session(self.engine) as sessao:

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    {"ALFA FICTICIO": 2},
                )

    def test_rejeita_mapeamento_duplicado(self):

        with Session(self.engine) as sessao:

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    {
                        "ALFA FICTICIO": 1,
                        "BETA FICTICIO": 1,
                    },
                )

    def test_rejeita_historico_vazio(self):

        with Session(self.engine) as sessao:

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    MAPA,
                )

    def test_detecta_hash_adulterado(self):

        self.inserir([
            gasto("001", "100.00"),
        ])

        with Session(self.engine) as sessao:

            sessao.execute(
                update(CustoHistoricoV77).values(
                    hash_conteudo="0" * 64,
                )
            )

            sessao.commit()

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    MAPA,
                )

    def test_detecta_valor_adulterado(self):

        self.inserir([
            gasto("001", "100.00"),
        ])

        with Session(self.engine) as sessao:

            sessao.execute(
                update(CustoHistoricoV77).values(
                    valor_centavos=999999,
                )
            )

            sessao.commit()

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    MAPA,
                )

    def test_detecta_competencia_adulterada(self):

        self.inserir([
            gasto("001", "100.00"),
        ])

        with Session(self.engine) as sessao:

            sessao.execute(
                update(CustoHistoricoV77).values(
                    competencia=date(2026, 2, 1),
                )
            )

            sessao.commit()

            with self.assertRaises(
                ErroFonteIntelligence
            ):

                carregar_historico_validado_v78(
                    sessao,
                    MAPA,
                )

    def test_bloqueia_sqlite_fora_da_memoria(self):

        engine = create_engine(
            "sqlite:///arquivo_nao_autorizado.db"
        )

        try:

            with Session(engine) as sessao:

                with self.assertRaises(
                    RuntimeError
                ):

                    carregar_historico_validado_v78(
                        sessao,
                        MAPA,
                    )

        finally:

            engine.dispose()

    def test_analise_nao_altera_banco(self):

        self.inserir([
            gasto("001", "100.00"),
            gasto("002", "200.00"),
        ])

        with Session(self.engine) as sessao:

            tabelas = (
                CustoHistoricoV77,
                CustoImportacaoLoteV77,
                CustoHistoricoEventoV77,
            )

            antes = tuple(
                sessao.scalar(
                    select(func.count()).select_from(t)
                )
                for t in tabelas
            )

            analisar_fonte_historica_v78(
                sessao,
                MAPA,
            )

            depois = tuple(
                sessao.scalar(
                    select(func.count()).select_from(t)
                )
                for t in tabelas
            )

            self.assertEqual(antes, depois)

            self.assertFalse(sessao.new)
            self.assertFalse(sessao.dirty)
            self.assertFalse(sessao.deleted)

    def test_bloqueia_sessao_com_alteracoes_pendentes(self):

        self.inserir([
            gasto("001", "100.00"),
        ])

        with Session(self.engine) as sessao:

            condominio = sessao.get(
                models.Condominio,
                1,
            )

            condominio.nome = "NOME ALTERADO"

            try:

                with self.assertRaisesRegex(
                    ErroFonteIntelligence,
                    "alteracoes pendentes",
                ):

                    carregar_historico_validado_v78(
                        sessao,
                        MAPA,
                    )

                self.assertIn(
                    condominio,
                    sessao.dirty,
                )

            finally:

                sessao.rollback()

    def test_detecta_aumento_pelo_historico(self):

        self.inserir([
            gasto("001", "100.00", "2026-01-10"),
            gasto("002", "110.00", "2026-02-10"),
            gasto("003", "90.00", "2026-03-10"),
            gasto("004", "600.00", "2026-04-10"),
        ])

        with Session(self.engine) as sessao:

            resultado = analisar_fonte_historica_v78(
                sessao,
                MAPA,
            )

            self.assertEqual(
                len(resultado.alertas),
                1,
            )

            self.assertEqual(
                resultado.alertas[0].aumento_centavos,
                50000,
            )


if __name__ == "__main__":
    unittest.main()

