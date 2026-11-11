# -*- coding: utf-8 -*-
"""V7.7 — SOMENTE dados fictícios e SQLite em memória.

Não importa arquivos reais, não acessa Neon, não chama API.
"""
import os
from pathlib import Path
import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import models
from custos_historicos_v77 import (
    CustoImportacaoLoteV77, CustoHistoricoV77, CustoHistoricoEventoV77,
)
from custos_importacao_v77 import (
    ErroValidacaoCustos, validar_lote, montar_previa,
)

MAPA = {"Condomínio Fictício Alfa": 1, "Condomínio Fictício Beta": 2}


def ficticio(**mudar):
    registro = {
        "condominio": "Condomínio Fictício Alfa",
        "id": "00123",
        "descricao": "Despesa inteiramente inventada",
        "data": "2026-07-15",
        "valor": Decimal("1250.35"),
        "categoria": "JARDIM",
    }
    registro.update(mudar)
    return registro


class ValidacaoCustoV77(unittest.TestCase):
    def test_valores_em_centavos_sem_arredondamento_e_mes_normalizado(self):
        reg = validar_lote([ficticio()], MAPA)[0]
        self.assertEqual(reg.valor_centavos, 125035)
        self.assertEqual(reg.data_original, date(2026, 7, 15))
        self.assertEqual(reg.competencia, date(2026, 7, 1))
        self.assertEqual(reg.id_origem, "00123")
        self.assertEqual(reg.categoria_chave, "jardim")
        self.assertEqual(len(reg.hash_conteudo), 64)

    def test_reimportacao_identica_nao_gera_inclusoes(self):
        registros = validar_lote([ficticio()], MAPA)
        primeira = montar_previa(registros, {})
        segunda = montar_previa(registros, {registros[0].chave: registros[0]})
        self.assertEqual((primeira.novos, primeira.inalterados), (1, 0))
        self.assertEqual((segunda.novos, segunda.alterados, segunda.inalterados), (0, 0, 1))

    def test_atualizacao_proposta_nao_muda_snapshot(self):
        antigo = validar_lote([ficticio()], MAPA)[0]
        novo = validar_lote([ficticio(valor=Decimal("1250.36"))], MAPA)[0]
        fotografia = {antigo.chave: antigo}
        pre = montar_previa([novo], fotografia)
        self.assertEqual((pre.novos, pre.alterados), (0, 1))
        self.assertEqual(fotografia[antigo.chave].valor_centavos, 125035)

    def test_nunca_remove_registros_ausentes(self):
        antigo, extra = validar_lote([ficticio(), ficticio(id="00999")], MAPA)
        anteriores = {antigo.chave: antigo, extra.chave: extra}
        parcial = montar_previa([antigo], anteriores)
        completo = montar_previa([antigo], anteriores, cobertura_completa=True)
        self.assertEqual(parcial.ausentes_na_origem, 0)
        self.assertEqual(completo.ausentes_na_origem, 1)
        self.assertEqual(len(anteriores), 2)
        self.assertTrue(completo.revisao_manual_obrigatoria)

    def test_id_igual_em_condominios_diferentes_nao_e_duplicado(self):
        dados = validar_lote([
            ficticio(), ficticio(condominio="Condomínio Fictício Beta")], MAPA)
        self.assertNotEqual(dados[0].chave, dados[1].chave)
        self.assertEqual(montar_previa(dados, {}).novos, 2)

    def test_identificador_repetido_no_mesmo_condominio_falha(self):
        with self.assertRaisesRegex(ErroValidacaoCustos, "linha 2"):
            validar_lote([ficticio(), ficticio(valor="10.00")], MAPA)

    def test_nome_desconhecido_nao_cria_condominio(self):
        with self.assertRaisesRegex(ErroValidacaoCustos, "sem vínculo aprovado"):
            validar_lote([ficticio(condominio="Terceiro Inventado")], MAPA)

    def test_mapeamentos_ambiguos_sao_rejeitados(self):
        with self.assertRaises(ErroValidacaoCustos):
            validar_lote([ficticio()], {"Condôminio Fictício Alfa": 1, "Condominio Ficticio Alfa": 2})
        with self.assertRaises(ErroValidacaoCustos):
            validar_lote([ficticio()], {"A": 1, "B": 1})

    def test_dados_invalidos_bloqueiam_lote_inteiro(self):
        invalidos = [
            {"valor": 12.10}, {"valor": "2.123"}, {"valor": "NaN"},
            {"valor": Decimal("1.234")}, {"valor": "1e2"},
            {"valor": "999999999999999999.00"}, {"id": ""},
            {"data": "2026-02-30"}, {"data": "1900-01-01"},
            {"categoria": "NÃO CLASSIFICADO"},
            {"categoria": "NAO CLASSIFICADOS"},
            {"descricao": ""},
        ]
        for caso in invalidos:
            with self.subTest(caso=str(caso)), self.assertRaises(ErroValidacaoCustos):
                invalido = ficticio(id="novo")
                invalido.update(caso)
                validar_lote([ficticio(), invalido], MAPA)

    def test_valores_negativos_preservados_sem_inferir_reembolso(self):
        reg = validar_lote([ficticio(valor="-21.12")], MAPA)[0]
        self.assertEqual(reg.valor_centavos, -2112)

    def test_hash_detecta_alteracao_de_descricao_ou_categoria(self):
        original = validar_lote([ficticio()], MAPA)[0]
        outro = validar_lote([ficticio(categoria="LIMPEZA")], MAPA)[0]
        self.assertNotEqual(original.hash_conteudo, outro.hash_conteudo)

    def test_963_lancamentos_ficticios_validam_sem_repeticao(self):
        dados = [ficticio(id=f"id-ficticio-{i:04d}", valor="1.01") for i in range(963)]
        lote = validar_lote(dados, MAPA)
        self.assertEqual(montar_previa(lote, {}).novos, 963)
        self.assertEqual(montar_previa(lote, {}).total_centavos, 963 * 101)
        self.assertEqual(montar_previa(lote, {r.chave: r for r in lote}).inalterados, 963)


class ModeloFicticioSQLiteV77(unittest.TestCase):
    """Exercita o schema proposto exclusivamente num SQLite criado em memória."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def ligar_chaves(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
        # Somente tabelas necessárias nesta memória, não Neon ou produção.
        for tabela in (models.Condominio.__table__, CustoImportacaoLoteV77.__table__,
                       CustoHistoricoV77.__table__, CustoHistoricoEventoV77.__table__):
            tabela.create(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_constraint_unica_por_condominio_e_origem(self):
        reg = validar_lote([ficticio()], MAPA)[0]
        with Session(self.engine) as ses:
            ses.add_all([
                models.Condominio(id=1, nome="Condomínio Fictício Alfa"),
                models.Condominio(id=2, nome="Condomínio Fictício Beta"),
            ])
            ses.add(CustoImportacaoLoteV77(
                id=1, origem=reg.origem, arquivo_sha256="f" * 64,
                status="planejado", qtd_registros=1, total_centavos=reg.valor_centavos))
            ses.commit()

            def custo(cid):
                return CustoHistoricoV77(
                    condominio_id=cid, origem=reg.origem, id_origem=reg.id_origem,
                    data_original=reg.data_original, competencia=reg.competencia,
                    descricao=reg.descricao, categoria_original=reg.categoria_original,
                    categoria_chave=reg.categoria_chave, valor_centavos=reg.valor_centavos,
                    hash_conteudo=reg.hash_conteudo,
                    lote_primeira_entrada_id=1, lote_ultima_atualizacao_id=1,
                )
            ses.add_all([custo(1), custo(2)])
            ses.commit()
            self.assertEqual(ses.query(CustoHistoricoV77).count(), 2)
            ses.add(custo(1))
            with self.assertRaises(IntegrityError):
                ses.commit()
            ses.rollback()
            self.assertEqual(ses.query(CustoHistoricoV77).count(), 2)

    def test_condominio_inexistente_bloqueado_pelo_banco_ficticio(self):
        reg = validar_lote([ficticio()], MAPA)[0]
        with Session(self.engine) as ses:
            ses.add(CustoImportacaoLoteV77(
                id=1, origem=reg.origem, arquivo_sha256="a" * 64,
                status="planejado", qtd_registros=1, total_centavos=reg.valor_centavos))
            ses.commit()
            ses.add(CustoHistoricoV77(
                condominio_id=999, origem=reg.origem, id_origem=reg.id_origem,
                data_original=reg.data_original, competencia=reg.competencia,
                descricao=reg.descricao, categoria_original=reg.categoria_original,
                categoria_chave=reg.categoria_chave, valor_centavos=reg.valor_centavos,
                hash_conteudo=reg.hash_conteudo,
                lote_primeira_entrada_id=1, lote_ultima_atualizacao_id=1,
            ))
            with self.assertRaises(IntegrityError):
                ses.commit()
