# Controladoria Haize V7.5 — Recuperacao de notificacoes (somente TESTES)

## Objetivo

Oferecer verificacao gratuita e temporaria quando o backend de testes da Render fica inativo. O Google Apps Script acorda o servidor por uma requisicao publica `GET /status` uma vez por hora; o recuperador instalado no backend e responsavel pela fila, pelas permissoes e pelos reenvios. O script nao acessa o banco, nao envia Push e nao tem credenciais.

**Importante:** nao garante tempo real nem disponibilidade 24/7. A Render suspende servicos gratuitos apos 15 minutos ociosos e usa franquia compartilhada entre servicos gratuitos do workspace. Como os servidores TESTES e PRODUCAO estao no mesmo workspace, o acionador tem vida maxima de 48 horas. Nao usar rotina de keep-alive permanente.

## Instalacao guiada (uma unica vez)

1. **Google Apps Script (site oficial):** acesse https://script.google.com/home/projects/create com a conta autorizada para os testes. Crie um projeto independente chamado `HAIZE_Push_Recuperacao_TESTES_V75`. **Nao altere** os projetos de armazenamento no Drive nem de e-mails da Haize.
2. No arquivo `Código.gs`, substitua o conteudo existente pelo codigo de `scripts/haize_push_recuperacao_testes_v75.gs` neste mesmo repositorio. Salve o projeto. Nao adicione senhas ou tokens.
3. Na lista de funcoes do editor, selecione **`haizePushV75InstalarTeste48Horas`**, clique em **Executar** e analise as permissoes solicitadas pelo Google. A funcao primeiro consulta o servidor de **TESTES** e so entao instala um acionador **a cada 1 hora**.
4. Confira no menu **Execucoes** se aparece a mensagem: `Acionador de testes instalado, 1 vez por hora, expira em 48 horas.`. Em **Acionadores** deve haver somente 1 acionador para `haizePushV75VerificarServidorTeste`.
5. Envie ao responsavel pela homologacao somente a confirmacao de sucesso ou mensagem de erro (sem compartilhar tokens, dados de contas ou capturas de credenciais).

## Encerrar antecipadamente

Selecione e execute a funcao **`haizePushV75CancelarTeste`**. Somente o acionador criado por este script sera removido. A expiracao automatica ocorre na primeira execucao depois das 48 horas.

## Limites e comportamento

- Se o servidor de testes estiver dormindo, o pedido do Google pode levar cerca de 1 minuto para acordar o backend. O job temporario pode nao executar exatamente no horario esperado.
- A entrega de Push permanece oportunista; o aceite dos servidores Apple/Google nao prova a visualizacao no celular.
- Render Free: 750 horas mensais **compartilhadas no workspace**; um acionador permanente que evite a hibernacao pode esgotar a franquia e suspender os servicos. Antes de um acionador de longo prazo, avaliar o uso real da franquia e os requisitos de disponibilidade.
- Google Apps Script esta sujeito a cotas de acionadores, execucoes e `UrlFetchApp`; nao criar varios acionadores iguais.
- O servidor e os aparelhos de producao nao sao modificados por este teste.

## Validacao do codigo

Teste local sem rede e sem envio de notificacoes:

```sh
node scripts/teste_push_gas_v75.cjs
```

Documentacao oficial:
- https://render.com/docs/free
- https://developers.google.com/apps-script/guides/triggers/installable
- https://developers.google.com/apps-script/guides/services/quotas
