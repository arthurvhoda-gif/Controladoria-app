# -*- coding: utf-8 -*-
"""V7.7: simulação transacional APENAS com SQLite descartável e dados inventados."""
import os
from pathlib import Path
import sys
import unittest

backend = Path(__file__).resolve().parents[1] / "backend"
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
import models
from custos_importacao_v77 import ErroValidacaoCustos
from custos_historicos_v77 import (
    CustoImportacaoLoteV77 as Lote, CustoHistoricoV77 as Custo,
    CustoHistoricoEventoV77 as Evento,
)
from custos_servico_v77 import ensaiar_aplicacao_sqlite_v77 as ensaiar

MAP = {"ALFA FICTICIO": 1, "BETA FICTICIO": 2}


def gasto(uid="001", valor="123.45", condo="ALFA FICTICIO", categoria="LIMPEZA"):
    return {"id": uid, "condominio": condo,
            "descricao": "Despesa fictícia de homologação",
            "data": "2026-07-15", "valor": valor, "categoria": categoria}


class PersistenciaV77SQLite(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def chaves_estrangeiras(conexao, _):
            conexao.execute("PRAGMA foreign_keys=ON")
        for table in (models.Condominio.__table__, Lote.__table__,
                      Custo.__table__, Evento.__table__):
            table.create(self.engine)
        with Session(self.engine) as s:
            s.add_all([models.Condominio(id=1, nome="ALFA FICTICIO"),
                       models.Condominio(id=2, nome="BETA FICTICIO")])
            s.commit()

    def tearDown(self):
        self.engine.dispose()

    def contagens(self, ses):
        return tuple(ses.scalar(select(__import__("sqlalchemy").func.count()).select_from(t))
                     for t in (Lote, Custo, Evento))

    def test_importacao_repetida_nao_cria_eventos_duplicados(self):
        with Session(self.engine) as ses:
            a = ensaiar(ses, [gasto()], MAP)
            self.assertEqual((a.novos, a.alterados, a.inalterados), (1, 0, 0))
            ses.commit()
            self.assertEqual(self.contagens(ses), (1, 1, 1))
            b = ensaiar(ses, [gasto()], MAP)
            self.assertEqual((b.novos, b.alterados, b.inalterados, b.lote_id),
                             (0, 0, 1, None))
            ses.commit()
            self.assertEqual(self.contagens(ses), (1, 1, 1))

    def test_atualizacao_guarda_hash_anterior_e_nao_soma_despesa(self):
        with Session(self.engine) as ses:
            a = ensaiar(ses, [gasto()], MAP); ses.commit()
            antes = ses.scalars(select(Custo)).one()
            primeira_id = antes.lote_primeira_entrada_id
            hash_anterior = antes.hash_conteudo
            b = ensaiar(ses, [gasto(valor="125.99")], MAP)
            self.assertEqual((b.novos, b.alterados), (0, 1))
            ses.commit()
            custos = ses.scalars(select(Custo)).all()
            self.assertEqual(len(custos), 1)
            self.assertEqual(custos[0].valor_centavos, 12599)
            self.assertEqual(custos[0].lote_primeira_entrada_id, primeira_id)
            self.assertNotEqual(custos[0].lote_ultima_atualizacao_id, primeira_id)
            eventos = ses.scalars(select(Evento).order_by(Evento.id)).all()
            self.assertEqual([e.acao for e in eventos], ["inclusao", "atualizacao"])
            self.assertEqual(eventos[1].hash_anterior, hash_anterior)
            self.assertEqual(eventos[1].hash_novo, custos[0].hash_conteudo)
            self.assertEqual(self.contagens(ses), (2, 1, 2))

    def test_id_repetido_permitido_em_condominios_diferentes(self):
        with Session(self.engine) as ses:
            res = ensaiar(ses, [gasto(), gasto(condo="BETA FICTICIO")], MAP)
            ses.commit()
            self.assertEqual(res.novos, 2)
            self.assertEqual(self.contagens(ses), (1, 2, 2))

    def test_lote_invalido_rejeitado_integralmente(self):
        with Session(self.engine) as ses:
            with self.assertRaises(ErroValidacaoCustos):
                ensaiar(ses, [gasto(), gasto(uid="novo", valor="NaN")], MAP)
            self.assertEqual(self.contagens(ses), (0, 0, 0))
            ses.rollback()

    def test_mapeamento_adulterado_nao_altera_banco(self):
        with Session(self.engine) as ses:
            with self.assertRaisesRegex(ErroValidacaoCustos, "ID não corresponde"):
                ensaiar(ses, [gasto()], {"ALFA FICTICIO": 2})
            self.assertEqual(self.contagens(ses), (0, 0, 0))

    def test_lote_parcial_nao_exclui_ausentes(self):
        with Session(self.engine) as ses:
            ensaiar(ses, [gasto(), gasto(uid="002")], MAP)
            ses.commit()
            v = ensaiar(ses, [gasto()], MAP, cobertura_completa=True)
            ses.commit()
            self.assertEqual(v.ausentes_na_origem, 1)
            self.assertEqual(self.contagens(ses), (1, 2, 2))

    def test_rollback_do_chamador_reverte_tudo(self):
        with Session(self.engine) as ses:
            ensaiar(ses, [gasto()], MAP)
            ses.rollback()
            self.assertEqual(self.contagens(ses), (0, 0, 0))

    def test_963_despesas_ficticias_uma_unica_vez(self):
        dados = [gasto(uid=f"FICTICIO-{i:04}") for i in range(963)]
        with Session(self.engine) as ses:
            a = ensaiar(ses, dados, MAP)
            ses.commit()
            self.assertEqual(a.novos, 963)
            self.assertEqual(self.contagens(ses), (1, 963, 963))
            b = ensaiar(ses, dados, MAP)
            self.assertEqual(b.inalterados, 963)
            ses.commit()
            self.assertEqual(self.contagens(ses), (1, 963, 963))

    def test_bloqueia_sqlite_em_arquivo(self):
        # Nenhuma tentativa de acesso ao Neon ou a uma conexão externa.
        with Session(create_engine("sqlite:///arquivo_ficticio_nunca_criar.db")) as s:
            with self.assertRaisesRegex(RuntimeError, "somente em SQLite em memória"):
                ensaiar(s, [gasto()], MAP)
