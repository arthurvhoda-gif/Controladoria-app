/* Controladoria Haize V7.4 — receptor Web Push.
 * Só atua quando houver assinatura e envio pelo servidor (não habilitados ainda).
 * O conteúdo da notificação é genérico para não expor informações na tela bloqueada.
 */
// Diagnóstico sem conteúdo sensível: confirma se o aparelho executa o
// receptor que entende o payload "haize-teste-v1".
self.addEventListener('message', (event) => {
  if (event.data?.tipo === 'haize-push-probe-v1' && event.ports?.[0]) {
    event.ports[0].postMessage({ tipo: 'haize-push-probe-v1', versao: 'v74-t2' });
  }
});

self.addEventListener('push', (event) => {
  let payload;
  try {
    payload = event.data ? event.data.json() : null;
  } catch {
    return;
  }
  if (payload?.tipo === 'haize-teste-v1') {
    // Notificacao generica de homologacao, sem informacoes confidenciais.
    const identificador = typeof payload.id === 'string' && /^[0-9a-f]{16}$/.test(payload.id)
      ? payload.id : 'sem-id';
    event.waitUntil(self.registration.showNotification('Controladoria Haize — teste', {
      body: 'Teste de notificação recebido neste celular.',
      icon: '/logo.png',
      badge: '/logo.png',
      tag: 'haize-teste-' + identificador,
      data: { destino: new URL('/', self.registration.scope).href }
    }));
    return;
  }
  const servicoId = Number(payload?.servico_id);
  if (payload?.tipo !== 'haize-servico-v1' ||
      !Number.isSafeInteger(servicoId) ||
      servicoId < 1 || servicoId > 2147483647) {
    return;
  }

  const destino = new URL('/?servico=' + servicoId, self.registration.scope).href;
  const evento = Number(payload.evento_id);
  const tag = Number.isSafeInteger(evento) && evento > 0
    ? 'haize-evento-' + evento
    : 'haize-servico-' + servicoId;

  event.waitUntil(
    self.registration.showNotification('Controladoria Haize', {
      body: 'Você tem uma atualização de tarefa. Abra o aplicativo para consultar.',
      icon: '/logo.png',
      badge: '/logo.png',
      tag,
      data: { destino }
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  // Nunca abrir origem externa recebida em dados de notificação.
  let url;
  try {
    url = new URL(event.notification.data?.destino || '/', self.registration.scope);
    if (url.origin !== self.location.origin) return;
  } catch {
    return;
  }

  event.waitUntil((async () => {
    const janelas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const janela of janelas) {
      if (new URL(janela.url).origin !== url.origin) continue;
      if ('navigate' in janela) {
        try {
          await janela.navigate(url.href);
          return await janela.focus();
        } catch {
          // Navegação pode falhar quando a janela está sendo fechada.
        }
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(url.href);
  })());
});
