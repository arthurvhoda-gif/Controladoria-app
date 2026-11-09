/* Controladoria Haize V7.4 — receptor Web Push.
 * Só atua quando houver assinatura e envio pelo servidor (não habilitados ainda).
 * O conteúdo da notificação é genérico para não expor informações na tela bloqueada.
 */
self.addEventListener('push', (event) => {
  let payload;
  try {
    payload = event.data ? event.data.json() : null;
  } catch {
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
    const janelas = await clients.matchAll({ type: 'window', includeUncontrolled: true });
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
    if (clients.openWindow) await clients.openWindow(url.href);
  })());
});
