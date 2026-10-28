"""Matriz de acesso baseada no método real do backend, sem acessar banco."""
import ast
import re
import unittest
from pathlib import Path

main_path = Path(__file__).resolve().parents[1] / 'backend' / 'main.py'
tree = ast.parse(main_path.read_text(encoding='utf-8'))
func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_permissao_rota')
mod = ast.Module(body=[func], type_ignores=[])
namespace = {'re': re}
exec(compile(mod, '<permissoes>', 'exec'), namespace)
permissao = namespace['_permissao_rota']

class TestePermissoes(unittest.TestCase):
    def test_acessos_e_negacoes(self):
        testes = [
            ('POST', '/servicos', 'Controladoria', True),
            ('POST', '/servicos', 'Checklist', False),
            ('POST', '/servicos', 'Solicitante', False),
            ('GET', '/servicos', 'Checklist', True),
            ('GET', '/servicos', 'Solicitante', True),
            ('GET', '/servicos/responsaveis', 'Checklist', False),
            ('GET', '/servicos/responsaveis', 'Controladoria', True),
            ('GET', '/servicos/35/historico', 'Checklist', True),
            ('POST', '/servicos/35/acoes', 'Checklist', True),
            ('DELETE', '/servicos/35', 'Controladoria', False),
            ('GET', '/servicos/35', 'Financeiro', False),
        ]
        for method, path, perfil, esperado in testes:
            with self.subTest(method=method, path=path, perfil=perfil):
                self.assertEqual(permissao(method, path, perfil), esperado)

if __name__ == '__main__':
    unittest.main()
