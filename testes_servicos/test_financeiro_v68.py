# -*- coding: utf-8 -*-
"""V6.8: testes inteiramente em SQLite em memória; sem produção ou e-mail."""
import ast
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import uuid4

from fastapi import HTTPException, UploadFile
import test_servicos as base
import financeiro_api as f
import main as principal

models = base.models


def req(uid):
    return SimpleNamespace(state=SimpleNamespace(auth_user_id=uid, auth_user_role={
        1: 'Controladoria', 2: 'Financeiro', 3: 'Solicitante', 4: 'Checklist', 5: 'Solicitante'}[uid],
        auth_user_name={1: 'Gestora', 2: 'Financeiro', 3: 'Ana', 4: 'Zelador', 5: 'Ana'}[uid]))


def pdf():
    return UploadFile(filename='comprovante.pdf', file=BytesIO(b'%PDF-1.4\n% pagamento em teste'))


class TesteFinanceiroV68(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.drop_all(base.stub.engine)
        models.Base.metadata.create_all(base.stub.engine)
        self.db = base.stub.SessionLocal()
        self.db.add(models.Condominio(id=1, nome='Condomínio Teste'))
        for uid, nome, perfil in [(1, 'Gestora', 'Controladoria'), (2, 'Financeiro', 'Financeiro'),
                                  (3, 'Ana', 'Solicitante'), (4, 'Zelador', 'Checklist'),
                                  (5, 'Ana', 'Solicitante')]:
            self.db.add(models.Usuario(id=uid, nome=nome, email=f'{uid}@teste.local', senha='x', perfil=perfil,
                                      condominio_id=1 if uid == 4 else None))
        self.db.add(models.Solicitacao(id=10, numero='SOL-0010', condominio='Condomínio Teste', condominio_id=1,
                    categoria='Serviço', fornecedor='Empresa', descricao='Teste de pagamento',
                    valor=1500., valor_aprovado=1000., valor_realizado=0., solicitante='Ana', solicitante_id=3,
                    status='Aprovada'))
        self.db.add(models.Solicitacao(id=11, numero='SOL-0011', condominio='Condomínio Teste', condominio_id=1,
                    categoria='Serviço', fornecedor='Empresa', descricao='Pendente',
                    valor=1500., valor_aprovado=0., solicitante='Ana', solicitante_id=5,
                    status='Aprovação pendente'))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def pagar(self, valor, chave=None, uid=1, sol=10, arquivo=None):
        return f.registrar_pagamento(sol, req(uid), date.today(), valor, chave or str(uuid4()),
                                    'Pagamento de teste', arquivo or pdf(), self.db)

    def test_01_conversao_precisa_e_validacao(self):
        self.assertEqual(f.centavos('700.00'), 70000)
        self.assertEqual(f.centavos('400'), 40000)
        for valor in ('0', '-4.00', '1.001', '1e6', 'NaN', '0,00', '01.00'):
            with self.subTest(valor=valor), self.assertRaises(HTTPException):
                f.centavos(valor)

    def test_02_contas_duplicadas_pelo_nome_nao_alteram_identidade(self):
        self.assertEqual(self.db.get(models.Solicitacao, 10).solicitante_id, 3)
        self.assertEqual(self.db.get(models.Solicitacao, 11).solicitante_id, 5)

    def test_03_financeiro_pode_visualizar_lista(self):
        lista = f.listar_solicitacoes(req(2), self.db)['solicitacoes']
        self.assertEqual(len(lista), 2)
        self.assertEqual(lista[0]['numero'], 'SOL-0011')

    def test_04_solicitante_e_zelador_rejeitados_em_financeiro(self):
        for uid in (3, 4, 5):
            with self.subTest(uid=uid), self.assertRaises(HTTPException) as cm:
                f.listar_solicitacoes(req(uid), self.db)
            self.assertEqual(cm.exception.status_code, 403)

    def test_21_financeiro_nao_pode_registrar_pagamento(self):
        with self.assertRaises(HTTPException) as cm:
            self.pagar('200.00', uid=2)
        self.assertEqual(cm.exception.status_code, 403)
        self.assertEqual(self.db.query(models.FinanceiroLancamento).count(), 0)

    def test_22_financeiro_pode_consultar_historico_mas_nao_alterar(self):
        original = self.pagar('45.10', uid=1)['lancamento']['id']
        historico = f.listar_lancamentos(10, req(2), self.db)
        self.assertEqual(historico['lancamentos'][0]['id'], original)
        self.assertEqual(historico['resumo']['pago_centavos'], 4510)
        with self.assertRaises(HTTPException) as cm:
            f.estornar_pagamento(original, f.EstornoEntrada(
                motivo='Tentativa de alterar pelo Financeiro', chave_operacao=str(uuid4())),
                req(2), self.db)
        self.assertEqual(cm.exception.status_code, 403)
        self.assertEqual(self.db.query(models.FinanceiroLancamento).count(), 1)

    def test_05_pagamentos_e_excedente_nao_bloqueado(self):
        p1 = self.pagar('700.00')['resumo']
        self.assertEqual(p1['pago_centavos'], 70000)
        self.assertFalse(p1['alerta_sobrepagamento'])
        p2 = self.pagar('400.00')
        self.assertEqual(p2['resumo']['pago_centavos'], 110000)
        self.assertEqual(p2['resumo']['excedente_centavos'], 10000)
        self.assertTrue(p2['resumo']['alerta_sobrepagamento'])
        self.assertEqual(p2['lancamento']['excedente_centavos_no_lancamento'], 10000)
        self.assertEqual(len(f.listar_lancamentos(10, req(1), self.db)['lancamentos']), 2)

    def test_06_estorno_preserva_original_e_alerta_historico(self):
        self.pagar('700.00')
        original = self.pagar('400.00')['lancamento']['id']
        estorno = f.estornar_pagamento(original, f.EstornoEntrada(motivo='Comprovante incorreto',
                       chave_operacao=str(uuid4())), req(1), self.db)
        self.assertEqual(estorno['resumo']['pago_centavos'], 70000)
        self.assertEqual(estorno['resumo']['excedente_centavos'], 0)
        eventos = f.listar_lancamentos(10, req(1), self.db)['lancamentos']
        self.assertEqual(len(eventos), 3)
        self.assertEqual(eventos[1]['excedente_centavos_no_lancamento'], 10000)
        self.assertEqual(eventos[-1]['estorno_de_id'], original)

    def test_07_estorno_so_controladoria(self):
        original = self.pagar('30')['lancamento']['id']
        for uid in (2, 3):
            with self.subTest(uid=uid), self.assertRaises(HTTPException) as cm:
                f.estornar_pagamento(original, f.EstornoEntrada(motivo='Comprovante duplicado',
                              chave_operacao=str(uuid4())), req(uid), self.db)
            self.assertEqual(cm.exception.status_code, 403)

    def test_08_nao_estorna_duas_vezes(self):
        original = self.pagar('30')['lancamento']['id']
        f.estornar_pagamento(original, f.EstornoEntrada(motivo='Comprovante duplicado',
                              chave_operacao=str(uuid4())), req(1), self.db)
        with self.assertRaises(HTTPException) as cm:
            f.estornar_pagamento(original, f.EstornoEntrada(motivo='Tentativa duplicada',
                              chave_operacao=str(uuid4())), req(1), self.db)
        self.assertEqual(cm.exception.status_code, 409)

    def test_09_idempotencia_mantem_um_pagamento(self):
        chave = str(uuid4())
        self.pagar('123.45', chave)
        with self.assertRaises(HTTPException) as cm:
            self.pagar('123.45', chave)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertEqual(self.db.query(models.FinanceiroLancamento).count(), 1)

    def test_10_compra_pendente_nao_recebe_pagamento(self):
        with self.assertRaises(HTTPException) as cm:
            self.pagar('10', sol=11)
        self.assertEqual(cm.exception.status_code, 409)

    def test_11_comprovante_invalido_rejeitado(self):
        arquivo = UploadFile(filename='pagamento.pdf', file=BytesIO(b'EXE nao e PDF'))
        with self.assertRaises(HTTPException) as cm:
            self.pagar('100', arquivo=arquivo)
        self.assertEqual(cm.exception.status_code, 422)

    def test_12_comprovante_grande_rejeitado(self):
        arquivo = UploadFile(filename='pagamento.pdf', file=BytesIO(b'%PDF-' + b'0' * (f.MAX_COMPROVANTE + 1)))
        with self.assertRaises(HTTPException) as cm:
            self.pagar('100', arquivo=arquivo)
        self.assertEqual(cm.exception.status_code, 413)

    def test_13_download_com_permissao(self):
        original = self.pagar('100')['lancamento']['id']
        saida = f.baixar_comprovante(original, req(2), self.db)
        self.assertEqual(saida.headers['content-type'], 'application/octet-stream')
        self.assertEqual(saida.headers['x-content-type-options'], 'nosniff')
        with self.assertRaises(HTTPException) as cm:
            f.baixar_comprovante(original, req(3), self.db)
        self.assertEqual(cm.exception.status_code, 403)

    def test_14_sem_exclusao_lancamentos_por_api(self):
        # Não há rota DELETE de lançamentos ou comprovantes, nem PUT de pagamentos.
        raiz = Path(__file__).resolve().parents[1] / 'backend' / 'financeiro_api.py'
        tree = ast.parse(raiz.read_text(encoding='utf8'))
        nomes = [a.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                 for a in [n.func] if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
                 and a.value.id == 'router']
        self.assertNotIn('delete', nomes)
        self.assertNotIn('put', nomes)

    def test_15_resumo_separa_realizado_de_pago(self):
        sol = self.db.get(models.Solicitacao, 10)
        sol.valor_realizado = 990
        self.db.commit()
        resumo = f.listar_solicitacoes(req(1), self.db)['solicitacoes'][1]
        self.assertIsNone(resumo['realizado_centavos'])  # Só finalizada é realizado.
        self.pagar('300')
        resumo = f.listar_solicitacoes(req(1), self.db)['solicitacoes'][1]
        self.assertEqual(resumo['pago_centavos'], 30000)
        self.assertEqual(resumo['aprovado_centavos'], 100000)

    def test_16_matriz_do_middleware(self):
        main = Path(__file__).resolve().parents[1] / 'backend' / 'main.py'
        tree = ast.parse(main.read_text(encoding='utf8'))
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_permissao_rota')
        namespace = {'re': __import__('re')}
        exec(compile(ast.Module(body=[func], type_ignores=[]), '<matriz>', 'exec'), namespace)
        regra = namespace['_permissao_rota']
        self.assertFalse(regra('POST','/financeiro/solicitacoes/10/pagamentos','Financeiro'))
        self.assertTrue(regra('POST','/financeiro/solicitacoes/10/pagamentos','Controladoria'))
        self.assertTrue(regra('GET','/financeiro/solicitacoes/10/lancamentos','Financeiro'))
        self.assertTrue(regra('GET','/financeiro/comprovantes/7','Financeiro'))
        self.assertFalse(regra('PUT','/solicitacoes/10/status','Financeiro'))
        self.assertFalse(regra('DELETE','/solicitacoes/10','Financeiro'))
        self.assertTrue(regra('POST','/financeiro/lancamentos/3/estornar','Controladoria'))
        self.assertFalse(regra('POST','/financeiro/lancamentos/3/estornar','Financeiro'))
        self.assertFalse(regra('GET','/financeiro/solicitacoes','Solicitante'))


    def test_17_isolamento_por_id_com_nomes_iguais(self):
        self.assertEqual(principal._solicitacao_visivel(self.db, req(3).state, 10).id, 10)
        with self.assertRaises(HTTPException) as cm:
            principal._solicitacao_visivel(self.db, req(5).state, 10)
        self.assertEqual(cm.exception.status_code, 403)
        proprio = principal.listar_solicitacoes(req(3), self.db)
        self.assertEqual([s.id for s in proprio], [10])
        outro = principal.listar_solicitacoes(req(5), self.db)
        self.assertEqual([s.id for s in outro], [11])

    def test_18_financeiro_nao_exclui_compra_ou_altera_aprovacao(self):
        self.pagar('20')
        with self.assertRaises(HTTPException) as cm:
            principal.excluir_solicitacao(10, req(1), self.db)
        self.assertEqual(cm.exception.status_code, 409)
        with self.assertRaises(HTTPException) as cm2:
            principal.atualizar_status_solicitacao(10, principal.schemas.StatusUpdate(
                    status='Reprovada', valor_aprovado=0), self.db)
        self.assertEqual(cm2.exception.status_code, 409)

    def test_19_sol_legada_sem_vinculo_nao_visivel_ao_homonimo(self):
        sol = self.db.get(models.Solicitacao, 10)
        sol.solicitante_id = None
        self.db.commit()
        for uid in (3, 5):
            with self.subTest(uid=uid), self.assertRaises(HTTPException) as cm:
                principal._solicitacao_visivel(self.db, req(uid).state, 10)
            self.assertEqual(cm.exception.status_code, 403)

    def test_20_vinculo_manual_com_auditoria(self):
        sol = self.db.get(models.Solicitacao, 10)
        sol.solicitante_id = None
        self.db.commit()
        resultado = principal.vincular_solicitante_legado(10,
            principal.VincularSolicitanteEntrada(usuario_id=3,
                justificativa='Autoria verificada no pedido assinado'), req(1), self.db)
        self.assertEqual(resultado['solicitante_id'], 3)
        self.assertEqual(principal._solicitacao_visivel(self.db, req(3).state, 10).id, 10)
        self.assertTrue(self.db.query(models.HistoricoSolicitacao).filter_by(solicitacao_id=10).first())
        with self.assertRaises(HTTPException) as cm:
            principal.vincular_solicitante_legado(10,
                principal.VincularSolicitanteEntrada(usuario_id=5,
                    justificativa='Tentativa de reatribuir vinculo'), req(1), self.db)
        self.assertEqual(cm.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
