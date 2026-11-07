# Controladoria Haize — notificações V7.3
## Registro objetivo do que foi implementado e do que falta

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
3. Sino global na interface consulta avisos de serviços, checklist atrasado
   e solicitações pendentes; exibe contador e permite abrir a tarefa.
4. Atualização de avisos de serviços a cada 45 s com a aplicação visível,
   ao ganhar foco e ao abrir a central; separada das consultas de checklist.
   Requisições antigas são canceladas em troca de sessão.
5. Leitura é confirmada no frontend somente após resposta positiva da API.
6. `GET /servicos/alertas-prazos` lista somente tarefas vencidas e abertas,
   respeitando identidade, perfil, condomínio e vínculos de participação.
   O sino global mostra o prazo vencido, abre a tarefa e para de alertar
   quando ela é concluída. Não cria notificações repetidas nem WhatsApp.

**Preparação WhatsApp, SEM qualquer disparo externo**
6. Controladoria cadastra/altera números e usuários dão opt-in/opt-out
   individualmente na própria conta.
7. Alteração de número revoga consentimento e cancela itens preparados.
8. Histórico auditável de concessão/revogação e de alterações de telefone
   acessível somente à Controladoria; exibe apenas os quatro últimos dígitos
   dos telefones, nunca números completos no histórico.
9. Novo cadastro recusa um número compartilhado por duas contas (HTTP 409).
   Novos bancos também têm restrição UNIQUE. Para bancos existentes,
   a migração precisa ser aplicada SOMENTE depois de auditar duplicidades:
   `migracoes/v73_whatsapp_telefone_unico.sql`.
10. Prévia de avisos é somente leitura e simulação conservadora.
    Nenhum status de pré-envio é autorização para disparar mensagens.

### Barreiras obrigatórias para concluir o módulo

- [x] Testes unitários e de integração offline por perfil/condomínio.
- [x] Testes de backend de consentimento e auditoria (banco fictício).
- [x] Teste de navegação com sino, abertura de tarefa e confirmação de leitura.
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
- Notificação interna não necessita comprar pacote WhatsApp; envio oficial,
  caso escolhido, poderá ter custos e não deve ser ativado automaticamente.
