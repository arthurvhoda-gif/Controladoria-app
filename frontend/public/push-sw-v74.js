/* Controladoria Haize V7.4 — receptor Web Push.
 * Só atua quando houver assinatura e envio pelo servidor (não habilitados ainda).
 * O conteúdo da notificação é genérico para não expor informações na tela bloqueada.
 */
// Diagnóstico sem conteúdo sensível: confirma se o aparelho executa o
// receptor que entende o payload "haize-teste-v1".
self.addEventListener('message', (event) => {
  if (event.data?.tipo === 'haize-push-probe-v1' && event.ports?.[0]) {
    event.ports[0].postMessage({ tipo: 'haize-push-probe-v1', versao: 'v74-t3' });
  }
});

self.addEventListener('push', (event) => {
  // A Apple exige que TODO push recebido resulte em um aviso visível.
  // O receptor antigo ignorava mensagens desconhecidas ou JSON inválido,
  // o que pode levar o Safari a revogar silenciosamente a assinatura.
  let payload = null;
  try {
    payload = event.data ? event.data.json() : null;
  } catch {
    // Conteúdo inesperado: exibir aviso genérico em vez de descartar.
  }

  let titulo = 'Controladoria Haize';
  let corpo = 'Você tem uma atualização. Abra o aplicativo para consultar.';
  let tag = 'haize-push-generico';
  let destino = '/';

  if (payload?.tipo === 'haize-teste-v1') {
    const identificador = typeof payload.id === 'string' && /^[0-9a-f]{16}$/.test(payload.id)
      ? payload.id : 'sem-id';
    titulo = 'Controladoria Haize — teste';
    corpo = 'Teste de notificação recebido neste celular.';
    tag = 'haize-teste-' + identificador;
  } else if (payload?.tipo === 'haize-servico-v1') {
    const servicoId = Number(payload.servico_id);
    if (Number.isSafeInteger(servicoId) && servicoId >= 1 && servicoId <= 2147483647) {
      destino = '/?servico=' + servicoId;
      const eventoId = Number(payload.evento_id);
      tag = Number.isSafeInteger(eventoId) && eventoId > 0
        ? 'haize-evento-' + eventoId
        : 'haize-servico-' + servicoId;
      corpo = 'Você tem uma atualização de tarefa. Abra o aplicativo para consultar.';
    }
  }

  const url = new URL(destino, self.registration.scope).href;
  event.waitUntil(self.registration.showNotification(titulo, {
    body: corpo,
    // Sem ícones adicionais no teste: evita interferência de recursos externos.
    tag,
    data: { destino: url },
  }));
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
