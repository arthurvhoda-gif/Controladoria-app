# V7.6 - Conciliação local de custos

A aba Conciliação de Custos aparece apenas para Controladoria no site de testes. Ela lê localmente o arquivo resumo_por_condominio.csv produzido pela auditoria, sem upload, sem guardar no servidor e sem alterar planilhas.

O arquivo fica em Documentos / Haize_Auditoria_Custos_V76 / resumo_por_condominio.csv no computador do usuário. A tela mostra totais e permite filtrar condomínios com divergências. Não classifica automaticamente os 19 lançamentos nem os insere na base geral.

Homologação: entrar com Gestora no site de testes, abrir Conciliação de Custos e selecionar o CSV. Esperados na auditoria 10 condomínios, 963 classificadas, 944 na base geral e 19 divergências. Conferir filtros e botão Limpar dados. No reload, dados não persistem.

Segurança: só Controladoria vê a aba, não há API nova de custos; este pacote não envia dados reais para o Neon, não escreve nas planilhas e não modifica a produção. Regressão do parser: node --test src/custosConsolidacao.test.mjs (executado no GitHub Actions).
