# Controladoria Haize V7.7 — Etapa 1 (somente GitHub e dados fictícios)

## Escopo aprovado

Preparação do **modelo de despesas históricas e prévia de importação** para substituir o BI antigo. Esta etapa **não acessa** as 10 planilhas reais, **não altera Neon**, **não altera main/produção** e **não cria rotas de importação**.

Branch isolada: `inteligencia-custos-v77-20261111`, derivada da branch de testes V7.6.

### O que foi implementado

- `backend/custos_importacao_v77.py`: normalizador/validador puro e simulação de conciliação de lotes. Não acessa a rede ou banco.
- `backend/custos_historicos_v77.py`: modelo SQLAlchemy **inativo** de três tabelas propostas: lote de importação, despesas históricas, eventos de alteração. Não é importado por `main.py` nem adicionado às migrações.
- `testes_servicos/test_custos_importacao_v77.py`: testes com dados inteiramente inventados e SQLite **somente em memória**. Inclui lote fictício de 963 registros, centavos exatos, duplicidades, alterações, datas inválidas e referências entre condomínios.
- Pipeline de regressão da nova branch habilitado no GitHub Actions, com `DATABASE_URL=sqlite://`. Não tem segredos nem credenciais do usuário.

### Especificação do dado histórico

A estrutura preserva `condominio_id`, fonte, `id_origem` da coluna L, data original, competência no primeiro dia do mês, categoria original e chave padronizada, descrição e valor em **centavos inteiros**, além de hash SHA-256 para detectar alterações.

**Chave única:** `(condominio_id, origem, id_origem)`. IDs iguais de condomínios diferentes são válidos.

**Proteção contra dupla contagem:** histórico não se mistura automaticamente com `solicitacoes` ou `financeiro_lancamentos`. Futuros indicadores deverão distinguir essas fontes explicitamente.

**Atualizações futuras:** prévia compara lote validado com situação conhecida, classificando como novos, alterados ou inalterados. Registros ausentes em um novo arquivo **não são excluídos**. O operador deve declarar se o lote representa cobertura completa para que ausências sejam apenas sinalizadas, sem ação automática. O modelo prevê trilha append-only de eventos, ainda não ativada.

**Validação fail-closed:** todo o lote é recusado se houver identificadores repetidos por condomínio, nomes sem mapeamento aprovado para IDs do cadastro, categoria não classificada, valor malformado/float/mais que duas casas, competência inválida, campos vazios ou valores fora do limite. Um registro recusado não é ignorado silenciosamente.

### Limites e decisões para a etapa 2

1. Rever com a Controladoria o mapeamento dos nomes das 10 planilhas aos IDs reais dos condomínios. Este mapeamento **não é criado automaticamente**.
2. Definir como a importação será autorizada, auditada e revertida antes de escrever no Neon de testes.
3. Implementar uma migração explícita para tabelas novas, após aprovação. **Não ativar estas tabelas por mera inicialização do backend.**
4. Incluir confirmação de totais/quantidades dos 963 registros e `R$ 1.042.114,86` no lote real antes do primeiro commit no banco de testes.
5. Verificar regras de créditos e estornos, pois valores negativos são preservados, mas não rotulados automaticamente como reembolsos.
6. Os 963 lançamentos devem ser vinculados à fonte histórica, nunca somados automaticamente a solicitações e pagamentos da Central Financeira.

### Testes de regressão

O workflow existente `.github/workflows/haize-v70.yml` foi estendido para executar na branch isolada. O job **Testes Python (sem producao)** usa `python -m unittest discover -s testes_servicos -p 'test_*.py' -v` e descobre automaticamente os novos testes. A suíte inteira também executa verificações de segurança, frontend e banco PostgreSQL **descartável de CI**, sem banco real da Haize.

Nenhum deploy é solicitado nesta etapa. Não há mudança em `backend/main.py`, `backend/models.py` ou arquivos de produção.
