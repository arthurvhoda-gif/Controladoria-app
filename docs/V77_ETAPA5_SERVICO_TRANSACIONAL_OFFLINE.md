## V7.7.5 — Protótipo de serviço transacional offline

**Escopo:** branch `inteligencia-custos-v77-20261111`. O módulo `backend/custos_servico_v77.py` **não é ligado à API** nem pode operar com banco Postgres nesta etapa: `ensaiar_aplicacao_sqlite_v77` recusa conexões que não sejam SQLite em memória.

### Proteções validadas

- Valida lote completo, condo/ID e hash antes de qualquer escrita.
- Só grava no banco descartável gerido pelo próprio teste; nenhuma planilha é lida.
- Segunda importação idêntica retorna `inalterados`, sem nova despesa, lote ou evento.
- Mudanças de valor/descrição/categoria atualizam registro e registram evento com hash anterior/novo.
- Registros ausentes são sinalizados apenas, nunca excluídos.
- O chamador controla `commit`/`rollback`; erro no lote impede gravação parcial.
- Cobertura de 963 despesas totalmente fictícias e testes de restrição de ambiente.
- O script SQL executado manualmente no Neon de testes anteriormente deixou 1 despesa marcada `origem='teste_ficticio_v77'`; ela **não é dado real**. Não deletar sem autorização específica.

### Pendências antes de usar com as planilhas reais

1. Criar API autenticada só para Controladoria e verificar RBAC por condomínio.
2. Validar migração, constraints, índices e disponibilidade do banco homologado.
3. Controle transacional e concorrência Postgres (advisory lock/transação serializável).
4. Validar assinatura/resumo de arquivo, 963 despesas / R$ 1.042.114,86, e reconciliação de histórico e pagamentos existentes.
5. Autorização explícita da Controladoria para primeira escrita de dados reais.
6. Separar demonstrativos de custos históricos de pagamentos da Central Financeira.
