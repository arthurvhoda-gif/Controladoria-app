import { useCallback, useEffect, useMemo, useState } from 'react'
import './CentralServicos.css'

const ETAPAS = {
  'Aguardando ciência': 'Receber',
  'Recebido': 'Iniciar',
  'Em andamento': 'Concluir',
  'Aguardando validação': 'Validar',
}
const ACOES = {
  'Aguardando ciência': 'confirmar',
  'Recebido': 'iniciar',
  'Em andamento': 'concluir',
  'Aguardando validação': 'validar',
}
const inicial = { titulo: '', descricao: '', condominio_id: '', responsavel_id: '', prioridade: 'Normal', prazo: '' }
const hojeLocal = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
const exibirData = s => s ? new Date(String(s).length === 10 ? `${s}T12:00:00` : s).toLocaleDateString('pt-BR') : '-'

export default function CentralServicos({ apiUrl, usuario, condominios = [] }) {
  const gestor = usuario?.perfil === 'Controladoria'
  const [servicos, setServicos] = useState([])
  const [pessoas, setPessoas] = useState([])
  const [avisos, setAvisos] = useState([])
  const [selecionado, setSelecionado] = useState(null)
  const [historico, setHistorico] = useState([])
  const [form, setForm] = useState(inicial)
  const [mostrarNovo, setMostrarNovo] = useState(false)
  const [textoAcao, setTextoAcao] = useState('')
  const [devolvendo, setDevolvendo] = useState(false)
  const [filtro, setFiltro] = useState('todos')
  const [busca, setBusca] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [mensagem, setMensagem] = useState('')
  const token = usuario?.token

  const requisitar = useCallback(async (caminho, opcoes = {}) => {
    const res = await fetch(`${apiUrl}${caminho}`, {
      ...opcoes,
      cache: 'no-store',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...opcoes.headers }
    })
    if (!res.ok) {
      let detalhe = `Erro ${res.status}.`
      try { const json = await res.json(); detalhe = json.detail || detalhe } catch { /* sem corpo JSON */ }
      throw new Error(typeof detalhe === 'string' ? detalhe : JSON.stringify(detalhe))
    }
    return res.json()
  }, [apiUrl, token])

  const atualizar = useCallback(async (silencioso = false) => {
    if (!token) return
    if (!silencioso) setCarregando(true)
    try {
      const chamadas = [requisitar('/servicos'), requisitar('/servicos/notificacoes')]
      if (gestor) chamadas.push(requisitar('/servicos/responsaveis'))
      const [lista, notificacoes, responsaveis] = await Promise.all(chamadas)
      setServicos(lista)
      setAvisos(notificacoes)
      if (gestor) setPessoas(responsaveis)
      setSelecionado(anterior => anterior ? (lista.find(s => s.id === anterior.id) || null) : null)
      setErro('')
    } catch (e) { if (!silencioso) setErro(e.message) }
    finally { if (!silencioso) setCarregando(false) }
  }, [token, gestor, requisitar])

  useEffect(() => {
    setServicos([]); setAvisos([]); setSelecionado(null); setHistorico([])
    atualizar()
    const id = setInterval(() => { if (document.visibilityState === 'visible') atualizar(true) }, 60000)
    return () => clearInterval(id)
  }, [atualizar])

  useEffect(() => {
    if (!selecionado) { setHistorico([]); return }
    let valido = true
    requisitar(`/servicos/${selecionado.id}/historico`).then(dados => { if (valido) setHistorico(dados) }).catch(e => { if (valido) setErro(e.message) })
    return () => { valido = false }
  }, [selecionado?.id, selecionado?.status, requisitar])

  const candidatos = useMemo(() => pessoas.filter(p => p.perfil !== 'Checklist' || Number(p.condominio_id) === Number(form.condominio_id)), [pessoas, form.condominio_id])
  const filtrados = useMemo(() => servicos.filter(s => {
    if (filtro === 'atrasadas' && !s.atrasado) return false
    if (filtro === 'abertas' && s.status === 'Concluído') return false
    if (filtro === 'concluidas' && s.status !== 'Concluído') return false
    const termo = busca.toLocaleLowerCase('pt-BR')
    return !termo || `${s.titulo} ${s.condominio} ${s.responsavel}`.toLocaleLowerCase('pt-BR').includes(termo)
  }), [servicos, filtro, busca])
  const pendentes = servicos.filter(s => s.status !== 'Concluído').length
  const atrasadas = servicos.filter(s => s.atrasado).length
  const naoLidas = avisos.filter(a => !a.lida).length

  async function abrirServico(s) {
    setSelecionado(s); setTextoAcao(''); setDevolvendo(false); setMensagem('')
    const avisosDessaTarefa = avisos.filter(a => a.servico_id === s.id && !a.lida)
    for (const aviso of avisosDessaTarefa) {
      try { await requisitar(`/servicos/notificacoes/${aviso.id}/ler`, { method: 'POST' }) }
      catch { /* tentará de novo na próxima atualização */ }
    }
    if (avisosDessaTarefa.length) setAvisos(prev => prev.map(a => a.servico_id === s.id ? { ...a, lida: true } : a))
  }

  async function criar(e) {
    e.preventDefault(); if (salvando) return
    setSalvando(true); setErro('')
    try {
      const dados = {
        ...form, condominio_id: Number(form.condominio_id), responsavel_id: Number(form.responsavel_id),
      }
      const criado = await requisitar('/servicos', { method: 'POST', body: JSON.stringify(dados) })
      setMostrarNovo(false); setForm(inicial); setMensagem('Serviço criado e aviso interno registrado.')
      await atualizar(true); setSelecionado(criado)
    } catch (e) { setErro(e.message) }
    finally { setSalvando(false) }
  }

  async function executar(acao) {
    if (!selecionado || salvando) return
    if (['concluir', 'devolver'].includes(acao) && textoAcao.trim().length < 10) {
      setErro('Escreva uma observação com pelo menos 10 caracteres.'); return
    }
    setSalvando(true); setErro('')
    try {
      const atualizado = await requisitar(`/servicos/${selecionado.id}/acoes`, {
        method: 'POST', body: JSON.stringify({ acao, observacao: textoAcao.trim() })
      })
      setMensagem('Andamento registrado com sucesso.')
      setSelecionado(atualizado); setTextoAcao(''); setDevolvendo(false)
      await atualizar(true)
    } catch (e) { setErro(e.message); await atualizar(true) }
    finally { setSalvando(false) }
  }

  const responsavelAtual = selecionado && usuario?.id === selecionado.responsavel_id
  const acaoPrincipal = selecionado && ACOES[selecionado.status]
  const podeAcao = selecionado && (selecionado.status === 'Aguardando validação' ? gestor : responsavelAtual)

  return <section className="haize-servicos">
    <div className="hs-top">
      <div><span className="hs-eyebrow">OPERAÇÃO & CONTROLE</span><h2>Central de Serviços</h2><p>Solicitações internas com responsável, prazo e histórico auditável.</p></div>
      <div className="hs-top-actions"><button className="hs-btn hs-outline" onClick={() => atualizar()} disabled={carregando}>Atualizar</button>{gestor && <button className="hs-btn hs-primary" onClick={() => { setForm(inicial); setMostrarNovo(true); setErro('') }}>+ Novo serviço</button>}</div>
    </div>
    <div className="hs-stats"><div><span>Meus serviços / serviços da equipe</span><strong>{servicos.length}</strong></div><div><span>Em aberto</span><strong>{pendentes}</strong></div><div><span>Atrasados</span><strong className={atrasadas ? 'hs-danger' : ''}>{atrasadas}</strong></div><div><span>Avisos não lidos</span><strong>{naoLidas}</strong></div></div>
    {erro && <p className="hs-alert" role="alert">{erro}</p>}
    {mensagem && <p className="hs-success" role="status">{mensagem}</p>}
    {avisos.some(a => !a.lida) && <div className="hs-notices"><strong>Avisos recentes</strong>{avisos.filter(a => !a.lida).slice(0, 3).map(a => <button key={a.id} onClick={() => { const s = servicos.find(s => s.id === a.servico_id); if (s) abrirServico(s) }}>{a.mensagem} <span>Ver tarefa</span></button>)}</div>}
    <div className="hs-filters"><input aria-label="Buscar serviço" value={busca} placeholder="Buscar serviço, condomínio ou responsável..." onChange={e => setBusca(e.target.value)}/><select aria-label="Filtrar serviços" value={filtro} onChange={e => setFiltro(e.target.value)}><option value="todos">Todos os serviços</option><option value="abertas">Em aberto</option><option value="atrasadas">Atrasados</option><option value="concluidas">Concluídos</option></select></div>
    <div className="hs-layout"><div className="hs-list">{carregando ? <p>Carregando serviços...</p> : filtrados.length ? filtrados.map(s => <button className={`hs-task ${selecionado?.id === s.id ? 'hs-selected' : ''}`} key={s.id} onClick={() => abrirServico(s)}><span className="hs-task-top"><strong>#{s.id} · {s.titulo}</strong><span className={`hs-priority hs-${s.prioridade.toLowerCase()}`}>{s.prioridade}</span></span><small>{s.condominio} · {s.responsavel}</small><span className="hs-task-bottom"><span>{s.status}</span><span className={s.atrasado ? 'hs-danger' : ''}>{s.atrasado ? 'Atrasado · ' : 'Prazo: '}{exibirData(s.prazo)}</span></span></button>) : <div className="hs-empty">Nenhum serviço encontrado.</div>}</div>
      <aside className="hs-detail">{selecionado ? <><div className="hs-detail-head"><span>Serviço #{selecionado.id}</span><span className="hs-status">{selecionado.status}</span></div><h3>{selecionado.titulo}</h3><p>{selecionado.descricao}</p><dl><div><dt>Condomínio</dt><dd>{selecionado.condominio}</dd></div><div><dt>Responsável</dt><dd>{selecionado.responsavel}</dd></div><div><dt>Solicitado por</dt><dd>{selecionado.criador}</dd></div><div><dt>Prioridade</dt><dd>{selecionado.prioridade}</dd></div><div><dt>Prazo</dt><dd>{exibirData(selecionado.prazo)}</dd></div></dl>
      {podeAcao && <div className="hs-action"><label htmlFor="hs-observacao">Observação / resultado</label><textarea id="hs-observacao" rows="3" value={textoAcao} onChange={e => setTextoAcao(e.target.value)} placeholder="Descreva o andamento ou a conclusão..."/><div className="hs-action-buttons"><button className="hs-btn hs-primary" disabled={salvando} onClick={() => executar(acaoPrincipal)}>{salvando ? 'Salvando...' : ETAPAS[selecionado.status]}</button>{gestor && selecionado.status === 'Aguardando validação' && <button className="hs-btn hs-outline" disabled={salvando} onClick={() => setDevolvendo(!devolvendo)}>{devolvendo ? 'Cancelar devolução' : 'Devolver'}</button>}{devolvendo && <button className="hs-btn hs-warn" disabled={salvando} onClick={() => executar('devolver')}>Confirmar devolução</button>}</div>{['concluir', 'devolver'].includes(devolvendo ? 'devolver' : acaoPrincipal) && <small>Observação obrigatória: pelo menos 10 caracteres.</small>}</div>}
      <h4>Histórico</h4><ol className="hs-history">{historico.map(e => <li key={e.id}><strong>{e.acao}</strong><span>{e.autor} · {exibirData(e.data)}</span>{e.observacao && <p>{e.observacao}</p>}</li>)}</ol>
      </> : <div className="hs-empty">Selecione um serviço para visualizar os detalhes e o histórico.</div>}</aside>
    </div>
    {mostrarNovo && <div className="hs-modal-overlay" onClick={e => { if (e.target === e.currentTarget && !salvando) setMostrarNovo(false) }}><form className="hs-modal" onSubmit={criar}><div className="hs-modal-head"><h3>Novo serviço</h3><button type="button" onClick={() => setMostrarNovo(false)} aria-label="Fechar formulário">×</button></div><label>Título<input maxLength={180} minLength={4} required value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}/></label><label>Condomínio<select required value={form.condominio_id} onChange={e => setForm(f => ({ ...f, condominio_id: e.target.value, responsavel_id: '' }))}><option value="">Selecione</option>{condominios.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></label><label>Responsável<select required value={form.responsavel_id} onChange={e => setForm(f => ({ ...f, responsavel_id: e.target.value }))}><option value="">Selecione</option>{candidatos.map(p => <option key={p.id} value={p.id}>{p.nome} · {p.perfil}</option>)}</select></label><label>Prioridade<select value={form.prioridade} onChange={e => setForm(f => ({ ...f, prioridade: e.target.value }))}><option>Baixa</option><option>Normal</option><option>Alta</option><option>Urgente</option></select></label><label>Prazo<input type="date" required value={form.prazo} min={hojeLocal()} onChange={e => setForm(f => ({ ...f, prazo: e.target.value }))}/></label><label>Descrição<textarea required minLength={5} maxLength={4000} rows={4} value={form.descricao} onChange={e => setForm(f => ({ ...f, descricao: e.target.value }))}/></label><button className="hs-btn hs-primary" disabled={salvando || !form.condominio_id || !form.responsavel_id}>{salvando ? 'Criando...' : 'Criar serviço e avisar responsável'}</button></form></div>}
  </section>
}
