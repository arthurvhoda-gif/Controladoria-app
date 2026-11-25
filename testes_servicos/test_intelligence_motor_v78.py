# -*- coding: utf-8 -*-
"""Testes fictícios e isolados do motor privado V7.8. Nenhum acesso à produção."""
import os
from pathlib import Path
import sys
import unittest
from dataclasses import replace

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from custos_importacao_v77 import validar_lote
from intelligence_motor_v78 import (
    ErroAnalisePrivada, analisar_historico_privado,
)

MAPA = {"ALFA FICTICIO": 1, "BETA FICTICIO": 2}


def registro(identificador, mes="2026-01-10", valor="100.00",
             categoria="LIMPEZA", condominio="ALFA FICTICIO"):
    return {
        "id": identificador, "condominio": condominio,
        "descricao": "Despesa inteiramente fictícia",
        "data": mes, "valor": valor, "categoria": categoria,
    }


def analisar(registros):
    return analisar_historico_privado(validar_lote(registros, MAPA))


class TestesIntelligenceV78(unittest.TestCase):
    def test_totais_preservam_centavos_positivos_e_ajustes_separados(self):
        resultado = analisar([
            registro("A", valor="100.05"),
            registro("B", valor="-20.03"),
            registro("C", valor="0.01"),
        ])
        self.assertEqual(resultado.lancamentos, 3)
        self.assertEqual(resultado.despesas_positivas_centavos, 10006)
        self.assertEqual(resultado.ajustes_negativos_centavos, 2003)
        self.assertEqual(resultado.saldo_centavos, 8003)
        self.assertEqual(resultado.meses[0].saldo_centavos, 8003)
        self.assertEqual(resultado.alertas, ())

    def test_isolamento_por_condominio_e_categoria(self):
        r = analisar([
            registro("A", valor="12.00", categoria="Limpeza"),
            registro("A", valor="30.00", categoria="Limpeza", condominio="BETA FICTICIO"),
            registro("B", valor="4.00", categoria="Energia"),
        ])
        self.assertEqual(r.condominios, 2)
        self.assertEqual(
            [(c.condominio_id, c.categoria_chave, c.saldo_centavos) for c in r.categorias],
            [(1, "energia", 400), (1, "limpeza", 1200), (2, "limpeza", 3000)],
        )

    def test_mes_ausente_nao_e_zero_nem_fabrica_alerta(self):
        r = analisar([
            registro("A", "2026-01-03", "100.00"),
            registro("B", "2026-02-03", "100.00"),
            registro("C", "2026-04-03", "100.00"),
            registro("D", "2026-05-03", "700.00"),
        ])
        self.assertEqual(r.competencias_observadas, 4)
        self.assertEqual(r.alertas, ())
        self.assertEqual(len(r.meses), 4)

    def test_alerta_somente_apos_tres_meses_consecutivos_com_evidencia(self):
        r = analisar([
            registro("A", "2026-01-01", "100.00"),
            registro("B", "2026-02-01", "110.00"),
            registro("C", "2026-03-01", "90.00"),
            registro("D", "2026-04-01", "600.00"),
        ])
        self.assertEqual(len(r.alertas), 1)
        a = r.alertas[0]
        self.assertEqual(a.competencia, "2026-04-01")
        self.assertEqual(a.referencia_mediana_centavos, 10000)
        self.assertEqual(a.valor_atual_centavos, 60000)
        self.assertEqual(a.aumento_centavos, 50000)
        self.assertEqual(a.aumento_percentual_inteiro, 500)
        self.assertEqual(a.classificacao, "aumento_para_revisao")

    def test_sem_alerta_se_aumento_absoluto_insuficiente(self):
        r = analisar([
            registro("A", "2026-01-01", "100.00"),
            registro("B", "2026-02-01", "100.00"),
            registro("C", "2026-03-01", "100.00"),
            registro("D", "2026-04-01", "140.00"),
        ])
        self.assertEqual(r.alertas, ())

    def test_sem_alerta_se_variacao_percentual_insuficiente(self):
        r = analisar([
            registro("A", "2026-01-01", "1000.00"),
            registro("B", "2026-02-01", "1000.00"),
            registro("C", "2026-03-01", "1000.00"),
            registro("D", "2026-04-01", "1250.00"),
        ])
        self.assertEqual(r.alertas, ())

    def test_valor_negativo_nao_e_interpretado_como_despesa_positiva(self):
        r = analisar([
            registro("A", "2026-01-01", "-100.00"),
            registro("B", "2026-02-01", "-100.00"),
            registro("C", "2026-03-01", "-100.00"),
            registro("D", "2026-04-01", "900.00"),
        ])
        self.assertEqual(r.alertas, ())
        self.assertEqual(r.ajustes_negativos_centavos, 30000)

    def test_rejeita_identificador_repetido_mesmo_em_lotes_validados_distintos(self):
        a = validar_lote([registro("A")], MAPA)[0]
        with self.assertRaisesRegex(ErroAnalisePrivada, "duplicado"):
            analisar_historico_privado((a, a))

    def test_rejeita_fonte_diferente_sem_mesclar_dados(self):
        a = validar_lote([registro("A")], MAPA)[0]
        with self.assertRaisesRegex(ErroAnalisePrivada, "fonte"):
            analisar_historico_privado((replace(a, origem="financeiro"),))

    def test_rejeita_lote_vazio_ou_objeto_nao_validado(self):
        for lote in ([], {}, [registro("A")]):
            with self.subTest(lote=type(lote).__name__):
                with self.assertRaises(ErroAnalisePrivada):
                    analisar_historico_privado(lote)

    def test_resultado_deterministico_independente_da_ordem(self):
        dados = validar_lote([
            registro("A", "2026-04-01", "90.00"),
            registro("B", "2026-02-01", "20.00", categoria="Energia"),
            registro("C", "2026-03-01", "-5.00"),
        ], MAPA)
        self.assertEqual(
            analisar_historico_privado(dados),
            analisar_historico_privado(tuple(reversed(dados))),
        )

    def test_nao_altera_os_registros_recebidos(self):
        dados = validar_lote([registro("A"), registro("B", valor="-5.00")], MAPA)
        antes = tuple(dados)
        analisar_historico_privado(dados)
        self.assertEqual(dados, antes)


if __name__ == "__main__":
    unittest.main()
