import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './CentralServicos.css'

// V3: apresentação e usabilidade. Mantém os contratos HTTP da Central de Serviços V2.
const NOVO = { titulo: '', descricao: '', condominio_id: '', executores_ids: [], fiscalizadores_ids: [], prioridade: 'Normal', prazo: '' }
const NOMES_ACOES = { confirmar: 'Confirmar ciência', iniciar: 'Iniciar minha etapa', concluir: 'Concluir minha etapa', validar: 'Aprovar etapa', devolver: 'Devolver para ajustes' }
const ACENTOS = { Baixa: 1, Normal: 2, Alta: 3, Urgente: 4 }
const horarioBR = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo' })
const dataBR = data => {
  if (!data) return 'Sem prazo'
  const texto = String(data)
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) {
    const [ano, mes, dia] = texto.split('-')
    return `${dia}/${mes}/${ano}`
  }
  const d = new Date(texto)
  return Number.isNaN(d.getTime()) ? 'Data indisponível' : horarioBR.format(d)
}
const diaHoje = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const prazoInfo = (texto, concluido = false) => {
  if (!texto) return { texto: 'Sem prazo', tom: 'neutral' }
  if (concluido) return { texto: `Prazo ${dataBR(texto)}`, tom: 'neutral' }
  const hoje = diaHoje()
  const utc = d => Date.parse(`${d}T12:00:00Z`)
  const dif = Math.round((utc(String(texto).slice(0, 10)) - utc(hoje)) / 86400000)
  if (!Number.isFinite(dif)) return { texto: dataBR(texto), tom: 'neutral' }
  if (dif < 0) return { texto: `Atrasado ${Math.abs(dif)} ${dif === -1 ? 'dia' : 'dias'}`, tom: 'danger' }
  if (dif === 0) return { texto: 'Vence hoje', tom: 'warning' }
  if (dif === 1) return { texto: 'Vence amanhã', tom: 'warning' }
  if (dif <= 3) return { texto: `Vence em ${dif} dias`, tom: 'warning' }
  return { texto: dataBR(texto), tom: 'neutral' }
}
const iniciais = nome => String(nome || '?').trim().split(/\s+/).slice(0, 2).map(p => p.charAt(0)).join('').toUpperCase()
const normaliza = valor => String(valor ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR')
const classeStatus = status => {
  if (status === 'Concluído' || status === 'Finalizado' || status === 'Aprovado') return 'done'
  if (status === 'Aguardando ciência') return 'new'
  if (status === 'Aguardando fiscalização' || status === 'Aguardando validação') return 'review'
  return 'progress'
}

function SIcon({ nome, size = 18 }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  const p = {
    plus: <><path d="M12 5v14M5 12h14"/></>,
    refresh: <><path d="M20 11a8 8 0 0 0-14.6-4.5L3 9m0-5v5h5M4 13a8 8 0 0 0 14.6 4.5L21 15m0 5v-5h-5"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.5"/><path d="m16 16 5 5"/></>,
    close: <><path d="M18 6 6 18M6 6l12 12"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
    check: <><path d="M20 6 9 17l-5-5"/></>,
    checkCircle: <><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></>,
    alert: <><path d="M12 3 2 20h20L12 3Z"/><path d="M12 9v5M12 17h.01"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1"/></>,
    clipboard: <><rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6M9 15h6"/></>,
    arrow: <><path d="m9 18 6-6-6-6"/></>,
    back: <><path d="m15 18-6-6 6-6"/></>,
    filter: <><path d="M4 7h16M7 12h10M10 17h4"/></>,
    spark: <><path d="m12 3 1.9 6.1L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9L12 3Z"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  }
  return <svg {...props}>{p[nome] || p.info}</svg>
}

function Etiqueta({ status }) { return <span className={`hs-v3-status hs-v3-${classeStatus(status)}`}>{status || 'Indefinido'}</span> }
function Avatar({ nome }) { return <span className="hs-v3-avatar" aria-hidden="true">{iniciais(nome)}</span> }

export default function CentralServicos({ apiUrl, usuario, condominios = [] }) {
  const gestor = usuario?.perfil === 'Controladoria'
  const token = usuario?.token
  const [servicos, setServicos] = useState([])
  const [pessoas, setPessoas] = useState([])
  const [avisos, setAvisos] = useState([])
  const [selecionado, setSelecionado] = useState(null)
  const [historico, setHistorico] = useState([])
  const [form, setForm] = useState(NOVO)
  const [novoAberto, setNovoAberto] = useState(false)
  const [pesquisaExec, setPesquisaExec] = useState('')
  const [pesquisaFiscal, setPesquisaFiscal] = useState('')
  const [textoAcao, setTextoAcao] = useState('')
  const [filtro, setFiltro] = useState('todos')
  const [ordem, setOrdem] = useState('recentes')
  const [busca, setBusca] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [erroForm, setErroForm] = useState('')
  const [mensagem, setMensagem] = useState('')
  const [mostraAvisos, setMostraAvisos] = useState(false)
  const [abaMobile, setAbaMobile] = useState('lista')
  const modalRef = useRef(null)
  const abrirRef = useRef(null)
  const ultimaRequisicao = useRef(0)

  const requisitar = useCallback(async (caminho, opcoes = {}) => {
    const resposta = await fetch(`${apiUrl}${caminho}`, {
      ...opcoes, cache: 'no-store',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...opcoes.headers },
    })
    if (!resposta.ok) {
      let detalhe = `Não foi possível concluir a operação (${resposta.status}).`
      try { const json = await resposta.json(); detalhe = json.detail || detalhe } catch { /* erro sem JSON */ }
      throw new Error(typeof detalhe === 'string' ? detalhe : JSON.stringify(detalhe))
    }
    return resposta.json()
  }, [apiUrl, token])

  const atualizar = useCallback(async (silencioso = false) => {
    if (!token) return
    const chave = ++ultimaRequisicao.current
    if (!silencioso) setCarregando(true)
    try {
      const rotas = [requisitar('/servicos'), requisitar('/servicos/notificacoes')]
      if (gestor) rotas.push(requisitar('/servicos/responsaveis'))
      const [lista, notificacoes, responsaveis] = await Promise.all(rotas)
      if (chave !== ultimaRequisicao.current) return
      setServicos(Array.isArray(lista) ? lista : [])
      setAvisos(Array.isArray(notificacoes) ? notificacoes : [])
      if (gestor) setPessoas(Array.isArray(responsaveis) ? responsaveis : [])
      setSelecionado(anterior => anterior ? (lista.find(s => s.id === anterior.id) || null) : null)
      setErro('')
    } catch (e) { if (!silencioso && chave === ultimaRequisicao.current) setErro(e.message || 'Falha ao atualizar os serviços.') }
    finally { if (!silencioso && chave === ultimaRequisicao.current) setCarregando(false) }
  }, [token, gestor, requisitar])

  useEffect(() => {
    setServicos([]); setAvisos([]); setSelecionado(null); setHistorico([])
    atualizar()
    const timer = setInterval(() => { if (document.visibilityState === 'visible') atualizar(true) }, 60000)
    return () => { ultimaRequisicao.current++; clearInterval(timer) }
  }, [atualizar])

  useEffect(() => {
    if (!selecionado) { setHistorico([]); return }
    let ativo = true
    requisitar(`/servicos/${selecionado.id}/historico`)
      .then(dados => { if (ativo) setHistorico(dados) })
      .catch(e => { if (ativo) setErro(e.message) })
    return () => { ativo = false }
  }, [selecionado?.id, selecionado?.status, requisitar])

  useEffect(() => {
    if (!novoAberto) return
    const anterior = document.activeElement
    const tecla = e => {
      if (e.key === 'Escape' && !salvando) fecharModal()
      if (e.key !== 'Tab' || !modalRef.current) return
      const focaveis = [...modalRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)')]
      if (!focaveis.length) return
      const primeiro = focaveis[0], ultimo = focaveis[focaveis.length - 1]
      if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus() }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus() }
    }
    document.addEventListener('keydown', tecla)
    document.body.style.overflow = 'hidden'
    const primeiroCampo = modalRef.current?.querySelector('input[name="titulo"]')
    primeiroCampo?.focus()
    return () => { document.removeEventListener('keydown', tecla); document.body.style.overflow = ''; anterior?.focus?.() }
  }, [novoAberto, salvando])

  const candidatos = useMemo(() => form.condominio_id ? pessoas.filter(p => p.perfil !== 'Checklist' || Number(p.condominio_id) === Number(form.condominio_id)) : [], [pessoas, form.condominio_id])
  const candidatosExec = useMemo(() => candidatos.filter(p => normaliza(`${p.nome} ${p.perfil}`).includes(normaliza(pesquisaExec))), [candidatos, pesquisaExec])
  const candidatosFiscal = useMemo(() => candidatos.filter(p => normaliza(`${p.nome} ${p.perfil}`).includes(normaliza(pesquisaFiscal))), [candidatos, pesquisaFiscal])
  const nomePorId = useMemo(() => new Map(pessoas.map(p => [p.id, p.nome])), [pessoas])

  const filtrados = useMemo(() => {
    const termo = normaliza(busca.trim())
    const itens = servicos.filter(s => {
      if (filtro === 'atrasados' && !s.atrasado) return false
      if (filtro === 'abertos' && s.status === 'Concluído') return false
      if (filtro === 'concluidos' && s.status !== 'Concluído') return false
      if (filtro === 'revisao' && !['Aguardando fiscalização', 'Aguardando validação'].includes(s.status)) return false
      const nomes = [...(s.executores || []), ...(s.fiscalizadores || [])].map(p => p.nome).join(' ')
      return !termo || normaliza(`${s.id} ${s.titulo} ${s.condominio} ${s.descricao} ${s.criador} ${nomes}`).includes(termo)
    })
    return [...itens].sort((a, b) => {
      if (ordem === 'prazo') return (a.prazo || '9999').localeCompare(b.prazo || '9999') || b.id - a.id
      if (ordem === 'prioridade') return (ACENTOS[b.prioridade] || 0) - (ACENTOS[a.prioridade] || 0) || b.id - a.id
      if (ordem === 'antigos') return a.id - b.id
      return b.id - a.id
    })
  }, [servicos, filtro, busca, ordem])

  const abertos = servicos.filter(s => s.status !== 'Concluído').length
  const atrasados = servicos.filter(s => s.atrasado).length
  const revisao = servicos.filter(s => ['Aguardando fiscalização', 'Aguardando validação'].includes(s.status)).length
  const naoLidas = avisos.filter(a => !a.lida)
  const acoes = selecionado?.acoes_disponiveis || []
  const concluidos = selecionado?.executores?.filter(p => p.status === 'Finalizado').length || 0
  const totalExec = selecionado?.executores?.length || 0

  function abrirModal() { setForm({ ...NOVO, executores_ids: [], fiscalizadores_ids: [] }); setPesquisaExec(''); setPesquisaFiscal(''); setErroForm(''); setMensagem(''); setNovoAberto(true) }
  function fecharModal() { if (!salvando) { setNovoAberto(false); setErroForm('') } }
  function alterarForm(campo, valor) { setForm(anterior => ({ ...anterior, [campo]: valor })); if (erroForm) setErroForm('') }
  function alternarParticipante(campo, id) {
    setForm(anterior => ({ ...anterior, [campo]: anterior[campo].includes(id) ? anterior[campo].filter(p => p !== id) : [...anterior[campo], id] }))
    if (erroForm) setErroForm('')
  }

  async function abrirServico(s) {
    setSelecionado(s); setTextoAcao(''); setErro(''); setMensagem(''); setAbaMobile('detalhe')
    const pendentes = avisos.filter(a => a.servico_id === s.id && !a.lida)
    if (pendentes.length) {
      // A leitura é por usuário; o backend nunca altera avisos de terceiros.
      const resultados = await Promise.allSettled(pendentes.map(a => requisitar(`/servicos/notificacoes/${a.id}/ler`, { method: 'POST' })))
      const lidos = new Set(pendentes.filter((_, i) => resultados[i].status === 'fulfilled').map(a => a.id))
      setAvisos(anterior => anterior.map(a => lidos.has(a.id) ? { ...a, lida: true } : a))
    }
  }

  async function criar(e) {
    e.preventDefault(); if (salvando) return
    if (form.titulo.trim().length < 4 || form.descricao.trim().length < 5) { setErroForm('Preencha o título e a descrição com detalhes suficientes.'); return }
    if (!form.condominio_id) { setErroForm('Selecione o condomínio.'); return }
    if (!form.executores_ids.length) { setErroForm('Escolha pelo menos um executor.'); return }
    if (!form.prazo) { setErroForm('Informe o prazo do serviço.'); return }
    if (form.prazo < diaHoje()) { setErroForm('O prazo não pode estar no passado.'); return }
    setSalvando(true); setErroForm(''); setErro('')
    try {
      const dados = { ...form, titulo: form.titulo.trim(), descricao: form.descricao.trim(), condominio_id: Number(form.condominio_id) }
      const criado = await requisitar('/servicos', { method: 'POST', body: JSON.stringify(dados) })
      setNovoAberto(false)
      setMensagem('Serviço criado! Os participantes receberam avisos internos na Controladoria.')
      await atualizar(true)
      setSelecionado(criado); setAbaMobile('detalhe')
      setHistorico(await requisitar(`/servicos/${criado.id}/historico`))
    } catch (e) { setErroForm(e.message || 'Não foi possível criar o serviço.') }
    finally { setSalvando(false) }
  }

  async function executar(acao) {
    if (!selecionado || salvando) return
    if (['concluir', 'devolver'].includes(acao) && textoAcao.trim().length < 10) {
      setErro('Descreva o resultado ou motivo com pelo menos 10 caracteres.'); return
    }
    setSalvando(true); setErro(''); setMensagem('')
    try {
      const id = selecionado.id
      const atualizado = await requisitar(`/servicos/${id}/acoes`, { method: 'POST', body: JSON.stringify({ acao, observacao: textoAcao.trim() }) })
      setSelecionado(atualizado); setTextoAcao('')
      setMensagem('Atualização registrada no histórico do serviço.')
      await atualizar(true)
      setHistorico(await requisitar(`/servicos/${id}/historico`))
    } catch (e) { setErro(e.message || 'Não foi possível registrar a ação.'); await atualizar(true) }
    finally { setSalvando(false) }
  }

  return <section className="haize-servicos hs-v3" aria-label="Central de Serviços">
    <header className="hs-v3-heading">
      <div className="hs-v3-heading-copy"><div className="hs-v3-eyebrow"><span className="hs-v3-eyebrow-dot"/>GESTÃO OPERACIONAL <span className="hs-v3-eyebrow-separator">/</span> SERVIÇOS</div><h2>Central de Serviços</h2><p>Responsabilidades definidas, execução acompanhada e histórico transparente de cada atividade.</p></div>
      <div className="hs-v3-heading-actions"><button type="button" className="hs-v3-button hs-v3-button-light" onClick={() => atualizar()} disabled={carregando || salvando}><SIcon nome="refresh" size={16}/><span>Atualizar</span></button>{gestor && <button type="button" ref={abrirRef} className="hs-v3-button hs-v3-button-primary" onClick={abrirModal}><SIcon nome="plus" size={18}/>Novo serviço</button>}</div>
    </header>

    <div className="hs-v3-metrics" aria-label="Indicadores de serviços">
      <button className={`hs-v3-metric ${filtro === 'todos' ? 'is-active' : ''}`} onClick={() => setFiltro('todos')} type="button"><span className="hs-v3-metric-label">Total de serviços <SIcon nome="layers" size={18}/></span><strong>{servicos.length}</strong><span className="hs-v3-metric-meta">Todos os registros</span></button>
      <button className={`hs-v3-metric ${filtro === 'abertos' ? 'is-active' : ''}`} onClick={() => setFiltro('abertos')} type="button"><span className="hs-v3-metric-label">Em aberto <SIcon nome="clock" size={18}/></span><strong>{abertos}</strong><span className="hs-v3-metric-meta">Acompanhamento ativo</span></button>
      <button className={`hs-v3-metric ${filtro === 'atrasados' ? 'is-active' : ''} ${atrasados ? 'hs-v3-metric-alert' : ''}`} onClick={() => setFiltro('atrasados')} type="button"><span className="hs-v3-metric-label">Atrasados <SIcon nome="alert" size={18}/></span><strong>{atrasados}</strong><span className="hs-v3-metric-meta">Precisam de atenção</span></button>
      <button className={`hs-v3-metric ${filtro === 'revisao' ? 'is-active' : ''}`} onClick={() => setFiltro('revisao')} type="button"><span className="hs-v3-metric-label">Para validar <SIcon nome="checkCircle" size={18}/></span><strong>{revisao}</strong><span className="hs-v3-metric-meta">Fiscalização ou Controladoria</span></button>
    </div>

    {erro && <div className="hs-v3-flash hs-v3-flash-error" role="alert"><SIcon nome="alert"/><span>{erro}</span><button type="button" aria-label="Fechar mensagem" onClick={() => setErro('')}><SIcon nome="close" size={16}/></button></div>}
    {mensagem && <div className="hs-v3-flash hs-v3-flash-ok" role="status"><SIcon nome="checkCircle"/><span>{mensagem}</span><button type="button" aria-label="Fechar mensagem" onClick={() => setMensagem('')}><SIcon nome="close" size={16}/></button></div>}

    {naoLidas.length > 0 && <div className="hs-v3-notice-panel"><button type="button" className="hs-v3-notice-trigger" onClick={() => setMostraAvisos(v => !v)} aria-expanded={mostraAvisos}><span className="hs-v3-notice-icon"><SIcon nome="bell" size={19}/></span><span><strong>{naoLidas.length} {naoLidas.length === 1 ? 'aviso não lido' : 'avisos não lidos'}</strong><small>Atualizações de tarefas que precisam da sua atenção</small></span><span className="hs-v3-notice-link">{mostraAvisos ? 'Ocultar avisos' : 'Ver avisos'} <SIcon nome="arrow" size={16}/></span></button>{mostraAvisos && <div className="hs-v3-notices">{naoLidas.slice(0, 8).map(aviso => <button type="button" key={aviso.id} onClick={() => { const s = servicos.find(item => item.id === aviso.servico_id); if (s) abrirServico(s); else setErro('Este serviço não está disponível para o seu perfil.') }}><SIcon nome="bell" size={16}/><span>{aviso.mensagem}<small>{dataBR(aviso.criada_em)}</small></span><SIcon nome="arrow" size={15}/></button>)}</div>}</div>}

    <div className="hs-v3-workspace">
      <div className={`hs-v3-list-column ${abaMobile === 'detalhe' ? 'hs-v3-mobile-hide' : ''}`}>
        <div className="hs-v3-panel-header"><div><h3>Solicitações</h3><p>{filtrados.length} {filtrados.length === 1 ? 'resultado' : 'resultados'} {busca || filtro !== 'todos' ? 'encontrados' : 'registrados'}</p></div><span className="hs-v3-list-count">{filtrados.length}</span></div>
        <div className="hs-v3-searchbar"><SIcon nome="search" size={18}/><input type="search" aria-label="Pesquisar serviços" value={busca} placeholder="Buscar serviço, condomínio, pessoa..." onChange={e => setBusca(e.target.value)}/>{busca && <button type="button" aria-label="Limpar busca" onClick={() => setBusca('')}><SIcon nome="close" size={16}/></button>}</div>
        <div className="hs-v3-controls"><div className="hs-v3-chips" aria-label="Filtrar serviços">{[['todos','Todos'],['abertos','Em aberto'],['atrasados','Atrasados'],['revisao','Para validar'],['concluidos','Concluídos']].map(([valor, label]) => <button key={valor} type="button" className={filtro === valor ? 'is-active' : ''} aria-pressed={filtro === valor} onClick={() => setFiltro(valor)}>{label}</button>)}</div><label className="hs-v3-sort"><SIcon nome="filter" size={16}/><select aria-label="Ordenação das solicitações" value={ordem} onChange={e => setOrdem(e.target.value)}><option value="recentes">Mais recentes</option><option value="prazo">Prazo mais próximo</option><option value="prioridade">Maior prioridade</option><option value="antigos">Mais antigos</option></select></label></div>
        <div className="hs-v3-task-list" role="list" aria-label="Lista de solicitações">
          {carregando ? <div className="hs-v3-loading" role="status"><span className="hs-v3-spinner"/>Carregando serviços...</div> : filtrados.length === 0 ? <div className="hs-v3-zero"><span className="hs-v3-zero-icon"><SIcon nome="clipboard" size={28}/></span><h4>{servicos.length ? 'Nenhum serviço com esses filtros' : 'Tudo pronto para começar'}</h4><p>{servicos.length ? 'Experimente outro filtro ou limpe sua pesquisa.' : gestor ? 'Crie o primeiro serviço e acompanhe os responsáveis em um só lugar.' : 'Quando uma tarefa for atribuída a você, ela aparecerá aqui.'}</p>{servicos.length ? <button type="button" className="hs-v3-button hs-v3-button-light" onClick={() => { setFiltro('todos'); setBusca('') }}>Limpar filtros</button> : gestor ? <button type="button" className="hs-v3-button hs-v3-button-primary" onClick={abrirModal}><SIcon nome="plus" size={16}/>Criar primeiro serviço</button> : null}</div> : filtrados.map(s => {
            const due = prazoInfo(s.prazo, s.status === 'Concluído')
            return <div role="listitem" key={s.id}><button type="button" className={`hs-v3-task ${selecionado?.id === s.id ? 'is-selected' : ''}`} onClick={() => abrirServico(s)} aria-pressed={selecionado?.id === s.id}><span className="hs-v3-task-line"><span className="hs-v3-task-id">SERVIÇO #{s.id}</span><span className={`hs-v3-tag hs-v3-priority-${normaliza(s.prioridade)}`}>{s.prioridade}</span></span><strong className="hs-v3-task-title">{s.titulo}</strong><span className="hs-v3-task-condo">{s.condominio}</span><span className="hs-v3-task-footer"><Etiqueta status={s.status}/><span className={`hs-v3-due hs-v3-due-${due.tom}`}><SIcon nome="calendar" size={14}/>{due.texto}</span></span><span className="hs-v3-task-team"><SIcon nome="users" size={14}/>{(s.executores?.length || (s.responsavel ? 1 : 0))} executor(es){s.fiscalizadores?.length ? ` · ${s.fiscalizadores.length} fiscalizador(es)` : ''}</span></button></div>
          })}
        </div>
      </div>

      <div className={`hs-v3-detail-column ${abaMobile === 'lista' ? 'hs-v3-mobile-hide' : ''}`}>
        {!selecionado ? <div className="hs-v3-detail-empty"><span className="hs-v3-zero-icon"><SIcon nome="clipboard" size={30}/></span><h3>Selecione uma solicitação</h3><p>Acompanhe responsáveis, prazos, execução, fiscalização e todo o histórico em um único lugar.</p></div> : <div className="hs-v3-detail-inner">
          <button type="button" className="hs-v3-back" onClick={() => setAbaMobile('lista')}><SIcon nome="back" size={16}/>Voltar aos serviços</button>
          <div className="hs-v3-detail-top"><span className="hs-v3-task-id">SERVIÇO #{selecionado.id}</span><Etiqueta status={selecionado.status}/></div>
          <h3 className="hs-v3-detail-title">{selecionado.titulo}</h3><p className="hs-v3-detail-desc">{selecionado.descricao}</p>
          <div className="hs-v3-detail-info"><div><span>Condomínio</span><strong>{selecionado.condominio}</strong></div><div><span>Prioridade</span><strong><span className={`hs-v3-tag hs-v3-priority-${normaliza(selecionado.prioridade)}`}>{selecionado.prioridade}</span></strong></div><div><span>Prazo</span><strong className={selecionado.atrasado ? 'hs-v3-red' : ''}>{dataBR(selecionado.prazo)}</strong></div><div><span>Criado por</span><strong>{selecionado.criador}</strong></div></div>
          <div className="hs-v3-section-head"><h4><SIcon nome="users" size={17}/>Equipe responsável</h4><span>{totalExec} executor(es)</span></div>
          {totalExec > 0 && <div className="hs-v3-execution-progress"><div className="hs-v3-progress-head"><span>Execução individual</span><strong>{concluidos} de {totalExec} concluídas</strong></div><div className="hs-v3-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={totalExec} aria-valuenow={concluidos} aria-label="Etapas dos executores concluídas"><span style={{ width: `${100 * concluidos / totalExec}%` }}/></div></div>}
          <div className="hs-v3-team"><h5>Execução</h5>{(selecionado.executores || []).map(p => <div className="hs-v3-person" key={`e-${p.usuario_id}`}><Avatar nome={p.nome}/><span className="hs-v3-person-name">{p.nome}<small>Executor</small></span><Etiqueta status={p.status}/></div>)}<h5>Fiscalização</h5>{selecionado.fiscalizadores?.length ? selecionado.fiscalizadores.map(p => <div className="hs-v3-person" key={`f-${p.usuario_id}`}><Avatar nome={p.nome}/><span className="hs-v3-person-name">{p.nome}<small>Fiscalizador</small></span><Etiqueta status={p.status}/></div>) : <p className="hs-v3-no-inspector">Sem fiscalizador designado. A validação final será feita pela Controladoria.</p>}</div>
          {!!acoes.length && <section className="hs-v3-action"><div className="hs-v3-action-title"><SIcon nome="checkCircle" size={18}/><strong>Sua próxima ação</strong></div><p>Registre sua participação. As atualizações ficam vinculadas ao seu usuário no histórico.</p><label htmlFor="hs-v3-observacao">Observação ou resultado</label><textarea id="hs-v3-observacao" rows={3} maxLength={3000} value={textoAcao} onChange={e => setTextoAcao(e.target.value)} placeholder="Descreva o andamento, os resultados ou o motivo da devolução..."/><div className="hs-v3-action-buttons">{acoes.map(acao => <button key={acao} type="button" className={`hs-v3-button ${acao === 'devolver' ? 'hs-v3-button-warn' : 'hs-v3-button-primary'}`} onClick={() => executar(acao)} disabled={salvando}>{salvando ? 'Registrando...' : NOMES_ACOES[acao] || acao}</button>)}</div>{acoes.some(acao => ['concluir', 'devolver'].includes(acao)) && <small>Ao concluir ou devolver, informe pelo menos 10 caracteres.</small>}</section>}
          <div className="hs-v3-section-head hs-v3-history-heading"><h4><SIcon nome="clock" size={17}/>Linha do tempo</h4><span>{historico.length} registros</span></div><ol className="hs-v3-timeline">{historico.length ? historico.map(ev => <li key={ev.id}><span className="hs-v3-timeline-dot"/><div><strong>{String(ev.acao || 'Atualização').replaceAll('_', ' ')}</strong><small>{ev.autor} · {dataBR(ev.data)}</small>{ev.observacao && <p>{ev.observacao}</p>}</div></li>) : <li className="hs-v3-timeline-empty">Nenhum evento encontrado.</li>}</ol>
        </div>}
      </div>
    </div>

    {novoAberto && <div className="hs-v3-modal-backdrop" ><form className="hs-v3-modal" ref={modalRef} onSubmit={criar} role="dialog" aria-modal="true" aria-labelledby="hs-v3-modal-title" noValidate>
      <div className="hs-v3-modal-top"><div><span className="hs-v3-eyebrow">NOVA DEMANDA</span><h3 id="hs-v3-modal-title">Criar solicitação de serviço</h3><p>Organize a execução e a fiscalização em uma única tarefa.</p></div><button type="button" className="hs-v3-icon-button" aria-label="Fechar" onClick={fecharModal} disabled={salvando}><SIcon nome="close" size={20}/></button></div>
      <div className="hs-v3-modal-body"><div className="hs-v3-form-block"><div className="hs-v3-form-step"><span>01</span><div><strong>Dados da solicitação</strong><small>Identifique o serviço, o condomínio e o prazo.</small></div></div>
        <div className="hs-v3-field"><label htmlFor="hs-v3-titulo">Título do serviço <em>*</em></label><input name="titulo" id="hs-v3-titulo" minLength={4} maxLength={180} required value={form.titulo} placeholder="Ex.: Verificar iluminação da garagem" onChange={e => alterarForm('titulo', e.target.value)}/></div>
        <div className="hs-v3-form-row"><div className="hs-v3-field"><label htmlFor="hs-v3-condominio">Condomínio <em>*</em></label><select id="hs-v3-condominio" required value={form.condominio_id} onChange={e => { setForm(f => ({ ...f, condominio_id: e.target.value, executores_ids: [], fiscalizadores_ids: [] })); setPesquisaExec(''); setPesquisaFiscal(''); setErroForm('') }}><option value="">Selecione o condomínio</option>{condominios.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></div><div className="hs-v3-field"><label htmlFor="hs-v3-prazo">Prazo <em>*</em></label><input type="date" id="hs-v3-prazo" min={diaHoje()} value={form.prazo} onChange={e => alterarForm('prazo', e.target.value)} required/></div></div>
        <div className="hs-v3-field"><label htmlFor="hs-v3-prioridade">Prioridade</label><select id="hs-v3-prioridade" value={form.prioridade} onChange={e => alterarForm('prioridade', e.target.value)}><option>Baixa</option><option>Normal</option><option>Alta</option><option>Urgente</option></select></div>
        <div className="hs-v3-field"><label htmlFor="hs-v3-descricao">Descrição e orientações <em>*</em></label><textarea id="hs-v3-descricao" rows={4} minLength={5} maxLength={4000} required value={form.descricao} placeholder="Explique o que deve ser feito, o local e os critérios de conclusão." onChange={e => alterarForm('descricao', e.target.value)}/><small>Inclua instruções que evitem dúvidas e retrabalho.</small></div>
      </div>
      <div className="hs-v3-form-block"><div className="hs-v3-form-step"><span>02</span><div><strong>Execução</strong><small>Selecione quantas pessoas forem necessárias. Cada uma registra sua própria etapa.</small></div></div>
        <div className="hs-v3-select-head"><label htmlFor="hs-v3-busca-exec">Executores <em>*</em></label><strong>{form.executores_ids.length} selecionado(s)</strong></div><div className="hs-v3-searchbar hs-v3-people-search"><SIcon nome="search" size={16}/><input type="search" id="hs-v3-busca-exec" placeholder="Buscar colaborador ou zelador" value={pesquisaExec} onChange={e => setPesquisaExec(e.target.value)} disabled={!form.condominio_id}/></div>
        <div className="hs-v3-selected-people">{form.executores_ids.map(id => <button type="button" key={id} onClick={() => alternarParticipante('executores_ids', id)} title="Remover executor">{nomePorId.get(id) || `Usuário ${id}`} <SIcon nome="close" size={13}/></button>)}</div>
        <div className="hs-v3-people-list" role="group" aria-label="Escolher executores">{!form.condominio_id ? <p>Selecione um condomínio para ver os colaboradores disponíveis.</p> : candidatosExec.length === 0 ? <p>Nenhum colaborador encontrado.</p> : candidatosExec.map(p => <label key={p.id} className={`hs-v3-person-option ${form.executores_ids.includes(p.id) ? 'is-checked' : ''} ${form.fiscalizadores_ids.includes(p.id) ? 'is-disabled' : ''}`}><input type="checkbox" checked={form.executores_ids.includes(p.id)} disabled={form.fiscalizadores_ids.includes(p.id)} onChange={() => alternarParticipante('executores_ids', p.id)}/><Avatar nome={p.nome}/><span>{p.nome}<small>{p.perfil === 'Checklist' ? 'Zelador' : p.perfil}</small></span><SIcon nome="check" size={16}/></label>)}</div>
      </div>
      <div className="hs-v3-form-block"><div className="hs-v3-form-step"><span>03</span><div><strong>Fiscalização <small className="hs-v3-optional">Opcional</small></strong><small>Escolha quem irá conferir a execução, sem acumular o papel de executor.</small></div></div>
        <div className="hs-v3-select-head"><label htmlFor="hs-v3-busca-fiscal">Fiscalizadores</label><strong>{form.fiscalizadores_ids.length} selecionado(s)</strong></div><div className="hs-v3-searchbar hs-v3-people-search"><SIcon nome="search" size={16}/><input type="search" id="hs-v3-busca-fiscal" placeholder="Buscar fiscalizador" value={pesquisaFiscal} onChange={e => setPesquisaFiscal(e.target.value)} disabled={!form.condominio_id}/></div>
        <div className="hs-v3-selected-people">{form.fiscalizadores_ids.map(id => <button type="button" key={id} onClick={() => alternarParticipante('fiscalizadores_ids', id)} title="Remover fiscalizador">{nomePorId.get(id) || `Usuário ${id}`} <SIcon nome="close" size={13}/></button>)}</div>
        <div className="hs-v3-people-list" role="group" aria-label="Escolher fiscalizadores">{!form.condominio_id ? <p>Selecione um condomínio para ver os colaboradores disponíveis.</p> : candidatosFiscal.length === 0 ? <p>Nenhum colaborador encontrado.</p> : candidatosFiscal.map(p => <label key={p.id} className={`hs-v3-person-option ${form.fiscalizadores_ids.includes(p.id) ? 'is-checked' : ''} ${form.executores_ids.includes(p.id) ? 'is-disabled' : ''}`}><input type="checkbox" checked={form.fiscalizadores_ids.includes(p.id)} disabled={form.executores_ids.includes(p.id)} onChange={() => alternarParticipante('fiscalizadores_ids', p.id)}/><Avatar nome={p.nome}/><span>{p.nome}<small>{p.perfil === 'Checklist' ? 'Zelador' : p.perfil}</small></span><SIcon nome="check" size={16}/></label>)}</div>
      </div></div>
      <footer className="hs-v3-modal-footer">{erroForm && <div className="hs-v3-form-error" role="alert"><SIcon nome="alert" size={16}/>{erroForm}</div>}<div className="hs-v3-modal-footer-row"><p><SIcon nome="info" size={15}/>Avisos internos serão criados automaticamente. WhatsApp ainda não está ativado.</p><div><button type="button" className="hs-v3-button hs-v3-button-light" onClick={fecharModal} disabled={salvando}>Cancelar</button><button type="submit" className="hs-v3-button hs-v3-button-primary" disabled={salvando || !form.condominio_id || !form.executores_ids.length}>{salvando ? 'Salvando...' : `Criar serviço${form.executores_ids.length > 1 ? ` (${form.executores_ids.length} executores)` : ''}`}</button></div></div></footer>
    </form></div>}
  </section>
}
