# -*- coding: utf-8 -*-
"""Testes OFFLINE do simulador V6.7; sem banco, API, rede ou envio."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from whatsapp_preenvio import avaliar_preenvio


def base(**mudancas):
    dados = dict(
        status_fila="preparada", consentimento=True, telefone_ativo=True,
        usuario_ativo=True, destinatario_autorizado=True,
        vinculos_consistentes=True, evento_origem_id=9,
        diagnostico_atual="coerente", diagnostico_historico="nao_comprovado",
        duplicidade_detectada=False,
    )
    dados.update(mudancas)
    return dados


class TestPreEnvioV67(unittest.TestCase):
    def validar(self, esperado, **mudancas):
        resposta = avaliar_preenvio(**base(**mudancas))
        self.assertEqual(resposta["situacao"], esperado)
        self.assertIs(resposta["envio_autorizado"], False)
        self.assertTrue(resposta["motivo"])

    def test_base_nao_autoriza(self):
        self.validar("pendente_de_validacao_operacional")

    def test_cancelada_impedida(self):
        self.validar("impedido", status_fila="cancelada")

    def test_status_desconhecido_revisar(self):
        self.validar("revisar", status_fila="enviada")

    def test_sem_consentimento_impedido(self):
        self.validar("impedido", consentimento=False)

    def test_telefone_inativo_impedido(self):
        self.validar("impedido", telefone_ativo=False)

    def test_usuario_inativo_impedido(self):
        self.validar("impedido", usuario_ativo=False)

    def test_destinatario_sem_acesso_impedido(self):
        self.validar("impedido", destinatario_autorizado=False)

    def test_vinculos_inconsistentes_impedido(self):
        self.validar("impedido", vinculos_consistentes=False)

    def test_duplicidade_impedida(self):
        self.validar("impedido", duplicidade_detectada=True)

    def test_historico_superado_impedido(self):
        self.validar("impedido", diagnostico_historico="superado")

    def test_situacao_desatualizada_impedida(self):
        self.validar("impedido", diagnostico_atual="possivelmente_desatualizado")

    def test_legado_revisar(self):
        self.validar("revisar", evento_origem_id=None)

    def test_id_invalido_revisar(self):
        self.validar("revisar", evento_origem_id=True)

    def test_historico_revisar(self):
        self.validar("revisar", diagnostico_historico="revisar")

    def test_historico_informativo_revisar(self):
        self.validar("revisar", diagnostico_historico="informativo")

    def test_historico_desconhecido_revisar(self):
        self.validar("revisar", diagnostico_historico="desconhecido")

    def test_situacao_atual_revisar(self):
        self.validar("revisar", diagnostico_atual="revisar")

    def test_booleano_invalido_revisar(self):
        self.validar("revisar", consentimento=1)

    def test_entrada_ausente_revisar(self):
        self.validar("revisar", destinatario_autorizado=None)

    def test_situacao_informativa_revisar(self):
        self.validar("revisar", diagnostico_atual="informativo")


if __name__ == "__main__":
    unittest.main()
