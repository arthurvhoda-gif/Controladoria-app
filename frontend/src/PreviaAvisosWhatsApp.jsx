import { useEffect, useState } from 'react'
import './PreviaAvisosWhatsApp.css'

const rotulosDiagnostico = {
  coerente: 'Coerente',
  possivelmente_desatualizado: 'Possivelmente desatualizado',
  informativo: 'Informativo',
  revisar: 'Revisar',
}
const rotulosHistorico = {
  superado: 'Superado',
  nao_comprovado: 'Não comprovado',
  informativo: 'Informativo',
  revisar: 'Revisar',
}

const rotulosPreenvio = {
  impedido: 'Impedido',
  revisar: 'Revisar',
  pendente_de_validacao_operacional: 'Pendente de validação operacional',
}

export default function PreviaAvisosWhatsApp({ apiUrl, token }) {
  const [aberto, setAberto] = useState(false)
  const [recarregar, setRecarregar] = useState(0)
  // Cada consulta possui sua propria chave: dados de outra sessao nao aparecem.
  const [resultado, setResultado] = useState({ chave: '', dados: [], erro: '' })
  const chaveAtual = JSON.stringify([apiUrl, token, recarregar])
  const atual = resultado.chave === chaveAtual
  const dados = atual ? resultado.dados : []
  const erro = atual ? resultado.erro : ''
  const carregando = aberto && !atual

  useEffect(() => {
    if (!aberto) return undefined
    const controller = new AbortController()
    let ativo = true
    fetch(`${apiUrl}/avisos-whatsapp/fila/previas`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
      signal: controller.signal,
    }).then(async resposta => {
      const corpo = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(corpo.detail || 'Não foi possível carregar as prévias.')
      if (!Array.isArray(corpo.previa)) throw new Error('Formato de resposta inesperado.')
      if (ativo) setResultado({ chave: chaveAtual, dados: corpo.previa, erro: '' })
    }).catch(e => {
      if (ativo && e.name !== 'AbortError') {
        setResultado({ chave: chaveAtual, dados: [], erro: e.message || 'Erro ao carregar prévias.' })
      }
    })
    return () => { ativo = false; controller.abort() }
  }, [aberto, chaveAtual, apiUrl, token])

  return <section className="wa-previa" aria-label="Prévia de avisos WhatsApp">
    <div className="wa-previa-cabecalho">
      <div>
        <h3>Prévia de notificações</h3>
        <p>Consulte as mensagens preparadas. Nenhum WhatsApp é enviado.</p>
      </div>
      <button className="wa-previa-botao" type="button" aria-expanded={aberto} onClick={() => {
        if (!aberto) setRecarregar(i => i + 1)
        setAberto(!aberto)
      }}>
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
          {item.diagnostico_historico && <span className={
            item.sem_evento_origem && item.diagnostico_historico.situacao === 'revisar'
              ? ''
              : ['superado', 'revisar'].includes(item.diagnostico_historico.situacao) ? 'wa-previa-alerta' : ''
          }>
            Histórico: {item.sem_evento_origem && item.diagnostico_historico.situacao === 'revisar'
              ? 'Origem não registrada (revisar)'
              : (rotulosHistorico[item.diagnostico_historico.situacao] || 'Revisar')}
          </span>}
          {item.diagnostico_preenvio && <span className={item.diagnostico_preenvio.situacao === 'impedido' ? 'wa-previa-alerta' : ''}>
            Pré-envio: {rotulosPreenvio[item.diagnostico_preenvio.situacao] || 'Revisar'}
          </span>}
        </div>
        <small>Tipo de aviso: {item.evento.replaceAll('_', ' ')}</small>
        <pre className="wa-previa-mensagem">{item.mensagem}</pre>
        {item.diagnostico?.motivo && <p className="wa-previa-nota">Análise: {item.diagnostico.motivo}</p>}
        {item.diagnostico_historico?.motivo && <p className="wa-previa-nota">
          Histórico: {item.sem_evento_origem && item.diagnostico_historico.situacao === 'revisar'
            ? 'Aviso sem vínculo com evento de origem. Pode ser anterior à V6.5; exige conferência manual.'
            : item.diagnostico_historico.motivo}
          {item.diagnostico_historico.evento_superador ? ` (evento #${item.diagnostico_historico.evento_superador})` : ''}
        </p>}
        {item.diagnostico_preenvio?.motivo && <p className="wa-previa-nota">Pré-envio (simulação): {item.diagnostico_preenvio.motivo}</p>}
        <p className="wa-previa-nota">Diagnóstico indicativo: não autoriza envio automático. Ações e registros devem ser feitos no aplicativo.</p>
      </article>)}
    </div>}
  </section>
}
