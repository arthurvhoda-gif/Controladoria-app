"""Testes OFFLINE da vigência indicativa de avisos; não conecta a nenhum banco."""
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BASE))
from whatsapp_validade import avaliar_vigencia as avaliar


class VigenciaFilaV64Teste(unittest.TestCase):
    def confere(self, esperado, evento, status_servico, **kwargs):
        resultado = avaliar(evento, status_servico, **kwargs)
        self.assertEqual(resultado['situacao'], esperado)
        self.assertTrue(resultado['motivo'])

    def test_nova_tarefa_aguardando_ciencia(self):
        self.confere('coerente', 'nova_tarefa', 'Aguardando ciência',
                     papel='executor', status_participante='Aguardando ciência')

    def test_nova_tarefa_apos_ciencia(self):
        self.confere('possivelmente_desatualizado', 'nova_tarefa', 'Em andamento',
                     papel='executor', status_participante='Recebido')

    def test_nova_tarefa_individual_pendente_com_outra_execucao(self):
        self.confere('coerente', 'nova_tarefa', 'Em andamento',
                     papel='executor', status_participante='Aguardando ciência')

    def test_fiscalizador_designado_sem_ciencia(self):
        self.confere('coerente', 'designacao_fiscal', 'Aguardando ciência',
                     papel='fiscalizador', status_participante='Aguardando ciência')

    def test_fiscalizacao_pendente(self):
        self.confere('coerente', 'pronto_fiscalizacao', 'Aguardando fiscalização',
                     papel='fiscalizador', status_participante='Recebido')

    def test_fiscalizacao_ja_aprovada(self):
        self.confere('possivelmente_desatualizado', 'pronto_fiscalizacao', 'Aguardando fiscalização',
                     papel='fiscalizador', status_participante='Aprovado')

    def test_devolucao_em_ajustes(self):
        self.confere('coerente', 'devolucao', 'Em andamento',
                     papel='executor', status_participante='Em andamento')

    def test_devolucao_superada(self):
        self.confere('possivelmente_desatualizado', 'devolucao', 'Aguardando fiscalização',
                     papel='executor', status_participante='Finalizado')

    def test_validacao_final_do_criador(self):
        self.confere('coerente', 'validacao_final', 'Aguardando validação',
                     destinatario_eh_criador=True)

    def test_validacao_final_destinatario_duvidoso(self):
        self.confere('revisar', 'validacao_final', 'Aguardando validação',
                     destinatario_eh_criador=False)

    def test_encerramento_informativo(self):
        self.confere('informativo', 'servico_validado', 'Concluído')

    def test_encerramento_inconsistente(self):
        self.confere('revisar', 'servico_validado', 'Em andamento')

    def test_papel_divergente(self):
        self.confere('revisar', 'pronto_fiscalizacao', 'Aguardando fiscalização',
                     papel='executor', status_participante='Recebido')

    def test_participante_ausente(self):
        self.confere('revisar', 'nova_tarefa', 'Aguardando ciência')

    def test_evento_desconhecido(self):
        self.confere('revisar', 'mensagem_desconhecida', 'Aguardando ciência')

    def test_ciclo_repetido_nao_pode_ser_diferenciado_pelo_status(self):
        # Dois avisos de fiscalizacao de ciclos diferentes podem ter MESMO estado atual.
        primeiro = avaliar('pronto_fiscalizacao', 'Aguardando fiscalização',
                           papel='fiscalizador', status_participante='Recebido')
        segundo = avaliar('pronto_fiscalizacao', 'Aguardando fiscalização',
                          papel='fiscalizador', status_participante='Recebido')
        self.assertEqual(primeiro, segundo)
        self.assertEqual(primeiro['situacao'], 'coerente')
        # Portanto, nenhum desses resultados autoriza enviar/cancelar.


if __name__ == '__main__':
    unittest.main()
