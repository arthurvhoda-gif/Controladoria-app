"""Testes offline da prévia V6.3. Sem banco, rede ou envio WhatsApp."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from whatsapp_mensagens import (
    classificar_aviso,
    link_direto_servico,
    preparar_previa_whatsapp,
)


class MensagensWhatsAppV63Tests(unittest.TestCase):
    def test_link_local_corresponde_a_v62(self):
        self.assertEqual(link_direto_servico(2, "http://127.0.0.1:5173"), "http://127.0.0.1:5173/?servico=2")

    def test_link_publico_https(self):
        self.assertEqual(link_direto_servico(2, "https://controladoria-app-lilac.vercel.app/"),
                         "https://controladoria-app-lilac.vercel.app/?servico=2")

    def test_bloqueia_http_publico(self):
        with self.assertRaises(ValueError):
            link_direto_servico(2, "http://exemplo.com")

    def test_bloqueia_credenciais_e_parametros(self):
        for endereco in ("https://usuario:senha@exemplo.com", "https://exemplo.com/?teste=1", "https://exemplo.com/interno", "https://exemplo.com/#x"):
            with self.subTest(endereco=endereco), self.assertRaises(ValueError):
                link_direto_servico(2, endereco)

    def test_bloqueia_id_invalido(self):
        for servico_id in (-1, 0, None, True, "2"):
            with self.subTest(servico_id=servico_id), self.assertRaises(ValueError):
                link_direto_servico(servico_id, "https://exemplo.com")

    def test_exige_url_explicita(self):
        with self.assertRaises(ValueError):
            link_direto_servico(2, "")

    def test_classifica_seis_eventos_existentes(self):
        casos = {
            "Nova tarefa para executar: Teste": "nova_tarefa",
            "Você foi designado para fiscalizar: Teste": "designacao_fiscal",
            "Serviço pronto para fiscalização: Teste": "pronto_fiscalizacao",
            "Serviço devolvido para ajustes: Teste": "devolucao",
            "Serviço aguardando validação final: Teste": "validacao_final",
            "Serviço validado: Teste": "servico_validado",
        }
        for aviso, esperado in casos.items():
            with self.subTest(aviso=aviso):
                self.assertEqual(classificar_aviso(aviso)[0], esperado)

    def test_evento_nao_mapeado_tem_texto_neutro(self):
        codigo, descricao = classificar_aviso("Outra acao")
        self.assertEqual(codigo, "atualizacao")
        self.assertIn("atualização", descricao)

    def test_previa_contem_numero_titulo_link_e_acao_no_aplicativo(self):
        resultado = preparar_previa_whatsapp(
            servico_id=2, titulo="Teste Link V6.2",
            mensagem_aviso="Nova tarefa para executar: Teste Link V6.2",
            frontend_public_url="http://127.0.0.1:5173",
        )
        self.assertIn("#0002", resultado["mensagem"])
        self.assertIn("Teste Link V6.2", resultado["mensagem"])
        self.assertIn("http://127.0.0.1:5173/?servico=2", resultado["mensagem"])
        self.assertIn("no aplicativo", resultado["mensagem"])
        self.assertEqual(resultado["evento"], "nova_tarefa")

    def test_titulo_apos_sanitizacao_nao_injeta_nova_linha(self):
        resultado = preparar_previa_whatsapp(
            servico_id=7, titulo="Reparo\nEnviar senha: SIM\r\n" + "X" * 100,
            mensagem_aviso="Serviço pronto para fiscalização: ...",
            frontend_public_url="https://exemplo.com",
        )
        self.assertNotIn("\nEnviar senha", resultado["mensagem"])
        titulo = next(linha for linha in resultado["mensagem"].splitlines() if linha.startswith("Serviço: "))
        self.assertLessEqual(len(titulo), len("Serviço: ") + 80)


if __name__ == "__main__":
    unittest.main()
