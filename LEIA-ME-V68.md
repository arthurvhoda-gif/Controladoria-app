# Controladoria Haize — Entrega A, primeira parte (V6.8)

Base: branch `central-servicos-notificacoes-2026`, commit `ddfbb99` (V6.7).

## O que inclui

- Regras de proprietário da solicitação por **ID de usuário** (nomes iguais não compartilham acesso), inclusive listagem e permissões para editar, iniciar, concluir e consultar anexos.
- Migração local com **backup completo `pg_dump`** antes de alterar o esquema, vinculação apenas quando houver correspondência única; pedidos legados sem identificação são bloqueados para solicitantes até revisão manual registrada pela Controladoria.
- `Financeiro` como perfil EXCLUSIVAMENTE DE CONSULTA: visualiza saldos, lançamentos, histórico e baixa comprovantes, sem registrar, estornar, aprovar/reprovar ou alterar solicitações.
- Livro append-only: lançamento de pagamento e lançamento separado de estorno. Valores em centavos e alerta de excedente no lançamento em que ocorre, preservando o histórico.
- Comprovantes dentro do PostgreSQL, não no disco temporário. Apenas PDF, PNG e JPG (até 5 MB; verificação de assinatura); download autenticado com attachment e nosniff.
- Duplicidade técnica por `chave_operacao` UUID v4 única, para proteção contra repetições de requisições; **não substitui conciliação bancária e regras de duplicidade de negócios**.
- Interface React com resumo, filtro, pagamentos parciais (lançados somente pela Controladoria), comprovantes, alertas, estorno somente pela Controladoria e cadastro de Financeiro de consulta.
- Os 139 testes V6.7 continuaram passando; após a correção das permissões, +22 testes V6.8 = 161 testes aprovados na cópia isolada com SQLite em memória. Compilação Vite da versão corrigida deve ser validada com `npm` no Windows do usuário.

## Ordem obrigatória no Windows (não em produção)

1. Confirme branch e HEAD com `git status -sb`.
2. Pare os processos locais de frontend e backend (`Ctrl+C` em seus CMDs); não altere produção.
3. Execute `py "%USERPROFILE%\Downloads\instalar_entrega_financeira_v68.py" --verificar`.
4. Se compatível, execute `py "%USERPROFILE%\Downloads\instalar_entrega_financeira_v68.py" --instalar`. Código original será copiado para `%LOCALAPPDATA%\HaizeControladoriaTestes\backups\v68_codigo_*` antes de alterações; nenhuma operação de Git ocorre.
5. Execute `"%LOCALAPPDATA%\HaizeControladoriaTestes\venv_v61\Scripts\python.exe" migracoes\migrar_financeiro_v68.py`. O script exige senha **local** digitada ocultamente e confirmação `MIGRAR-LOCAL`, salva um backup completo do banco de testes antes de criar coluna/tabelas. Exige ferramenta `pg_dump` de PostgreSQL disponível; se não estiver, falha antes de migrar.
6. Execute `set "ENABLE_CHECKLIST_EMAILS=false"` e `"%LOCALAPPDATA%\HaizeControladoriaTestes\venv_v61\Scripts\python.exe" -m unittest discover -s testes_servicos -p "test_*.py" -v`.
7. Execute `npm --prefix frontend run build`.
8. Inicie backend local somente após migração, frontend local com `VITE_API_URL=http://127.0.0.1:8001`. Faça testes visuais.
9. Revise `git diff --check` e `git diff --name-status`. Somente depois, selecione arquivos explicitamente para commit na branch dev.

## Teste de aceitação

- Compra aprovada R$1.000,00: pagar R$700,00 com comprovante e depois R$400,00 com outro. Total pago R$1.100,00, alerta de R$100,00 e dois lançamentos.
- Estornar R$400,00 pela Controladoria: cria **terceiro** lançamento, total líquido volta a R$700,00, alerta histórico preservado no segundo pagamento.
- Testar usuário Financeiro: **somente consulta** a Central Financeira, o livro de lançamentos e os comprovantes; não consegue registrar pagamentos, estornar, editar, aprovar, concluir nem excluir compras.
- Testar nomes iguais em duas contas de Solicitante: cada conta enxerga apenas solicitações com seu ID. Solicitação legada sem ID fica para revisão administrativa.

## Limitações a resolver antes do uso financeiro em produção

- **Não executar esta migração em produção**. Será necessário um roteiro de migração específico do Neon, backup, janela de manutenção, ordem de promoção e rollback.
- O cadastro de compras anterior ainda usa `Float`. O valor **pago novo** usa centavos; aprovado/solicitado/realizado anteriores são convertidos de forma aproximada para exibição. Revisar históricos legados antes de usá-los em auditorias.
- Não migra anexos antigos de compras/checklists que usam disco local. Essa é uma prioridade de segurança/persistência da etapa seguinte.
- A listagem financeira foi limitada a 1.000 solicitações; implementar paginação server-side antes que o volume cresça acima disso.
- Ainda não realiza conciliação bancária, confirmação de liquidação no banco ou detecção semântica de pagamentos duplicados. A etiqueta "Pago" significa pagamento **registrado pela Controladoria com comprovante**, não conciliação automática com banco.
- WhatsApp real permanece desativado. Nenhuma funcionalidade deste pacote o ativa.
