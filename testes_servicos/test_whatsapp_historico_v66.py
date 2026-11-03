"""V6.6: 16 testes puros + 5 testes de integracao SQLite em memoria.

Nao se conecta ao PostgreSQL ou a servicos externos.
"""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
import test_multiplos_participantes as base
import whatsapp_alertas as wa
from whatsapp_historico import avaliar_historico

models = base.models

def evento(identificador, acao, autor_id, servico_id=3):
    return {"id": identificador, "acao": acao, "autor_id": autor_id, "servico_id": servico_id}


HISTORICO_0003 = [
    evento(3, "criado", 1),
    evento(4, "confirmar", 1),
    evento(5, "confirmar", 3),
    evento(6, "iniciar", 3),
    evento(7, "concluir", 3),
    evento(8, "devolver", 1),
    evento(9, "concluir", 3),
]


class TestesV66(unittest.TestCase):
    def avalia(self, tipo, origem, destinatario, eventos=HISTORICO_0003, servico=3):
        return avaliar_historico(tipo=tipo, evento_origem_id=origem,
                                 destinatario_id=destinatario, servico_id=servico,
                                 eventos=eventos)

    def test_01_nova_tarefa_superada_confirmacao_zelador(self):
        a = self.avalia("nova_tarefa", 3, 3)
        self.assertEqual((a["situacao"], a["evento_superador"]), ("superado", 5))

    def test_02_confirmacao_de_outro_usuario_nao_supera(self):
        h = HISTORICO_0003[:2]
        self.assertEqual(self.avalia("nova_tarefa", 3, 3, h)["situacao"], "nao_comprovado")

    def test_03_devolucao_superada_por_conclusao_do_executor(self):
        a = self.avalia("devolucao", 8, 3)
        self.assertEqual((a["situacao"], a["evento_superador"]), ("superado", 9))

    def test_04_conclusao_de_outro_usuario_nao_supera_devolucao(self):
        h = [evento(8, "devolver", 1), evento(9, "concluir", 4)]
        self.assertEqual(self.avalia("devolucao", 8, 3, h)["situacao"], "nao_comprovado")

    def test_05_primeira_fiscalizacao_superada_pela_devolucao(self):
        a = self.avalia("pronto_fiscalizacao", 7, 1)
        self.assertEqual((a["situacao"], a["evento_superador"]), ("superado", 8))

    def test_06_segunda_fiscalizacao_nao_e_confundida_com_primeira(self):
        self.assertEqual(self.avalia("pronto_fiscalizacao", 9, 1)["situacao"], "nao_comprovado")

    def test_07_fiscalizacao_superada_por_acao_do_fiscalizador(self):
        h = [evento(11, "concluir", 3), evento(12, "fiscalizar", 1)]
        self.assertEqual(self.avalia("pronto_fiscalizacao", 11, 1, h)["situacao"], "superado")

    def test_08_confirmacao_de_fiscalizador_supera_designacao(self):
        self.assertEqual(self.avalia("designacao_fiscal", 3, 1)["situacao"], "superado")

    def test_09_validacao_final_superada_por_validacao(self):
        h = [evento(11, "fiscalizar", 1), evento(12, "validar", 1)]
        self.assertEqual(self.avalia("validacao_final", 11, 1, h)["situacao"], "superado")

    def test_10_aviso_encerramento_informativo(self):
        h = [evento(12, "validar", 1)]
        self.assertEqual(self.avalia("servico_validado", 12, 3, h)["situacao"], "informativo")

    def test_11_sem_evento_origem_eh_revisar(self):
        self.assertEqual(self.avalia("nova_tarefa", None, 3)["situacao"], "revisar")

    def test_12_evento_origem_incompativel_eh_revisar(self):
        self.assertEqual(self.avalia("devolucao", 7, 3)["situacao"], "revisar")

    def test_13_historico_de_outro_servico_eh_revisar(self):
        h = [evento(3, "criado", 1, servico_id=99)]
        self.assertEqual(self.avalia("nova_tarefa", 3, 3, h)["situacao"], "revisar")

    def test_14_autor_ausente_para_confirmacao_eh_revisar(self):
        h = [evento(3, "criado", 1), evento(5, "confirmar", None)]
        self.assertEqual(self.avalia("nova_tarefa", 3, 3, h)["situacao"], "revisar")

    def test_15_acao_desconhecida_eh_revisar(self):
        h = [evento(3, "criado", 1), evento(4, "status_customizado", 3)]
        self.assertEqual(self.avalia("nova_tarefa", 3, 3, h)["situacao"], "revisar")

    def test_16_mesmo_id_de_evento_duplicado_eh_revisar(self):
        h = [evento(3, "criado", 1), evento(3, "confirmar", 3)]
        self.assertEqual(self.avalia("nova_tarefa", 3, 3, h)["situacao"], "revisar")


class IntegracaoPreviaHistoricaV66(unittest.TestCase):
    def setUp(self):
        self.cenario = base.MultiplosParticipantesTeste()
        self.cenario.setUp()
        self.db = self.cenario.db

    def tearDown(self):
        self.cenario.tearDown()

    def autorizar(self, *usuarios):
        for uid in usuarios:
            wa.salvar_numero_admin(
                uid, wa.NumeroAdministrado(numero=f'4399999{uid:04d}'),
                self.cenario.req(1), self.db)
            wa.salvar_preferencias(
                wa.PreferenciaEntrada(receber_alertas=True),
                self.cenario.req(uid), self.db)

    def previas(self, uid=1):
        with patch.dict(os.environ, {'FRONTEND_PUBLIC_URL': 'http://127.0.0.1:5173'}):
            return wa.listar_previas_fila(self.cenario.req(uid), self.db)['previa']

    def aviso(self, sid, evento, destino):
        return next(x for x in self.previas() if x['servico_id'] == sid and
                    x['evento'] == evento and x['destinatario'])

    def test_17_nova_tarefa_historico_muda_sem_cancelar_fila(self):
        self.autorizar(2)
        s = self.cenario.novo(execs=[2], fisc=[6])
        sid = s['id']
        a = next(x for x in self.previas() if x['servico_id'] == sid and x['evento'] == 'nova_tarefa')
        self.assertEqual(a['diagnostico_historico']['situacao'], 'nao_comprovado')
        self.cenario.acao(s, 2, 'confirmar')
        a = next(x for x in self.previas() if x['servico_id'] == sid and x['evento'] == 'nova_tarefa')
        self.assertEqual(a['diagnostico_historico']['situacao'], 'superado')
        self.assertIsInstance(a['diagnostico_historico']['evento_superador'], int)
        fila = self.db.query(models.FilaWhatsApp).filter_by(servico_id=sid).all()
        self.assertEqual([x.status for x in fila], ['preparada'])

    def test_18_devolucao_superada_por_ajustes(self):
        self.autorizar(2)
        s = self.cenario.novo(execs=[2], fisc=[6])
        self.cenario.acao(s, 2, 'confirmar')
        self.cenario.acao(s, 6, 'confirmar')
        self.cenario.acao(s, 2, 'iniciar')
        self.cenario.acao(s, 2, 'concluir', 'Primeiro ciclo encerrado.')
        self.cenario.acao(s, 6, 'devolver', 'Devolucao para novo teste.')
        a = next(x for x in self.previas() if x['servico_id'] == s['id'] and x['evento'] == 'devolucao')
        self.assertEqual(a['diagnostico_historico']['situacao'], 'nao_comprovado')
        self.cenario.acao(s, 2, 'concluir', 'Segundo ciclo encerrado.')
        a = next(x for x in self.previas() if x['servico_id'] == s['id'] and x['evento'] == 'devolucao')
        self.assertEqual(a['diagnostico_historico']['situacao'], 'superado')

    def test_19_dois_ciclos_fiscalizacao_independentes(self):
        self.autorizar(6)
        s = self.cenario.novo(execs=[2], fisc=[6])
        self.cenario.acao(s, 2, 'confirmar')
        self.cenario.acao(s, 6, 'confirmar')
        self.cenario.acao(s, 2, 'iniciar')
        self.cenario.acao(s, 2, 'concluir', 'Primeiro ciclo encerrado.')
        self.cenario.acao(s, 6, 'devolver', 'Revisar trabalho efetuado.')
        self.cenario.acao(s, 2, 'concluir', 'Segundo ciclo encerrado.')
        avisos = [x for x in self.previas() if x['servico_id'] == s['id'] and x['evento'] == 'pronto_fiscalizacao']
        self.assertEqual(len(avisos), 2)
        self.assertEqual({x['diagnostico_historico']['situacao'] for x in avisos}, {'superado', 'nao_comprovado'})
        self.assertEqual(len({x['fila_id'] for x in avisos}), 2)

    def test_20_aviso_sem_evento_eh_revisar(self):
        self.autorizar(2)
        s = self.cenario.novo(execs=[2], fisc=[6])
        aviso = self.db.query(models.ServicoAviso).filter_by(servico_id=s['id'], usuario_id=2).first()
        aviso.evento_id = None
        self.db.commit()
        a = next(x for x in self.previas() if x['servico_id'] == s['id'] and x['evento'] == 'nova_tarefa')
        self.assertEqual(a['diagnostico_historico']['situacao'], 'revisar')

    def test_21_acesso_nao_controladoria_403(self):
        self.autorizar(2)
        self.cenario.novo(execs=[2], fisc=[6])
        with self.assertRaises(HTTPException) as erro:
            self.previas(uid=2)
        self.assertEqual(erro.exception.status_code, 403)


if __name__ == '__main__':
    unittest.main()
