"""Testes offline do vinculo aviso -> evento (V6.5).

Executa as funcoes reais extraidas de servicos_api.py sem importar app, banco
ou rotas; FakeDB e FakeModels impedem qualquer acesso a PostgreSQL/Neon.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / 'backend' / 'servicos_api.py'

class Registro:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = kwargs.get('id')

class Evento(Registro):
    pass

class Aviso(Registro):
    pass

class Fila(Registro):
    pass

class Pref(Registro):
    pass

class BancoFalso:
    def __init__(self):
        self.itens = []
        self.prefs = {}
        self.sequencia = 1

    def add(self, obj):
        self.itens.append(obj)

    def flush(self):
        for obj in self.itens:
            if getattr(obj, 'id', None) is None:
                obj.id = self.sequencia
                self.sequencia += 1

    def get(self, cls, uid):
        assert cls is Pref
        return self.prefs.get(uid)

    def coletar(self, tipo):
        return [x for x in self.itens if isinstance(x, tipo)]

def carregar_funcoes():
    arvore = ast.parse(ARQUIVO.read_text(encoding='utf-8'))
    nomes = {'evento', 'notificar', 'publicar_para'}
    funcoes = [n for n in arvore.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in nomes]
    assert {f.name for f in funcoes} == nomes
    modulo = ast.fix_missing_locations(ast.Module(body=funcoes, type_ignores=[]))
    modelos = SimpleNamespace(
        ServicoEvento=Evento, ServicoAviso=Aviso,
        FilaWhatsApp=Fila, PreferenciaWhatsApp=Pref,
    )
    ctx = {'models': modelos, 'agora': lambda: 'instante-de-teste',
           'push_automatico': SimpleNamespace(enfileirar_aviso=lambda *_: 0)}
    exec(compile(modulo, str(ARQUIVO), 'exec'), ctx)
    return ctx

class RastreabilidadeV65(unittest.TestCase):
    def setUp(self):
        self.ctx = carregar_funcoes()
        self.db = BancoFalso()
        self.servico = SimpleNamespace(id=17, titulo='Servico de teste')
        self.autor = SimpleNamespace(id=9, nome='Controladoria')

    def origem(self, acao='concluir'):
        return self.ctx['evento'](self.db, self.servico, self.autor, acao, 'Teste')

    def test_evento_retorna_registro_com_identificador(self):
        registro = self.origem()
        self.assertIsInstance(registro, Evento)
        self.assertIsNotNone(registro.id)
        self.assertEqual(registro.servico_id, 17)

    def test_aviso_guarda_origem(self):
        registro = self.origem()
        self.ctx['notificar'](self.db, 3, self.servico, 'Nova tarefa', evento_origem=registro)
        self.assertEqual(self.db.coletar(Aviso)[0].evento_id, registro.id)

    def test_ciclos_repetidos_nao_confundem_eventos(self):
        r1 = self.origem('concluir')
        self.ctx['notificar'](self.db, 3, self.servico, 'Pronto para fiscalizacao', evento_origem=r1)
        r2 = self.origem('concluir')
        self.ctx['notificar'](self.db, 3, self.servico, 'Pronto para fiscalizacao', evento_origem=r2)
        avisos = self.db.coletar(Aviso)
        self.assertEqual(len(avisos), 2)
        self.assertNotEqual(avisos[0].evento_id, avisos[1].evento_id)

    def test_multiplos_participantes_compartilham_evento(self):
        reg = self.origem()
        pessoas = [SimpleNamespace(usuario_id=3), SimpleNamespace(usuario_id=4)]
        self.ctx['publicar_para'](self.db, self.servico, pessoas, 'Pronto', evento_origem=reg)
        avisos = self.db.coletar(Aviso)
        self.assertEqual({a.usuario_id for a in avisos}, {3, 4})
        self.assertEqual({a.evento_id for a in avisos}, {reg.id})

    def test_mesmo_participante_nao_duplicado_no_mesmo_publicar(self):
        reg = self.origem()
        pessoas = [SimpleNamespace(usuario_id=3), SimpleNamespace(usuario_id=3)]
        self.ctx['publicar_para'](self.db, self.servico, pessoas, 'Pronto', evento_origem=reg)
        self.assertEqual(len(self.db.coletar(Aviso)), 1)

    def test_com_consentimento_fila_referencia_aviso(self):
        self.db.prefs[3] = Pref(consentimento=1, telefone='+5543999999999')
        reg = self.origem()
        self.ctx['notificar'](self.db, 3, self.servico, 'Nova tarefa', evento_origem=reg)
        aviso = self.db.coletar(Aviso)[0]
        fila = self.db.coletar(Fila)[0]
        self.assertEqual(aviso.evento_id, reg.id)
        self.assertEqual(fila.aviso_id, aviso.id)
        self.assertEqual(fila.status, 'preparada')

    def test_sem_consentimento_nao_coloca_na_fila(self):
        reg = self.origem()
        self.ctx['notificar'](self.db, 3, self.servico, 'Nova tarefa', evento_origem=reg)
        self.assertEqual(len(self.db.coletar(Aviso)), 1)
        self.assertEqual(self.db.coletar(Fila), [])

    def test_evento_de_outro_servico_rejeitado(self):
        reg = self.origem()
        diferente = SimpleNamespace(id=999, titulo='Outro')
        with self.assertRaises(ValueError):
            self.ctx['notificar'](self.db, 3, diferente, 'Nao pode', evento_origem=reg)
        self.assertEqual(len(self.db.coletar(Aviso)), 0)

    def test_chamada_legada_sem_origem_permanece_compativel(self):
        self.ctx['notificar'](self.db, 3, self.servico, 'Aviso antigo')
        self.assertIsNone(self.db.coletar(Aviso)[0].evento_id)

    def test_criacao_gera_evento_antes_de_notificar(self):
        src = ARQUIVO.read_text(encoding='utf-8')
        inicio = src.index('    db.add(servico)\n    db.flush()\n')
        fim = src.index('    db.commit()', inicio)
        bloco = src[inicio:fim]
        self.assertLess(bloco.index('evento_criacao = evento('), bloco.index('notificar(db, uid, servico'))
        self.assertIn('evento_origem=evento_criacao', bloco)

    def test_acoes_vinculam_todos_os_avisos(self):
        src = ARQUIVO.read_text(encoding='utf-8')
        inicio = src.index('def atualizar(servico_id: int,')
        bloco = src[inicio:]
        self.assertEqual(bloco.count('evento_atual = evento(db, servico, user,'), 6)
        self.assertEqual(bloco.count('evento_origem=evento_atual'), 4)

    def test_migracao_registrada_sem_execucao_automatica(self):
        texto = (RAIZ / 'migracoes' / 'v65_servicos_avisos_evento_id.sql').read_text(encoding='utf-8')
        self.assertIn('ADD COLUMN IF NOT EXISTS evento_id INTEGER', texto)
        self.assertIn('ON DELETE SET NULL', texto)
        self.assertIn('CREATE INDEX IF NOT EXISTS', texto)
        self.assertIn('COMMIT;', texto)

if __name__ == '__main__':
    unittest.main()
