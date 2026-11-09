import { useEffect, useState } from 'react'

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
  const [feedback, setFeedback] = useState('')
  const [erro, setErro] = useState('')
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
    if (!suportado || !config?.registro_disponivel || !config?.chave_publica) return
    if (ehIOS && !instalado()) {
      setErro('No iPhone, abra o aplicativo pela tela inicial antes de ativar os avisos.')
      return
    }
    let assinatura = null
    let criadaAgora = false
    try {
      // A permissão precisa ser solicitada diretamente após o toque do usuário.
      const permissao = await Notification.requestPermission()
      if (permissao !== 'granted') {
        setErro('Permissão negada ou não concedida. Você pode alterá-la nas configurações do aparelho.')
        return
      }
      setOcupado(true)
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
        assinatura = await registro.pushManager.subscribe({
          userVisibleOnly: true, applicationServerKey: publica,
        })
        criadaAgora = true
      }
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
      setFeedback('Este aparelho foi registrado para receber Web Push. O envio automático ainda está em preparação.')
    } catch (e) {
      if (criadaAgora && assinatura) {
        await assinatura.unsubscribe().catch(() => {})
      }
      setErro(e.message || 'Falha ao registrar dispositivo.')
    } finally {
      setOcupado(false)
    }
  }

  async function testarNotificacao() {
    setErro('')
    setFeedback('')
    setTestando(true)
    try {
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
              style={estiloAcao}>Ativar notificações neste aparelho</button>
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
              Envia um aviso fictício somente aos seus dispositivos cadastrados.
              Feche os aplicativos nos celulares antes de testar a entrega.
            </p>
            <button type="button" onClick={testarNotificacao}
              disabled={ocupado || testando || !total} style={estiloAcao}>
              {testando ? 'Enviando teste...' : 'Enviar notificação de teste'}
            </button>
            <p style={{ margin: '8px 0 0', fontSize: 12, color: '#64748b' }}>
              Limite: um teste por minuto. O envio de tarefas reais permanece desativado.
            </p>
          </div>}
          {config?.envios_ativos === false && <p style={{ fontSize: 12, color: '#854d0e', margin: 0 }}>
            Homologação: notificações automáticas de tarefas ainda não estão ativas.
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
