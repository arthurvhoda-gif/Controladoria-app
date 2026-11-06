# HAIZE — Plano de estabilização V7.0 (06/11/2026)

## Escopo e garantias

- Base remota: `central-servicos-notificacoes-2026` em `0118482`; produção `main` em `db9f327`.
- **Não promover esta branch para `main` sem plano de migração, backup e validação de regressão.**
- Não remover, desativar ou simplificar funcionalidades para fazer os testes passarem.
- Envios externos WhatsApp continuam desligados. `HAIZE_ATRASOS_ENVIO_ATIVO=NAO` continua no Google Apps Script até liberação específica.
- Não colocar credenciais, arquivos de banco ou dados reais no repositório, issues, logs ou PRs.

## Linha de base verificável (primeiro GitHub Actions da V7.0)

Workflow: `.github/workflows/haize-v70.yml`.

- Python (SQLite em memória; sem acesso ao Neon): **172 testes aprovados**.
- `npm ci` e `npm run build`: **aprovados**.
- `npm run lint`: **falhou com 17 erros e 13 avisos**. Manter a checagem obrigatória e corrigir as causas, sem desabilitar regras.
- Auditoria dos arquivos rastreados: **6 artefatos legados sinalizados**, nenhum artefato novo proibido.
- Estes resultados são testes automatizados parciais, **não** comprovam comportamento integral em produção.

## Resultado após correções do frontend (06/11/2026)

- Execução CI: https://github.com/arthurvhoda-gif/Controladoria-app/actions/runs/42223173495
- **172 testes Python aprovados** (SQLite em memória, sem Neon).
- **Build e lint do frontend aprovados**, com as regras originais de ESLint preservadas.
- **Scanner de novos artefatos sensíveis aprovado**; 6 arquivos legados continuam sinalizados para revisão.
- Refatoração dos efeitos de carregamento, de gerenciamento de contatos e das prévias WhatsApp; tratamento de falhas visível; isolamento por sessão; navegação por perfil e paginação com estado derivado.
- Nenhum código de backend, migração, envio de email ou envio oficial WhatsApp alterado neste pacote.
- **Ainda pendente:** validação funcional/visual em ambiente de desenvolvimento para troca de conta, navegação, upload e visualização de fotos, atualização de serviços, filtros e páginas, rateio, gestão de números e prévias de WhatsApp. O CI não cobre interações reais de navegador.

## Pendências de segurança e dados

1. `backend/controladoria.db` e cinco `.pyc` rastreados desde antes da V7.0. O scanner não abre, apaga nem remove arquivos. Determinar se o banco contém informações reais; avaliar rotação de credenciais e, somente após plano seguro, remediação do histórico público.
2. Na `main`, o escopo do solicitante ainda é validado por **nome**. A V6.8 no desenvolvimento muda para `solicitante_id`; exigir backfill auditável e revisão de pedidos legados sem correspondência única.
3. Compras e execuções de checklist possuem anexos/fotos referenciados por caminho de disco. Levantar volume, integridade e existência dos originais antes de migrar para armazenamento persistente; não alterar metadados ou remover arquivos antes de confirmar cópia e acesso.
4. Alterar `AUTOMATION_SECRET` de forma coordenada no Render e Apps Script antes de habilitar e-mails diários reais; `HAIZE_SECRET` de PDFs separadamente para não interromper serviço existente.
5. Avaliar limites de upload, nomes de arquivo, quotas e persistência; isolar acesso por perfil, solicitante e condomínio nos testes de integração.

## Migração financeira e serviços

- Central Financeira V6.8: lançamentos imutáveis em centavos, estornos registrados, alertas de excedente e comprovantes no PostgreSQL. Financeiro é somente consulta na versão atual (não alterar essa regra sem decisão de produto).
- Migrar `solicitante_id`, novas tabelas e eventuais índices no Neon com **backup testado**, plano de compatibilidade e rollback.
- Preservar os serviços internos, seus participantes, fotografias, histórico, notificações e consentimentos WhatsApp.
- Evoluir para paginação server-side e conciliação bancária sem declarar pagamentos já conciliados.
- WhatsApp oficial deve manter consentimento individual, verificação de destinatário e link para ação *dentro* do aplicativo.

## Definição de pronto por pacote

1. Requisitos e fluxos existentes inventariados; mudança mínima e explicitamente delimitada.
2. Testes unitários e de integração (incluindo negativa de permissão e cenários antigos) passando.
3. Build React e lint sem erros, corrigidos na origem, sem desabilitar verificações.
4. Nenhum segredo novo versionado e nenhuma credencial impressa em log.
5. Migração com inventário de registros, backup restaurável e validação de integridade antes/depois.
6. Revisão do diff, PR separado, validação em ambiente de teste e liberação explícita de produção.
7. Evidência do deploy e teste funcional dos perfis Controladoria, Solicitante, Checklist e Financeiro.

## Próxima frente (sem publicar)

- Tratar os **17 erros e 13 avisos** identificados pelo lint, distinguindo problemas de efeitos React de avisos sobre dependências, sem alterar fluxo de sessão, permissões ou notificações.
- Adicionar suíte de regressão para fluxo de compras/checklists/armazenamento; validar dados legados em cópia do banco.
- Planejar a promoção V6.8/V6.9 a partir de cópia de `main` com migração e compatibilidade, nunca merge irrestrito.
