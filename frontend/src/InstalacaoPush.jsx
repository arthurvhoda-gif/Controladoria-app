import { useEffect, useState } from 'react'

const VERSAO_RECEPTOR = 'v74-t3'

function consultarReceptor(worker) {
  if (!worker) return Promise.resolve(false)
  return new Promise(resolve => {
    const canal = new MessageChannel()
    let concluido = false
    const encerrar = pronto => {
      if (concluido) return
      concluido = true
      clearTimeout(limite)
      canal.port1.close()
      canal.port2.close()
      resolve(pronto)
    }
    const limite = setTimeout(() => encerrar(false), 900)
    canal.port1.onmessage = ({ data }) => encerrar(
      data?.tipo === 'haize-push-probe-v1' && data?.versao === VERSAO_RECEPTOR
    )
    try {
      worker.postMessage({ tipo: 'haize-push-probe-v1' }, [canal.port2])
    } catch {
      encerrar(false)
    }
  })
}

async function prepararReceptor() {
  if (!('serviceWorker' in navigator) || !('MessageChannel' in window)) return false
  const registro = await navigator.serviceWorker.ready
  // A versão anterior descartava avisos de teste. Conferir a versão ativa
  // antes de disparar novamente evita um falso positivo (aceito 2/2).
  try { await registro.update() } catch { /* Pode estar temporariamente offline. */ }
  for (let tentativa = 0; tentativa < 12; tentativa += 1) {
    if (registro.waiting) registro.waiting.postMessage({ type: 'SKIP_WAITING' })
    if (await consultarReceptor(registro.active)) return true
    await new Promise(resolve => setTimeout(resolve, 350))
  }
  return false
}

// O prompt nativo do Android pode chegar antes de abrir o assistente.
let conviteInstalacao = null
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', evento => {
    evento.preventDefault()
    conviteInstalacao = evento
  })
}

function chaveVapidBytes(base64url) {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const preenchida = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
  return Uint8Array.from(atob(preenchida), caractere => caractere.charCodeAt(0))
}

function mensagemErro(detalhes, padrao) {
  return typeof detalhes?.detail === 'string' ? detalhes.detail : padrao
}

function instalado() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
}

const estiloAcao = {
  padding: '10px 13px', border: '1px solid #cbd5e1',
  borderRadius: 9, background: '#f8fafc', cursor: 'pointer',
  color: '#0f172a', fontWeight: 650,
}

export default function InstalacaoPush({ apiUrl, token, onClose }) {
  const [config, setConfig] = useState(null)
  const [total, setTotal] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [ocupado, setOcupado] = useState(false)
  const [testando, setTestando] = useState(false)
  const [diagnosticando, setDiagnosticando] = useState(false)
  const [checandoReceptor, setChecandoReceptor] = useState(true)
  const [receptorAtual, setReceptorAtual] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [erro, setErro] = useState('')
  const [estadoAtivacao, setEstadoAtivacao] = useState('')
  const [falhaAtivacao, setFalhaAtivacao] = useState(false)
  const [naTelaInicial, setNaTelaInicial] = useState(instalado)

  const ehIOS = /iPad|iPhone|iPod/i.test(navigator.userAgent)
  const ehAndroid = /Android/i.test(navigator.userAgent)
  const suportado = window.isSecureContext && 'serviceWorker' in navigator &&
    'PushManager' in window && 'Notification' in window

  useEffect(() => {
    const controller = new AbortController()
    async function carregar() {
      try {
        const headers = { Authorization: `Bearer ${token}` }
        const [c, d] = await Promise.all([
          fetch(`${apiUrl}/push/config`, { headers, signal: controller.signal }),
          fetch(`${apiUrl}/push/dispositivos`, { headers, signal: controller.signal }),
        ])
        if (!c.ok || !d.ok) throw new Error('O servidor ainda não disponibiliza o cadastro de dispositivos V7.4.')
        const [configuracao, dispositivos] = await Promise.all([c.json(), d.json()])
        setConfig(configuracao)
        setTotal(dispositivos.total)
      } catch (e) {
        if (!controller.signal.aborted) setErro(e.message)
      } finally {
        if (!controller.signal.aborted) setCarregando(false)
      }
    }
    carregar()
    return () => controller.abort()
  }, [apiUrl, token])

  useEffect(() => {
    let ativo = true
    prepararReceptor().then(ok => {
      if (ativo) setReceptorAtual(ok)
    }).catch(() => {
      if (ativo) setReceptorAtual(false)
    }).finally(() => {
      if (ativo) setChecandoReceptor(false)
    })
    return () => { ativo = false }
  }, [])

  async function verificarReceptor() {
    setChecandoReceptor(true)
    setErro('')
    try {
      const ok = await prepararReceptor()
      setReceptorAtual(ok)
      if (!ok) setErro('O receptor antigo ainda está ativo neste aparelho. Feche completamente o aplicativo, abra novamente e verifique outra vez.')
    } catch {
      setReceptorAtual(false)
      setErro('Não foi possível atualizar o receptor. Confira a conexão com a internet e reabra o aplicativo.')
    } finally {
      setChecandoReceptor(false)
    }
  }

  async function instalar() {
    setErro('')
    if (ehIOS) {
      setFeedback('No Safari do iPhone, toque Compartilhar → Adicionar à Tela de Início e abra a Controladoria pelo ícone criado.')
      return
    }
    if (!conviteInstalacao) {
      setFeedback('No Chrome, abra o menu ⋮ e escolha Instalar aplicativo ou Adicionar à tela inicial.')
      return
    }
    try {
      setOcupado(true)
      await conviteInstalacao.prompt()
      const escolha = await conviteInstalacao.userChoice
      conviteInstalacao = null
      setNaTelaInicial(instalado())
      setFeedback(escolha?.outcome === 'accepted'
        ? 'Instalação solicitada. Abra a Controladoria pela tela inicial para continuar.'
        : 'Você pode instalar posteriormente pelo menu do navegador.')
    } catch {
      setErro('Use o menu do navegador para adicionar o aplicativo à tela inicial.')
    } finally {
      setOcupado(false)
    }
  }

  async function ativar() {
    setErro('')
    setFeedback('')
    setFalhaAtivacao(false)
    setEstadoAtivacao('Solicitando permissão de notificações…')
    if (!suportado || !config?.registro_disponivel || !config?.chave_publica) {
      setFalhaAtivacao(true)
      setEstadoAtivacao('O registro de notificações não está disponível neste aparelho.')
      return
    }
    if (ehIOS && !instalado()) {
      setFalhaAtivacao(true)
      setEstadoAtivacao('No iPhone, abra o aplicativo pelo ícone da tela inicial antes de ativar os avisos.')
      return
    }
    let assinatura = null
    let criadaAgora = false
    try {
      setOcupado(true)
      // Permissão solicitada em resposta direta ao toque, antes de qualquer await.
      const permissao = await Notification.requestPermission()
      if (permissao !== 'granted') {
        setFalhaAtivacao(true)
        setEstadoAtivacao('Permissão não concedida. Verifique as configurações de notificações do aparelho.')
        return
      }
      setEstadoAtivacao('Verificando a assinatura Web Push do aparelho…')
      const registro = await navigator.serviceWorker.ready
      assinatura = await registro.pushManager.getSubscription()
      const publica = chaveVapidBytes(config.chave_publica)
      if (assinatura?.options?.applicationServerKey) {
        const anterior = new Uint8Array(assinatura.options.applicationServerKey)
        if (anterior.length !== publica.length || anterior.some((valor, i) => valor !== publica[i])) {
          await assinatura.unsubscribe()
          assinatura = null
        }
      }
      if (!assinatura) {
        setEstadoAtivacao('Criando uma nova assinatura Web Push…')
        assinatura = await registro.pushManager.subscribe({
          userVisibleOnly: true, applicationServerKey: publica,
        })
        criadaAgora = true
      }
      setEstadoAtivacao('Salvando o aparelho no servidor de testes…')
      const resposta = await fetch(`${apiUrl}/push/dispositivos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(assinatura.toJSON()),
      })
      if (!resposta.ok) {
        const detalhes = await resposta.json().catch(() => null)
        throw new Error(mensagemErro(detalhes, 'Não foi possível registrar este celular.'))
      }
      const lista = await fetch(`${apiUrl}/push/dispositivos`, { headers: { Authorization: `Bearer ${token}` } })
      if (lista.ok) setTotal((await lista.json()).total)
      setEstadoAtivacao(config?.envios_ativos
        ? '✓ Este aparelho está registrado para receber notificações, inclusive avisos automáticos de tarefas.'
        : '✓ Este aparelho está registrado para receber Web Push. As notificações automáticas estão desativadas neste ambiente.')
    } catch (e) {
      if (criadaAgora && assinatura) {
        await assinatura.unsubscribe().catch(() => {})
      }
      setFalhaAtivacao(true)
      setEstadoAtivacao(e.message || 'Falha ao registrar dispositivo.')
    } finally {
      setOcupado(false)
    }
  }

  async function diagnosticarEsteAparelho() {
    setErro('')
    setFeedback('')
    setDiagnosticando(true)
    try {
      if (!instalado() && ehIOS) {
        throw new Error('Abra a Controladoria pelo ícone da tela inicial do iPhone, não pelo Safari.')
      }
      if (Notification.permission !== 'granted') {
        throw new Error('A permissão de notificações não está concedida neste aparelho. Verifique Ajustes → Notificações.')
      }
      const registro = await navigator.serviceWorker.ready
      const assinatura = await registro.pushManager.getSubscription()
      if (!assinatura) {
        throw new Error('Este aparelho não possui mais assinatura Web Push ativa. Toque em Ativar notificações neste aparelho para renovar o cadastro.')
      }
      const host = new URL(assinatura.endpoint).hostname
      // Diagnóstico local: não utiliza o servidor, não envia dados e não cobra mensagens.
      await registro.showNotification('Controladoria Haize — diagnóstico', {
        body: 'Notificação local de teste. Não é uma tarefa real.',
        tag: 'haize-diagnostico-local-' + Date.now(),
        data: { destino: new URL('/', window.location.origin).href },
      })
      const ehApple = host === 'web.push.apple.com'
      setFeedback(
        'Permissão concedida e assinatura ativa ' +
        (ehApple ? '(provedor Apple).' : '(provedor do navegador).') +
        ' O sistema solicitou ao aparelho uma notificação LOCAL, sem passar pelo servidor. ' +
        'Abra a Central de Notificações para conferir se ela apareceu. ' +
        'Se não aparecer no iPhone, verifique Ajustes → Notificações → Controladoria e os modos de Foco.'
      )
    } catch (e) {
      setErro(e.message || 'Falha no diagnóstico de notificações deste aparelho.')
    } finally {
      setDiagnosticando(false)
    }
  }

  async function testarNotificacao() {
    setErro('')
    setFeedback('')
    setTestando(true)
    try {
      const pronto = await prepararReceptor()
      setReceptorAtual(pronto)
      if (!pronto) throw new Error('Receptor ainda desatualizado neste celular. Verifique e reabra o aplicativo antes de enviar.')
      const resposta = await fetch(`${apiUrl}/push/teste`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const resultado = await resposta.json().catch(() => null)
      if (!resposta.ok) throw new Error(mensagemErro(resultado, 'O teste não pôde ser enviado.'))
      const aceitos = Number(resultado?.aceitos_pelo_provedor ?? 0)
      const consultados = Number(resultado?.aparelhos_consultados ?? 0)
      if (resultado?.assinaturas_expiradas_removidas) {
        setErro('Uma assinatura expirou. Abra o assistente no aparelho e ative as notificações novamente.')
      }
      setFeedback(
        `Provedores aceitaram ${aceitos} de ${consultados} envio(s). ` +
        'Verifique a notificação diretamente em cada celular; o aceite não garante a entrega.'
      )
    } catch (e) {
      setErro(e.message || 'Falha no envio de teste.')
    } finally {
      setTestando(false)
    }
  }

  async function desativar() {
    setErro('')
    setFeedback('')
    try {
      setOcupado(true)
      const registro = await navigator.serviceWorker.ready
      const assinatura = await registro.pushManager.getSubscription()
      if (!assinatura) {
        setFeedback('Este navegador não possui uma assinatura ativa.')
        return
      }
      const resposta = await fetch(`${apiUrl}/push/dispositivos`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ endpoint: assinatura.endpoint }),
      })
      if (!resposta.ok) throw new Error('Não foi possível revogar o aparelho no servidor.')
      await assinatura.unsubscribe()
      const lista = await fetch(`${apiUrl}/push/dispositivos`, { headers: { Authorization: `Bearer ${token}` } })
      if (lista.ok) setTotal((await lista.json()).total)
      setFeedback('Assinatura deste aparelho desativada.')
    } catch (e) {
      setErro(e.message || 'Erro ao revogar assinatura.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 100001 }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <section className="modal" role="dialog" aria-modal="true" aria-label="Instalação e notificações da Controladoria" style={{ maxWidth: 520, maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <h3>Instalação e notificações</h3>
          <button type="button" className="modal-close" aria-label="Fechar" onClick={onClose}>×</button>
        </div>
        <div className="modal-body" style={{ display: 'grid', gap: 18, padding: 22 }}>
          <p style={{ margin: 0, color: '#475569', lineHeight: 1.5 }}>
            Configure a Controladoria no seu celular. Nenhuma permissão será concedida sem sua autorização.
          </p>
          <div style={{ border: '1px solid #cbd5e1', borderRadius: 12, padding: 14 }}>
            <strong>1. Instale o aplicativo</strong>
            <p style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.5 }}>
              {naTelaInicial ? 'O aplicativo já está aberto em modo instalado.' :
                ehIOS ? 'No iPhone: abra no Safari, toque Compartilhar e depois Adicionar à Tela de Início. Abra pelo novo ícone.' :
                  ehAndroid ? 'No Android: no Chrome, escolha Instalar aplicativo ou Adicionar à tela inicial.' :
                    'Abra o menu do navegador e procure Instalar aplicativo.'}
            </p>
            {naTelaInicial ? <span style={{ color: '#047857', fontWeight: 650 }}>✓ Instalação identificada</span> :
              <button type="button" onClick={instalar} disabled={ocupado} style={estiloAcao}>
                {ehIOS ? 'Como instalar no iPhone' : 'Instalar ou ver instruções'}
              </button>}
          </div>
          <div style={{ border: '1px solid #cbd5e1', borderRadius: 12, padding: 14 }}>
            <strong>2. Autorize as notificações do celular</strong>
            <p style={{ margin: '8px 0', fontSize: 13 }}>
              {!suportado ? 'Este navegador ou aparelho não oferece Web Push nas condições atuais.' :
                Notification.permission === 'granted' ? '✓ Permissão do aparelho concedida.' :
                  Notification.permission === 'denied' ? 'Permissão bloqueada nas configurações do aparelho.' :
                    'A permissão será solicitada após você tocar em Ativar.'}
            </p>
            <button type="button" onClick={ativar}
              disabled={ocupado || carregando || !suportado || !config?.registro_disponivel || (ehIOS && !naTelaInicial)}
              style={estiloAcao}>{ocupado ? 'Registrando aparelho…' : 'Ativar notificações neste aparelho'}</button>
            {estadoAtivacao && <p role="status" aria-live="polite"
              style={{ margin: '9px 0 0', fontSize: 13, lineHeight: 1.5, fontWeight: 600,
                color: falhaAtivacao ? '#b91c1c' : '#047857' }}>{estadoAtivacao}</p>}
            {config && !config.registro_disponivel && <p style={{ marginBottom: 0, fontSize: 12, color: '#b45309' }}>
              O cadastro ainda está sendo habilitado no servidor de testes.
            </p>}
          </div>
          <div style={{ border: '1px solid #cbd5e1', borderRadius: 12, padding: 14 }}>
            <strong>3. Gerencie seus dispositivos</strong>
            <p style={{ margin: '8px 0', fontSize: 13 }}>Dispositivos vinculados a esta conta: {total ?? '—'}.</p>
            <button type="button" onClick={desativar} disabled={ocupado || !suportado || carregando} style={estiloAcao}>
              Desativar notificações deste aparelho
            </button>
          </div>
          {config?.teste_disponivel && <div style={{ border: '1px solid #cbd5e1', borderRadius: 12, padding: 14 }}>
            <strong>4. Enviar notificação de teste</strong>
            <p style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.5 }}>
              Primeiro confirme o receptor atualizado nos dois aparelhos.
              Depois feche os aplicativos e envie um aviso fictício somente para sua conta.
            </p>
            <p style={{ fontSize: 13, margin: '8px 0', color: receptorAtual ? '#047857' : '#854d0e' }}>
              {checandoReceptor ? 'Conferindo e atualizando o receptor deste celular...' :
                receptorAtual ? '✓ Receptor deste celular atualizado para notificações de teste.' :
                  'Receptor ainda não confirmado neste celular.'}
            </p>
            <button type="button" onClick={verificarReceptor} disabled={checandoReceptor || ocupado || testando}
              style={{ ...estiloAcao, marginBottom: 8 }}>Verificar receptor novamente</button>
            <button type="button" onClick={testarNotificacao}
              disabled={ocupado || testando || diagnosticando || checandoReceptor || !receptorAtual || !total} style={estiloAcao}>
              {testando ? 'Enviando teste...' : 'Enviar notificação de teste'}
            </button>
            <p style={{ margin: '8px 0 0', fontSize: 12, color: '#64748b' }}>
              Limite: um teste por minuto. O envio de tarefas reais permanece desativado.
            </p>
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
              <strong>Diagnóstico deste aparelho (sem envio remoto)</strong>
              <p style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.5 }}>
                Confira a permissão e a assinatura deste celular e solicite uma notificação local.
                Não envia nada ao outro aparelho.
              </p>
              <button type="button" onClick={diagnosticarEsteAparelho}
                disabled={ocupado || testando || diagnosticando || checandoReceptor || !receptorAtual}
                style={estiloAcao}>
                {diagnosticando ? 'Verificando aparelho...' : 'Testar notificação local neste aparelho'}
              </button>
            </div>
          </div>}
          {config?.envios_ativos === true && <p role="status" style={{ fontSize: 12, color: '#047857', margin: 0 }}>
            Notificações automáticas de tarefas ativas neste ambiente.
          </p>}
          {config?.envios_ativos === false && <p style={{ fontSize: 12, color: '#854d0e', margin: 0 }}>
            Notificações automáticas de tarefas desativadas neste ambiente.
          </p>}
          {erro && <p role="alert" style={{ color: '#b91c1c', fontSize: 13, margin: 0 }}>{erro}</p>}
          {feedback && <p role="status" style={{ color: '#047857', fontSize: 13, margin: 0 }}>{feedback}</p>}
        </div>
        <div className="modal-actions">
          <button type="button" className="button-secondary" onClick={onClose}>Fechar</button>
        </div>
      </section>
    </div>
  )
}
