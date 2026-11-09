# Controladoria Haize V7.3 — liberação controlada, sem afetar produção

**Situação em 09/11/2026:** a distribuição de avisos internos e a
homologação de Windows com usuários fictícios foram aprovadas.
**Não houve implantação da V7.3 em Render, Vercel ou Neon.**
O envio oficial de WhatsApp **não faz parte desta liberação** e continua
desativado. Não criar gastos ou conexões externos implicitamente.

## Decisão de escopo

A versão de notificações **dentro do aplicativo** pode avançar como
candidata a um ambiente **separado de homologação**. Este marco não libera
produção e não pressupõe plano gratuito nos provedores.

A integração oficial de WhatsApp é um projeto futuro, opcional e isolado:
depende de orçamento aprovado, conta habilitada, templates, entrega,
retentativas, auditoria, cobranças e consentimento explícito. Nenhum
despachante deve ser ativado por essa homologação.

## O que já está comprovado

- 245 testes Python e 25 testes Chromium aprovados na V7.3;
- cinco cenários reais React/FastAPI/PostgreSQL e três de demonstração
  local SQLite também aprovados;
- usuário validou no Windows uma **nova tarefa** da Controladoria
  notificada ao Zelador Alfa, sem aparecer para o Zelador Beta;
- recebimento, leitura e isolamento de tarefas por condomínio;
- consentimento, duplicidades e pré-conferência somente leitura de WhatsApp;
- ausência de envio real e produção preservada na branch `main`.

## Checklist obrigatório antes de qualquer implantação

1. **Infraestrutura de homologação fisicamente separada:** verificar,
   com consentimento do responsável, se há condições sem custo adicional
   para um backend isolado, frontend isolado e um banco descartável
   exclusivo. Não utilizar credenciais, banco ou variáveis de produção.
2. **Inventário de configuração:** usar segredos fictícios próprios
   do ambiente; desabilitar GAS/Resend, agendamentos externos e WhatsApp;
   armazenamento local de dados fictícios. Confirmar domínio e CORS isolados.
3. **Backup independente e restauração ensaiada:** fazer cópia verificável
   do banco de origem antes de qualquer migração aprovada, com acesso
   restrito e prazo de retenção definido. Nunca publicar arquivos de banco
   no GitHub nem em logs de CI.
4. **Pré-diagnóstico da unicidade dos telefones:** verificar apenas
   contagens de contatos duplicados e validade do índice; não exportar
   números ou dados pessoais para relatórios. Havendo duplicatas, a
   Controladoria precisa decidir caso a caso — não resolver por script.
5. **Migração V7.3 exclusivamente após autorização:** aplicar
   `migracoes/v73_whatsapp_telefone_unico.sql` SOMENTE na cópia
   homologada, com backup e verificação posterior. O SQL bloqueia
   duplicatas e agora também índices de mesmo nome que não garantem
   unicidade. Confirmar idempotência e dados preservados.
6. **Cenários operacionais:** login por perfil, notebook e celular,
   links profundos, marcação de leitura, troca de usuário e condomínio,
   queda/reconexão, comportamento de permissões revogadas e tarefas
   vencidas. Validar anexos, checklist, compras e financeiro sem
   regressões.
7. **Rollback:** testar retorno do backend e do frontend ao artefato
   anteriormente aprovado e restauração da cópia de banco em
   homologação. Não tratar `git revert` como restauração de dados.
8. **Decisão explícita de GO/NO-GO:** registrar aprovação para
   promoção à produção, incluindo janela de implantação, responsáveis,
   evidências, orçamento nulo comprovado e plano de reversão.

**Se um item estiver pendente, a liberação fica em NO-GO.**

## Diagnóstico automático do PostgreSQL

O script `scripts/preflight_migracao_whatsapp_v73.py` foi criado para
**ensaios em PostgreSQL descartável da CI**, exclusivamente no endereço
`127.0.0.1:5432` e banco `haize_v73_notificacoes` com o usuário
`haize_ci`. Não deve ser adaptado de forma improvisada para o Neon.

- Somente transação de leitura no PostgreSQL; não aplica migração.
- Relatório com **quantidade de grupos duplicados**, **contas afetadas**
  e se o índice é **único, válido e atende à coluna correta**.
- Não apresenta números, nomes, e-mails ou credenciais.
- Estados: `bloqueado`, `pronto_para_migracao_na_copia` ou
  `migracao_ja_aplicada_na_copia`.
- CI simula duplicados legados, correção fictícia, migração repetida
  e índice não único com nome conflitante; o script deve falhar fechado.

A auditoria em dados **reais** exige procedimento próprio, aprovação,
acesso autorizado e ambiente de homologação, e **não foi executada**.

## Limite do marco

Os avisos internos são recuperados enquanto o aplicativo está em uso.
Permissão de notificação no navegador NÃO equivale a push remoto com
o navegador fechado. Nenhuma mensagem WhatsApp, e-mail ou Push remoto é
autorizada por este documento.

A produção permanece na `main`; toda preparação está na branch
`notificacoes-v73-20261107`.
