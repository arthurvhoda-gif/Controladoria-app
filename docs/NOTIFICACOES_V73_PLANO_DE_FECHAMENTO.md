# Controladoria Haize — notificações V7.3
## Registro objetivo do que foi implementado e do que falta

**Marco de 07/11/2026:** notificações internas concluídas em desenvolvimento
e aprovadas na suíte automatizada; **homologação implantada não realizada**.
A preparação WhatsApp continua SEM despachante real. Este marco não libera produção.

**Branch exclusiva de desenvolvimento:** `notificacoes-v73-20261107` (base V7.2).
**Não enviar para `main` nem implantar em produção sem homologação e autorização explícita.**
**WhatsApp real está DESATIVADO. Não há integração oficial de despacho ou contratação de custos.**

### Objetivo preservado
- Avisos fortes e segmentados, sem expor dados de um condomínio a outro.
- WhatsApp, se futuramente contratado, somente como AVISO + link para o aplicativo.
- Ciência, respostas, andamento, evidências e conclusão SEMPRE dentro da Controladoria.
- Consentimento individual para todos os perfis, inclusive aparelhos corporativos.
- Zeladores acessam apenas o condomínio próprio; Controladoria supervisiona.
- Não remover funcionalidades de compras, checklist, serviços, financeiro ou e-mails.

### Funcionalidades implementadas, sujeitas à homologação final

**Dentro do aplicativo**
1. Eventos da Central de Serviços produzem avisos persistentes por destinatário
   na mesma transação do serviço; não dependem de WhatsApp.
2. `GET /servicos/notificacoes` e `POST /servicos/notificacoes/{id}/ler`
   exigem sessão, identidade e acesso ATUAL à tarefa/condomínio, inclusive para
   avisos antigos de tarefas legadas. A filtragem ocorre antes do limite de 100.
3. Sino global na interface consulta avisos de serviços, prazos vencidos de
   serviços, checklist atrasado e solicitações pendentes; exibe contador e
   permite abrir a tarefa.
4. Atualização de avisos de serviços a cada 45 s com a aplicação visível,
   ao ganhar foco e ao abrir a central; separada das consultas de checklist.
   Criação/atualização de tarefa sincroniza o sino imediatamente, sem F5.
   Requisições antigas são canceladas em troca de sessão.
5. Leitura é confirmada no frontend somente após resposta positiva da API.
   Avisos não lidos têm prioridade antes do limite de 100 registros. Em erro
   de API ou perda de acesso, o sino remove dados de serviços antigos e exibe
   erro, sem continuar expondo possíveis tarefas de outro condomínio.
   Alertas de checklist também são limpos quando a API falha ou devolve
   estrutura inválida; o usuário vê aviso de consulta incompleta, **não**
   a afirmação enganosa de "Tudo em dia!". Reconexão e sincronização manual
   recuperam os registros corretos.
6. Avisos locais (Notification API) pedem permissão somente por clique:
   o primeiro carregamento não dispara alertas antigos; avisos novos geram
   notificação genérica sem dados sensíveis, uma vez por ID e por sessão.
   Isto NÃO é Web Push remoto nem funciona com o navegador fechado.
7. `GET /servicos/alertas-prazos` lista somente tarefas vencidas e abertas,
   respeitando identidade, perfil, condomínio e vínculos de participação.
   O sino global mostra o prazo vencido, abre a tarefa e para de alertar
   quando ela é concluída. Não cria notificações repetidas nem WhatsApp.

**Preparação WhatsApp, SEM qualquer disparo externo**
7. Controladoria cadastra/altera números e usuários dão opt-in/opt-out
   individualmente na própria conta.
8. Alteração de número revoga consentimento e cancela itens preparados.
   Para conceder opt-in, a pessoa confirma o E.164 que viu na tela;
   número mudado nesse intervalo produz HTTP 409 sem novo consentimento.
   PostgreSQL usa FOR UPDATE na mesma linha de titularidade para serializar
   duas alterações simultâneas, comprovado por ensaio de concorrência real
   na CI, isolado do Neon.
9. Histórico auditável de concessão/revogação e de alterações de telefone
   acessível somente à Controladoria; exibe apenas os quatro últimos dígitos
   dos telefones, nunca números completos no histórico.
10. Novo cadastro recusa um número compartilhado por duas contas (HTTP 409).
   Novos bancos também têm restrição UNIQUE. Para bancos existentes,
   a migração precisa ser aplicada SOMENTE depois de auditar duplicidades:
   `migracoes/v73_whatsapp_telefone_unico.sql`.
11. Prévia de avisos é somente leitura e simulação conservadora.
    Verifica também telefones duplicados de cadastros legados, bloqueando
    a triagem nesses casos mesmo se a migração UNIQUE ainda não ocorreu.
    Nenhum status de pré-envio é autorização para disparar mensagens.

### Barreiras obrigatórias para concluir o módulo

- [x] Testes unitários e de integração offline por perfil/condomínio.
- [x] Testes de backend de consentimento e auditoria (banco fictício).
- [x] Teste de navegação com sino, abertura de tarefa e confirmação de leitura.
- [x] Teste Chromium de troca de contas sem vazamento de alertas.
- [x] Teste Chromium de falha HTTP de checklist, descarte de aviso antigo,
      recuperação sem F5, payload incorreto e sincronização manual do sino.
- [x] Teste Chromium de acesso revogado entre listagem e abertura de tarefa
      e de retentativa de link após indisponibilidade temporária.
- [x] Teste Chromium de permissão só após clique, alerta local sem repetição
      e novo serviço atualizando o sino automaticamente sem F5.
- [x] HTTP FastAPI+JWT real com banco fictício, perfil/condomínio, opt-in
      protegido, histórico auditável e negação de acesso após mudança.
- [x] Ensaio PostgreSQL real de corrida entre troca do número e opt-in,
      usando SOMENTE banco local descartável da CI.
- [x] Confirmação do número visto na tela, proteção de duplicidades e
      ordenação de avisos pendentes antes do histórico já lido.
- [x] Teste da migração `v73_whatsapp_telefone_unico.sql` no PostgreSQL
      descartável: recusa bancos com duplicados sem alterar os dados;
      aplica UNIQUE após saneamento do cenário fictício.
- [x] Prévia bloqueia telefones duplicados em base SQLite legada sem UNIQUE.
- [ ] Verificação transacional, na mesma sessão DB, de identidade, consentimento,
      acesso atual, evento/ciclo, vigência, duplicidade e bloqueio de reenvio.
- [ ] Despachante oficial WhatsApp Business Platform: templates aprovados,
      token seguro, callbacks autenticados de entrega/erro, retentativas limitadas,
      idempotência, opt-out, auditoria e política de custos — DEPENDE de
      aprovação de orçamento/conta do provedor. Nenhum envio implementado.
- [x] Exibir atrasos existentes de serviços no sino, sem spam.
- [ ] Definir política de escalonamento de atrasos de serviços (se necessária),
      responsáveis, prazos e nível hierárquico, antes de criar disparos
      externos ou alterar os destinatários atuais.
- [ ] Verificar a lista de números duplicados na base real e aplicar a
      migração única em ambiente homologado, com backup.
- [ ] Homologar com usuários fictícios e dispositivos móveis; validar
      login, privacidade, link profundo, mudança de usuário, reconexão,
      erros de rede e rollback antes de qualquer promoção à produção.

### Teste / reversão / custos
- CI: `.github/workflows/haize-v70.yml` executa Python, frontend, Chromium,
  PostgreSQL descartável, dependências e prevenção de arquivos sensíveis.
- Sem segredos, números reais de telefone ou dados de condomínios reais na CI.
- Rollback seguro: a versão fica na branch, sem merge/deploy.
- Notificação interna não necessita comprar pacote WhatsApp; toda ação
  efetiva é feita e registrada dentro do aplicativo.
- Não confundir a API de Notification do navegador com push remoto: avisos
  internos dependem de consultas do aplicativo aberto; não prometem alerta
  quando o aparelho está offline ou o navegador fechado.
- **Política de custo em novembro de 2026:** templates proativos de utilidade
  da WhatsApp Business Platform estão sujeitos a cobrança por entrega,
  inclusive dentro da janela de 24 h desde 01/10/2026. A franquia de
  mensagens de serviço NÃO é uma autorização para disparar templates proativos
  gratuitamente. Conferir custos e condições atuais antes de contratar:
  https://developers.facebook.com/docs/whatsapp/pricing/
  e https://respond.io/help/whatsapp/whatsapp-pricing
- Consequentemente, não implementar serviços de disparo em massa por
  automação não oficial, nem ativar despacho real sem custo comprovado,
  conta do provedor e decisão explícita.
- CI confirmada com **236 testes Python, 24 testes Chromium e ensaios
  PostgreSQL descartáveis**; os seis jobs ficaram verdes na execução
  https://github.com/arthurvhoda-gif/Controladoria-app/actions/runs/42376103572
  (commit `dee2fd9`).
- Código da branch de desenvolvimento não foi promovido à `main`.
