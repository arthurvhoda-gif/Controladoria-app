/**
 * Controladoria Haize V7.5 — TESTES, nao producao.
 * Recuperacao gratuita, temporaria e conservadora: 1 verificacao por hora,
 * por ate 48 horas. Nao mantem o Render permanentemente ligado.
 *
 * O endpoint publico /status somente desperta o backend. Quem reprocessa
 * a fila e o recuperador no backend, com permissoes e limites proprios.
 * Nao ha tokens, senhas ou assinaturas Web Push neste script.
 */
const HAIZE_PUSH_V75_TESTE = Object.freeze({
  url: 'https://controladoria-api-teste.onrender.com/status',
  funcao: 'haizePushV75VerificarServidorTeste',
  propriedadeExpiracao: 'HAIZE_PUSH_V75_TESTE_EXPIRA_EM',
  duracaoHoras: 48,
});

/** Executar uma vez para instalar o unico acionador de testes. */
function haizePushV75InstalarTeste48Horas() {
  const existentes = ScriptApp.getProjectTriggers().filter(
    (gatilho) => gatilho.getHandlerFunction() === HAIZE_PUSH_V75_TESTE.funcao
  );
  if (existentes.length > 0) {
    throw new Error('O acionador de recuperacao ja esta instalado neste projeto.');
  }

  const propriedades = PropertiesService.getScriptProperties();
  const expiracao = Date.now() + HAIZE_PUSH_V75_TESTE.duracaoHoras * 60 * 60 * 1000;
  propriedades.setProperty(HAIZE_PUSH_V75_TESTE.propriedadeExpiracao, String(expiracao));
  try {
    // Verifica a URL de TESTES antes de criar um acionador recorrente.
    haizePushV75VerificarServidorTeste();
    ScriptApp.newTrigger(HAIZE_PUSH_V75_TESTE.funcao)
      .timeBased().everyHours(1).create();
  } catch (erro) {
    propriedades.deleteProperty(HAIZE_PUSH_V75_TESTE.propriedadeExpiracao);
    throw erro;
  }
  Logger.log('Acionador de testes instalado, 1 vez por hora, expira em 48 horas.');
}

/** Executada pelo relogio; nao cria tarefas nem envia notificacoes diretamente. */
function haizePushV75VerificarServidorTeste() {
  const propriedades = PropertiesService.getScriptProperties();
  const expiracao = Number(
    propriedades.getProperty(HAIZE_PUSH_V75_TESTE.propriedadeExpiracao)
  );
  if (!Number.isFinite(expiracao) || expiracao <= 0 || Date.now() >= expiracao) {
    haizePushV75CancelarTeste();
    Logger.log('Teste expirado ou nao instalado; nenhum pedido enviado.');
    return;
  }

  const cadeado = LockService.getScriptLock();
  if (!cadeado.tryLock(3000)) {
    Logger.log('Outra verificacao ja esta em andamento; nao duplicar.');
    return;
  }
  try {
    const resposta = UrlFetchApp.fetch(HAIZE_PUSH_V75_TESTE.url, {
      method: 'get',
      muteHttpExceptions: true,
      followRedirects: false,
      headers: { Accept: 'application/json' },
    });
    const codigo = resposta.getResponseCode();
    if (codigo !== 200) {
      throw new Error('Servidor de testes respondeu HTTP ' + codigo);
    }
    const dados = JSON.parse(resposta.getContentText());
    if (dados.status !== 'online' || !dados.timestamp) {
      throw new Error('Resposta inesperada do servidor de testes.');
    }
    Logger.log('Servidor de testes acessivel; recuperacao da fila e feita pelo backend.');
  } finally {
    cadeado.releaseLock();
  }
}

/** Executar a qualquer momento para encerrar sem afetar outros projetos. */
function haizePushV75CancelarTeste() {
  ScriptApp.getProjectTriggers()
    .filter((gatilho) => gatilho.getHandlerFunction() === HAIZE_PUSH_V75_TESTE.funcao)
    .forEach((gatilho) => ScriptApp.deleteTrigger(gatilho));
  PropertiesService.getScriptProperties().deleteProperty(
    HAIZE_PUSH_V75_TESTE.propriedadeExpiracao
  );
  Logger.log('Acionador de recuperacao de testes desativado.');
}
