import { useEffect, useState } from 'react'
import './PreviaAvisosWhatsApp.css'

const rotulosDiagnostico = {
  coerente: 'Coerente',
  possivelmente_desatualizado: 'Possivelmente desatualizado',
  informativo: 'Informativo',
  revisar: 'Revisar',
}

export default function PreviaAvisosWhatsApp({ apiUrl, token }) {
  const [aberto, setAberto] = useState(false)
  const [recarregar, setRecarregar] = useState(0)
  const [dados, setDados] = useState([])
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (!aberto) return undefined
    const controller = new AbortController()
    let ativo = true
    setCarregando(true)
    setErro('')
    fetch(`${apiUrl}/avisos-whatsapp/fila/previas`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
      signal: controller.signal,
    }).then(async resposta => {
      const corpo = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(corpo.detail || 'Não foi possível carregar as prévias.')
      if (!Array.isArray(corpo.previa)) throw new Error('Formato de resposta inesperado.')
      if (ativo) setDados(corpo.previa)
    }).catch(e => {
      if (ativo && e.name !== 'AbortError') setErro(e.message || 'Erro ao carregar prévias.')
    }).finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false; controller.abort() }
  }, [aberto, recarregar, apiUrl, token])

  return <section className="wa-previa" aria-label="Prévia de avisos WhatsApp">
    <div className="wa-previa-cabecalho">
      <div>
        <h3>Prévia de notificações</h3>
        <p>Consulte as mensagens preparadas. Nenhum WhatsApp é enviado.</p>
      </div>
      <button className="wa-previa-botao" type="button" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>
        {aberto ? 'Ocultar prévias' : 'Exibir prévias'}
      </button>
    </div>
    {aberto && <div className="wa-previa-conteudo">
      <div className="wa-previa-barra">
        <span>Até 30 avisos preparados mais recentes</span>
        <button className="wa-previa-botao" type="button" onClick={() => setRecarregar(i => i + 1)} disabled={carregando}>
          Atualizar prévias
        </button>
      </div>
      {carregando && <p role="status">Carregando prévias...</p>}
      {erro && <p className="wa-previa-erro" role="alert">{erro}</p>}
      {!carregando && !erro && dados.length === 0 && <p>Nenhuma notificação preparada no momento.</p>}
      {!carregando && !erro && dados.map(item => <article className="wa-previa-item" key={item.fila_id}>
        <div className="wa-previa-meta">
          <strong>{item.destinatario}</strong>
          <span>Solicitação #{String(item.servico_id).padStart(4, '0')}</span>
          <span>{item.status}</span>
          {!item.elegivel_agora && <span className="wa-previa-alerta">Sem autorização ou número ativo</span>}
          {item.diagnostico && <span className={['revisar', 'possivelmente_desatualizado'].includes(item.diagnostico.situacao) ? 'wa-previa-alerta' : ''}>
            Diagnóstico: {rotulosDiagnostico[item.diagnostico.situacao] || 'Revisar'}
          </span>}
        </div>
        <small>Tipo de aviso: {item.evento.replaceAll('_', ' ')}</small>
        <pre className="wa-previa-mensagem">{item.mensagem}</pre>
        {item.diagnostico?.motivo && <p className="wa-previa-nota">Análise: {item.diagnostico.motivo}</p>}
        <p className="wa-previa-nota">Diagnóstico indicativo: não autoriza envio automático. Ações e registros devem ser feitos no aplicativo.</p>
      </article>)}
    </div>}
  </section>
}
