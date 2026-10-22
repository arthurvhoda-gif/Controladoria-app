import { useEffect, useState, useRef, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer
} from 'recharts'
import XLSX from 'xlsx-js-style'
import './App.css'

const API_URL = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

function lerCache(chave, padrao = []) {
  try {
    const item = sessionStorage.getItem(`haize_cache_${chave}`)
    return item ? JSON.parse(item) : padrao
  } catch {
    return padrao
  }
}

function salvarCache(chave, dados) {
  try {
    sessionStorage.setItem(`haize_cache_${chave}`, JSON.stringify(dados))
  } catch { }
}

function parseDataSegura(dataStr) {
  if (!dataStr) return null
  let str = String(dataStr).trim()
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(str)) {
    str = str.replace(' ', 'T')
  }
  const d = new Date(str)
  return isNaN(d.getTime()) ? null : d
}

function calcularStatusSLA(frequencia, ultimaExecucao) {
  if (!ultimaExecucao || !ultimaExecucao.data_execucao) {
    return {
      status: 'pendente',
      label: 'Pendente',
      bg: '#f1f5f9',
      color: '#475569',
      border: '#cbd5e1'
    }
  }

  const dataUltima = parseDataSegura(ultimaExecucao.data_execucao)
  if (!dataUltima) {
    return {
      status: 'indefinido',
      label: 'Data indisponível',
      bg: '#f1f5f9',
      color: '#64748b',
      border: '#cbd5e1'
    }
  }

  const agora = new Date()
  const diffHoras = Math.max(0, (agora - dataUltima) / (1000 * 60 * 60))

  const limitesHoras = {
    'diaria': 24,
    'diária': 24,
    'diario': 24,
    'diário': 24,
    'semanal': 7 * 24,
    'quinzenal': 15 * 24,
    'mensal': 30 * 24
  }

  const freqKey = String(frequencia || '').toLowerCase().trim()
  const limite = limitesHoras[freqKey] || 24

  if (diffHoras > limite) {
    return {
      status: 'atrasado',
      label: 'Atrasada',
      bg: '#fef2f2',
      color: '#dc2626',
      border: '#fecaca'
    }
  }

  return {
    status: 'em_dia',
    label: 'Em dia',
    bg: '#ecfdf5',
    color: '#059669',
    border: '#a7f3d0'
  }
}

function numero(v) {
  if (v === null || v === undefined || v === '') return 0
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  let normalizado = String(v).replace(/[^0-9.,-]/g, '')
  if (normalizado.includes('.') && normalizado.includes(',')) normalizado = normalizado.replace(/\./g, '').replace(',', '.')
  else normalizado = normalizado.replace(',', '.')
  const resultado = parseFloat(normalizado)
  return Number.isFinite(resultado) ? resultado : 0
}

function solicitado(item) { return numero(item?.valor) }
function aprovado(item) { return numero(item?.valor_aprovado) }
function realizado(item) { return numero(item?.valor_realizado) }
function formatarValor(v) { return numero(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) }
function formatarNumero(v) { return numero(v).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) }

function escaparHtml(valor) {
  return String(valor ?? '').replace(/[&<>"']/g, caractere => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[caractere]))
}

function dataLocalISO(data) {
  const dois = valor => String(valor).padStart(2, '0')
  return `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}`
}

function formatarDataHora(dataStr) {
  if (!dataStr) return '-'
  const d = parseDataSegura(dataStr)
  return !d ? dataStr : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function normalizarTexto(v) {
  return String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

function textoStatus(status) {
  const n = normalizarTexto(status)
  if (n.includes('finalizada') || n.includes('finalizado')) return 'Finalizada'
  if (n.includes('em execucao') || n === 'execucao') return 'Em execução'
  if (n.includes('ajuste')) return 'Ajuste solicitado'
  if (n.includes('reprovada') || n.includes('reprovado')) return 'Reprovada'
  if (n.includes('aprovada') || n.includes('aprovado')) return 'Aprovada'
  if (n.includes('em analise')) return 'Em análise'
  return 'Aprovação pendente'
}

// Ícones vetoriais locais: não exigem instalação de bibliotecas.
const iconesHaize = {
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></>,
  analyses: <><path d="M4 19V11M10 19V5M16 19v-8M22 19V8"/><path d="M2 21h20"/></>,
  requests: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></>,
  shopping: <><path d="M3 5h2l2.2 10.5a2 2 0 0 0 2 1.5H19a2 2 0 0 0 2-1.5L22 9H6"/><circle cx="10" cy="21" r="1"/><circle cx="19" cy="21" r="1"/></>,
  checklist: <><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3v3M15 3v3M9 11l1.5 1.5L14 9M9 17h6"/></>,
  buildings: <><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M14 7h2M9 11h2M14 11h2M9 15h2M14 15h2M11 21v-3h3v3"/></>,
  categories: <><path d="M3 12V5a2 2 0 0 1 2-2h7l9 9-9 9-9-9Z"/><circle cx="8" cy="8" r="1"/></>,
  suppliers: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M19 14a5 5 0 0 1 2 4v2"/></>,
  trending: <><path d="m3 17 6-6 4 4 8-8M15 7h6v6"/></>,
  approved: <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
  wallet: <><rect x="3" y="6" width="18" height="15" rx="2"/><path d="M3 9h18M7 3h11"/></>,
  savings: <><path d="M12 3v18M17 7c-1-2-9-2-9 2s8 2 8 6-7 4-9 1"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5 9a8 8 0 0 1 14-2l1 5M4 12l1 5a8 8 0 0 0 14-2"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6"/>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  logout: <><path d="M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M9 12h10"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  file: <><path d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2"/><path d="M14 3v5h4"/></>
}
function IconeHaize({ nome, tamanho = 18, className = '' }) {
  return <svg aria-hidden="true" className={className} width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.85" strokeLinecap="round" strokeLinejoin="round">{iconesHaize[nome] || iconesHaize.file}</svg>
}

function App() {
  const [usuarioLogado, setUsuarioLogado] = useState(() => {
    try {
      const salvo = sessionStorage.getItem('usuarioControladoria')
      return salvo ? JSON.parse(salvo) : null
    } catch { return null }
  })

  function paginaInicialPorPerfil(perfil) {
    if (perfil === 'Checklist') return 'checklist'
    if (perfil === 'Solicitante') return 'solicitacoes'
    return 'dashboard'
  }

  const [emailLogin, setEmailLogin] = useState('')
  const [senhaLogin, setSenhaLogin] = useState('')
  const [mostrarTrocaSenha, setMostrarTrocaSenha] = useState(false)
  const [senhaAtual, setSenhaAtual] = useState('')
  const [senhaNova, setSenhaNova] = useState('')
  const [trocandoSenha, setTrocandoSenha] = useState(false)
  const [carregandoLogin, setCarregandoLogin] = useState(false)
  const [pagina, setPagina] = useState(paginaInicialPorPerfil(usuarioLogado?.perfil))
  const [abaChecklist, setAbaChecklist] = useState('vistorias')
  const [sidebarAberta, setSidebarAberta] = useState(false)

  const [backendOnline, setBackendOnline] = useState(true)
  const [sincronizando, setSincronizando] = useState(false)
  const [carregandoChecklist, setCarregandoChecklist] = useState(false)
  const [erroChecklist, setErroChecklist] = useState('')
  const [ultimaAtualizacaoChecklist, setUltimaAtualizacaoChecklist] = useState(null)

  const [solicitacoes, setSolicitacoes] = useState(() => lerCache('solicitacoes', []))
  const [condominios, setCondominios] = useState([])
  const [fornecedores, setFornecedores] = useState(() => lerCache('fornecedores', []))
  const [categorias, setCategorias] = useState(() => lerCache('categorias', []))
  const [checklists, setChecklists] = useState([])

  // Cadastro e vinculação dos zeladores (somente Controladoria).
  const [zeladores, setZeladores] = useState([])
  const [carregandoZeladores, setCarregandoZeladores] = useState(false)
  const [salvandoZelador, setSalvandoZelador] = useState(false)
  const [formZelador, setFormZelador] = useState({ nome: '', email: '', senha: '', condominio_id: '' })
  const [atribuicoesZeladores, setAtribuicoesZeladores] = useState({})

  // GESTÃO DE UNIDADES E RATEIO POR FRAÇÃO
  const [condominioUnidades, setCondominioUnidades] = useState(null)
  const [listaUnidades, setListaUnidades] = useState([])
  const [carregandoUnidades, setCarregandoUnidades] = useState(false)
  const [novaUnidade, setNovaUnidade] = useState({ identificacao: '', fracao_ideal: '' })
  const [rateioDados, setRateioDados] = useState(null)
  const [carregandoRateio, setCarregandoRateio] = useState(false)

  // GESTÃO DE CHECKLIST E VISTORIAS
  const [filtroCondominioChecklist, setFiltroCondominioChecklist] = useState('todos')
  const [filtroFrequenciaChecklist, setFiltroFrequenciaChecklist] = useState('todas')
  const [filtroSLAChecklist, setFiltroSLAChecklist] = useState('todos')
  const [buscaChecklist, setBuscaChecklist] = useState('')
  const [ordenacaoChecklist, setOrdenacaoChecklist] = useState('prioridade')
  const [salvandoExecucaoChecklist, setSalvandoExecucaoChecklist] = useState(false)
  const [enviandoRelatorio, setEnviandoRelatorio] = useState(false)
  const [mostrarModalNovoChecklist, setMostrarModalNovoChecklist] = useState(false)
  const [checklistEditando, setChecklistEditando] = useState(null)
  const [formNovoChecklist, setFormNovoChecklist] = useState({
    condominio: '',
    titulo: '',
    descricao_orientacao: '',
    frequencia: 'Diária',
    plano_acao_padrao: ''
  })
  const [itemChecklistExecutando, setItemChecklistExecutando] = useState(null)
  const [formExecucaoChecklist, setFormExecucaoChecklist] = useState({
    status_conformidade: 'Conforme',
    observacao: '',
    foto: null
  })
  const [itemChecklistHistorico, setItemChecklistHistorico] = useState(null)

  // POP-UP AUTOMÁTICO DE PLANO DE AÇÃO QUANDO HÁ INCONFORMIDADE
  const [alertaPlanoAcao, setAlertaPlanoAcao] = useState(null)

  // NOTIFICAÇÕES E ALERTAS
  const [mostrarMenuNotificacoes, setMostrarMenuNotificacoes] = useState(false)
  const [notificacoesPushAtivas, setNotificacoesPushAtivas] = useState(false)

  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState({
    isOpen: false, type: 'confirm', title: '', message: '', inputValue: '',
    confirmText: 'Confirmar', cancelText: 'Cancelar', isDanger: false, onConfirm: null
  })

  const [solicitacaoEditando, setSolicitacaoEditando] = useState(null)
  const [solicitacaoSelecionada, setSolicitacaoSelecionada] = useState(null)
  const [historicoSolicitacao, setHistoricoSolicitacao] = useState([])

  const [anexosSolicitacao, setAnexosSolicitacao] = useState([])
  const [fazendoUpload, setFazendoUpload] = useState(false)

  // ARQUIVOS ANEXADOS DIRETO NA CRIAÇÃO DA SOLICITAÇÃO (SOLICITANTE)
  const [arquivosNovaSolicitacao, setArquivosNovaSolicitacao] = useState([])

  const [mostrarFormulario, setMostrarFormulario] = useState(false)
  const [condominioEditando, setCondominioEditando] = useState(null)
  const [mostrarFormularioCondominio, setMostrarFormularioCondominio] = useState(false)

  const [fornecedorEditando, setFornecedorEditando] = useState(null)
  const [mostrarFormularioFornecedor, setMostrarFormularioFornecedor] = useState(false)

  const [categoriaEditando, setCategoriaEditando] = useState(null)
  const [mostrarFormularioCategoria, setMostrarFormularioCategoria] = useState(false)

  const [filtroSolicitacao, setFiltroSolicitacao] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('todos')
  const [filtroCondominioSolicitacao, setFiltroCondominioSolicitacao] = useState('todos')
  const [filtroCategoriaSolicitacao, setFiltroCategoriaSolicitacao] = useState('todos')
  const [filtroInicioSolicitacao, setFiltroInicioSolicitacao] = useState('')
  const [filtroFimSolicitacao, setFiltroFimSolicitacao] = useState('')
  const [ordenacaoSolicitacao, setOrdenacaoSolicitacao] = useState('recentes')
  const [paginaSolicitacoes, setPaginaSolicitacoes] = useState(1)
  const [filtroCompra, setFiltroCompra] = useState('')
  const [filtroCondominioCompra, setFiltroCondominioCompra] = useState('todos')
  const [filtroStatusCompra, setFiltroStatusCompra] = useState('todos')
  const [ordenacaoCompra, setOrdenacaoCompra] = useState('recentes')
  const [paginaCompra, setPaginaCompra] = useState(1)
  const [buscaCondominioCadastro, setBuscaCondominioCadastro] = useState('')
  const [buscaCategoriaCadastro, setBuscaCategoriaCadastro] = useState('')
  const [buscaFornecedorCadastro, setBuscaFornecedorCadastro] = useState('')
  const [salvando, setSalvando] = useState(false)

  const [filtroDataInicio, setFiltroDataInicio] = useState('')
  const [filtroDataFim, setFiltroDataFim] = useState('')
  const [filtroCondominioAnalise, setFiltroCondominioAnalise] = useState('todos')

  const [formulario, setFormulario] = useState({
    condominio: '', categoria: '', fornecedor: '', descricao: '',
    valor_servico: '', valor_produto: '', observacao: ''
  })

  const [formularioCondominio, setFormularioCondominio] = useState({ nome: '', cnpj: '', codigo: '' })
  const [formularioFornecedor, setFormularioFornecedor] = useState({ nome: '', cnpj: '', categoria: '' })
  const [formularioCategoria, setFormularioCategoria] = useState({ nome: '', descricao: '', limites: {} })

  const qtdSolicitacoesRef = useRef(solicitacoes.length)
  const hashCacheRef = useRef({
    sol: '', cond: '', forn: '', cat: '', chk: ''
  })
  // Impede que uma resposta iniciada na conta anterior atualize a nova sessão.
  const tokenSessaoRef = useRef(usuarioLogado?.token || null)
  // Impede que atualizações periódicas se cancelem mutuamente quando a API está lenta.
  const carregamentoGeralRef = useRef(null)
  // A sincronização do checklist tem requisição independente dos demais módulos.
  const requisicaoChecklistRef = useRef(null)

  function getAuthHeaders(isFormData = false) {
    const headers = {}
    if (!isFormData) headers['Content-Type'] = 'application/json'
    if (usuarioLogado?.token) headers['Authorization'] = `Bearer ${usuarioLogado.token}`
    return headers
  }

  async function abrirArquivoProtegido(caminho, nome = 'documento') {
    const resposta = await fetch(`${API_URL}${caminho}`, { headers: getAuthHeaders() })
    if (!resposta.ok) throw new Error(await extrairErro(resposta, 'Não foi possível abrir o arquivo.'))
    const blob = await resposta.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
    const extensaoPorTipo = { 'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif' }
    link.download = /\.[a-z0-9]{2,7}$/i.test(nome) ? nome : `${nome}${extensaoPorTipo[blob.type] || ''}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  }

  function limparCacheLocal() {
    for (const chave of Object.keys(sessionStorage)) {
      if (chave.startsWith('haize_cache_')) sessionStorage.removeItem(chave)
    }
    for (const chave of Object.keys(localStorage)) {
      if (chave.startsWith('haize_cache_')) localStorage.removeItem(chave)
    }
    localStorage.removeItem('usuarioControladoria')
  }

  // Toda troca de conta começa com dados e filtros limpos, sem pedir F5.
  function reiniciarDadosDaSessao(proximoToken = null) {
    tokenSessaoRef.current = proximoToken
    carregamentoGeralRef.current = null
    if (requisicaoChecklistRef.current) {
      requisicaoChecklistRef.current.controller.abort()
      requisicaoChecklistRef.current = null
    }
    limparCacheLocal()
    hashCacheRef.current = { sol: '', cond: '', forn: '', cat: '', chk: '' }
    qtdSolicitacoesRef.current = 0
    setSolicitacoes([])
    setCondominios([])
    setFornecedores([])
    setCategorias([])
    setChecklists([])
    setCarregandoChecklist(false)
    setErroChecklist('')
    setUltimaAtualizacaoChecklist(null)
    setZeladores([])
    setAtribuicoesZeladores({})
    setFiltroCondominioChecklist('todos')
    setFiltroFrequenciaChecklist('todas')
    setFiltroSLAChecklist('todos')
    setBuscaChecklist('')
    setOrdenacaoChecklist('prioridade')
    setAbaChecklist('vistorias')
    setSincronizando(false)
    setItemChecklistHistorico(null)
    setItemChecklistExecutando(null)
    setChecklistEditando(null)
    setMostrarModalNovoChecklist(false)
    setSolicitacaoSelecionada(null)
  }

  useEffect(() => {
    // Descarta tokens e caches legados do localStorage, anteriores à autenticação segura.
    for (const chave of Object.keys(localStorage)) {
      if (chave.startsWith('haize_cache_') || chave === 'usuarioControladoria') localStorage.removeItem(chave)
    }
  }, [])

  useEffect(() => {
    if (!usuarioLogado?.token) return
    let canceled = false
    fetch(`${API_URL}/usuarios/me`, { headers: { Authorization: `Bearer ${usuarioLogado.token}` } })
      .then(async res => {
        if (!res.ok) throw new Error('Sessão expirada. Faça login novamente.')
        return await res.json()
      })
      .then(perfil => {
        if (!canceled) setUsuarioLogado(atual => atual ? { ...atual, ...perfil } : null)
      })
      .catch(() => {
        if (!canceled) {
          sessionStorage.removeItem('usuarioControladoria')
          reiniciarDadosDaSessao()
          setUsuarioLogado(null)
        }
      })
    return () => { canceled = true }
  }, [usuarioLogado?.token])

  async function trocarMinhaSenha(e) {
    e.preventDefault()
    if (senhaNova.length < 10) {
      mostrarToast('A nova senha deve conter ao menos 10 caracteres.', 'error')
      return
    }
    setTrocandoSenha(true)
    try {
      const res = await fetch(`${API_URL}/usuarios/me/senha`, {
        method: 'PUT', headers: getAuthHeaders(),
        body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: senhaNova })
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível trocar a senha.'))
      setMostrarTrocaSenha(false)
      setSenhaAtual('')
      setSenhaNova('')
      fazerLogout()
      mostrarToast('Senha atualizada. Faça login com a nova senha.', 'success')
    } catch (erro) {
      mostrarToast(erro.message, 'error')
    } finally {
      setTrocandoSenha(false)
    }
  }

  async function extrairErro(res, mensagemPadrao) {
    try {
      const data = await res.json()
      return data.detail || mensagemPadrao
    } catch {
      return mensagemPadrao
    }
  }

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        if (alertaPlanoAcao) { setAlertaPlanoAcao(null); return }
        if (dialog.isOpen) { fecharDialog(); return }
        if (itemChecklistExecutando) { if (!salvandoExecucaoChecklist) setItemChecklistExecutando(null); return }
        if (itemChecklistHistorico) { setItemChecklistHistorico(null); return }
        if (mostrarModalNovoChecklist) { setMostrarModalNovoChecklist(false); return }
        if (condominioUnidades) { setCondominioUnidades(null); return }
        if (mostrarFormularioCondominio) { fecharFormularioCondominio(); return }
        if (mostrarFormularioCategoria) { fecharFormularioCategoria(); return }
        if (mostrarFormularioFornecedor) { fecharFormularioFornecedor(); return }
        if (mostrarFormulario) { fecharFormulario(); return }
        if (solicitacaoSelecionada) { fecharSolicitacao(); return }
        if (mostrarMenuNotificacoes) { setMostrarMenuNotificacoes(false); return }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    alertaPlanoAcao, dialog.isOpen, itemChecklistExecutando, salvandoExecucaoChecklist, itemChecklistHistorico,
    mostrarModalNovoChecklist, condominioUnidades, mostrarFormularioCondominio,
    mostrarFormularioCategoria, mostrarFormularioFornecedor, mostrarFormulario,
    solicitacaoSelecionada, mostrarMenuNotificacoes
  ])

  useEffect(() => {
    if ('Notification' in window) {
      if (Notification.permission === 'granted') {
        setNotificacoesPushAtivas(true)
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') setNotificacoesPushAtivas(true)
        })
      }
    }
  }, [])

  function dispararNotificacaoNativa(titulo, corpo) {
    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(titulo, { body: corpo, icon: '/logo.png' })
      } catch { }
    }
  }

  async function fazerLogin(e) {
    e.preventDefault()
    setCarregandoLogin(true)
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailLogin.trim().toLowerCase(), senha: senhaLogin })
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao entrar')
        throw new Error(erroMsg)
      }
      const dados = await res.json()
      const dadosUsuario = { ...dados.usuario, token: dados.access_token }
      reiniciarDadosDaSessao(dadosUsuario.token)
      setUsuarioLogado(dadosUsuario)
      sessionStorage.setItem('usuarioControladoria', JSON.stringify(dadosUsuario))
      setSenhaLogin('')
      mostrarToast(`Bem-vindo(a), ${dadosUsuario.nome}!`, 'success')
      setPagina(paginaInicialPorPerfil(dadosUsuario.perfil))
    } catch (err) {
      mostrarToast(err.message, 'error')
    } finally {
      setCarregandoLogin(false)
    }
  }

  function fazerLogout() {
    sessionStorage.removeItem('usuarioControladoria')
    reiniciarDadosDaSessao()
    setUsuarioLogado(null)
    setPagina('dashboard')
    setEmailLogin('')
    setSenhaLogin('')
  }

  function mostrarToast(mensagem, tipo = 'success') {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, mensagem, tipo }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }

  function confirmarAcao(titulo, mensagem, onConfirm, isDanger = false) {
    setDialog({ isOpen: true, type: 'confirm', title: titulo, message: mensagem, inputValue: '', confirmText: 'Sim, confirmar', cancelText: 'Cancelar', isDanger, onConfirm })
  }

  function pedirInput(titulo, mensagem, valorPadrao, onConfirm, isDanger = false) {
    setDialog({ isOpen: true, type: 'prompt', title: titulo, message: mensagem, inputValue: valorPadrao || '', confirmText: 'Salvar', cancelText: 'Cancelar', isDanger, onConfirm })
  }

  function fecharDialog() {
    setDialog(prev => ({ ...prev, isOpen: false, inputValue: '' }))
  }

  function handleConfirmDialog() {
    const callback = dialog.onConfirm
    const val = dialog.inputValue
    const tipo = dialog.type
    fecharDialog()
    if (callback) {
      tipo === 'prompt' ? callback(val) : callback()
    }
  }

  // Consulta isolada: o carregamento lento de solicitações/fornecedores não bloqueia vistorias.
  // Uma nova sessão sempre invalida e aborta solicitações feitas na conta anterior.
  async function carregarChecklists({ forcar = false, notificarErro = false } = {}) {
    const token = usuarioLogado?.token
    if (!token || tokenSessaoRef.current !== token) return false

    const anterior = requisicaoChecklistRef.current
    if (anterior?.token === token) {
      if (!forcar) return anterior.promise
      anterior.controller.abort()
    }

    const controller = new AbortController()
    const requisicao = { token, controller, promise: null }
    requisicaoChecklistRef.current = requisicao
    setCarregandoChecklist(true)

    const promise = (async () => {
      try {
        const resposta = await fetch(`${API_URL}/checklists`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
          signal: controller.signal
        })
        if (tokenSessaoRef.current !== token || requisicaoChecklistRef.current !== requisicao) return false
        if (resposta.status === 401) {
          fazerLogout()
          mostrarToast('Sua sessão expirou. Faça login novamente.', 'error')
          return false
        }
        if (!resposta.ok) throw new Error(await extrairErro(resposta, 'Não foi possível atualizar as atividades.'))
        const dados = await resposta.json()
        if (!Array.isArray(dados)) throw new Error('A API retornou uma lista de checklists inválida.')
        if (tokenSessaoRef.current !== token || requisicaoChecklistRef.current !== requisicao) return false

        // Recebe a lista completa que o servidor autorizou para esta conta;
        // não reaproveita a lista do zelador ao retornar para a Controladoria.
        setChecklists(dados)
        setItemChecklistHistorico(prev => prev ? (dados.find(c => c.id === prev.id) || null) : null)
        setErroChecklist('')
        setUltimaAtualizacaoChecklist(new Date().toISOString())
        setBackendOnline(true)
        return true
      } catch (erro) {
        if (erro.name === 'AbortError') return false
        if (tokenSessaoRef.current === token && requisicaoChecklistRef.current === requisicao) {
          const mensagem = erro.message || 'Não foi possível sincronizar o Checklist.'
          setErroChecklist(mensagem)
          if (notificarErro) mostrarToast(mensagem, 'error')
        }
        return false
      } finally {
        if (requisicaoChecklistRef.current === requisicao) {
          requisicaoChecklistRef.current = null
          setCarregandoChecklist(false)
        }
      }
    })()
    requisicao.promise = promise
    return promise
  }

  async function carregarDados(forcarIndicador = false) {
    const tokenDestaSessao = usuarioLogado?.token
    if (!tokenDestaSessao || tokenSessaoRef.current !== tokenDestaSessao) return
    // Somente uma consulta geral simultânea por conta: intervalos de 12s não
    // invalidam a consulta anterior se o Render demorar para responder.
    if (carregamentoGeralRef.current === tokenDestaSessao) return
    carregamentoGeralRef.current = tokenDestaSessao
    const respostaDaSessaoAtual = () => tokenSessaoRef.current === tokenDestaSessao

    if (forcarIndicador) setSincronizando(true)
    try {
      const opcoes = {
        headers: { Authorization: `Bearer ${tokenDestaSessao}` },
        cache: 'no-store'
      }
      const [resSol, resCond, resForn, resCat] = await Promise.all([
        fetch(`${API_URL}/solicitacoes`, opcoes),
        fetch(`${API_URL}/condominios`, opcoes),
        fetch(`${API_URL}/fornecedores`, opcoes),
        fetch(`${API_URL}/categorias`, opcoes)
      ])
      if (!respostaDaSessaoAtual()) return

      if ([resSol, resCond, resForn, resCat].some(r => r.status === 401)) {
        fazerLogout()
        mostrarToast('Sua sessão expirou. Faça login novamente.', 'error')
        return
      }
      setBackendOnline(true)

      if (resSol.ok) {
        let dados = await resSol.json()
        if (!respostaDaSessaoAtual()) return
        if (usuarioLogado.perfil === 'Solicitante') {
          dados = dados.filter(s => s.solicitante === usuarioLogado.nome)
        }
        const strSol = JSON.stringify(dados)
        if (strSol !== hashCacheRef.current.sol) {
          hashCacheRef.current.sol = strSol
          const qtdAntiga = qtdSolicitacoesRef.current
          if (dados.length > qtdAntiga && qtdAntiga > 0 && usuarioLogado.perfil !== 'Checklist') {
            dispararNotificacaoNativa('Nova Solicitação', 'Um novo pedido foi registrado no sistema.')
          }
          qtdSolicitacoesRef.current = dados.length
          setSolicitacoes(dados)
          salvarCache('solicitacoes', dados)
          setSolicitacaoSelecionada(prev => prev ? (dados.find(i => i.id === prev.id) || null) : null)
        }
      }

      if (resCond.ok) {
        const dadosCond = await resCond.json()
        if (!respostaDaSessaoAtual()) return
        if (usuarioLogado.perfil === 'Checklist') {
          setFiltroCondominioChecklist(dadosCond[0]?.nome || 'todos')
        }
        const strCond = JSON.stringify(dadosCond)
        if (strCond !== hashCacheRef.current.cond) {
          hashCacheRef.current.cond = strCond
          setCondominios(dadosCond)
          salvarCache('condominios', dadosCond)
        }
      }

      if (resForn.ok) {
        const dadosForn = await resForn.json()
        if (!respostaDaSessaoAtual()) return
        const strForn = JSON.stringify(dadosForn)
        if (strForn !== hashCacheRef.current.forn) {
          hashCacheRef.current.forn = strForn
          setFornecedores(dadosForn)
          salvarCache('fornecedores', dadosForn)
        }
      }

      if (resCat.ok) {
        const dadosCat = await resCat.json()
        if (!respostaDaSessaoAtual()) return
        const strCat = JSON.stringify(dadosCat)
        if (strCat !== hashCacheRef.current.cat) {
          hashCacheRef.current.cat = strCat
          setCategorias(dadosCat)
          salvarCache('categorias', dadosCat)
        }
      }
    } catch {
      if (respostaDaSessaoAtual()) setBackendOnline(false)
    } finally {
      if (carregamentoGeralRef.current === tokenDestaSessao) carregamentoGeralRef.current = null
      if (forcarIndicador && respostaDaSessaoAtual()) setSincronizando(false)
    }
  }

  useEffect(() => {
    if (!usuarioLogado?.token) return
    if (usuarioLogado.perfil === 'Checklist' && pagina !== 'checklist') {
      setPagina('checklist')
    }
    carregarDados(false)
    if (pagina === 'checklist' && abaChecklist === 'vistorias') carregarChecklists()

    const atualizarSeVisivel = () => {
      if (document.visibilityState !== 'visible') return
      carregarDados(false)
      if (pagina === 'checklist' && abaChecklist === 'vistorias') carregarChecklists()
    }
    const intervalo = setInterval(atualizarSeVisivel, 12000)
    document.addEventListener('visibilitychange', atualizarSeVisivel)
    window.addEventListener('focus', atualizarSeVisivel)
    return () => {
      clearInterval(intervalo)
      document.removeEventListener('visibilitychange', atualizarSeVisivel)
      window.removeEventListener('focus', atualizarSeVisivel)
    }
  }, [usuarioLogado?.token, pagina, abaChecklist])

  function renderBadge(sol) {
    if (!sol) return null
    const statusStr = typeof sol === 'string' ? sol : sol.status
    let txt = textoStatus(statusStr)
    if (typeof sol === 'object') {
      const vSol = solicitado(sol)
      const vApr = aprovado(sol)
      if (txt === 'Aprovada' && vApr > 0 && vApr < vSol) txt = 'Aprovada Parcial'
    }

    let backgroundColor = '#FEF3C7'; let color = '#B45309'; let borderColor = '#FDE68A'
    if (txt === 'Aprovada') { backgroundColor = '#EFF6FF'; color = '#1D4ED8'; borderColor = '#BFDBFE' }
    if (txt === 'Aprovada Parcial') { backgroundColor = '#FEF3C7'; color = '#B45309'; borderColor = '#FDE68A' }
    if (txt === 'Em execução') { backgroundColor = '#EEF2FF'; color = '#4338CA'; borderColor = '#C7D2FE' }
    if (txt === 'Finalizada') { backgroundColor = '#ECFDF5'; color = '#047857'; borderColor = '#A7F3D0' }
    if (txt === 'Ajuste solicitado') { backgroundColor = '#FFFBEB'; color = '#B45309'; borderColor = '#FDE68A' }
    if (txt === 'Reprovada') { backgroundColor = '#FEF2F2'; color = '#B91C1C'; borderColor = '#FECACA' }

    return (
      <span style={{ padding: '4px 10px', borderRadius: '999px', fontSize: '11.5px', fontWeight: '700', backgroundColor, color, border: `1px solid ${borderColor}`, display: 'inline-flex', alignItems: 'center', width: 'fit-content' }}>
        {txt}
      </span>
    )
  }

  function classeVariacao(valor) { return numero(valor) > 0 ? 'positive' : numero(valor) < 0 ? 'negative' : 'neutral' }

  const {
    quantidadePendentes,
    valorTotalSolicitado,
    valorTotalAprovado,
    valorTotalRealizado,
    economiaTotal,
    maioresSolicitacoes,
    solicitacoesPendentesLista
  } = useMemo(() => {
    let pendentes = 0
    let totSol = 0
    let totApr = 0
    let totReal = 0
    let econ = 0
    const listaPend = []

    for (const item of solicitacoes) {
      const st = textoStatus(item.status)
      const vSol = solicitado(item)
      const vApr = aprovado(item)
      const vReal = realizado(item)

      totSol += vSol
      if (st === 'Aprovação pendente') {
        pendentes++
        listaPend.push(item)
      }
      if (['Aprovada', 'Em execução', 'Finalizada'].includes(st)) {
        totApr += (vApr || vSol)
      }
      if (st === 'Finalizada') {
        const finalReal = vReal || vApr || vSol
        totReal += finalReal
        econ += (vSol - finalReal)
      }
    }

    const maiores = [...solicitacoes].sort((a, b) => solicitado(b) - solicitado(a)).slice(0, 6)

    return {
      quantidadePendentes: pendentes,
      valorTotalSolicitado: totSol,
      valorTotalAprovado: totApr,
      valorTotalRealizado: totReal,
      economiaTotal: econ,
      maioresSolicitacoes: maiores,
      solicitacoesPendentesLista: listaPend
    }
  }, [solicitacoes])

  const indicadoresStatusDashboard = useMemo(() => {
    const ordem = [
      { status: 'Aprovação pendente', label: 'Pendentes', tom: 'amber' },
      { status: 'Em análise', label: 'Em análise', tom: 'blue' },
      { status: 'Ajuste solicitado', label: 'Em ajuste', tom: 'violet' },
      { status: 'Aprovada', label: 'Aprovadas', tom: 'blue' },
      { status: 'Em execução', label: 'Em execução', tom: 'indigo' },
      { status: 'Finalizada', label: 'Finalizadas', tom: 'green' },
      { status: 'Reprovada', label: 'Reprovadas', tom: 'red' }
    ]
    const contagem = {}
    for (const sol of solicitacoes) {
      const st = textoStatus(sol.status)
      contagem[st] = (contagem[st] || 0) + 1
    }
    return ordem.map(item => ({ ...item, total: contagem[item.status] || 0 }))
  }, [solicitacoes])

  // Filtros da Central de Solicitações: não alteram nem gravam dados no servidor.
  const opcoesCondominiosSolicitacoes = useMemo(() =>
    [...new Set(solicitacoes.map(item => item.condominio).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [solicitacoes]
  )
  const opcoesCategoriasSolicitacoes = useMemo(() =>
    [...new Set(solicitacoes.map(item => item.categoria).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [solicitacoes]
  )
  const solicitacoesFiltradas = useMemo(() => {
    const buscaNorm = normalizarTexto(filtroSolicitacao)
    const lista = solicitacoes.filter(sol => {
      const status = textoStatus(sol.status)
      if (filtroStatus !== 'todos' && status !== filtroStatus) return false
      if (filtroCondominioSolicitacao !== 'todos' && sol.condominio !== filtroCondominioSolicitacao) return false
      if (filtroCategoriaSolicitacao !== 'todos' && sol.categoria !== filtroCategoriaSolicitacao) return false
      const data = String(sol.data || '').slice(0, 10)
      if (filtroInicioSolicitacao && (!data || data < filtroInicioSolicitacao)) return false
      if (filtroFimSolicitacao && (!data || data > filtroFimSolicitacao)) return false
      if (!buscaNorm) return true
      const campos = `${sol.numero || ''} ${sol.condominio || ''} ${sol.categoria || ''} ${sol.descricao || ''} ${sol.fornecedor || ''} ${sol.solicitante || ''} ${status}`
      return normalizarTexto(campos).includes(buscaNorm)
    })
    return lista.sort((a, b) => {
      if (ordenacaoSolicitacao === 'maior_valor') return solicitado(b) - solicitado(a) || numero(b.id) - numero(a.id)
      if (ordenacaoSolicitacao === 'menor_valor') return solicitado(a) - solicitado(b) || numero(b.id) - numero(a.id)
      if (ordenacaoSolicitacao === 'condominio') return String(a.condominio || '').localeCompare(String(b.condominio || ''), 'pt-BR') || numero(b.id) - numero(a.id)
      const delta = String(b.data || '').localeCompare(String(a.data || '')) || numero(b.id) - numero(a.id)
      return ordenacaoSolicitacao === 'antigas' ? -delta : delta
    })
  }, [solicitacoes, filtroSolicitacao, filtroStatus, filtroCondominioSolicitacao, filtroCategoriaSolicitacao, filtroInicioSolicitacao, filtroFimSolicitacao, ordenacaoSolicitacao])

  const filtrosSolicitacoesAtivos = Boolean(
    filtroSolicitacao || filtroStatus !== 'todos' || filtroCondominioSolicitacao !== 'todos' ||
    filtroCategoriaSolicitacao !== 'todos' || filtroInicioSolicitacao || filtroFimSolicitacao
  )
  const solicitacoesPorPagina = 10
  const totalPaginasSolicitacoes = Math.max(1, Math.ceil(solicitacoesFiltradas.length / solicitacoesPorPagina))
  const paginaAtualSolicitacoes = Math.min(paginaSolicitacoes, totalPaginasSolicitacoes)
  const inicioSolicitacoes = (paginaAtualSolicitacoes - 1) * solicitacoesPorPagina
  const solicitacoesPaginadas = solicitacoesFiltradas.slice(inicioSolicitacoes, inicioSolicitacoes + solicitacoesPorPagina)

  useEffect(() => { setPaginaSolicitacoes(1) }, [
    filtroSolicitacao, filtroStatus, filtroCondominioSolicitacao, filtroCategoriaSolicitacao,
    filtroInicioSolicitacao, filtroFimSolicitacao, ordenacaoSolicitacao
  ])

  function limparFiltrosSolicitacoes() {
    setFiltroSolicitacao('')
    setFiltroStatus('todos')
    setFiltroCondominioSolicitacao('todos')
    setFiltroCategoriaSolicitacao('todos')
    setFiltroInicioSolicitacao('')
    setFiltroFimSolicitacao('')
    setOrdenacaoSolicitacao('recentes')
    setPaginaSolicitacoes(1)
  }

  const resumoSolicitacoes = useMemo(() => {
    const status = solicitacoes.map(sol => textoStatus(sol.status))
    return {
      total: status.length,
      pendentes: status.filter(st => ['Aprovação pendente', 'Em análise', 'Ajuste solicitado'].includes(st)).length,
      emExecucao: status.filter(st => st === 'Em execução').length,
      finalizadas: status.filter(st => st === 'Finalizada').length
    }
  }, [solicitacoes])

  // Compras: somente registros nas etapas aprovadas, execução ou finalização.
  const comprasBase = useMemo(() => solicitacoes.filter(sol =>
    ['Aprovada', 'Em execução', 'Finalizada'].includes(textoStatus(sol.status))
  ), [solicitacoes])
  const comprasFiltradas = useMemo(() => {
    const busca = normalizarTexto(filtroCompra)
    return comprasBase.filter(sol => {
      if (filtroCondominioCompra !== 'todos' && sol.condominio !== filtroCondominioCompra) return false
      if (filtroStatusCompra !== 'todos' && textoStatus(sol.status) !== filtroStatusCompra) return false
      return !busca || normalizarTexto(`${sol.numero || ''} ${sol.condominio || ''} ${sol.descricao || ''} ${sol.categoria || ''} ${sol.fornecedor || ''}`).includes(busca)
    }).sort((a, b) => {
      if (ordenacaoCompra === 'maior_valor') return aprovado(b) - aprovado(a) || numero(b.id) - numero(a.id)
      if (ordenacaoCompra === 'menor_valor') return aprovado(a) - aprovado(b) || numero(b.id) - numero(a.id)
      if (ordenacaoCompra === 'condominio') return String(a.condominio || '').localeCompare(String(b.condominio || ''), 'pt-BR') || numero(b.id) - numero(a.id)
      return String(b.data || '').localeCompare(String(a.data || '')) || numero(b.id) - numero(a.id)
    })
  }, [comprasBase, filtroCompra, filtroCondominioCompra, filtroStatusCompra, ordenacaoCompra])
  const resumoCompras = useMemo(() => ({
    total: comprasBase.length,
    aprovadas: comprasBase.filter(sol => textoStatus(sol.status) === 'Aprovada').length,
    emExecucao: comprasBase.filter(sol => textoStatus(sol.status) === 'Em execução').length,
    finalizadas: comprasBase.filter(sol => textoStatus(sol.status) === 'Finalizada').length
  }), [comprasBase])
  const totalComprasAprovado = comprasFiltradas.reduce((acc, sol) => acc + aprovado(sol), 0)
  const totalComprasRealizado = comprasFiltradas.reduce((acc, sol) => acc + realizado(sol), 0)
  const comprasPorPagina = 10
  const totalPaginasCompra = Math.max(1, Math.ceil(comprasFiltradas.length / comprasPorPagina))
  const paginaAtualCompra = Math.min(paginaCompra, totalPaginasCompra)
  const comprasPaginadas = comprasFiltradas.slice((paginaAtualCompra - 1) * comprasPorPagina, paginaAtualCompra * comprasPorPagina)
  useEffect(() => { setPaginaCompra(1) }, [filtroCompra, filtroCondominioCompra, filtroStatusCompra, ordenacaoCompra])
  function limparFiltrosCompra() {
    setFiltroCompra('')
    setFiltroCondominioCompra('todos')
    setFiltroStatusCompra('todos')
    setOrdenacaoCompra('recentes')
    setPaginaCompra(1)
  }
  const opcoesCondominiosCompra = useMemo(() =>
    [...new Set(comprasBase.map(sol => sol.condominio).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [comprasBase]
  )
  const condominiosCadastroFiltrados = useMemo(() => condominios.filter(cond =>
    normalizarTexto(`${cond.nome || ''} ${cond.cnpj || ''} ${cond.codigo || ''}`).includes(normalizarTexto(buscaCondominioCadastro))
  ), [condominios, buscaCondominioCadastro])
  const categoriasCadastroFiltradas = useMemo(() => categorias.filter(cat =>
    normalizarTexto(`${cat.nome || ''} ${cat.descricao || ''}`).includes(normalizarTexto(buscaCategoriaCadastro))
  ), [categorias, buscaCategoriaCadastro])
  const fornecedoresCadastroFiltrados = useMemo(() => fornecedores.filter(forn =>
    normalizarTexto(`${forn.nome || ''} ${forn.cnpj || ''} ${forn.categoria || ''}`).includes(normalizarTexto(buscaFornecedorCadastro))
  ), [fornecedores, buscaFornecedorCadastro])

  const {
    solicitacoesAnaliseFiltradas,
    dadosGraficoCondominios,
    listaOrcamentoCondominio
  } = useMemo(() => {
    const filtradas = solicitacoes.filter(sol => {
      const nomeCondominio = sol.condominio || ''
      const matchCondominio = filtroCondominioAnalise === 'todos' || nomeCondominio === filtroCondominioAnalise
      if (!matchCondominio) return false

      if (sol.data && typeof sol.data === 'string') {
        const dataSol = sol.data.substring(0, 10)
        if (filtroDataInicio && dataSol < filtroDataInicio) return false
        if (filtroDataFim && dataSol > filtroDataFim) return false
      } else if (filtroDataInicio || filtroDataFim) {
        return false
      }
      return true
    })

    const mapaGrafico = {}
    const mapaOrcamento = {}

    for (const sol of filtradas) {
      const cond = sol.condominio || 'Sem condomínio'
      const st = textoStatus(sol.status)
      const vSol = solicitado(sol)
      const vApr = ['Aprovada', 'Em execução', 'Finalizada'].includes(st) ? (aprovado(sol) || vSol) : 0
      const vReal = st === 'Finalizada' ? (realizado(sol) || aprovado(sol) || vSol) : 0

      if (!mapaGrafico[cond]) mapaGrafico[cond] = { name: cond, Solicitado: 0, Aprovado: 0, Realizado: 0 }
      mapaGrafico[cond].Solicitado += vSol
      mapaGrafico[cond].Aprovado += vApr
      mapaGrafico[cond].Realizado += vReal

      if (!mapaOrcamento[cond]) mapaOrcamento[cond] = { aprovado: 0, realizado: 0, qtdSolicitacoes: 0 }
      mapaOrcamento[cond].qtdSolicitacoes += 1
      mapaOrcamento[cond].aprovado += vApr
      mapaOrcamento[cond].realizado += vReal
    }

    const grafico = Object.values(mapaGrafico).sort((a, b) => b.Solicitado - a.Solicitado).slice(0, 10)
    const orcamento = Object.entries(mapaOrcamento)
      .map(([nome, d]) => ({ nome, ...d, saldo: d.aprovado - d.realizado }))
      .sort((a, b) => b.aprovado - a.aprovado)

    return {
      solicitacoesAnaliseFiltradas: filtradas,
      dadosGraficoCondominios: grafico,
      listaOrcamentoCondominio: orcamento
    }
  }, [solicitacoes, filtroCondominioAnalise, filtroDataInicio, filtroDataFim])

  // Indicadores baseados na mesma agregação do gráfico e da tabela financeira.
  // Não alteram valores persistidos, status nem as regras do backend.
  const resumoFinanceiro = useMemo(() => {
    const totalSolicitado = solicitacoesAnaliseFiltradas.reduce((total, sol) => total + solicitado(sol), 0)
    const totalAprovado = listaOrcamentoCondominio.reduce((total, item) => total + item.aprovado, 0)
    const totalRealizado = listaOrcamentoCondominio.reduce((total, item) => total + item.realizado, 0)
    return {
      totalSolicitado,
      totalAprovado,
      totalRealizado,
      saldo: totalAprovado - totalRealizado,
      pedidos: solicitacoesAnaliseFiltradas.length,
      condominios: listaOrcamentoCondominio.length
    }
  }, [solicitacoesAnaliseFiltradas, listaOrcamentoCondominio])

  const categoriasFinanceiras = useMemo(() => {
    const mapa = new Map()
    for (const sol of solicitacoesAnaliseFiltradas) {
      if (textoStatus(sol.status) !== 'Finalizada') continue
      const nome = sol.categoria || 'Sem categoria'
      // Mantém o critério legado dos totais apresentados no gráfico financeiro.
      const valor = realizado(sol) || aprovado(sol) || solicitado(sol)
      mapa.set(nome, (mapa.get(nome) || 0) + valor)
    }
    return [...mapa.entries()]
      .map(([nome, valor]) => ({ nome, valor }))
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 6)
  }, [solicitacoesAnaliseFiltradas])

  function aplicarPeriodoAnalise(tipo) {
    if (tipo === 'todos') {
      setFiltroDataInicio('')
      setFiltroDataFim('')
      return
    }
    const hoje = new Date()
    const inicio = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate())
    if (tipo === '30dias') inicio.setDate(inicio.getDate() - 29)
    if (tipo === 'mes') inicio.setDate(1)
    if (tipo === 'ano') { inicio.setMonth(0); inicio.setDate(1) }
    setFiltroDataInicio(dataLocalISO(inicio))
    setFiltroDataFim(dataLocalISO(hoje))
  }

  // A contagem acompanha condomínio, frequência e busca, sem depender da aba de situação.
  const checklistsNoEscopo = useMemo(() => {
    const busca = normalizarTexto(buscaChecklist)
    return checklists.filter(item => {
      if (filtroCondominioChecklist !== 'todos' && item.condominio !== filtroCondominioChecklist) return false
      if (filtroFrequenciaChecklist !== 'todas' && item.frequencia !== filtroFrequenciaChecklist) return false
      if (!busca) return true
      return [item.titulo, item.condominio, item.descricao_orientacao, item.frequencia, item.plano_acao_padrao]
        .some(valor => normalizarTexto(valor).includes(busca))
    })
  }, [checklists, filtroCondominioChecklist, filtroFrequenciaChecklist, buscaChecklist])

  const indicadoresChecklist = useMemo(() => ({
    todos: checklistsNoEscopo.length,
    em_dia: checklistsNoEscopo.filter(item => calcularStatusSLA(item.frequencia, item.ultima_execucao).status === 'em_dia').length,
    atrasados: checklistsNoEscopo.filter(item => calcularStatusSLA(item.frequencia, item.ultima_execucao).status === 'atrasado').length,
    pendentes: checklistsNoEscopo.filter(item => !item.ultima_execucao).length,
    divergencias: checklistsNoEscopo.filter(item => item.ultima_execucao?.status_conformidade === 'Não Conforme').length
  }), [checklistsNoEscopo])

  const checklistsFiltrados = useMemo(() => {
    const listagem = checklistsNoEscopo.filter(item => {
      const sla = calcularStatusSLA(item.frequencia, item.ultima_execucao)
      if (filtroSLAChecklist === 'atrasados') return sla.status === 'atrasado'
      if (filtroSLAChecklist === 'pendentes') return !item.ultima_execucao
      if (filtroSLAChecklist === 'em_dia') return sla.status === 'em_dia'
      if (filtroSLAChecklist === 'divergencias') return item.ultima_execucao?.status_conformidade === 'Não Conforme'
      return true
    })
    const ordemPrioridade = item => {
      if (item.ultima_execucao?.status_conformidade === 'Não Conforme') return 0
      const sla = calcularStatusSLA(item.frequencia, item.ultima_execucao).status
      if (sla === 'atrasado') return 1
      if (sla === 'pendente') return 2
      if (sla === 'indefinido') return 3
      return 4
    }
    return [...listagem].sort((a, b) => {
      if (ordenacaoChecklist === 'titulo') return a.titulo.localeCompare(b.titulo, 'pt-BR')
      if (ordenacaoChecklist === 'recentes') {
        return (parseDataSegura(b.ultima_execucao?.data_execucao)?.getTime() || 0) - (parseDataSegura(a.ultima_execucao?.data_execucao)?.getTime() || 0)
      }
      return ordemPrioridade(a) - ordemPrioridade(b) || a.titulo.localeCompare(b.titulo, 'pt-BR')
    })
  }, [checklistsNoEscopo, filtroSLAChecklist, ordenacaoChecklist])

  // =========================================================================
  // FUNÇÕES DE CHECKLIST, EDIÇÃO, PLANO DE AÇÃO E PDF AUTOMÁTICO POR E-MAIL
  // =========================================================================
  function abrirModalCriarChecklist() {
    setChecklistEditando(null)
    setFormNovoChecklist({
      condominio: filtroCondominioChecklist !== 'todos' ? filtroCondominioChecklist : '',
      titulo: '',
      descricao_orientacao: '',
      frequencia: 'Diária',
      plano_acao_padrao: ''
    })
    setMostrarModalNovoChecklist(true)
  }

  function abrirModalEditarChecklist(item) {
    setChecklistEditando(item)
    setFormNovoChecklist({
      condominio: item.condominio || '',
      titulo: item.titulo || '',
      descricao_orientacao: item.descricao_orientacao || '',
      frequencia: item.frequencia || 'Diária',
      plano_acao_padrao: item.plano_acao_padrao || ''
    })
    setMostrarModalNovoChecklist(true)
  }

  async function salvarNovoChecklist(e) {
    e.preventDefault()
    if (!formNovoChecklist.condominio || !formNovoChecklist.titulo.trim()) {
      mostrarToast('Selecione o condomínio e informe o título da atividade.', 'error')
      return
    }
    setSalvando(true)
    try {
      const editando = checklistEditando
      const url = editando ? `${API_URL}/checklists/${editando.id}` : `${API_URL}/checklists`
      const metodo = editando ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method: metodo,
        headers: getAuthHeaders(),
        body: JSON.stringify(formNovoChecklist)
      })
      if (!res.ok) {
        const err = await extrairErro(res, 'Erro ao salvar item de checklist.')
        throw new Error(err)
      }
      setMostrarModalNovoChecklist(false)
      setChecklistEditando(null)
      setFormNovoChecklist({ condominio: '', titulo: '', descricao_orientacao: '', frequencia: 'Diária', plano_acao_padrao: '' })
      mostrarToast(editando ? 'Atividade atualizada com sucesso!' : 'Atividade adicionada ao checklist!', 'success')
      carregarChecklists({ forcar: true, notificarErro: true })
    } catch (err) {
      mostrarToast(err.message, 'error')
    } finally {
      setSalvando(false)
    }
  }

  async function gerarRelatorioDivergenciasPDF() {
    if (enviandoRelatorio) return
    if (filtroCondominioChecklist === 'todos') {
      mostrarToast('Selecione um condomínio específico no filtro para gerar o relatório de divergências.', 'error')
      return
    }
    const condObj = condominios.find(c => c.nome === filtroCondominioChecklist)
    if (!condObj) {
      mostrarToast('Condomínio não encontrado.', 'error')
      return
    }

    // Abra a aba no próprio clique para evitar bloqueio de pop-ups após o fetch.
    const janela = window.open('', '_blank')
    setEnviandoRelatorio(true)
    try {
      const res = await fetch(`${API_URL}/condominios/${condObj.id}/checklist-relatorio-divergencias`, { headers: getAuthHeaders() })
      if (!res.ok) throw new Error('Erro ao buscar dados de divergências.')
      const dados = await res.json()

      if (!janela) {
        mostrarToast('Permita pop-ups no navegador para visualizar o PDF. O envio por e-mail continuará normalmente.', 'error')
      }

      const linhasDivergencias = dados.divergencias.length === 0 ? `
        <tr>
          <td colspan="3" style="padding: 24px; text-align: center; color: #059669; font-weight: 700; background: #f0fdf4;">
            ✓ Nenhuma irregularidade identificada nas rotinas operacionais deste condomínio. Todas as verificações estão em conformidade.
          </td>
        </tr>
      ` : dados.divergencias.map((d, index) => `
        <tr style="background: ${index % 2 === 0 ? '#ffffff' : '#f8fafc'}; page-break-inside: avoid;">
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; vertical-align: top;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13px;">${d.atividade}</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
              <span><strong>Frequência:</strong> ${d.frequencia}</span> | 
              <span><strong>Data:</strong> ${formatarDataHora(d.data_ocorrencia)}</span>
            </div>
            <div style="font-size: 11px; color: #334155; margin-top: 2px;">
              <strong>Vistoriador:</strong> ${d.responsavel}
            </div>
          </td>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; vertical-align: top; color: #b91c1c; font-size: 12.5px; line-height: 1.45;">
            ${d.relato}
            ${d.tem_foto ? '<div style="margin-top: 6px; font-size: 11px; color: #2563eb; font-weight: 600;">[Evidência fotográfica anexada no sistema]</div>' : ''}
          </td>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; vertical-align: top; background: #fffbeb; color: #92400e; font-size: 12.5px; line-height: 1.45; font-weight: 600;">
            ${d.plano_acao}
          </td>
        </tr>
      `).join('')

      if (janela) janela.document.write(`
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8">
          <title>Relatório de Divergências - ${dados.condominio}</title>
          <style>
            @page { size: A4 portrait; margin: 15mm; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 14px; margin-bottom: 20px; }
            .title-area h1 { font-size: 18px; font-weight: 800; margin: 0; color: #0f172a; }
            .title-area p { font-size: 12px; color: #475569; margin: 3px 0 0 0; }
            .kpi-badge { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 8px 16px; border-radius: 8px; text-align: right; }
            .kpi-badge .num { font-size: 18px; font-weight: 800; }
            .kpi-badge .label { font-size: 10px; text-transform: uppercase; font-weight: 700; display: block; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th { background-color: #0f172a; color: #ffffff; padding: 10px 14px; font-size: 11px; text-transform: uppercase; text-align: left; border: 1px solid #0f172a; }
            .footer-sign { margin-top: 40px; display: flex; justify-content: space-between; page-break-inside: avoid; padding-top: 20px; }
            .sign-box { width: 45%; border-top: 1px solid #94a3b8; text-align: center; padding-top: 6px; font-size: 11px; color: #475569; }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="title-area">
              <h1>HAIZE SÍNDICO PROFISSIONAL</h1>
              <p>Relatório de Auditoria e Divergências de Vistoria</p>
              <p style="margin-top: 6px;"><strong>Condomínio:</strong> ${dados.condominio} | <strong>Emissão:</strong> ${new Date().toLocaleDateString('pt-BR')}</p>
            </div>
            <div class="kpi-badge">
              <span class="label">Total de Divergências</span>
              <span class="num">${dados.total_divergencias}</span>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th style="width: 32%;">Item Vistoriado</th>
                <th style="width: 34%;">Apontamento / Não Conformidade</th>
                <th style="width: 34%;">Diretriz / Plano de Ação</th>
              </tr>
            </thead>
            <tbody>${linhasDivergencias}</tbody>
          </table>
          <div class="footer-sign">
            <div class="sign-box">Responsável pela Vistoria Operacional</div>
            <div class="sign-box">Controladoria / Gestão Haize</div>
          </div>
          <script>window.onload = function() { window.print(); }</script>
        </body>
        </html>
      `)
      if (janela) janela.document.close()

      // O GET apenas consulta as divergências. O POST solicita o envio real do PDF.
      // Não exibimos sucesso antes da confirmação do provedor de e-mail.
      try {
        const respostaEnvio = await fetch(
          `${API_URL}/condominios/${condObj.id}/checklist-relatorio-divergencias/enviar`,
          { method: 'POST', headers: getAuthHeaders() }
        )
        if (!respostaEnvio.ok) {
          throw new Error(await extrairErro(respostaEnvio, 'O serviço de e-mail não aceitou o relatório.'))
        }
        mostrarToast('Envio solicitado pelo Gmail para os dois destinatários! Confira o recebimento.', 'success')
      } catch (erroEmail) {
        mostrarToast(`PDF gerado, mas e-mail NÃO enviado: ${erroEmail.message}`, 'error')
      }
    } catch (erro) {
      if (janela && !janela.closed) janela.close()
      mostrarToast(erro.message || 'Erro ao gerar relatório de divergências.', 'error')
    } finally {
      setEnviandoRelatorio(false)
    }
  }

  function excluirItemChecklist(item) {
    confirmarAcao('Excluir Atividade', `Deseja realmente excluir "${item.titulo}" do condomínio ${item.condominio}?`, async () => {
      try {
        const res = await fetch(`${API_URL}/checklists/${item.id}`, {
          method: 'DELETE',
          headers: getAuthHeaders()
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível excluir a atividade.'))
        setChecklists(prev => prev.filter(c => c.id !== item.id))
        mostrarToast('Atividade excluída com sucesso.', 'success')
        carregarChecklists({ forcar: true, notificarErro: true })
      } catch (erro) {
        mostrarToast(erro.message || 'Não foi possível excluir a atividade. Tente novamente.', 'error')
      }
    }, true)
  }

  function abrirModalExecutarChecklist(item) {
    setItemChecklistExecutando(item)
    setFormExecucaoChecklist({
      status_conformidade: 'Conforme',
      observacao: '',
      foto: null
    })
  }

  async function confirmarExecucaoChecklist(e) {
    e?.preventDefault?.()
    if (salvandoExecucaoChecklist || !itemChecklistExecutando) return
    if (formExecucaoChecklist.status_conformidade === 'Não Conforme' && !formExecucaoChecklist.observacao.trim()) {
      mostrarToast('Descreva o problema antes de registrar uma vistoria não conforme.', 'error')
      return
    }

    const itemAtual = itemChecklistExecutando
    const statusEscolhido = formExecucaoChecklist.status_conformidade
    const relatoDigitado = formExecucaoChecklist.observacao.trim()
    const formData = new FormData()
    formData.append('responsavel', usuarioLogado.nome)
    formData.append('status_conformidade', statusEscolhido)
    formData.append('observacao', relatoDigitado)
    if (formExecucaoChecklist.foto) formData.append('foto', formExecucaoChecklist.foto)

    setSalvandoExecucaoChecklist(true)
    try {
      const res = await fetch(`${API_URL}/checklists/${itemAtual.id}/executar`, {
        method: 'POST',
        headers: getAuthHeaders(true),
        body: formData
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível registrar a vistoria.'))
      const itemAtualizado = await res.json()
      setChecklists(prev => prev.map(item => item.id === itemAtual.id ? itemAtualizado : item))
      setItemChecklistExecutando(null)
      if (statusEscolhido === 'Não Conforme') {
        setAlertaPlanoAcao({
          condominio: itemAtual.condominio,
          titulo: itemAtual.titulo,
          relato: relatoDigitado,
          plano_acao: itemAtual.plano_acao_padrao || 'Comunicar imediatamente a Controladoria Haize para providências corretivas.'
        })
      } else {
        mostrarToast('Vistoria registrada com sucesso!', 'success')
      }
      carregarChecklists({ forcar: true, notificarErro: true })
    } catch (erro) {
      mostrarToast(erro.message || 'Falha na conexão. A vistoria não foi salva.', 'error')
    } finally {
      setSalvandoExecucaoChecklist(false)
    }
  }

  // =========================================================================
  // GESTÃO DE UNIDADES E RATEIO
  // =========================================================================
  async function abrirGerenciadorUnidades(cond) {
    setCondominioUnidades(cond)
    setCarregandoUnidades(true)
    setNovaUnidade({ identificacao: '', fracao_ideal: '' })
    try {
      const res = await fetch(`${API_URL}/condominios/${cond.id}/unidades`, { headers: getAuthHeaders() })
      if (res.ok) {
        setListaUnidades(await res.json())
      } else {
        setListaUnidades([])
      }
    } catch {
      setListaUnidades([])
    } finally {
      setCarregandoUnidades(false)
    }
  }

  async function salvarNovaUnidade(e) {
    e.preventDefault()
    if (!novaUnidade.identificacao.trim()) {
      mostrarToast('Informe o número ou identificação da unidade.', 'error')
      return
    }
    const fracao = numero(novaUnidade.fracao_ideal)
    if (fracao <= 0) {
      mostrarToast('A fração ideal deve ser maior que zero.', 'error')
      return
    }

    try {
      const res = await fetch(`${API_URL}/condominios/${condominioUnidades.id}/unidades`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ identificacao: novaUnidade.identificacao.trim(), fracao_ideal: fracao })
      })
      if (!res.ok) {
        const err = await extrairErro(res, 'Erro ao cadastrar unidade.')
        throw new Error(err)
      }
      const criada = await res.json()
      setListaUnidades(prev => [...prev, criada])
      setNovaUnidade({ identificacao: '', fracao_ideal: '' })
      mostrarToast('Unidade cadastrada!', 'success')
    } catch (e) {
      mostrarToast(e.message, 'error')
    }
  }

  async function excluirUnidade(unidadeId) {
    confirmarAcao('Excluir Unidade', 'Deseja excluir esta unidade e sua respectiva fração?', async () => {
      setListaUnidades(prev => prev.filter(u => u.id !== unidadeId))
      mostrarToast('Unidade removida com sucesso.', 'success')
      try {
        const res = await fetch(`${API_URL}/unidades/${unidadeId}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error('Erro ao excluir unidade.')
      } catch (e) {
        mostrarToast(e.message, 'error')
      }
    }, true)
  }

  async function calcularRateioCondominio(condominioNome) {
    const condObj = condominios.find(c => c.nome === condominioNome)
    if (!condObj) {
      setRateioDados(null)
      return
    }
    setCarregandoRateio(true)
    try {
      const mesParam = filtroDataInicio ? `?mes=${filtroDataInicio.substring(0, 7)}` : ''
      const res = await fetch(`${API_URL}/condominios/${condObj.id}/rateio${mesParam}`, { headers: getAuthHeaders() })
      if (res.ok) {
        const dados = await res.json()
        setRateioDados(dados)
      } else {
        setRateioDados(null)
      }
    } catch {
      setRateioDados(null)
    } finally {
      setCarregandoRateio(false)
    }
  }

  useEffect(() => {
    if (pagina === 'analises' && filtroCondominioAnalise !== 'todos') {
      calcularRateioCondominio(filtroCondominioAnalise)
    } else {
      setRateioDados(null)
    }
  }, [filtroCondominioAnalise, filtroDataInicio, pagina, condominios])

  const somaFracaoTotal = useMemo(() => {
    return listaUnidades.reduce((acc, u) => acc + numero(u.fracao_ideal), 0)
  }, [listaUnidades])

  // =========================================================================
  // EXPORTAÇÃO EXCEL (.XLSX) E PDF FINANCEIRO
  // =========================================================================
  function exportarRelatorioExcel() {
    if (solicitacoesAnaliseFiltradas.length === 0 && listaOrcamentoCondominio.length === 0) {
      mostrarToast('Não existem dados para exportar no filtro selecionado.', 'error')
      return
    }

    const wb = XLSX.utils.book_new()
    const periodoFormatado = filtroDataInicio || filtroDataFim ? `De ${filtroDataInicio ? new Date(filtroDataInicio + 'T00:00:00').toLocaleDateString('pt-BR') : 'Início'} até ${filtroDataFim ? new Date(filtroDataFim + 'T00:00:00').toLocaleDateString('pt-BR') : 'Hoje'}` : 'Todo o Período'
    const condFormatado = filtroCondominioAnalise === 'todos' ? 'Todos os Condomínios' : filtroCondominioAnalise
    const dataEmissao = new Date().toLocaleString('pt-BR')

    const bordaPadrao = { top: { style: 'thin', color: { rgb: 'CBD5E1' } }, bottom: { style: 'thin', color: { rgb: 'CBD5E1' } }, left: { style: 'thin', color: { rgb: 'CBD5E1' } }, right: { style: 'thin', color: { rgb: 'CBD5E1' } } }
    const bordaTotal = { top: { style: 'medium', color: { rgb: '0F172A' } }, bottom: { style: 'double', color: { rgb: '0F172A' } }, left: { style: 'thin', color: { rgb: 'CBD5E1' } }, right: { style: 'thin', color: { rgb: 'CBD5E1' } } }

    const estiloTitulo = { font: { name: 'Calibri', sz: 14, bold: true, color: { rgb: 'FFFFFF' } }, fill: { fgColor: { rgb: '0F172A' } }, alignment: { vertical: 'center', horizontal: 'left' } }
    const estiloSubtitulo = { font: { name: 'Calibri', sz: 10, italic: true, color: { rgb: '334155' } }, fill: { fgColor: { rgb: 'F1F5F9' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao }
    const estiloCabecalhoTabela = { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: 'FFFFFF' } }, fill: { fgColor: { rgb: '1E293B' } }, alignment: { vertical: 'center', horizontal: 'center', wrapText: true }, border: bordaPadrao }
    const formatoMoeda = '"R$" #,##0.00'

    const totalQtdResumo = listaOrcamentoCondominio.reduce((acc, i) => acc + (i.qtdSolicitacoes || 0), 0)
    const totalTeto = listaOrcamentoCondominio.reduce((acc, i) => acc + i.aprovado, 0)
    const totalRealizado = listaOrcamentoCondominio.reduce((acc, i) => acc + i.realizado, 0)
    const totalSaldo = totalTeto - totalRealizado

    const linhasResumo = [
      [{ v: 'HAIZE SÍNDICO PROFISSIONAL — RESUMO EXECUTIVO POR CONDOMÍNIO', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }],
      [{ v: `Condomínio: ${condFormatado}   |   Período: ${periodoFormatado}   |   Emitido em: ${dataEmissao}`, s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }],
      [],
      [
        { v: 'Condomínio', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Qtd Solicitações', s: estiloCabecalhoTabela },
        { v: 'Teto Aprovado (R$)', s: estiloCabecalhoTabela },
        { v: 'Gasto Realizado (R$)', s: estiloCabecalhoTabela },
        { v: 'Saldo Orçamentário (R$)', s: estiloCabecalhoTabela },
        { v: 'Status Orçamentário', s: estiloCabecalhoTabela }
      ]
    ]

    listaOrcamentoCondominio.forEach((item, idx) => {
      const corZebra = idx % 2 === 0 ? 'FFFFFF' : 'F8FAFC'
      let estado = 'No Limite'; let bgStatus = 'F1F5F9'; let corStatus = '475569'
      if (item.saldo > 0) { estado = 'Economia'; bgStatus = 'D1FAE5'; corStatus = '065F46' }
      if (item.saldo < 0) { estado = 'Estourado'; bgStatus = 'FEE2E2'; corStatus = '991B1B' }
      if (item.aprovado === 0) { estado = 'Sem Orçamento'; bgStatus = 'F1F5F9'; corStatus = '64748B' }
      const corSaldo = item.saldo < 0 ? 'DC2626' : '059669'

      linhasResumo.push([
        { v: item.nome, t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: item.qtdSolicitacoes || 0, t: 'n', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: Number(item.aprovado.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1E293B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number(item.realizado.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1E293B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number(item.saldo.toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: corSaldo } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: estado, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corStatus } }, fill: { fgColor: { rgb: bgStatus } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } }
      ])
    })

    const ultimaLinhaDadosResumo = 4 + listaOrcamentoCondominio.length
    const bgTotalSaldoResumo = totalSaldo < 0 ? 'FEE2E2' : 'D1FAE5'
    const corTotalSaldoResumo = totalSaldo < 0 ? '991B1B' : '065F46'

    linhasResumo.push([
      { v: 'TOTAL CONSOLIDADO', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { t: 'n', f: `SUM(B5:B${ultimaLinhaDadosResumo})`, v: totalQtdResumo, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `SUM(C5:C${ultimaLinhaDadosResumo})`, v: Number(totalTeto.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(D5:D${ultimaLinhaDadosResumo})`, v: Number(totalRealizado.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(E5:E${ultimaLinhaDadosResumo})`, v: Number(totalSaldo.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: corTotalSaldoResumo } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { v: totalSaldo >= 0 ? 'SALDO POSITIVO' : 'ORÇAMENTO ESTOURADO', t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corTotalSaldoResumo } }, fill: { fgColor: { rgb: bgTotalSaldoResumo } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } }
    ])

    const wsResumo = XLSX.utils.aoa_to_sheet(linhasResumo)
    wsResumo['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 5 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 5 } }]
    wsResumo['!cols'] = [{ wch: 32 }, { wch: 18 }, { wch: 22 }, { wch: 22 }, { wch: 24 }, { wch: 22 }]
    XLSX.utils.book_append_sheet(wb, wsResumo, 'Resumo por Condomínio')

    const totalSol = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + solicitado(s), 0)
    const totalApr = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (aprovado(s) || solicitado(s)), 0)
    const totalReal = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (realizado(s) || 0), 0)
    const qtdPedidos = solicitacoesAnaliseFiltradas.length

    const linhasExtrato = [
      [{ v: 'HAIZE SÍNDICO PROFISSIONAL — EXTRATO DETALHADO DE SOLICITAÇÕES', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }, { v: '', s: estiloTitulo }],
      [{ v: `Condomínio: ${condFormatado}   |   Período: ${periodoFormatado}   |   Total de Solicitações: ${qtdPedidos}   |   Emitido em: ${dataEmissao}`, s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }, { v: '', s: estiloSubtitulo }],
      [],
      [
        { v: 'Código', s: estiloCabecalhoTabela },
        { v: 'Condomínio', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Categoria', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Descrição do Pedido', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Fornecedor', s: { ...estiloCabecalhoTabela, alignment: { vertical: 'center', horizontal: 'left' } } },
        { v: 'Valor Solicitado (R$)', s: estiloCabecalhoTabela },
        { v: 'Valor Aprovado (R$)', s: estiloCabecalhoTabela },
        { v: 'Valor Realizado (R$)', s: estiloCabecalhoTabela },
        { v: 'Status', s: estiloCabecalhoTabela },
        { v: 'Data de Abertura', s: estiloCabecalhoTabela }
      ]
    ]

    solicitacoesAnaliseFiltradas.forEach((s, idx) => {
      const corZebra = idx % 2 === 0 ? 'FFFFFF' : 'F8FAFC'
      const st = textoStatus(s.status)
      let bgSt = 'FEF3C7'; let corSt = 'D97706'
      if (st === 'Aprovada') { bgSt = 'DBEAFE'; corSt = '1D4ED8' }
      if (st === 'Em execução') { bgSt = 'E0E7FF'; corSt = '4338CA' }
      if (st === 'Finalizada') { bgSt = 'D1FAE5'; corSt = '065F46' }
      if (st === 'Reprovada') { bgSt = 'FEE2E2'; corSt = '991B1B' }

      linhasExtrato.push([
        { v: s.numero || '', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '2563EB' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: s.condominio || '', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.categoria || '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '6B21A8' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.descricao || '', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: s.fornecedor || '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '475569' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaPadrao } },
        { v: Number(solicitado(s).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '334155' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number((aprovado(s) || solicitado(s)).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: Number((realizado(s) || 0).toFixed(2)), t: 'n', z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '059669' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaPadrao } },
        { v: st, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: corSt } }, fill: { fgColor: { rgb: bgSt } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } },
        { v: formatarDataHora(s.data), t: 's', s: { font: { name: 'Calibri', sz: 10, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: corZebra } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaPadrao } }
      ])
    })

    const ultimaLinhaDadosExtrato = 4 + solicitacoesAnaliseFiltradas.length

    linhasExtrato.push([
      { v: 'TOTAL GASTOS', t: 's', s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `COUNTA(A5:A${ultimaLinhaDadosExtrato})`, v: qtdPedidos, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { v: 'solicitações no período', t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: '475569' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { v: `Soma consolidada automática (${qtdPedidos} pedidos)`, t: 's', s: { font: { name: 'Calibri', sz: 10, italic: true, color: { rgb: '475569' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'left' }, border: bordaTotal } },
      { v: '-', t: 's', s: { font: { name: 'Calibri', sz: 11, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { t: 'n', f: `SUM(F5:F${ultimaLinhaDadosExtrato})`, v: Number(totalSol.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(G5:G${ultimaLinhaDadosExtrato})`, v: Number(totalApr.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '1D4ED8' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { t: 'n', f: `SUM(H5:H${ultimaLinhaDadosExtrato})`, v: Number(totalReal.toFixed(2)), z: formatoMoeda, s: { font: { name: 'Calibri', sz: 11, bold: true, color: { rgb: '059669' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'right' }, border: bordaTotal } },
      { v: `${qtdPedidos} itens`, t: 's', s: { font: { name: 'Calibri', sz: 10, bold: true, color: { rgb: '0F172A' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } },
      { v: '-', t: 's', s: { font: { name: 'Calibri', sz: 10, color: { rgb: '64748B' } }, fill: { fgColor: { rgb: 'E2E8F0' } }, alignment: { vertical: 'center', horizontal: 'center' }, border: bordaTotal } }
    ])

    const wsExtrato = XLSX.utils.aoa_to_sheet(linhasExtrato)
    wsExtrato['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 9 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 9 } }]
    wsExtrato['!cols'] = [{ wch: 16 }, { wch: 24 }, { wch: 22 }, { wch: 38 }, { wch: 24 }, { wch: 22 }, { wch: 22 }, { wch: 22 }, { wch: 18 }, { wch: 20 }]
    XLSX.utils.book_append_sheet(wb, wsExtrato, 'Extrato de Solicitações')

    const nomeArquivo = `Relatorio_Controladoria_${filtroCondominioAnalise !== 'todos' ? filtroCondominioAnalise : 'Geral'}.xlsx`
    XLSX.writeFile(wb, nomeArquivo)
    mostrarToast('Relatório Executivo Excel (.xlsx) gerado com sucesso!', 'success')
  }

  function exportarRelatorioPDF() {
    if (solicitacoesAnaliseFiltradas.length === 0 && listaOrcamentoCondominio.length === 0) {
      mostrarToast('Não existem dados para exportar no filtro selecionado.', 'error')
      return
    }

    const periodoFormatado = filtroDataInicio || filtroDataFim ? `De ${filtroDataInicio ? new Date(filtroDataInicio + 'T00:00:00').toLocaleDateString('pt-BR') : 'Início'} até ${filtroDataFim ? new Date(filtroDataFim + 'T00:00:00').toLocaleDateString('pt-BR') : 'Hoje'}` : 'Todo o Período'
    const condFormatado = filtroCondominioAnalise === 'todos' ? 'Todos os Condomínios' : filtroCondominioAnalise

    const totalQtd = listaOrcamentoCondominio.reduce((acc, i) => acc + (i.qtdSolicitacoes || 0), 0)
    const totalTeto = listaOrcamentoCondominio.reduce((acc, i) => acc + i.aprovado, 0)
    const totalRealizado = listaOrcamentoCondominio.reduce((acc, i) => acc + i.realizado, 0)
    const totalSaldo = totalTeto - totalRealizado

    const totalSol = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + solicitado(s), 0)
    const totalReal = solicitacoesAnaliseFiltradas.reduce((acc, s) => acc + (s.valor_realizado || s.valor_aprovado || s.valor), 0)

    const janela = window.open('', '_blank')
    if (!janela) {
      mostrarToast('Permita pop-ups no navegador para gerar o PDF.', 'error')
      return
    }

    const linhasResumo = listaOrcamentoCondominio.map((item, idx) => `
      <tr style="background: ${idx % 2 === 0 ? '#ffffff' : '#f8fafc'}; page-break-inside: avoid;">
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #0f172a;">${escaparHtml(item.nome)}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 600;">${item.qtdSolicitacoes || 0}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.aprovado)}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.realizado)}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right; color: ${item.saldo < 0 ? '#dc2626' : '#059669'}; font-weight: 700;">${formatarValor(item.saldo)}</td>
      </tr>
    `).join('')

    const linhasSols = solicitacoesAnaliseFiltradas.map((s, idx) => `
      <tr style="background: ${idx % 2 === 0 ? '#ffffff' : '#f8fafc'}; page-break-inside: avoid;">
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-family: monospace; font-size: 11px;">${escaparHtml(s.numero || '')}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: 600;">${escaparHtml(s.condominio || '')}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; color: #475569;">${escaparHtml(s.categoria || '-')}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0;">${escaparHtml(s.descricao || '')}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; text-align: right;">${formatarValor(s.valor)}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; text-align: right; font-weight: 600;">${formatarValor(s.valor_realizado || s.valor_aprovado || s.valor)}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; text-align: center; font-weight: 600; font-size: 11px;">${textoStatus(s.status)}</td>
      </tr>
    `).join('')

    janela.document.write(`
      <!DOCTYPE html>
      <html lang="pt-BR">
      <head>
        <meta charset="utf-8">
        <title>Fecho Orçamentário - Controladoria Haize</title>
        <style>
          @page { size: A4 portrait; margin: 12mm; }
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 0; color: #0f172a; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 14px; margin-bottom: 20px; }
          .title { font-size: 18px; font-weight: 800; }
          .subtitle { font-size: 12px; color: #64748b; margin-top: 2px; }
          .meta { font-size: 11px; color: #334155; }
          h3 { font-size: 12px; text-transform: uppercase; margin: 20px 0 8px 0; color: #1e293b; font-weight: 800; }
          table { width: 100%; border-collapse: collapse; font-size: 11.5px; margin-bottom: 16px; }
          th { background-color: #0f172a; color: #ffffff; padding: 8px 10px; border: 1px solid #0f172a; text-align: left; font-size: 10.5px; text-transform: uppercase; }
          tfoot td { background-color: #f1f5f9; font-weight: 800; border: 1px solid #cbd5e1; padding: 8px 10px; }
        </style>
      </head>
      <body>
        <div class="header">
          <div>
            <div class="title">HAIZE SÍNDICO PROFISSIONAL</div>
            <div class="subtitle">Relatório Consolidado de Fecho Orçamentário</div>
          </div>
          <div class="meta" style="text-align: right;">
            <div><strong>Filtro:</strong> ${escaparHtml(condFormatado)}</div>
            <div><strong>Período:</strong> ${escaparHtml(periodoFormatado)}</div>
            <div><strong>Emissão:</strong> ${new Date().toLocaleDateString('pt-BR')}</div>
          </div>
        </div>
        <h3>Resumo Executivo por Condomínio</h3>
        <table>
          <thead>
            <tr>
              <th>Condomínio</th>
              <th style="text-align: center;">Qtd Solicitações</th>
              <th style="text-align: right;">Teto Aprovado</th>
              <th style="text-align: right;">Gasto Realizado</th>
              <th style="text-align: right;">Saldo</th>
            </tr>
          </thead>
          <tbody>${linhasResumo}</tbody>
          <tfoot>
            <tr>
              <td>TOTAL CONSOLIDADO</td>
              <td style="text-align: center;">${totalQtd}</td>
              <td style="text-align: right;">${formatarValor(totalTeto)}</td>
              <td style="text-align: right;">${formatarValor(totalRealizado)}</td>
              <td style="text-align: right; color: ${totalSaldo < 0 ? '#dc2626' : '#059669'};">${formatarValor(totalSaldo)}</td>
            </tr>
          </tfoot>
        </table>
        <h3>Extrato Analítico de Solicitações</h3>
        <table>
          <thead>
            <tr>
              <th style="width: 12%;">Código</th>
              <th style="width: 18%;">Condomínio</th>
              <th style="width: 14%;">Categoria</th>
              <th style="width: 26%;">Descrição</th>
              <th style="text-align: right; width: 10%;">Solicitado</th>
              <th style="text-align: right; width: 10%;">Realizado</th>
              <th style="text-align: center; width: 10%;">Status</th>
            </tr>
          </thead>
          <tbody>${linhasSols}</tbody>
          <tfoot>
            <tr>
              <td colspan="4">TOTAL CONSOLIDADO (${solicitacoesAnaliseFiltradas.length} pedidos)</td>
              <td style="text-align: right;">${formatarValor(totalSol)}</td>
              <td style="text-align: right;">${formatarValor(totalReal)}</td>
              <td>-</td>
            </tr>
          </tfoot>
        </table>
        <script>window.onload = function() { window.print(); }</script>
      </body>
      </html>
    `)
    janela.document.close()
  }

  function atualizarCampoFormulario(campo, valor) { setFormulario(atual => ({ ...atual, [campo]: valor })) }
  function limparFormulario() {
    setFormulario({ condominio: '', categoria: '', fornecedor: '', descricao: '', valor_servico: '', valor_produto: '', observacao: '' })
    setSolicitacaoEditando(null)
    setArquivosNovaSolicitacao([])
  }
  function fecharFormulario() { setMostrarFormulario(false); limparFormulario() }

  function editarSolicitacao(solicitacao) {
    setSolicitacaoEditando(solicitacao)
    setArquivosNovaSolicitacao([])
    setFormulario({
      condominio: solicitacao.condominio || '', categoria: solicitacao.categoria || '', fornecedor: solicitacao.fornecedor || '',
      descricao: solicitacao.descricao || '', valor_servico: solicitacao.valor_servico || '', valor_produto: solicitacao.valor_produto || '', observacao: solicitacao.observacao || ''
    })
    setMostrarFormulario(true)
    setSolicitacaoSelecionada(null)
  }

  async function salvarSolicitacao(e) {
    e.preventDefault()
    if (!formulario.condominio || !formulario.categoria || !formulario.fornecedor || !formulario.descricao || !formulario.observacao) {
      mostrarToast('Por favor, preencha todos os campos obrigatórios (*).', 'error')
      return
    }
    const vServ = numero(formulario.valor_servico)
    const vProd = numero(formulario.valor_produto)
    if (vServ <= 0 && vProd <= 0) {
      mostrarToast('O valor total (Serviço ou Produto) deve ser maior que zero.', 'error')
      return
    }

    const condObj = condominios.find(c => c.nome === formulario.condominio)
    const payload = {
      ...formulario,
      condominio_id: condObj?.id || null,
      valor_servico: vServ,
      valor_produto: vProd,
      solicitante: usuarioLogado.nome,
      status: 'Aprovação pendente'
    }

    const editando = solicitacaoEditando
    const arquivosParaEnviar = [...arquivosNovaSolicitacao]
    setSalvando(true)
    try {
      const res = await fetch(`${API_URL}/solicitacoes${editando ? `/${editando.id}` : ''}`, {
        method: editando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao salvar solicitação.')
        throw new Error(erroMsg)
      }
      const criadaOuAtualizada = await res.json()

      // Se o solicitante anexou orçamento/documento/foto na criação, faz o upload automático
      if (arquivosParaEnviar.length > 0 && criadaOuAtualizada?.id) {
        for (const arquivo of arquivosParaEnviar) {
          if (arquivo.size <= 10 * 1024 * 1024) {
            const formData = new FormData()
            formData.append('arquivo', arquivo)
            formData.append('tipo', 'Orçamento')
            formData.append('responsavel', usuarioLogado.nome)
            await fetch(`${API_URL}/solicitacoes/${criadaOuAtualizada.id}/anexos`, {
              method: 'POST',
              headers: getAuthHeaders(true),
              body: formData
            }).catch(() => {})
          }
        }
      }

      setSolicitacoes(prev => {
        const novaLista = editando
          ? prev.map(s => s.id === editando.id ? criadaOuAtualizada : s)
          : [criadaOuAtualizada, ...prev]
        salvarCache('solicitacoes', novaLista)
        hashCacheRef.current.sol = JSON.stringify(novaLista)
        return novaLista
      })

      fecharFormulario()
      if (textoStatus(criadaOuAtualizada?.status) === 'Aprovada') {
        mostrarToast('Solicitação criada e aprovada automaticamente pela alçada!', 'success')
      } else {
        mostrarToast(editando ? 'Atualizada com sucesso!' : 'Solicitação enviada com sucesso!', 'success')
      }
      carregarDados(false)
    } catch (erro) {
      // Mesmo se houver oscilação na resposta, sincroniza para exibir caso tenha sido salva
      carregarDados(false)
      mostrarToast(erro.message, 'error')
    } finally {
      setSalvando(false)
    }
  }

  async function abrirSolicitacao(solicitacao) {
    setSolicitacaoSelecionada(solicitacao)
    setHistoricoSolicitacao([])
    setAnexosSolicitacao([])
    try {
      const [resHist, resAnexos] = await Promise.all([
        fetch(`${API_URL}/solicitacoes/${solicitacao.id}/historico`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/solicitacoes/${solicitacao.id}/anexos`, { headers: getAuthHeaders() })
      ])
      if (resHist.ok) setHistoricoSolicitacao(await resHist.json())
      if (resAnexos.ok) setAnexosSolicitacao(await resAnexos.json())
    } catch { }
  }

  function fecharSolicitacao() { setSolicitacaoSelecionada(null); setHistoricoSolicitacao([]); setAnexosSolicitacao([]) }

  async function fazerUploadAnexo(evento, tipoDocumento) {
    const arquivo = evento.target.files[0]
    if (!arquivo) return
    if (arquivo.size > 10 * 1024 * 1024) {
      mostrarToast('O arquivo deve ter no máximo 10MB', 'error')
      return
    }

    const formData = new FormData()
    formData.append('arquivo', arquivo)
    formData.append('tipo', tipoDocumento)
    formData.append('responsavel', usuarioLogado.nome)

    setFazendoUpload(true)
    try {
      const res = await fetch(`${API_URL}/solicitacoes/${solicitacaoSelecionada.id}/anexos`, {
        method: 'POST',
        headers: getAuthHeaders(true),
        body: formData
      })
      if (!res.ok) {
        const erroMsg = await extrairErro(res, 'Erro ao anexar arquivo.')
        throw new Error(erroMsg)
      }
      const novoAnexo = await res.json()
      setAnexosSolicitacao(prev => [...prev, novoAnexo])
      mostrarToast('Arquivo anexado com sucesso!', 'success')
    } catch (e) {
      mostrarToast(e.message, 'error')
    } finally {
      setFazendoUpload(false)
    }
  }

  function aprovarSolicitacao(solicitacao) {
    pedirInput('Aprovar solicitação', 'Informe o valor aprovado para essa compra:', String(aprovado(solicitacao) || solicitado(solicitacao) || ''), async v => {
      const vNum = numero(v)
      if (vNum <= 0) { mostrarToast('O valor aprovado deve ser maior que zero.', 'error'); return }

      fecharSolicitacao()
      setSolicitacoes(prev => prev.map(s => s.id === solicitacao.id ? { ...s, status: 'Aprovada', valor_aprovado: vNum } : s))
      mostrarToast('Solicitação aprovada com sucesso.', 'success')

      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Aprovada', valor_aprovado: vNum })
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao aprovar solicitação.'))
        dispararNotificacaoNativa('Solicitação Aprovada', `O pedido ${solicitacao.numero} foi aprovado.`)
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    })
  }

  function solicitarAjuste(solicitacao) {
    pedirInput('Solicitar Ajuste', 'Informe o motivo ou o que precisa ser corrigido pelo solicitante:', solicitacao.motivo_ajuste || '', async motivo => {
      if (!motivo || !motivo.trim()) { mostrarToast('Informe o motivo do ajuste.', 'error'); return }

      fecharSolicitacao()
      setSolicitacoes(prev => prev.map(s => s.id === solicitacao.id ? { ...s, status: 'Ajuste solicitado', motivo_ajuste: motivo.trim() } : s))
      mostrarToast('Ajuste solicitado ao autor.', 'success')

      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Ajuste solicitado', motivo_ajuste: motivo.trim() })
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao solicitar ajuste.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    })
  }

  function reprovarSolicitacao(solicitacao) {
    pedirInput('Reprovar Solicitação', 'Informe o motivo da reprovação:', '', async motivo => {
      if (!motivo || !motivo.trim()) { mostrarToast('Informe o motivo da reprovação.', 'error'); return }

      fecharSolicitacao()
      setSolicitacoes(prev => prev.map(s => s.id === solicitacao.id ? { ...s, status: 'Reprovada', motivo_ajuste: motivo.trim() } : s))
      mostrarToast('Solicitação reprovada.', 'success')

      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/status`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ status: 'Reprovada', motivo_ajuste: motivo.trim() })
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao reprovar solicitação.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    }, true)
  }

  function iniciarExecucao(solicitacao) {
    confirmarAcao('Executar solicitação', `Deseja iniciar a execução da compra ${solicitacao.numero || ''}?`, async () => {
      fecharSolicitacao()
      setSolicitacoes(prev => prev.map(s => s.id === solicitacao.id ? { ...s, status: 'Em execução' } : s))
      mostrarToast('Solicitação enviada para execução!', 'success')

      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/iniciar-execucao`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ observacao_execucao: '' })
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao executar a solicitação.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    })
  }

  function finalizarSolicitacao(solicitacao) {
    pedirInput('Finalizar solicitação', 'Informe o valor realmente realizado/pago:', String(realizado(solicitacao) || aprovado(solicitacao) || solicitado(solicitacao) || ''), async v => {
      const vNum = numero(v)
      if (vNum <= 0) { mostrarToast('O valor realizado deve ser maior que zero.', 'error'); return }

      fecharSolicitacao()
      setSolicitacoes(prev => prev.map(s => s.id === solicitacao.id ? { ...s, status: 'Finalizada', valor_realizado: vNum } : s))
      mostrarToast('Solicitação finalizada!', 'success')

      try {
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}/finalizar`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ valor_realizado: vNum })
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao finalizar solicitação.'))
        dispararNotificacaoNativa('Solicitação Finalizada', `O pedido ${solicitacao.numero} foi concluído com sucesso.`)
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    })
  }

  function excluirSolicitacao(solicitacao) {
    confirmarAcao('Excluir', `Apagar ${solicitacao.numero || ''}?`, async () => {
      try {
        // Primeiro confirma a exclusão no servidor; não remove dados nem exibe
        // sucesso antes de receber a resposta da API.
        const res = await fetch(`${API_URL}/solicitacoes/${solicitacao.id}`, {
          method: 'DELETE',
          headers: getAuthHeaders()
        })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir solicitação.'))

        // Só atualiza a tela e o cache depois da confirmação do banco de dados.
        const atualizadas = solicitacoes.filter(s => s.id !== solicitacao.id)
        setSolicitacoes(prev => prev.filter(s => s.id !== solicitacao.id))
        salvarCache('solicitacoes', atualizadas)
        hashCacheRef.current.sol = JSON.stringify(atualizadas)
        qtdSolicitacoesRef.current = atualizadas.length
        fecharSolicitacao()
        mostrarToast('Solicitação excluída com sucesso.', 'success')
        carregarDados(false)
      } catch (erro) {
        const falhaDeRede = erro instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(erro.message)
        const mensagem = falhaDeRede
          ? 'Falha na comunicação com o Render. Confira a API e os Logs do servidor.'
          : (erro.message || 'Erro inesperado ao excluir a solicitação.')
        mostrarToast(`Solicitação NÃO excluída: ${mensagem}`, 'error')
      }
    }, true)
  }

  function fecharFormularioCondominio() { setMostrarFormularioCondominio(false); setCondominioEditando(null); setFormularioCondominio({ nome: '', cnpj: '', codigo: '' }) }
  function abrirFormularioNovoCondominio() { setCondominioEditando(null); setFormularioCondominio({ nome: '', cnpj: '', codigo: '' }); setMostrarFormularioCondominio(true) }
  function editarCondominio(cond) { setCondominioEditando(cond); setFormularioCondominio({ nome: cond.nome || '', cnpj: cond.cnpj || '', codigo: cond.codigo || '' }); setMostrarFormularioCondominio(true) }

  async function salvarCondominio(e) {
    e.preventDefault()
    if (!formularioCondominio.nome) return
    const editando = condominioEditando
    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/condominios${editando ? `/${editando.id}` : ''}`, {
        method: editando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formularioCondominio)
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao salvar condomínio.'))
      const salvo = await res.json()
      setCondominios(prev => editando ? prev.map(c => c.id === editando.id ? salvo : c) : [...prev, salvo])
      fecharFormularioCondominio()
      if (mostrarFormulario && !editando) atualizarCampoFormulario('condominio', salvo.nome)
      mostrarToast('Condomínio salvo com sucesso!', 'success')
      carregarDados(false)
    } catch (err) { mostrarToast(err.message, 'error') } finally { setSalvando(false) }
  }

  function excluirCondominio(id, nome) {
    confirmarAcao('Excluir', `Apagar "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/condominios/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir condomínio.'))
        setCondominios(prev => prev.filter(c => c.id !== id))
        mostrarToast('Condomínio excluído.', 'success')
      } catch (e) {
        mostrarToast(`Não foi possível excluir o condomínio: ${e.message}`, 'error')
      } finally {
        carregarDados(false)
      }
    }, true)
  }

  function fecharFormularioCategoria() { setMostrarFormularioCategoria(false); setCategoriaEditando(null); setFormularioCategoria({ nome: '', descricao: '', limites: {} }) }
  function abrirFormularioNovoCategoria() { setCategoriaEditando(null); setFormularioCategoria({ nome: '', descricao: '', limites: {} }); setMostrarFormularioCategoria(true) }

  function editarCategoria(cat) {
    setCategoriaEditando(cat)
    const limitesObj = {}
    if (cat.limites && Array.isArray(cat.limites)) {
      cat.limites.forEach(l => { limitesObj[l.condominio] = formatarNumero(l.limite) })
    }
    setFormularioCategoria({ nome: cat.nome || '', descricao: cat.descricao || '', limites: limitesObj })
    setMostrarFormularioCategoria(true)
  }

  async function salvarCategoria(e) {
    e.preventDefault()
    if (!formularioCategoria.nome) return

    const limitesArray = Object.entries(formularioCategoria.limites).map(([condominio, limite]) => ({
      condominio: condominio, limite: numero(limite)
    })).filter(l => l.limite > 0)

    const payload = { nome: formularioCategoria.nome, descricao: formularioCategoria.descricao, limites: limitesArray }
    const editando = categoriaEditando

    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/categorias${editando ? `/${editando.id}` : ''}`, {
        method: editando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao salvar categoria.'))
      const salvo = await res.json()
      const catFormatada = { ...salvo, limites: limitesArray }
      setCategorias(prev => editando ? prev.map(c => c.id === editando.id ? catFormatada : c) : [...prev, catFormatada])
      fecharFormularioCategoria()
      if (mostrarFormulario && !editando) atualizarCampoFormulario('categoria', salvo.nome)
      mostrarToast('Categoria salva!', 'success')
      carregarDados(false)
    } catch (err) {
      mostrarToast(err.message, 'error')
    } finally {
      setSalvando(false)
    }
  }

  function excluirCategoria(id, nome) {
    confirmarAcao('Excluir', `Apagar a categoria "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/categorias/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir categoria.'))
        setCategorias(prev => prev.filter(c => c.id !== id))
        mostrarToast('Categoria excluída.', 'success')
      } catch (e) {
        mostrarToast(`Não foi possível excluir a categoria: ${e.message}`, 'error')
      } finally {
        carregarDados(false)
      }
    }, true)
  }

  function fecharFormularioFornecedor() { setMostrarFormularioFornecedor(false); setFornecedorEditando(null); setFormularioFornecedor({ nome: '', cnpj: '', categoria: '' }) }
  function abrirFormularioNovoFornecedor() { setFornecedorEditando(null); setFormularioFornecedor({ nome: '', cnpj: '', categoria: '' }); setMostrarFormularioFornecedor(true) }
  function editarFornecedor(forn) { setFornecedorEditando(forn); setFormularioFornecedor({ nome: forn.nome || '', cnpj: forn.cnpj || '', categoria: forn.categoria || '' }); setMostrarFormularioFornecedor(true) }

  async function salvarFornecedor(e) {
    e.preventDefault()
    if (!formularioFornecedor.nome) return
    const editando = fornecedorEditando
    try {
      setSalvando(true)
      const res = await fetch(`${API_URL}/fornecedores${editando ? `/${editando.id}` : ''}`, {
        method: editando ? 'PUT' : 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formularioFornecedor)
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao salvar fornecedor.'))
      const salvo = await res.json()
      setFornecedores(prev => editando ? prev.map(f => f.id === editando.id ? salvo : f) : [...prev, salvo])
      fecharFormularioFornecedor()
      if (mostrarFormulario && !editando) atualizarCampoFormulario('fornecedor', salvo.nome)
      mostrarToast('Fornecedor salvo com sucesso!', 'success')
      carregarDados(false)
    } catch (err) { mostrarToast(err.message, 'error') } finally { setSalvando(false) }
  }

  function excluirFornecedor(id, nome) {
    confirmarAcao('Excluir', `Apagar "${nome}"?`, async () => {
      try {
        const res = await fetch(`${API_URL}/fornecedores/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir fornecedor.'))
        setFornecedores(prev => prev.filter(f => f.id !== id))
        mostrarToast('Fornecedor excluído.', 'success')
      } catch (e) {
        mostrarToast(`Não foi possível excluir o fornecedor: ${e.message}`, 'error')
      } finally {
        carregarDados(false)
      }
    }, true)
  }

  function atualizarCampoCondominio(campo, valor) { setFormularioCondominio(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoCategoria(campo, valor) { setFormularioCategoria(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoFornecedor(campo, valor) { setFormularioFornecedor(atual => ({ ...atual, [campo]: valor })) }

  useEffect(() => {
    if (pagina === 'checklist' && abaChecklist === 'zeladores' && usuarioLogado?.perfil === 'Controladoria') carregarZeladores()
  }, [pagina, abaChecklist, usuarioLogado?.perfil, usuarioLogado?.token])

  async function carregarZeladores() {
    if (usuarioLogado?.perfil !== 'Controladoria') return
    setCarregandoZeladores(true)
    try {
      const res = await fetch(`${API_URL}/usuarios`, { headers: getAuthHeaders() })
      if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível consultar os zeladores.'))
      const lista = (await res.json()).filter(u => u.perfil === 'Checklist')
      setZeladores(lista)
      setAtribuicoesZeladores(Object.fromEntries(lista.map(u => [u.id, String(u.condominio_id || '')])))
    } catch (err) {
      mostrarToast(err.message, 'error')
    } finally { setCarregandoZeladores(false) }
  }

  async function criarContaZelador(e) {
    e.preventDefault()
    if (!formZelador.condominio_id) { mostrarToast('Selecione um condomínio.', 'error'); return }
    setSalvandoZelador(true)
    try {
      const payload = {
        nome: formZelador.nome.trim(), email: formZelador.email.trim().toLowerCase(),
        senha: formZelador.senha, perfil: 'Checklist', condominio_id: Number(formZelador.condominio_id)
      }
      const res = await fetch(`${API_URL}/usuarios`, {
        method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível criar a conta.'))
      setFormZelador({ nome: '', email: '', senha: '', condominio_id: '' })
      await carregarZeladores()
      mostrarToast('Conta do zelador criada e vinculada ao condomínio.', 'success')
    } catch (err) { mostrarToast(err.message, 'error') }
    finally { setSalvandoZelador(false) }
  }

  async function atualizarCondominioZelador(z) {
    const numero = Number(atribuicoesZeladores[z.id])
    if (!Number.isInteger(numero) || numero < 1) { mostrarToast('Selecione um condomínio.', 'error'); return }
    setSalvandoZelador(true)
    try {
      const res = await fetch(`${API_URL}/usuarios/${z.id}/condominio`, {
        method: 'PUT', headers: getAuthHeaders(), body: JSON.stringify({ condominio_id: numero })
      })
      if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível alterar o vínculo.'))
      await carregarZeladores()
      mostrarToast('Condomínio do zelador atualizado.', 'success')
    } catch (err) { mostrarToast(err.message, 'error') }
    finally { setSalvandoZelador(false) }
  }

  function excluirContaZelador(z) {
    confirmarAcao('Excluir conta de zelador', `Remover o acesso de ${z.nome}? O histórico de vistorias será preservado.`, async () => {
      try {
        const res = await fetch(`${API_URL}/usuarios/${z.id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Não foi possível remover a conta.'))
        await carregarZeladores()
        mostrarToast('Conta de zelador removida.', 'success')
      } catch (err) { mostrarToast(err.message, 'error') }
    }, true)
  }

  if (!usuarioLogado) {
    return (
      <div className="login-screen">
        <div className="toast-container">
          {toasts.map(t => (<div key={t.id} className={`toast ${t.tipo}`}><span className="toast-icon">{t.tipo === 'success' ? '✓' : '!'}</span><span>{t.mensagem}</span></div>))}
        </div>
        <div className="login-card">
          <img
            src="/logo.png"
            alt="Haize Logo"
            style={{ width: '72px', height: '72px', marginBottom: '16px', borderRadius: '16px', objectFit: 'contain' }}
            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
          />
          <div className="login-logo-box" style={{ display: 'none' }}>H</div>
          <span className="eyebrow" style={{ marginBottom: '4px' }}>HAIZE SÍNDICO PROFISSIONAL</span>
          <h2 style={{ fontSize: '24px', fontWeight: '800', color: '#0f172a', margin: '0 0 6px 0', letterSpacing: '-0.5px' }}>Controladoria</h2>
          <p style={{ fontSize: '13.5px', color: '#64748b', textAlign: 'center', margin: '0 0 28px 0' }}>Acesse com suas credenciais corporativas.</p>
          <form onSubmit={fazerLogin} style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="form-group">
              <label>E-mail Corporativo</label>
              <input type="email" placeholder="nome@haize.com.br" value={emailLogin} onChange={e => setEmailLogin(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Senha de Acesso</label>
              <input type="password" placeholder="••••••••" value={senhaLogin} onChange={e => setSenhaLogin(e.target.value)} required />
            </div>
            <button type="submit" className="button-primary" disabled={carregandoLogin} style={{ marginTop: '8px', padding: '13px', fontSize: '14.5px', width: '100%' }}>
              {carregandoLogin ? 'Autenticando...' : 'Entrar na Plataforma'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  const ehControladoria = usuarioLogado.perfil === 'Controladoria'
  const ehChecklist = usuarioLogado.perfil === 'Checklist'

  return (
    <div className="app">
      <div className="toast-container">
        {toasts.map(toast => (<div key={toast.id} className={`toast ${toast.tipo}`}><span className="toast-icon">{toast.tipo === 'success' ? '✓' : '!'}</span><span>{toast.mensagem}</span></div>))}
      </div>

      {dialog.isOpen && (
        <div className="dialog-overlay" style={{ zIndex: 11000 }} onClick={e => { if (e.target === e.currentTarget) fecharDialog() }}>
          <div className="dialog-box">
            <h3 style={{ margin: 0, fontSize: '17px', fontWeight: '800', color: '#0f172a' }}>{dialog.title}</h3>
            <p style={{ margin: 0, fontSize: '13.5px', color: '#475569' }}>{dialog.message}</p>
            {dialog.type === 'prompt' && (
              <input type="text" className="dialog-input" value={dialog.inputValue} onChange={e => setDialog(p => ({ ...p, inputValue: e.target.value }))} autoFocus onKeyDown={e => { if (e.key === 'Enter') handleConfirmDialog() }} />
            )}
            <div className="dialog-actions">
              <button type="button" className="button-secondary" onClick={fecharDialog}>{dialog.cancelText}</button>
              <button type="button" className={dialog.isDanger ? 'button-danger' : 'button-primary'} onClick={handleConfirmDialog}>{dialog.confirmText}</button>
            </div>
          </div>
        </div>
      )}

      {/* POP-UP AUTOMÁTICO: PLANO DE AÇÃO EM CASO DE NÃO CONFORMIDADE */}
      {alertaPlanoAcao && (
        <div className="modal-overlay" style={{ zIndex: 10000 }} onClick={e => { if (e.target === e.currentTarget) setAlertaPlanoAcao(null) }}>
          <div className="modal" style={{ maxWidth: '520px', borderTop: '6px solid #dc2626' }}>
            <div className="modal-header" style={{ borderBottom: '1px solid #fecaca', background: '#fef2f2' }}>
              <div>
                <span className="eyebrow" style={{ color: '#dc2626' }}>⚠️ INCONFORMIDADE REGISTRADA</span>
                <h3 style={{ color: '#991b1b', marginTop: '2px' }}>Diretriz e Plano de Ação</h3>
              </div>
              <button className="modal-close" onClick={() => setAlertaPlanoAcao(null)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '13px', color: '#334155', background: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <div><strong>Condomínio:</strong> {alertaPlanoAcao.condominio}</div>
                <div style={{ marginTop: '4px' }}><strong>Atividade:</strong> {alertaPlanoAcao.titulo}</div>
                <div style={{ marginTop: '6px', color: '#b91c1c' }}><strong>Problema relatado:</strong> "{alertaPlanoAcao.relato}"</div>
              </div>

              <div style={{ background: '#fffbeb', border: '2px solid #f59e0b', borderRadius: '12px', padding: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '18px' }}>📋</span>
                  <strong style={{ fontSize: '13px', color: '#92400e', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    Plano de Ação Estabelecido pela Controladoria:
                  </strong>
                </div>
                <p style={{ margin: 0, fontSize: '14px', color: '#78350f', fontWeight: '700', lineHeight: '1.5' }}>
                  {alertaPlanoAcao.plano_acao}
                </p>
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="button-primary"
                style={{ background: '#dc2626', borderColor: '#dc2626', width: '100%', padding: '12px' }}
                onClick={() => setAlertaPlanoAcao(null)}
              >
                ✓ Ciente do Plano de Ação
              </button>
            </div>
          </div>
        </div>
      )}

      {sidebarAberta && (
        <div className="sidebar-overlay" onClick={() => setSidebarAberta(false)} />
      )}

      <aside className={`sidebar ${sidebarAberta ? 'open' : ''}`}>
        <div className="brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img
              src="/logo.png"
              alt="Haize"
              style={{ width: '38px', height: '38px', borderRadius: '10px', backgroundColor: 'white', padding: '2px', objectFit: 'contain' }}
              onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
            />
            <div className="brand-logo-fallback" style={{ display: 'none' }}>H</div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: '16px', letterSpacing: '-0.3px', color: '#fff' }}>Controladoria</strong>
              <span style={{ fontSize: '11.5px', color: '#94a3b8' }}>Haize Síndico Profissional</span>
            </div>
          </div>
          <button onClick={() => setSidebarAberta(false)} className="fechar-menu-mobile">✕</button>
        </div>

        <nav className="sidebar-nav">
          {ehChecklist ? (
            <>
              <span className="sidebar-section-label">Operacional</span>
              <button className={pagina === 'checklist' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('checklist'); setAbaChecklist('vistorias'); setSidebarAberta(false); }}>
                <span className="nav-icon"><IconeHaize nome="checklist" /></span><span>Checklist Predial</span>
              </button>
            </>
          ) : (
            <>
              <span className="sidebar-section-label">Gestão & Controle</span>
              {ehControladoria && <>
                <button className={pagina === 'dashboard' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('dashboard'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="dashboard" /></span><span>Dashboard</span>
                </button>
                <button className={pagina === 'analises' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('analises'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="analyses" /></span><span>Análises & Rateio</span>
                </button>
              </>}
              <button className={pagina === 'solicitacoes' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('solicitacoes'); setSidebarAberta(false); }}>
                <span className="nav-icon"><IconeHaize nome="requests" /></span><span>Solicitações</span>
                {ehControladoria && quantidadePendentes > 0 && (<span className="nav-count">{quantidadePendentes}</span>)}
              </button>
              <button className={pagina === 'compras' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('compras'); setSidebarAberta(false); }}>
                <span className="nav-icon"><IconeHaize nome="shopping" /></span><span>Compras</span>
              </button>

              {ehControladoria && (
                <button className={pagina === 'checklist' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('checklist'); setAbaChecklist('vistorias'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="checklist" /></span><span>Checklist Predial</span>
                </button>
              )}

              <span className="sidebar-section-label">Cadastros Base</span>
              {ehControladoria && <>
                <button className={pagina === 'condominios' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('condominios'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="buildings" /></span><span>Condomínios</span>
                </button>
                <button className={pagina === 'categorias' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('categorias'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="categories" /></span><span>Categorias & Alçadas</span>
                </button>
                <button className={pagina === 'fornecedores' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('fornecedores'); setSidebarAberta(false); }}>
                  <span className="nav-icon"><IconeHaize nome="suppliers" /></span><span>Fornecedores</span>
                </button>
              </>}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="user-card-mini">
            <div className="user-avatar-mini">
              {String(usuarioLogado.nome || 'U').charAt(0).toUpperCase()}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {usuarioLogado.nome}
              </span>
              <span style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: '600' }}>
                {usuarioLogado.perfil}
              </span>
            </div>
          </div>
          <button onClick={fazerLogout} className="logout-btn">
            <IconeHaize nome="logout" tamanho={16} /> Encerrar Sessão
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="icon-button menu-mobile-btn" onClick={() => setSidebarAberta(!sidebarAberta)} aria-label="Abrir menu de navegação"><IconeHaize nome="menu" /></button>
            <div>
              <span className="breadcrumb">
                Controladoria Haize {' / '} {pagina === 'dashboard' ? 'Visão Executiva' : pagina === 'solicitacoes' ? 'Solicitações' : pagina === 'checklist' ? 'Checklist' : pagina}
              </span>
              <h1>
                {pagina === 'dashboard' ? 'Painel Geral' : pagina === 'solicitacoes' ? (ehControladoria ? 'Central de Aprovações' : 'Minhas Solicitações') : pagina === 'checklist' ? (ehControladoria && abaChecklist === 'zeladores' ? 'Checklist · Gestão de Zeladores' : 'Checklist Operacional') : pagina.charAt(0).toUpperCase() + pagina.slice(1)}
              </h1>
            </div>
          </div>

          <div className="topbar-actions">
            <div className={`status-pill ${backendOnline ? '' : 'offline'}`}>
              <span className="status-dot" />
              <span>{sincronizando ? 'Sincronizando...' : (backendOnline ? 'Sistema Online' : 'Modo Cache')}</span>
            </div>

            {!ehChecklist && (
              <div style={{ position: 'relative' }}>
                <button
                  className="icon-button"
                  onClick={() => setMostrarMenuNotificacoes(!mostrarMenuNotificacoes)}
                  title="Central de Alertas e Notificações"
                >
                  <IconeHaize nome="bell" tamanho={18} />
                  {quantidadePendentes > 0 && (
                    <span className="notification-badge">{quantidadePendentes}</span>
                  )}
                </button>

                {mostrarMenuNotificacoes && (
                  <div style={{ position: 'absolute', right: 0, top: '46px', width: '330px', background: 'white', border: '1px solid #e2e8f0', borderRadius: '14px', boxShadow: '0 20px 35px -5px rgba(15,23,42,0.18)', zIndex: 9999, overflow: 'hidden' }}>
                    <div style={{ padding: '14px 16px', background: '#0f172a', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '13.5px' }}>Central de Alertas</strong>
                      <span style={{ fontSize: '11px', background: '#334155', padding: '2px 8px', borderRadius: '999px', fontWeight: '700' }}>{quantidadePendentes} pendentes</span>
                    </div>
                    <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                      {solicitacoesPendentesLista.length === 0 ? (
                        <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: '#64748b' }}>Nenhuma solicitação pendente no momento. Tudo em dia!</div>
                      ) : (
                        solicitacoesPendentesLista.map(s => (
                          <div key={s.id} onClick={() => { abrirSolicitacao(s); setMostrarMenuNotificacoes(false) }} style={{ padding: '12px 16px', borderBottom: '1px solid #f1f5f9', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <strong style={{ fontSize: '12.5px', color: '#0f172a' }}>{s.numero} • {s.condominio}</strong>
                              <span style={{ fontSize: '11.5px', color: '#d97706', fontWeight: '700' }}>{formatarValor(s.valor)}</span>
                            </div>
                            <span style={{ fontSize: '12px', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.descricao}</span>
                          </div>
                        ))
                      )}
                    </div>
                    <div style={{ padding: '10px', background: '#f8fafc', textAlign: 'center', borderTop: '1px solid #e2e8f0' }}>
                      <span style={{ fontSize: '11px', color: notificacoesPushAtivas ? '#059669' : '#d97706', fontWeight: '700' }}>
                        {notificacoesPushAtivas ? '✓ Notificações Push ativas' : '⚠️ Notificações do navegador desativadas'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            <button className="icon-button" onClick={() => carregarDados(true)} title="Sincronizar agora" aria-label="Sincronizar dados"><IconeHaize nome="refresh" tamanho={18} /></button>
            {!ehChecklist && (
              <button className="new-request" onClick={() => setMostrarFormulario(true)}><IconeHaize nome="plus" tamanho={17} /> Nova Solicitação</button>
            )}
          </div>
        </header>


        {/* =========================================================================
            ABA DE CHECKLIST OPERACIONAL E VISTORIAS
           ========================================================================= */}
        {pagina === 'checklist' && (
          <div className="page page-checklist">
            {ehControladoria && (
              <nav className="checklist-abas" aria-label="Áreas do Checklist">
                <button type="button" className={`checklist-aba ${abaChecklist === 'vistorias' ? 'active' : ''}`}
                  onClick={() => setAbaChecklist('vistorias')} aria-current={abaChecklist === 'vistorias' ? 'page' : undefined}>
                  <IconeHaize nome="checklist" tamanho={17} /> Vistorias e atividades
                </button>
                <button type="button" className={`checklist-aba ${abaChecklist === 'zeladores' ? 'active' : ''}`}
                  onClick={() => setAbaChecklist('zeladores')} aria-current={abaChecklist === 'zeladores' ? 'page' : undefined}>
                  <IconeHaize nome="suppliers" tamanho={17} /> Gestão de Zeladores
                </button>
              </nav>
            )}
            {ehControladoria && abaChecklist === 'zeladores' ? (
              <div className="checklist-gestao-zeladores">
            <section className="checklist-intro">
              <div>
                <span className="eyebrow">PERMISSÕES POR CONDOMÍNIO</span>
                <h2>Gestão de zeladores</h2>
                <p>Crie uma conta para cada zelador e limite o acesso ao checklist do condomínio correspondente. Cada condomínio possui um número interno único.</p>
              </div>
              <button type="button" className="button-secondary" onClick={carregarZeladores} disabled={carregandoZeladores}>
                <IconeHaize nome="refresh" tamanho={16} /> {carregandoZeladores ? 'Atualizando...' : 'Atualizar lista'}
              </button>
            </section>
            <div className="zeladores-layout">
              <section className="panel zeladores-cadastro">
                <div className="panel-header"><h3>Nova conta de zelador</h3></div>
                <form onSubmit={criarContaZelador} className="zeladores-form">
                  <label className="form-group"><span>Nome completo</span>
                    <input required maxLength={120} value={formZelador.nome} onChange={e => setFormZelador(p => ({ ...p, nome: e.target.value }))} placeholder="Nome do zelador" />
                  </label>
                  <label className="form-group"><span>E-mail de acesso</span>
                    <input required type="email" autoComplete="off" value={formZelador.email} onChange={e => setFormZelador(p => ({ ...p, email: e.target.value }))} placeholder="zelador@exemplo.com" />
                  </label>
                  <label className="form-group"><span>Senha inicial (mínimo 10 caracteres)</span>
                    <input required type="password" minLength={10} autoComplete="new-password" value={formZelador.senha} onChange={e => setFormZelador(p => ({ ...p, senha: e.target.value }))} placeholder="Senha provisória segura" />
                  </label>
                  <label className="form-group"><span>Condomínio autorizado</span>
                    <select required value={formZelador.condominio_id} onChange={e => setFormZelador(p => ({ ...p, condominio_id: e.target.value }))}>
                      <option value="">Selecione um condomínio</option>
                      {condominios.map(c => {
                        const ocupado = zeladores.some(z => z.condominio_id === c.id)
                        return <option key={c.id} value={c.id} disabled={ocupado}>Nº {c.id} — {c.nome}{ocupado ? ' (já vinculado)' : ''}</option>
                      })}
                    </select>
                  </label>
                  <p className="zeladores-ajuda">O número corresponde ao ID permanente do condomínio no cadastro. O zelador verá somente as atividades, fotografias e relatórios desse condomínio.</p>
                  <button className="button-primary" type="submit" disabled={salvandoZelador || !condominios.length}>
                    <IconeHaize nome="plus" tamanho={16} /> {salvandoZelador ? 'Salvando...' : 'Criar conta e vincular'}
                  </button>
                </form>
              </section>
              <section className="panel zeladores-lista">
                <div className="panel-header"><h3>Zeladores cadastrados</h3><span className="badge neutral">{zeladores.length} contas</span></div>
                {zeladores.length === 0 ? <p className="zeladores-vazio">Nenhum zelador cadastrado com o perfil Checklist.</p> : (
                  <div className="zeladores-cards">
                    {zeladores.map(z => {
                      const cond = condominios.find(c => c.id === z.condominio_id)
                      return (
                        <article className="zelador-card" key={z.id}>
                          <div className="zelador-card-top"><span className="zelador-avatar">{z.nome?.charAt(0)?.toUpperCase()}</span><div><strong>{z.nome}</strong><small>{z.email}</small></div></div>
                          <div className="zelador-vinculo">Acesso atual: <strong>{cond ? `Nº ${cond.id} — ${cond.nome}` : 'Sem condomínio vinculado'}</strong></div>
                          <label className="form-group"><span>Alterar condomínio autorizado</span>
                            <select value={atribuicoesZeladores[z.id] ?? ''} onChange={e => setAtribuicoesZeladores(p => ({ ...p, [z.id]: e.target.value }))}>
                              <option value="">Selecione um condomínio</option>
                              {condominios.map(c => {
                                const ocupado = zeladores.some(outro => outro.id !== z.id && outro.condominio_id === c.id)
                                return <option key={c.id} value={c.id} disabled={ocupado}>Nº {c.id} — {c.nome}{ocupado ? ' (ocupado)' : ''}</option>
                              })}
                            </select>
                          </label>
                          <div className="zelador-card-actions">
                            <button className="button-secondary" disabled={salvandoZelador || !atribuicoesZeladores[z.id] || Number(atribuicoesZeladores[z.id]) === z.condominio_id} onClick={() => atualizarCondominioZelador(z)}>Salvar vínculo</button>
                            <button className="button-danger" onClick={() => excluirContaZelador(z)}>Excluir conta</button>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            </div>
              </div>
            ) : (
              <>
            <section className="checklist-intro">
              <div>
                <span className="eyebrow">OPERAÇÃO E MANUTENÇÃO PREVENTIVA</span>
                <h2>Checklist predial</h2>
                <p>Acompanhe as rotinas, registre vistorias e identifique rapidamente as atividades que precisam de atenção.</p>
              </div>
              <div className="checklist-intro-actions">
                {ehControladoria && (
                  <button type="button" className="button-primary" onClick={abrirModalCriarChecklist}>
                    <IconeHaize nome="plus" tamanho={16} /> Nova atividade
                  </button>
                )}
                {filtroCondominioChecklist !== 'todos' && (
                  <button type="button" className="button-secondary" onClick={gerarRelatorioDivergenciasPDF} disabled={enviandoRelatorio}>
                    <IconeHaize nome="file" tamanho={16} /> {enviandoRelatorio ? 'Enviando relatório...' : 'Gerar e enviar PDF'}
                  </button>
                )}
              </div>
            </section>

            {ehChecklist && (
              <div className={`checklist-acesso-condominio ${!condominios.length ? 'sem-vinculo' : ''}`}>
                <IconeHaize nome="buildings" tamanho={20} />
                <div>
                  <strong>{condominios[0] ? `Condomínio Nº ${condominios[0].id} — ${condominios[0].nome}` : 'Condomínio não vinculado'}</strong>
                  <span>{condominios[0] ? 'Seu acesso está limitado às vistorias deste condomínio.' : 'Solicite à Controladoria que vincule sua conta a um condomínio.'}</span>
                </div>
              </div>
            )}
            <section className="checklist-indicadores" aria-label="Resumo das vistorias">
              {[
                { chave: 'todos', titulo: 'Todas', descricao: 'Atividades cadastradas', icone: 'checklist' },
                { chave: 'em_dia', titulo: 'Em dia', descricao: 'Dentro da frequência', icone: 'approved' },
                { chave: 'atrasados', titulo: 'Atrasadas', descricao: 'Prazo ultrapassado', icone: 'clock' },
                { chave: 'pendentes', titulo: 'Nunca vistoriadas', descricao: 'Aguardam 1º registro', icone: 'file' },
                { chave: 'divergencias', titulo: 'Não conformes', descricao: 'Última vistoria com problema', icone: 'bell' }
              ].map(indicador => (
                <button
                  type="button"
                  key={indicador.chave}
                  className={`checklist-indicador checklist-indicador--${indicador.chave} ${filtroSLAChecklist === indicador.chave ? 'is-active' : ''}`}
                  onClick={() => setFiltroSLAChecklist(indicador.chave)}
                  aria-pressed={filtroSLAChecklist === indicador.chave}
                >
                  <span className="checklist-indicador-top"><span>{indicador.titulo}</span><IconeHaize nome={indicador.icone} tamanho={18} /></span>
                  <strong>{indicadoresChecklist[indicador.chave]}</strong>
                  <small>{indicador.descricao}</small>
                </button>
              ))}
            </section>

            <section className="panel checklist-painel" aria-label="Atividades do checklist">
              <div className="checklist-painel-cabecalho">
                <div>
                  <span className="eyebrow">ROTINAS CADASTRADAS</span>
                  <h3>Atividades e vistorias</h3>
                  <p>Os prazos seguem a frequência cadastrada; a conformidade mostra o resultado da última vistoria.</p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, textAlign: 'right' }}>
                  <span className="checklist-resultados">{checklistsFiltrados.length} de {checklistsNoEscopo.length} atividades</span>
                  <small role="status" style={{ color: erroChecklist ? '#b91c1c' : '#64748b' }}>
                    {carregandoChecklist ? 'Sincronizando vistorias...' : erroChecklist ? `Erro ao atualizar: ${erroChecklist}` : ultimaAtualizacaoChecklist ? `Atualizado às ${new Date(ultimaAtualizacaoChecklist).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'Aguardando sincronização'}
                  </small>
                </div>
              </div>
              <div className="checklist-controles">
                <label className="checklist-campo checklist-campo-busca">
                  <span>Buscar atividade</span>
                  <input type="search" value={buscaChecklist} onChange={e => setBuscaChecklist(e.target.value)} placeholder="Nome, condomínio ou instruções" aria-label="Buscar atividade do checklist" />
                </label>
                {ehControladoria && (
                  <label className="checklist-campo">
                    <span>Condomínio</span>
                    <select value={filtroCondominioChecklist} onChange={e => setFiltroCondominioChecklist(e.target.value)}>
                      <option value="todos">Todos os condomínios</option>
                      {condominios.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                    </select>
                  </label>
                )}
                <label className="checklist-campo">
                  <span>Frequência</span>
                  <select value={filtroFrequenciaChecklist} onChange={e => setFiltroFrequenciaChecklist(e.target.value)}>
                    <option value="todas">Todas as frequências</option>
                    <option value="Diária">Diária</option>
                    <option value="Semanal">Semanal</option>
                    <option value="Quinzenal">Quinzenal</option>
                    <option value="Mensal">Mensal</option>
                  </select>
                </label>
                <label className="checklist-campo">
                  <span>Ordenar por</span>
                  <select value={ordenacaoChecklist} onChange={e => setOrdenacaoChecklist(e.target.value)}>
                    <option value="prioridade">Prioridade</option>
                    <option value="titulo">Nome da atividade</option>
                    <option value="recentes">Vistorias recentes</option>
                  </select>
                </label>
              </div>
              {(buscaChecklist || filtroCondominioChecklist !== 'todos' || filtroFrequenciaChecklist !== 'todas' || filtroSLAChecklist !== 'todos') && (
                <div className="checklist-filtro-ativo">
                  <span>Os resultados consideram os filtros selecionados.</span>
                  <button type="button" onClick={() => { setBuscaChecklist(''); setFiltroCondominioChecklist('todos'); setFiltroFrequenciaChecklist('todas'); setFiltroSLAChecklist('todos') }}>Limpar filtros</button>
                </div>
              )}
              {carregandoChecklist && !ultimaAtualizacaoChecklist && checklists.length === 0 ? (
                <div className="checklist-vazio" role="status">
                  <IconeHaize nome="clock" tamanho={30} />
                  <strong>Buscando atividades no servidor...</strong>
                  <p>O checklist será exibido automaticamente assim que os dados chegarem.</p>
                </div>
              ) : erroChecklist && checklists.length === 0 ? (
                <div className="checklist-vazio" role="alert">
                  <IconeHaize nome="clock" tamanho={30} />
                  <strong>Não foi possível sincronizar as atividades.</strong>
                  <p>{erroChecklist}</p>
                  <button type="button" className="button-secondary" onClick={() => carregarChecklists({ forcar: true, notificarErro: true })}>Tentar novamente</button>
                </div>
              ) : checklistsFiltrados.length === 0 ? (
                <div className="checklist-vazio">
                  <IconeHaize nome="checklist" tamanho={30} />
                  <strong>Nenhuma atividade encontrada</strong>
                  <p>Experimente outros filtros ou faça uma busca diferente.</p>
                  <button type="button" className="button-secondary" onClick={() => { setBuscaChecklist(''); setFiltroCondominioChecklist('todos'); setFiltroFrequenciaChecklist('todas'); setFiltroSLAChecklist('todos') }}>Exibir todas as atividades</button>
                </div>
              ) : (
                <div className="checklist-grade">
                  {checklistsFiltrados.map(item => {
                    const ultima = item.ultima_execucao
                    const naoConforme = ultima?.status_conformidade === 'Não Conforme'
                    const sla = calcularStatusSLA(item.frequencia, ultima)
                    return (
                      <article className={`checklist-atividade ${naoConforme ? 'tem-divergencia' : ''}`} key={item.id}>
                        <div className="checklist-atividade-topo">
                          <span className="checklist-condominio" title={item.condominio}><IconeHaize nome="buildings" tamanho={14} /> {item.condominio}</span>
                          <span className="checklist-frequencia">{item.frequencia}</span>
                        </div>
                        <div className="checklist-atividade-corpo">
                          <h4>{item.titulo}</h4>
                          {item.descricao_orientacao && <p className="checklist-orientacao">{item.descricao_orientacao}</p>}
                          <div className="checklist-badges">
                            <span className={`checklist-situacao ${sla.status}`}>{sla.label}</span>
                            {naoConforme && <span className="checklist-situacao divergencia">Não conforme</span>}
                          </div>
                          <div className="checklist-ultima">
                            <span className="checklist-ultima-label">Última vistoria</span>
                            {ultima ? (
                              <>
                                <strong>{formatarDataHora(ultima.data_execucao)}</strong>
                                <span>Responsável: {ultima.responsavel}</span>
                                {ultima.observacao && <p className="checklist-relato">{ultima.observacao}</p>}
                                {ultima.tem_foto && ultima.id && (
                                  <button type="button" className="checklist-link-evidencia" onClick={() => abrirArquivoProtegido(`/checklists/execucoes/${ultima.id}/foto`, `evidencia-vistoria-${ultima.id}`).catch(erro => mostrarToast(erro.message, 'error'))}>
                                    Ver evidência anexada
                                  </button>
                                )}
                              </>
                            ) : <span>Nenhuma vistoria registrada até agora.</span>}
                          </div>
                          {naoConforme && item.plano_acao_padrao && (
                            <div className="checklist-plano"><strong>Plano de ação</strong><p>{item.plano_acao_padrao}</p></div>
                          )}
                        </div>
                        <div className="checklist-atividade-acoes">
                          <button type="button" className="checklist-registrar" onClick={() => abrirModalExecutarChecklist(item)}>
                            <IconeHaize nome="checklist" tamanho={16} /> Registrar vistoria
                          </button>
                          <div className="checklist-atividade-links">
                            <button type="button" onClick={() => setItemChecklistHistorico(item)}>Histórico ({item.historico_execucoes?.length || 0})</button>
                            {ehControladoria && <button type="button" onClick={() => abrirModalEditarChecklist(item)}>Editar</button>}
                            {ehControladoria && <button type="button" className="excluir" onClick={() => excluirItemChecklist(item)}>Excluir</button>}
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
            </section>
              </>
            )}
          </div>
        )}

        {pagina === 'dashboard' && !ehChecklist && (
          <div className="page page-executiva">
            <section className="executive-hero" aria-label="Resumo da Controladoria">
              <div className="executive-hero-main">
                <span className="hero-eyebrow"><span className="hero-eyebrow-dot" /> VISÃO CONSOLIDADA</span>
                <h2>Gestão clara. Decisões melhores.</h2>
                <p>Acompanhe as solicitações, os valores e o andamento dos processos em um só lugar.</p>
                <div className="executive-hero-meta">
                  <span><IconeHaize nome="file" tamanho={15} /> {solicitacoes.length} solicitações</span>
                  <span><IconeHaize nome="buildings" tamanho={15} /> {condominios.length} condomínios cadastrados</span>
                </div>
              </div>
              <div className="executive-hero-actions">
                <button className="hero-button-primary" onClick={() => { setFiltroStatus('Aprovação pendente'); setPagina('solicitacoes') }}>
                  Analisar pendências <IconeHaize nome="arrow" tamanho={16} />
                </button>
                <button className="hero-button-secondary" onClick={() => setPagina('analises')}>
                  Ver análises <IconeHaize nome="analyses" tamanho={16} />
                </button>
              </div>
            </section>

            <section className="executive-section" aria-label="Indicadores financeiros">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">RESULTADOS E CONTROLE</span>
                  <h2>Resumo financeiro</h2>
                </div>
                <span className="period-indicator">Todos os registros</span>
              </div>
              <div className="kpi-grid executive-kpi-grid">
                <article className="kpi-card kpi-solicitado">
                  <div className="kpi-top"><span>Total solicitado</span><span className="kpi-icon"><IconeHaize nome="wallet" tamanho={20} /></span></div>
                  <strong>{formatarValor(valorTotalSolicitado)}</strong>
                  <span className="kpi-footnote">{solicitacoes.length} pedidos registrados</span>
                </article>
                <article className="kpi-card kpi-aprovado">
                  <div className="kpi-top"><span>Total aprovado</span><span className="kpi-icon"><IconeHaize nome="approved" tamanho={20} /></span></div>
                  <strong>{formatarValor(valorTotalAprovado)}</strong>
                  <span className="kpi-footnote">Solicitações com aprovação</span>
                </article>
                <article className="kpi-card kpi-realizado">
                  <div className="kpi-top"><span>Total realizado</span><span className="kpi-icon"><IconeHaize nome="trending" tamanho={20} /></span></div>
                  <strong>{formatarValor(valorTotalRealizado)}</strong>
                  <span className="kpi-footnote">Solicitações finalizadas</span>
                </article>
                <article className="kpi-card highlight kpi-economia">
                  <div className="kpi-top"><span>Economia apurada</span><span className="kpi-icon success"><IconeHaize nome="savings" tamanho={20} /></span></div>
                  <strong>{formatarValor(economiaTotal)}</strong>
                  <span className="kpi-footnote">Diferença entre solicitado e realizado nas finalizadas</span>
                </article>
              </div>
            </section>

            <section className="executive-bottom-grid" aria-label="Solicitações e andamento">
              <div className="panel executive-table-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">FOCO DA CONTROLADORIA</span>
                    <h3>Solicitações de maior impacto</h3>
                    <p className="section-helper">Pedidos ordenados pelo maior valor solicitado.</p>
                  </div>
                  <button className="button-secondary" onClick={() => { setFiltroStatus('todos'); setPagina('solicitacoes') }}>
                    Ver todas <IconeHaize nome="arrow" tamanho={15} />
                  </button>
                </div>
                <div className="table executive-table">
                  <div className="table-header"><span>Código</span><span>Condomínio</span><span>Descrição</span><span>Valor</span><span>Status</span></div>
                  {maioresSolicitacoes.length === 0 ? (
                    <div className="dashboard-empty-state">
                      <IconeHaize nome="requests" tamanho={24} />
                      <strong>Nenhuma solicitação registrada</strong>
                      <span>Os pedidos aparecerão aqui assim que forem cadastrados.</span>
                    </div>
                  ) : maioresSolicitacoes.map(sol => (
                    <div className="table-row clickable" role="button" tabIndex={0} key={sol.id} onClick={() => abrirSolicitacao(sol)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abrirSolicitacao(sol) } }}>
                      <span className="id">{sol.numero}</span>
                      <strong className="table-condominio">{sol.condominio}</strong>
                      <span className="table-descricao" title={sol.descricao}>{sol.descricao}</span>
                      <div className="table-valor"><strong>{formatarValor(sol.valor)}</strong>
                        {aprovado(sol) > 0 && aprovado(sol) < solicitado(sol) && <small>Aprovado: {formatarValor(aprovado(sol))}</small>}
                      </div>
                      {renderBadge(sol)}
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel executive-status-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">ACOMPANHAMENTO</span>
                    <h3>Status das solicitações</h3>
                    <p className="section-helper">Distribuição de todos os pedidos registrados.</p>
                  </div>
                </div>
                <div className="status-overview">
                  <div className="status-overview-total">
                    <div><span>Total de solicitações</span><strong>{solicitacoes.length}</strong></div>
                    <span className="status-total-icon"><IconeHaize nome="requests" tamanho={24} /></span>
                  </div>
                  <div className="status-progress-list">
                    {indicadoresStatusDashboard.filter(item => item.status !== 'Em análise' || item.total > 0).map(item => (
                      <button type="button" className="status-progress-item" key={item.status} title={`Ver solicitações: ${item.label}`} onClick={() => { setFiltroStatus(item.status); setPagina('solicitacoes') }}>
                        <span className="status-progress-top"><span className="status-progress-label"><i className={`status-progress-dot ${item.tom}`} />{item.label}</span><strong>{item.total}</strong></span>
                        <span className="status-progress-track"><span className={`status-progress-fill ${item.tom}`} style={{ width: `${solicitacoes.length ? (item.total / solicitacoes.length) * 100 : 0}%` }} /></span>
                      </button>
                    ))}
                  </div>
                  <button className="status-all-link" onClick={() => { setFiltroStatus('todos'); setPagina('solicitacoes') }}>Abrir central de solicitações <IconeHaize nome="arrow" tamanho={16} /></button>
                </div>
              </div>
            </section>
          </div>
        )}

        {pagina === 'analises' && !ehChecklist && (
          <div className="page page-analises">
            <section className="analise-hero">
              <div className="analise-hero-texto">
                <span className="analise-hero-eyebrow">INTELIGÊNCIA FINANCEIRA • HAIZE</span>
                <h2>Visão analítica da controladoria</h2>
                <p>Acompanhe solicitações, aprovações e despesas por condomínio em uma única visão.</p>
                <span className="analise-hero-contagem">{resumoFinanceiro.pedidos} solicitações • {resumoFinanceiro.condominios} condomínios no filtro</span>
              </div>
              <span className="analise-hero-simbolo" aria-hidden="true"><IconeHaize nome="analyses" tamanho={58}/></span>
            </section>

            <section className="panel analise-filtros-painel" aria-label="Filtros dos relatórios financeiros">
              <div className="analise-painel-titulo">
                <div><span className="eyebrow">RECORTE DOS DADOS</span><h3>Filtros e período</h3></div>
                <div className="analise-exportar" role="group" aria-label="Exportar dados filtrados">
                  <button type="button" className="button-secondary" onClick={exportarRelatorioExcel} disabled={resumoFinanceiro.pedidos === 0}><IconeHaize nome="file" tamanho={16}/> Exportar Excel</button>
                  <button type="button" className="button-secondary" onClick={exportarRelatorioPDF} disabled={resumoFinanceiro.pedidos === 0}><IconeHaize nome="file" tamanho={16}/> Imprimir PDF</button>
                </div>
              </div>
              <div className="analise-filtros-grade">
                <label className="analise-campo analise-campo-condominio"><span>Condomínio</span>
                  <select value={filtroCondominioAnalise} onChange={e => setFiltroCondominioAnalise(e.target.value)}>
                    <option value="todos">Todos os condomínios</option>
                    {condominios.map(c => <option key={c.id} value={c.nome}>{c.nome}</option>)}
                  </select>
                </label>
                <label className="analise-campo"><span>Data inicial</span>
                  <input type="date" value={filtroDataInicio} max={filtroDataFim || undefined} onChange={e => setFiltroDataInicio(e.target.value)} />
                </label>
                <label className="analise-campo"><span>Data final</span>
                  <input type="date" value={filtroDataFim} min={filtroDataInicio || undefined} onChange={e => setFiltroDataFim(e.target.value)} />
                </label>
              </div>
              <div className="analise-periodos" role="group" aria-label="Selecionar período rápido">
                <span>Período rápido:</span>
                <button type="button" className={!filtroDataInicio && !filtroDataFim ? 'active' : ''} aria-pressed={!filtroDataInicio && !filtroDataFim} onClick={() => aplicarPeriodoAnalise('todos')}>Todo o período</button>
                <button type="button" onClick={() => aplicarPeriodoAnalise('30dias')}>Últimos 30 dias</button>
                <button type="button" onClick={() => aplicarPeriodoAnalise('mes')}>Este mês</button>
                <button type="button" onClick={() => aplicarPeriodoAnalise('ano')}>Este ano</button>
                {(filtroDataInicio || filtroDataFim || filtroCondominioAnalise !== 'todos') && <button type="button" className="analise-limpar" onClick={() => { setFiltroCondominioAnalise('todos'); aplicarPeriodoAnalise('todos') }}>Limpar tudo</button>}
              </div>
            </section>

            <section className="analise-kpis" aria-label="Indicadores financeiros filtrados">
              <article className="analise-kpi"><span className="analise-kpi-simbolo solicitado"><IconeHaize nome="requests" tamanho={19}/></span><div><span>Valor solicitado</span><strong>{formatarValor(resumoFinanceiro.totalSolicitado)}</strong><small>Pedidos do período</small></div></article>
              <article className="analise-kpi"><span className="analise-kpi-simbolo aprovado"><IconeHaize nome="approved" tamanho={19}/></span><div><span>Valor aprovado</span><strong>{formatarValor(resumoFinanceiro.totalAprovado)}</strong><small>Solicitações aprovadas</small></div></article>
              <article className="analise-kpi"><span className="analise-kpi-simbolo realizado"><IconeHaize nome="wallet" tamanho={19}/></span><div><span>Valor realizado</span><strong>{formatarValor(resumoFinanceiro.totalRealizado)}</strong><small>Despesas finalizadas</small></div></article>
              <article className={`analise-kpi ${resumoFinanceiro.saldo < 0 ? 'analise-kpi-negativo' : ''}`}><span className="analise-kpi-simbolo saldo"><IconeHaize nome="savings" tamanho={19}/></span><div><span>Saldo entre aprovado e realizado</span><strong>{formatarValor(resumoFinanceiro.saldo)}</strong><small>{resumoFinanceiro.saldo < 0 ? 'Realizado supera aprovado' : 'Diferença ainda não realizada'}</small></div></article>
            </section>

            {resumoFinanceiro.pedidos === 0 ? (
              <section className="panel analise-vazio"><IconeHaize nome="analyses" tamanho={33}/><strong>Sem dados para os filtros selecionados</strong><p>Experimente outro condomínio ou amplie o período da pesquisa.</p><button type="button" className="button-secondary" onClick={() => { setFiltroCondominioAnalise('todos'); aplicarPeriodoAnalise('todos') }}>Limpar filtros</button></section>
            ) : (
              <>
                <div className="analise-duas-colunas">
                  <section className="panel analise-grafico-painel">
                    <div className="analise-secao-cabecalho"><div><span className="eyebrow">VISÃO COMPARATIVA</span><h3>Solicitado × Aprovado × Realizado</h3><p>Até 10 condomínios com maior valor solicitado no período.</p></div></div>
                    <div className="analise-chart" style={{ height: Math.max(275, Math.min(510, dadosGraficoCondominios.length * 48 + 95)) }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart layout="vertical" data={dadosGraficoCondominios} margin={{ top: 8, right: 12, left: 3, bottom: 6 }} barCategoryGap="25%">
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e3eaf4" />
                          <XAxis type="number" tickFormatter={v => `R$ ${v >= 1000000 ? `${(v / 1000000).toFixed(1)}mi` : v >= 1000 ? `${Math.round(v / 1000)}mil` : v}`} fontSize={10} tickLine={false} axisLine={false} stroke="#8190a2" />
                          <YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 10, fill: '#50647e' }} tickFormatter={nome => String(nome).length > 19 ? `${String(nome).slice(0, 18)}…` : nome} tickLine={false} axisLine={false} />
                          <RechartsTooltip formatter={valor => formatarValor(valor)} cursor={{ fill: '#f4f7fc' }} />
                          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '9px' }} />
                          <Bar name="Solicitado" dataKey="Solicitado" fill="#9aacc7" radius={[0, 4, 4, 0]} isAnimationActive={false} />
                          <Bar name="Aprovado" dataKey="Aprovado" fill="#356ae6" radius={[0, 4, 4, 0]} isAnimationActive={false} />
                          <Bar name="Realizado" dataKey="Realizado" fill="#059669" radius={[0, 4, 4, 0]} isAnimationActive={false} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  <section className="panel analise-categorias-painel">
                    <div className="analise-secao-cabecalho"><div><span className="eyebrow">DESPESAS FINALIZADAS</span><h3>Principais categorias</h3><p>Distribuição de despesas nas solicitações finalizadas.</p></div></div>
                    {categoriasFinanceiras.length === 0 ? <div className="analise-categorias-vazio">Ainda não há despesas finalizadas neste período.</div> : (
                      <div className="analise-categorias-lista">
                        {categoriasFinanceiras.map(item => (
                          <div key={item.nome} className="analise-categoria">
                            <div className="analise-categoria-topo"><span title={item.nome}>{item.nome}</span><strong>{formatarValor(item.valor)}</strong></div>
                            <div className="analise-categoria-trilha"><span style={{ width: `${categoriasFinanceiras[0].valor > 0 ? Math.min(100, (item.valor / categoriasFinanceiras[0].valor) * 100) : 0}%` }} /></div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </div>

                <section className="panel analise-centros-painel">
                  <div className="analise-secao-cabecalho"><div><span className="eyebrow">POR CENTRO DE CUSTO</span><h3>Execução orçamentária por condomínio</h3><p>O saldo representa aprovado menos realizado, não necessariamente economia definitiva.</p></div><span className="analise-contagem">{listaOrcamentoCondominio.length} condomínio(s)</span></div>
                  <div className="analise-tabela-rolagem">
                    <table className="analise-tabela">
                      <thead><tr><th>Condomínio</th><th>Aprovado</th><th>Realizado</th><th>Saldo</th><th>Situação</th></tr></thead>
                      <tbody>
                        {listaOrcamentoCondominio.map(item => {
                          const semOrcamento = item.aprovado === 0
                          const estourado = item.saldo < 0 && !semOrcamento
                          const situacao = semOrcamento ? 'Sem aprovação' : estourado ? 'Acima do aprovado' : item.saldo === 0 ? 'Sem saldo' : 'Saldo disponível'
                          return <tr key={item.nome}>
                            <td><strong>{item.nome}</strong><small>{item.qtdSolicitacoes} pedido(s)</small></td>
                            <td>{formatarValor(item.aprovado)}</td>
                            <td>{formatarValor(item.realizado)}</td>
                            <td className={item.saldo < 0 ? 'analise-saldo-negativo' : 'analise-saldo-positivo'}>{formatarValor(item.saldo)}</td>
                            <td><span className={`analise-situacao ${semOrcamento ? 'sem-aprovacao' : estourado ? 'estourado' : 'disponivel'}`}>{situacao}</span></td>
                          </tr>
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {filtroCondominioAnalise !== 'todos' && (
              <section className="panel analise-rateio-painel">
                <div className="analise-secao-cabecalho"><div><span className="eyebrow">DISTRIBUIÇÃO POR FRAÇÃO IDEAL</span><h3>Rateio — {filtroCondominioAnalise}</h3><p>Rateio de solicitações finalizadas; consulte as unidades cadastradas para revisar as frações.</p></div></div>
                <div className="analise-aviso" role="note"><IconeHaize nome="clock" tamanho={18}/><span>O rateio utiliza <strong>{filtroDataInicio ? `o mês ${filtroDataInicio.slice(0, 7).split('-').reverse().join('/')}` : 'todo o histórico'}</strong> conforme a API atual. Ele não aplica o intervalo exato de datas selecionado acima.</span></div>
                {carregandoRateio ? <div className="analise-rateio-estado">Calculando rateio...</div> : !rateioDados || (rateioDados.rateio_unidades || []).length === 0 ? (
                  <div className="analise-rateio-estado">Nenhuma unidade ou fração cadastrada para este condomínio. Configure as unidades no cadastro de condomínios.</div>
                ) : (
                  <>
                    <div className="analise-rateio-total"><span>Total considerado pelo rateio</span><strong>{formatarValor(rateioDados.total_gasto_condominio)}</strong><small>{rateioDados.quantidade_solicitacoes} solicitação(ões) finalizada(s)</small></div>
                    <div className="analise-tabela-rolagem">
                      <table className="analise-tabela analise-rateio-tabela">
                        <thead><tr><th>Unidade</th><th>Fração ideal</th><th>Valor rateado</th></tr></thead>
                        <tbody>{rateioDados.rateio_unidades.map(u => <tr key={u.unidade_id}><td><strong>{u.unidade}</strong></td><td>{formatarNumero(u.fracao_ideal)}%</td><td className="analise-saldo-positivo">{formatarValor(u.valor_devido)}</td></tr>)}</tbody>
                      </table>
                    </div>
                  </>
                )}
              </section>
            )}
            <p className="analise-nota">Observação: indicadores seguem os valores informados nas solicitações; em registros antigos finalizados sem valor realizado, o critério legado pode considerar o valor aprovado ou solicitado. Revise os lançamentos antes de utilizar os relatórios em decisões contábeis.</p>
          </div>
        )}

        {pagina === 'solicitacoes' && !ehChecklist && (
          <div className="page page-central-solicitacoes">
            <section className="central-heading" aria-label="Central de Solicitações">
              <div>
                <span className="eyebrow">CONTROLADORIA / FLUXO DE COMPRAS</span>
                <h2>{ehControladoria ? 'Central de Solicitações' : 'Minhas Solicitações'}</h2>
                <p>Consulte pedidos, acompanhe aprovações e encontre rapidamente as informações de cada compra.</p>
              </div>
              <span className="central-heading-count">{resumoSolicitacoes.total} {resumoSolicitacoes.total === 1 ? 'registro' : 'registros'}</span>
            </section>

            <section className="central-resumo" aria-label="Resumo das solicitações">
              <article className="central-resumo-card"><div className="central-resumo-icon total"><IconeHaize nome="requests" /></div><div><span>Total de solicitações</span><strong>{resumoSolicitacoes.total}</strong></div></article>
              <article className="central-resumo-card"><div className="central-resumo-icon pendente"><IconeHaize nome="clock" /></div><div><span>Aguardando ação</span><strong>{resumoSolicitacoes.pendentes}</strong></div></article>
              <article className="central-resumo-card"><div className="central-resumo-icon execucao"><IconeHaize nome="shopping" /></div><div><span>Em execução</span><strong>{resumoSolicitacoes.emExecucao}</strong></div></article>
              <article className="central-resumo-card"><div className="central-resumo-icon finalizada"><IconeHaize nome="approved" /></div><div><span>Finalizadas</span><strong>{resumoSolicitacoes.finalizadas}</strong></div></article>
            </section>

            <section className="panel central-panel" aria-label="Consultar solicitações">
              <div className="central-toolbar-heading">
                <div><span className="eyebrow">CONSULTA E ACOMPANHAMENTO</span><h3>Lista de solicitações</h3><p>Filtre por condomínio, categoria, status ou data.</p></div>
                {filtrosSolicitacoesAtivos && <button className="central-limpar" type="button" onClick={limparFiltrosSolicitacoes}>Limpar filtros</button>}
              </div>

              <div className="central-filtros">
                <label className="central-campo central-busca">
                  <span>Pesquisar</span>
                  <input type="search" value={filtroSolicitacao} onChange={e => setFiltroSolicitacao(e.target.value)} placeholder="Código, descrição, fornecedor..." aria-label="Pesquisar solicitações" />
                </label>
                <label className="central-campo">
                  <span>Condomínio</span>
                  <select value={filtroCondominioSolicitacao} onChange={e => setFiltroCondominioSolicitacao(e.target.value)}>
                    <option value="todos">Todos os condomínios</option>
                    {opcoesCondominiosSolicitacoes.map(nome => <option key={nome} value={nome}>{nome}</option>)}
                  </select>
                </label>
                <label className="central-campo">
                  <span>Categoria</span>
                  <select value={filtroCategoriaSolicitacao} onChange={e => setFiltroCategoriaSolicitacao(e.target.value)}>
                    <option value="todos">Todas as categorias</option>
                    {opcoesCategoriasSolicitacoes.map(nome => <option key={nome} value={nome}>{nome}</option>)}
                  </select>
                </label>
                <label className="central-campo central-ordenacao">
                  <span>Ordenar por</span>
                  <select value={ordenacaoSolicitacao} onChange={e => setOrdenacaoSolicitacao(e.target.value)}>
                    <option value="recentes">Mais recentes</option>
                    <option value="antigas">Mais antigas</option>
                    <option value="maior_valor">Maior valor</option>
                    <option value="menor_valor">Menor valor</option>
                    <option value="condominio">Condomínio (A–Z)</option>
                  </select>
                </label>
                <label className="central-campo central-data"><span>Data inicial</span><input type="date" value={filtroInicioSolicitacao} max={filtroFimSolicitacao || undefined} onChange={e => setFiltroInicioSolicitacao(e.target.value)} /></label>
                <label className="central-campo central-data"><span>Data final</span><input type="date" value={filtroFimSolicitacao} min={filtroInicioSolicitacao || undefined} onChange={e => setFiltroFimSolicitacao(e.target.value)} /></label>
              </div>

              <div className="central-status-filtros" role="group" aria-label="Filtrar solicitações por status">
                {[
                  { id: 'todos', label: 'Todas' },
                  { id: 'Aprovação pendente', label: 'Pendentes' },
                  { id: 'Em análise', label: 'Em análise' },
                  { id: 'Ajuste solicitado', label: 'Em ajuste' },
                  { id: 'Aprovada', label: 'Aprovadas' },
                  { id: 'Em execução', label: 'Em execução' },
                  { id: 'Finalizada', label: 'Finalizadas' },
                  { id: 'Reprovada', label: 'Reprovadas' }
                ].map(item => (
                  <button type="button" key={item.id} aria-pressed={filtroStatus === item.id} className={`central-status-pill ${filtroStatus === item.id ? 'active' : ''}`} onClick={() => setFiltroStatus(item.id)}>{item.label}</button>
                ))}
              </div>

              <div className="central-resultado-barra" aria-live="polite">
                <span><strong>{solicitacoesFiltradas.length}</strong> {solicitacoesFiltradas.length === 1 ? 'solicitação encontrada' : 'solicitações encontradas'}</span>
                <span>{solicitacoesFiltradas.length ? `Mostrando ${inicioSolicitacoes + 1}–${Math.min(inicioSolicitacoes + solicitacoesPorPagina, solicitacoesFiltradas.length)}` : 'Nenhum resultado'}</span>
              </div>

              <div className="central-tabela" role="table" aria-label="Solicitações filtradas">
                <div className="central-tabela-cabecalho" role="row"><span role="columnheader">Solicitação</span><span role="columnheader">Condomínio</span><span role="columnheader">Descrição / Categoria</span><span role="columnheader">Valor</span><span role="columnheader">Status</span><span role="columnheader">Data</span></div>
                {solicitacoesPaginadas.length === 0 ? (
                  <div className="central-vazio"><IconeHaize nome="requests" tamanho={28} /><strong>{resumoSolicitacoes.total === 0 ? 'Nenhuma solicitação cadastrada' : 'Nenhum resultado para os filtros selecionados'}</strong><p>{resumoSolicitacoes.total === 0 ? 'Os pedidos registrados aparecerão nesta lista.' : 'Tente alterar a busca, o período ou o status.'}</p>{filtrosSolicitacoesAtivos && <button className="button-secondary" onClick={limparFiltrosSolicitacoes}>Limpar filtros</button>}</div>
                ) : solicitacoesPaginadas.map(sol => (
                  <div className="central-solicitacao-linha" role="row" key={sol.id}>
                    <div role="cell" className="central-cell-codigo"><span className="central-mobile-label">Solicitação</span><button type="button" className="central-codigo-botao" onClick={() => abrirSolicitacao(sol)} aria-label={`Abrir solicitação ${sol.numero || sol.id}`}>{sol.numero || `#${sol.id}`}</button></div>
                    <div role="cell" className="central-cell-condominio"><span className="central-mobile-label">Condomínio</span><strong>{sol.condominio}</strong></div>
                    <div role="cell" className="central-cell-descricao"><span className="central-mobile-label">Descrição</span><strong title={sol.descricao || ''}>{sol.descricao || 'Sem descrição'}</strong><small>{[sol.categoria, sol.fornecedor].filter(Boolean).join(' • ') || 'Sem categoria informada'}</small></div>
                    <div role="cell" className="central-cell-valor"><span className="central-mobile-label">Valor</span><strong>{formatarValor(sol.valor)}</strong>{aprovado(sol) > 0 && aprovado(sol) < solicitado(sol) && <small>Aprovado: {formatarValor(aprovado(sol))}</small>}</div>
                    <div role="cell" className="central-cell-status"><span className="central-mobile-label">Status</span>{renderBadge(sol)}</div>
                    <div role="cell" className="central-cell-data"><span className="central-mobile-label">Data</span><span>{sol.data ? formatarDataHora(sol.data).split(',')[0] : '—'}</span><button type="button" className="central-abrir" onClick={() => abrirSolicitacao(sol)} aria-label={`Ver detalhes da solicitação ${sol.numero || sol.id}`} title="Ver detalhes"><IconeHaize nome="arrow" tamanho={17} /></button></div>
                  </div>
                ))}
              </div>

              {totalPaginasSolicitacoes > 1 && (
                <nav className="central-paginacao" aria-label="Paginação de solicitações">
                  <span>Página {paginaAtualSolicitacoes} de {totalPaginasSolicitacoes}</span>
                  <div>
                    <button type="button" className="button-secondary" disabled={paginaAtualSolicitacoes <= 1} onClick={() => setPaginaSolicitacoes(p => Math.max(1, p - 1))}>Anterior</button>
                    <button type="button" className="button-secondary" disabled={paginaAtualSolicitacoes >= totalPaginasSolicitacoes} onClick={() => setPaginaSolicitacoes(p => Math.min(totalPaginasSolicitacoes, p + 1))}>Próxima</button>
                  </div>
                </nav>
              )}
            </section>
          </div>
        )}

        {pagina === 'compras' && !ehChecklist && (
          <div className="page compras-page">
            <header className="cadastro-hero compras-hero">
              <div>
                <span className="cadastro-hero-kicker">ACOMPANHAMENTO DE COMPRAS</span>
                <h2>Compras e execução</h2>
                <p>Visualize pedidos aprovados, acompanhe a execução e consulte os valores registrados.</p>
              </div>
              <div className="cadastro-hero-icon"><IconeHaize nome="shopping" tamanho={40}/></div>
            </header>
            <div className="compras-indicadores" aria-label="Resumo do fluxo de compras">
              <div className="compras-indicador"><span>Em acompanhamento</span><strong>{resumoCompras.total}</strong><small>Pedidos aprovados ou posteriores</small></div>
              <button type="button" className={`compras-indicador ${filtroStatusCompra === 'Aprovada' ? 'selecionado' : ''}`} onClick={() => setFiltroStatusCompra(filtroStatusCompra === 'Aprovada' ? 'todos' : 'Aprovada')}><span>Aprovadas</span><strong>{resumoCompras.aprovadas}</strong><small>Prontas para execução</small></button>
              <button type="button" className={`compras-indicador ${filtroStatusCompra === 'Em execução' ? 'selecionado' : ''}`} onClick={() => setFiltroStatusCompra(filtroStatusCompra === 'Em execução' ? 'todos' : 'Em execução')}><span>Em execução</span><strong>{resumoCompras.emExecucao}</strong><small>Compras em andamento</small></button>
              <button type="button" className={`compras-indicador ${filtroStatusCompra === 'Finalizada' ? 'selecionado' : ''}`} onClick={() => setFiltroStatusCompra(filtroStatusCompra === 'Finalizada' ? 'todos' : 'Finalizada')}><span>Finalizadas</span><strong>{resumoCompras.finalizadas}</strong><small>Compras concluídas</small></button>
            </div>
            <section className="panel compras-painel">
              <div className="cadastro-painel-topo">
                <div><span className="eyebrow">PAINEL DE COMPRAS</span><h3>Registros e valores</h3><p>Use os filtros para encontrar uma compra e abra seus detalhes para consultar o histórico.</p></div>
                <span className="cadastro-contador">{comprasFiltradas.length} {comprasFiltradas.length === 1 ? 'resultado' : 'resultados'}</span>
              </div>
              <div className="cadastro-filtros compras-filtros">
                <label className="cadastro-campo cadastro-busca"><span>Buscar compra</span><input type="search" value={filtroCompra} placeholder="Código, descrição, fornecedor..." onChange={e => setFiltroCompra(e.target.value)}/></label>
                <label className="cadastro-campo"><span>Condomínio</span><select value={filtroCondominioCompra} onChange={e => setFiltroCondominioCompra(e.target.value)}><option value="todos">Todos os condomínios</option>{opcoesCondominiosCompra.map(nome => <option value={nome} key={nome}>{nome}</option>)}</select></label>
                <label className="cadastro-campo"><span>Status</span><select value={filtroStatusCompra} onChange={e => setFiltroStatusCompra(e.target.value)}><option value="todos">Todos os status</option><option value="Aprovada">Aprovadas</option><option value="Em execução">Em execução</option><option value="Finalizada">Finalizadas</option></select></label>
                <label className="cadastro-campo"><span>Ordenar</span><select value={ordenacaoCompra} onChange={e => setOrdenacaoCompra(e.target.value)}><option value="recentes">Mais recentes</option><option value="maior_valor">Maior aprovado</option><option value="menor_valor">Menor aprovado</option><option value="condominio">Condomínio (A–Z)</option></select></label>
              </div>
              {(filtroCompra || filtroCondominioCompra !== 'todos' || filtroStatusCompra !== 'todos' || ordenacaoCompra !== 'recentes') && <div className="cadastro-acoes-filtro"><button type="button" className="text-button" onClick={limparFiltrosCompra}>Limpar filtros</button></div>}
              <div className="compras-resumo-valores" aria-live="polite">
                <div><span>Total aprovado no filtro</span><strong>{formatarValor(totalComprasAprovado)}</strong></div>
                <div><span>Total realizado no filtro</span><strong>{formatarValor(totalComprasRealizado)}</strong></div>
                <p>Valores calculados apenas com os lançamentos registrados. Aprovação não é pagamento.</p>
              </div>
              <div className="compras-tabela" role="table" aria-label="Compras aprovadas e em execução">
                <div className="compras-tabela-cabecalho" role="row"><span role="columnheader">Código</span><span role="columnheader">Condomínio / Descrição</span><span role="columnheader">Aprovado</span><span role="columnheader">Realizado</span><span role="columnheader">Status</span><span role="columnheader">Detalhes</span></div>
                {comprasPaginadas.length === 0 ? <div className="cadastro-vazio"><IconeHaize nome="shopping" tamanho={30}/><strong>{comprasBase.length === 0 ? 'Nenhuma compra em acompanhamento' : 'Nenhuma compra encontrada'}</strong><p>{comprasBase.length === 0 ? 'As solicitações aprovadas, em execução e finalizadas aparecerão aqui.' : 'Altere os filtros ou limpe a busca para ver mais resultados.'}</p><button type="button" className="button-secondary" onClick={limparFiltrosCompra}>Limpar filtros</button></div> : comprasPaginadas.map(sol => <div className="compras-linha" role="row" key={sol.id}>
                  <div role="cell"><span className="compras-mobile-label">Código</span><button type="button" className="central-codigo-botao" onClick={() => abrirSolicitacao(sol)}>{sol.numero || `#${sol.id}`}</button><small>{String(sol.data || '').slice(0,10).split('-').reverse().join('/')}</small></div>
                  <div role="cell" className="compras-descricao"><span className="compras-mobile-label">Condomínio / Descrição</span><strong>{sol.condominio}</strong><span title={sol.descricao || ''}>{sol.descricao || 'Sem descrição'}</span><small>{[sol.categoria, sol.fornecedor].filter(Boolean).join(' • ')}</small></div>
                  <div role="cell"><span className="compras-mobile-label">Aprovado</span><strong>{formatarValor(aprovado(sol))}</strong><small>Solicitado: {formatarValor(solicitado(sol))}</small></div>
                  <div role="cell"><span className="compras-mobile-label">Realizado</span><strong>{formatarValor(realizado(sol))}</strong><small>{textoStatus(sol.status) === 'Finalizada' ? 'Valor registrado' : 'Ainda em andamento'}</small></div>
                  <div role="cell"><span className="compras-mobile-label">Status</span>{renderBadge(sol)}</div>
                  <div role="cell" className="compras-cell-acao"><button type="button" className="button-secondary" onClick={() => abrirSolicitacao(sol)}>Ver detalhes <IconeHaize nome="arrow" tamanho={15}/></button></div>
                </div>)}
              </div>
              {totalPaginasCompra > 1 && <nav className="cadastro-paginacao" aria-label="Páginas das compras"><span>Página {paginaAtualCompra} de {totalPaginasCompra}</span><div><button type="button" className="button-secondary" disabled={paginaAtualCompra === 1} onClick={() => setPaginaCompra(p => Math.max(1, p-1))}>Anterior</button><button type="button" className="button-secondary" disabled={paginaAtualCompra === totalPaginasCompra} onClick={() => setPaginaCompra(p => Math.min(totalPaginasCompra, p+1))}>Próxima</button></div></nav>}
            </section>
          </div>
        )}

        {pagina === 'categorias' && !ehChecklist && (
          <div className="page cadastros-page">
            <header className="cadastro-hero"><div><span className="cadastro-hero-kicker">CATEGORIAS E ALÇADAS</span><h2>Categorias de despesas</h2><p>Organize os tipos de gasto e configure os limites de aprovação automática.</p></div><div className="cadastro-hero-icon"><IconeHaize nome="categories" tamanho={40}/></div></header>
            <section className="panel cadastro-painel">
              <div className="cadastro-painel-topo"><div><span className="eyebrow">CADASTROS BASE</span><h3>Gerenciar categorias</h3><p>{categorias.length} {categorias.length === 1 ? 'categoria cadastrada' : 'categorias cadastradas'}</p></div><button type="button" className="button-primary" onClick={abrirFormularioNovoCategoria}><IconeHaize nome="plus" tamanho={16}/> Nova categoria</button></div>
              <div className="cadastro-filtros cadastro-filtros-simples"><label className="cadastro-campo cadastro-busca"><span>Buscar categoria</span><input type="search" value={buscaCategoriaCadastro} onChange={e => setBuscaCategoriaCadastro(e.target.value)} placeholder="Nome ou descrição" /></label><span className="cadastro-contador">{categoriasCadastroFiltradas.length} {categoriasCadastroFiltradas.length === 1 ? 'resultado' : 'resultados'}</span></div>
              {categoriasCadastroFiltradas.length === 0 ? <div className="cadastro-vazio"><IconeHaize nome="categories" tamanho={28}/><strong>{categorias.length ? 'Nenhuma categoria encontrada' : 'Nenhuma categoria cadastrada'}</strong><p>{categorias.length ? 'Experimente outro termo de busca.' : 'Cadastre uma categoria para definir regras de aprovação.'}</p>{categorias.length > 0 && <button type="button" className="button-secondary" onClick={() => setBuscaCategoriaCadastro('')}>Limpar busca</button>}</div> : <div className="cadastro-grade">{categoriasCadastroFiltradas.map(cat => {
                const nome = cat.nome || 'Sem nome'
                const qtd = solicitacoes.filter(s => s.categoria === nome).length
                const limitesCadastrados = Array.isArray(cat.limites) ? cat.limites.length : 0
                return <article className="cadastro-card" key={cat.id}><div className="cadastro-card-topo"><span className="cadastro-avatar"><IconeHaize nome="categories" tamanho={20}/></span><span className="cadastro-chip">Cadastrada</span></div><h4>{nome}</h4><p className="cadastro-card-descricao">{cat.descricao || 'Sem descrição informada'}</p><div className="cadastro-card-info"><span><strong>{qtd}</strong> solicitações vinculadas</span><span>{limitesCadastrados ? `${limitesCadastrados} ${limitesCadastrados === 1 ? 'limite' : 'limites'} de alçada` : 'Aprovação manual padrão'}</span></div><div className="cadastro-card-rodape"><button type="button" className="button-secondary" onClick={() => editarCategoria(cat)}>Configurar alçadas</button><button type="button" className="cadastro-excluir" onClick={() => excluirCategoria(cat.id, nome)}>Excluir</button></div></article>
              })}</div>}
            </section>
          </div>
        )}

        {pagina === 'condominios' && !ehChecklist && (
          <div className="page cadastros-page">
            <header className="cadastro-hero"><div><span className="cadastro-hero-kicker">CARTEIRA DE CONDOMÍNIOS</span><h2>Condomínios gerenciados</h2><p>Consulte cadastros, dados administrativos e unidades de rateio em um só lugar.</p></div><div className="cadastro-hero-icon"><IconeHaize nome="buildings" tamanho={40}/></div></header>
            <section className="panel cadastro-painel">
              <div className="cadastro-painel-topo"><div><span className="eyebrow">CADASTROS BASE</span><h3>Carteira predial</h3><p>{condominios.length} {condominios.length === 1 ? 'condomínio cadastrado' : 'condomínios cadastrados'}</p></div><button type="button" className="button-primary" onClick={abrirFormularioNovoCondominio}><IconeHaize nome="plus" tamanho={16}/> Novo condomínio</button></div>
              <div className="cadastro-filtros cadastro-filtros-simples"><label className="cadastro-campo cadastro-busca"><span>Buscar condomínio</span><input type="search" value={buscaCondominioCadastro} onChange={e => setBuscaCondominioCadastro(e.target.value)} placeholder="Nome, CNPJ ou código"/></label><span className="cadastro-contador">{condominiosCadastroFiltrados.length} {condominiosCadastroFiltrados.length === 1 ? 'resultado' : 'resultados'}</span></div>
              {condominiosCadastroFiltrados.length === 0 ? <div className="cadastro-vazio"><IconeHaize nome="buildings" tamanho={28}/><strong>{condominios.length ? 'Nenhum condomínio encontrado' : 'Nenhum condomínio cadastrado'}</strong><p>{condominios.length ? 'Experimente outro termo de busca.' : 'Cadastre um condomínio para começar a organizar as solicitações.'}</p>{condominios.length > 0 && <button type="button" className="button-secondary" onClick={() => setBuscaCondominioCadastro('')}>Limpar busca</button>}</div> : <div className="cadastro-grade">{condominiosCadastroFiltrados.map(condominio => {
                const nome = condominio.nome || 'Sem nome'
                const qtd = solicitacoes.filter(s => s.condominio === nome).length
                return <article className="cadastro-card" key={condominio.id}><div className="cadastro-card-topo"><span className="cadastro-avatar"><IconeHaize nome="buildings" tamanho={20}/></span><span className="cadastro-chip">Condomínio Nº {condominio.id}</span></div><h4>{nome}</h4><div className="cadastro-card-info"><span>CNPJ: <strong>{condominio.cnpj || 'Não informado'}</strong></span><span>Código: <strong>{condominio.codigo || 'Não informado'}</strong></span><span><strong>{qtd}</strong> solicitações vinculadas</span></div><div className="cadastro-card-rodape"><button type="button" className="button-secondary" onClick={() => abrirGerenciadorUnidades(condominio)}>Unidades</button><button type="button" className="button-secondary" onClick={() => editarCondominio(condominio)}>Editar</button><button type="button" className="cadastro-excluir" onClick={() => excluirCondominio(condominio.id, nome)}>Excluir</button></div></article>
              })}</div>}
            </section>
          </div>
        )}

        {pagina === 'fornecedores' && !ehChecklist && (
          <div className="page cadastros-page">
            <header className="cadastro-hero"><div><span className="cadastro-hero-kicker">REDE DE FORNECEDORES</span><h2>Fornecedores e prestadores</h2><p>Organize parceiros, especialidades e dados cadastrais usados nas solicitações.</p></div><div className="cadastro-hero-icon"><IconeHaize nome="suppliers" tamanho={40}/></div></header>
            <section className="panel cadastro-painel">
              <div className="cadastro-painel-topo"><div><span className="eyebrow">CADASTROS BASE</span><h3>Gerenciar fornecedores</h3><p>{fornecedores.length} {fornecedores.length === 1 ? 'fornecedor cadastrado' : 'fornecedores cadastrados'}</p></div><button type="button" className="button-primary" onClick={abrirFormularioNovoFornecedor}><IconeHaize nome="plus" tamanho={16}/> Novo fornecedor</button></div>
              <div className="cadastro-filtros cadastro-filtros-simples"><label className="cadastro-campo cadastro-busca"><span>Buscar fornecedor</span><input type="search" value={buscaFornecedorCadastro} onChange={e => setBuscaFornecedorCadastro(e.target.value)} placeholder="Nome, CNPJ ou especialidade"/></label><span className="cadastro-contador">{fornecedoresCadastroFiltrados.length} {fornecedoresCadastroFiltrados.length === 1 ? 'resultado' : 'resultados'}</span></div>
              {fornecedoresCadastroFiltrados.length === 0 ? <div className="cadastro-vazio"><IconeHaize nome="suppliers" tamanho={28}/><strong>{fornecedores.length ? 'Nenhum fornecedor encontrado' : 'Nenhum fornecedor cadastrado'}</strong><p>{fornecedores.length ? 'Experimente outro termo de busca.' : 'Cadastre um fornecedor para facilitar as próximas solicitações.'}</p>{fornecedores.length > 0 && <button type="button" className="button-secondary" onClick={() => setBuscaFornecedorCadastro('')}>Limpar busca</button>}</div> : <div className="cadastro-grade">{fornecedoresCadastroFiltrados.map(forn => {
                const nome = forn.nome || 'Sem nome'
                const qtd = solicitacoes.filter(s => s.fornecedor === nome).length
                return <article className="cadastro-card" key={forn.id}><div className="cadastro-card-topo"><span className="cadastro-avatar"><IconeHaize nome="suppliers" tamanho={20}/></span><span className="cadastro-chip">Cadastrado</span></div><h4>{nome}</h4><div className="cadastro-card-info"><span>CNPJ: <strong>{forn.cnpj || 'Não informado'}</strong></span><span>Especialidade: <strong>{forn.categoria || 'Não informada'}</strong></span><span><strong>{qtd}</strong> solicitações vinculadas</span></div><div className="cadastro-card-rodape"><button type="button" className="button-secondary" onClick={() => editarFornecedor(forn)}>Editar</button><button type="button" className="cadastro-excluir" onClick={() => excluirFornecedor(forn.id, nome)}>Excluir</button></div></article>
              })}</div>}
            </section>
          </div>
        )}

        {/* MODAL: CRIAR OU EDITAR ATIVIDADE DE CHECKLIST */}
        {mostrarModalNovoChecklist && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setMostrarModalNovoChecklist(false) }}>
            <div className="modal">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">PLANEJAMENTO OPERACIONAL</span>
                  <h3>{checklistEditando ? 'Editar Atividade de Checklist' : 'Nova Atividade de Checklist'}</h3>
                </div>
                <button className="modal-close" onClick={() => setMostrarModalNovoChecklist(false)}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={salvarNovoChecklist}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Condomínio *</label>
                      <select
                        value={formNovoChecklist.condominio}
                        onChange={e => setFormNovoChecklist(p => ({ ...p, condominio: e.target.value }))}
                        required
                      >
                        <option value="">Selecione o condomínio...</option>
                        {condominios.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                      </select>
                    </div>

                    <div className="form-group full">
                      <label>Atividade / O que deve ser verificado? *</label>
                      <input
                        type="text"
                        placeholder="Ex: Verificar bombas de recalque, Limpeza da caixa de gordura..."
                        value={formNovoChecklist.titulo}
                        onChange={e => setFormNovoChecklist(p => ({ ...p, titulo: e.target.value }))}
                        required
                      />
                    </div>

                    <div className="form-group full">
                      <label>Frequência Exigida *</label>
                      <select
                        value={formNovoChecklist.frequencia}
                        onChange={e => setFormNovoChecklist(p => ({ ...p, frequencia: e.target.value }))}
                        required
                      >
                        <option value="Diária">Diária</option>
                        <option value="Semanal">Semanal</option>
                        <option value="Quinzenal">Quinzenal</option>
                        <option value="Mensal">Mensal</option>
                      </select>
                    </div>

                    <div className="form-group full">
                      <label>Instruções / O que observar na vistoria</label>
                      <textarea
                        rows="2"
                        placeholder="Ex: Checar se há vazamentos no selo mecânico, ruído anormal ou lâmpadas queimadas..."
                        value={formNovoChecklist.descricao_orientacao}
                        onChange={e => setFormNovoChecklist(p => ({ ...p, descricao_orientacao: e.target.value }))}
                      />
                    </div>

                    <div className="form-group full">
                      <label>Plano de Ação Predefinido (Exibido em pop-up caso haja inconformidade)</label>
                      <textarea
                        rows="3"
                        placeholder="Ex: Isolar a área imediatamente e acionar a manutenção credenciada..."
                        value={formNovoChecklist.plano_acao_padrao}
                        onChange={e => setFormNovoChecklist(p => ({ ...p, plano_acao_padrao: e.target.value }))}
                      />
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={() => setMostrarModalNovoChecklist(false)}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarNovoChecklist} disabled={salvando}>
                  {salvando ? 'Salvando...' : (checklistEditando ? 'Salvar Alterações' : 'Criar Atividade')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL: REGISTRAR EXECUÇÃO DO CHECKLIST */}
        {itemChecklistExecutando && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget && !salvandoExecucaoChecklist) setItemChecklistExecutando(null) }}>
            <div className="modal modal-checklist-execucao" role="dialog" aria-modal="true" aria-labelledby="titulo-modal-vistoria">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">{itemChecklistExecutando.condominio} • {itemChecklistExecutando.frequencia}</span>
                  <h3 id="titulo-modal-vistoria">{itemChecklistExecutando.titulo}</h3>
                </div>
                <button className="modal-close" aria-label="Fechar registro de vistoria" disabled={salvandoExecucaoChecklist} onClick={() => setItemChecklistExecutando(null)}>×</button>
              </div>
              <div className="modal-body">
                <form id="form-registrar-vistoria" className="form" onSubmit={confirmarExecucaoChecklist}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Resultado da Vistoria *</label>
                      <div className="checklist-opcoes-resultado">
                        <button
                          type="button"
                          onClick={() => setFormExecucaoChecklist(p => ({ ...p, status_conformidade: 'Conforme' }))}
                          className={`checklist-resultado-opcao conforme ${formExecucaoChecklist.status_conformidade === 'Conforme' ? 'selecionada' : ''}`}
                          aria-pressed={formExecucaoChecklist.status_conformidade === 'Conforme'}
                        >
                          Conforme
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormExecucaoChecklist(p => ({ ...p, status_conformidade: 'Não Conforme' }))}
                          className={`checklist-resultado-opcao nao-conforme ${formExecucaoChecklist.status_conformidade === 'Não Conforme' ? 'selecionada' : ''}`}
                          aria-pressed={formExecucaoChecklist.status_conformidade === 'Não Conforme'}
                        >
                          Não conforme
                        </button>
                      </div>
                    </div>

                    <div className="form-group full">
                      <label>
                        Observações / Descrição {formExecucaoChecklist.status_conformidade === 'Não Conforme' ? '* (Obrigatório relatar o problema)' : '(Opcional)'}
                      </label>
                      <textarea
                        rows="3"
                        placeholder="Descreva detalhes da vistoria ou relate qualquer irregularidade encontrada..."
                        value={formExecucaoChecklist.observacao}
                        onChange={e => setFormExecucaoChecklist(p => ({ ...p, observacao: e.target.value }))}
                      />
                    </div>

                    <div className="form-group full">
                      <label>Foto / Evidência (Câmera ou Galeria)</label>
                      <input
                        type="file"
                        accept="image/*,.pdf"
                        onChange={e => setFormExecucaoChecklist(p => ({ ...p, foto: e.target.files[0] || null }))}
                        style={{ padding: '10px', background: '#f8fafc', border: '1px dashed #cbd5e1' }}
                      />
                      {formExecucaoChecklist.foto && (
                        <span style={{ fontSize: '12px', color: '#059669', fontWeight: '700', marginTop: '4px' }}>
                          📎 Arquivo selecionado: {formExecucaoChecklist.foto.name}
                        </span>
                      )}
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" disabled={salvandoExecucaoChecklist} onClick={() => setItemChecklistExecutando(null)}>Cancelar</button>
                <button type="submit" form="form-registrar-vistoria" className="button-primary" disabled={salvandoExecucaoChecklist}>
                  {salvandoExecucaoChecklist ? 'Salvando vistoria...' : 'Confirmar vistoria'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL: HISTÓRICO DE EXECUÇÕES DA ATIVIDADE */}
        {itemChecklistHistorico && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setItemChecklistHistorico(null) }}>
            <div className="modal modal-large">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">HISTÓRICO DE VISTORIAS • {itemChecklistHistorico.condominio}</span>
                  <h3>{itemChecklistHistorico.titulo}</h3>
                </div>
                <button className="modal-close" onClick={() => setItemChecklistHistorico(null)}>×</button>
              </div>
              <div className="modal-body">
                {!itemChecklistHistorico.historico_execucoes || itemChecklistHistorico.historico_execucoes.length === 0 ? (
                  <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>
                    Nenhuma execução registrada para esta atividade até o momento.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '420px', overflowY: 'auto' }}>
                    {itemChecklistHistorico.historico_execucoes.map(ex => {
                      const ehProblema = ex.status_conformidade === 'Não Conforme'
                      return (
                        <div key={ex.id} style={{ padding: '14px 16px', borderRadius: '10px', border: `1px solid ${ehProblema ? '#fecaca' : '#e2e8f0'}`, background: ehProblema ? '#fef2f2' : '#ffffff', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                              <strong style={{ fontSize: '13px', color: ehProblema ? '#dc2626' : '#059669' }}>
                                {ehProblema ? '⚠️ Não Conforme' : '✅ Conforme'}
                              </strong>
                              <span style={{ fontSize: '12px', color: '#64748b' }}>• {formatarDataHora(ex.data_execucao)}</span>
                              <span style={{ fontSize: '12px', color: '#334155', fontWeight: '700' }}>• Vistoriador: {ex.responsavel}</span>
                            </div>
                            {ex.observacao && (
                              <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#1e293b' }}>
                                <strong>Relato:</strong> {ex.observacao}
                              </p>
                            )}
                          </div>
                          {ex.tem_foto && (
                            <a
                              href="#" onClick={e => { e.preventDefault(); abrirArquivoProtegido(`/checklists/execucoes/${ex.id}/foto`, `evidencia-vistoria-${ex.id}`).catch(err => mostrarToast(err.message, 'error')) }}
                              target="_blank"
                              rel="noreferrer"
                              className="button-secondary"
                              style={{ padding: '6px 12px', fontSize: '12px', textDecoration: 'none' }}
                            >
                              📷 Ver Evidência
                            </a>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={() => setItemChecklistHistorico(null)}>Fechar</button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL DE GERENCIAMENTO DE UNIDADES E FRAÇÕES */}
        {condominioUnidades && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setCondominioUnidades(null) }}>
            <div className="modal modal-large">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">CONFIGURAÇÃO DE RATEIO</span>
                  <h3>Unidades & Frações Ideais — {condominioUnidades.nome}</h3>
                </div>
                <button className="modal-close" onClick={() => setCondominioUnidades(null)}>×</button>
              </div>
              <div className="modal-body">
                <form onSubmit={salvarNovaUnidade} style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div style={{ flex: 2, minWidth: '180px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Identificação da Unidade *</label>
                    <input type="text" placeholder="Ex: Ap 101, Apto 202, Cobertura 01" value={novaUnidade.identificacao} onChange={e => setNovaUnidade(p => ({ ...p, identificacao: e.target.value }))} required style={{ width: '100%' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: '140px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Fração Ideal (%) *</label>
                    <input type="text" placeholder="Ex: 2,5 ou 5,0" value={novaUnidade.fracao_ideal} onChange={e => setNovaUnidade(p => ({ ...p, fracao_ideal: e.target.value }))} required style={{ width: '100%' }} />
                  </div>
                  <button type="submit" className="button-primary" style={{ height: '39px' }}>+ Adicionar</button>
                </form>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '18px 0 10px 0' }}>
                  <h4 style={{ margin: 0, fontSize: '13px', textTransform: 'uppercase', color: '#334155' }}>Unidades Cadastradas ({listaUnidades.length})</h4>
                  <span style={{ fontSize: '12.5px', fontWeight: '800', color: Math.round(somaFracaoTotal) === 100 ? '#059669' : '#d97706' }}>
                    Soma das Frações: {formatarNumero(somaFracaoTotal)}% {Math.round(somaFracaoTotal) === 100 ? '✓ (100% Fechado)' : '(Diferente de 100%)'}
                  </span>
                </div>

                <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                  {carregandoUnidades ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>Carregando unidades...</div>
                  ) : listaUnidades.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>Nenhuma unidade cadastrada para este condomínio.</div>
                  ) : (
                    <div className="table">
                      <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 100px' }}>
                        <span>Identificação</span>
                        <span>Fração Ideal (%)</span>
                        <span style={{ textAlign: 'center' }}>Ação</span>
                      </div>
                      {listaUnidades.map(u => (
                        <div className="table-row" key={u.id} style={{ gridTemplateColumns: '2fr 1fr 100px' }}>
                          <strong style={{ color: '#0f172a' }}>{u.identificacao}</strong>
                          <span style={{ fontWeight: '700', color: '#1d4ed8' }}>{formatarNumero(u.fracao_ideal)}%</span>
                          <div style={{ textAlign: 'center' }}>
                            <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirUnidade(u.id)}>Excluir</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={() => setCondominioUnidades(null)}>Fechar</button>
              </div>
            </div>
          </div>
        )}

        {solicitacaoSelecionada && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) fecharSolicitacao() }}>
            <div className="modal modal-large modal-solicitacao">
              <div className="modal-header">
                <div><span className="eyebrow">SOLICITAÇÃO / DETALHES</span><h3>{solicitacaoSelecionada.numero} • {solicitacaoSelecionada.condominio}</h3><p className="solicitacao-modal-subtitulo">Confira os valores, os anexos e o histórico antes de tomar uma decisão.</p></div>
                <button className="modal-close" onClick={fecharSolicitacao} aria-label="Fechar detalhes da solicitação">×</button>
              </div>
              <div className="modal-body">
                {(() => {
                  const vSol = solicitado(solicitacaoSelecionada); const vApr = aprovado(solicitacaoSelecionada); const vReal = realizado(solicitacaoSelecionada)
                  const temCorte = vApr > 0 && vApr < vSol; const taFinalizado = vReal > 0; const limite = vApr > 0 ? vApr : vSol; const estourou = taFinalizado && vReal > limite
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '18px' }}>
                      {solicitacaoSelecionada.motivo_ajuste && (
                        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>📌</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '13.5px', color: '#991b1b' }}>Motivo do Ajuste / Reprovação</strong>
                            <span style={{ fontSize: '13px', color: '#b91c1c' }}>{solicitacaoSelecionada.motivo_ajuste}</span>
                          </div>
                        </div>
                      )}
                      {temCorte && (
                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '12px 16px', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>⚠️</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '13.5px', color: '#b45309' }}>Aprovação Parcial</strong>
                            <span style={{ fontSize: '13px', color: '#d97706' }}>Aprovada com o valor de <strong>{formatarValor(vApr)}</strong> (inferior ao solicitado de <strong>{formatarValor(vSol)}</strong>).</span>
                          </div>
                        </div>
                      )}
                      {taFinalizado && (
                        <div style={{ background: estourou ? '#fef2f2' : '#f0fdf4', border: `1px solid ${estourou ? '#fecaca' : '#bbf7d0'}`, padding: '12px 16px', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '20px' }}>{estourou ? '🚨' : '✅'}</span>
                          <div>
                            <strong style={{ display: 'block', fontSize: '13.5px', color: estourou ? '#991b1b' : '#15803d' }}>{estourou ? 'Orçamento Ultrapassado' : 'Dentro do Orçamento'}</strong>
                            <span style={{ fontSize: '13px', color: estourou ? '#b91c1c' : '#166534' }}>
                              Valor finalizado: <strong>{formatarValor(vReal)}</strong> (Teto aprovado: {formatarValor(limite)}).
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div className="detail-grid">
                  <div className="detail-card"><span>Status</span><strong>{renderBadge(solicitacaoSelecionada)}</strong></div>
                  {solicitacaoSelecionada.categoria && (
                    <div className="detail-card" style={{ background: '#faf5ff', borderColor: '#f3e8ff' }}>
                      <span>Categoria</span><strong style={{ color: '#7e22ce' }}>📁 {solicitacaoSelecionada.categoria}</strong>
                    </div>
                  )}
                  <div className="detail-card"><span>Valor Serviço</span><strong>{formatarValor(solicitacaoSelecionada.valor_servico)}</strong></div>
                  <div className="detail-card"><span>Valor Produto</span><strong>{formatarValor(solicitacaoSelecionada.valor_produto)}</strong></div>
                  <div className="detail-card" style={{ background: '#eff6ff', borderColor: '#bfdbfe' }}><span>Total Solicitado</span><strong style={{ color: '#1d4ed8' }}>{formatarValor(solicitacaoSelecionada.valor)}</strong></div>
                  {aprovado(solicitacaoSelecionada) > 0 && (<div className="detail-card" style={{ background: '#f0fdf4', borderColor: '#bbf7d0' }}><span>Valor Aprovado</span><strong style={{ color: '#15803d' }}>{formatarValor(solicitacaoSelecionada.valor_aprovado)}</strong></div>)}
                  {realizado(solicitacaoSelecionada) > 0 && (<div className="detail-card" style={{ background: '#f0fdf4', borderColor: '#bbf7d0' }}><span>Valor Realizado</span><strong style={{ color: '#15803d' }}>{formatarValor(solicitacaoSelecionada.valor_realizado)}</strong></div>)}
                </div>

                <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '10px', border: '1px solid #e2e8f0', marginBottom: '20px', fontSize: '13px' }}>
                  <div><strong>Descrição:</strong> {solicitacaoSelecionada.descricao}</div>
                  {solicitacaoSelecionada.fornecedor && <div style={{ marginTop: '4px' }}><strong>Fornecedor:</strong> {solicitacaoSelecionada.fornecedor}</div>}
                  {solicitacaoSelecionada.observacao && <div style={{ marginTop: '4px' }}><strong>Observações:</strong> {solicitacaoSelecionada.observacao}</div>}
                </div>

                <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '12px', border: '1px solid #cbd5e1' }}>
                  <span className="eyebrow">DOCUMENTAÇÃO</span>
                  <h4 style={{ margin: '0 0 12px 0' }}>Arquivos e Comprovantes</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {anexosSolicitacao.length === 0 ? (
                      <div style={{ padding: '14px', background: 'white', border: '1px dashed #cbd5e1', borderRadius: '8px', textAlign: 'center', fontSize: '12.5px', color: '#64748b' }}>Nenhum arquivo anexado ainda.</div>
                    ) : (
                      anexosSolicitacao.map(anexo => (
                        <div key={anexo.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'white', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontSize: '20px' }}>📄</span>
                            <div>
                              <strong style={{ display: 'block', fontSize: '13px', color: '#0f172a' }}>{anexo.nome_arquivo}</strong>
                              <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>{String(anexo.tipo || '').toUpperCase()} • {formatarDataHora(anexo.data_upload)}</span>
                            </div>
                          </div>
                          <a href="#" onClick={e => { e.preventDefault(); abrirArquivoProtegido(`/anexos/${anexo.id}/download`, anexo.nome_arquivo || `anexo-${anexo.id}`).catch(err => mostrarToast(err.message, 'error')) }} target="_blank" rel="noreferrer" className="button-secondary" style={{ padding: '6px 12px', fontSize: '12px', textDecoration: 'none' }}>Baixar</a>
                        </div>
                      ))
                    )}
                    <div style={{ display: 'flex', gap: '10px', marginTop: '6px', flexWrap: 'wrap' }}>
                      <label className="button-secondary" style={{ cursor: 'pointer', flex: 1 }}>
                        {fazendoUpload ? 'Enviando...' : '+ Anexar Orçamento / Documento'}
                        <input type="file" style={{ display: 'none' }} onChange={e => fazerUploadAnexo(e, 'Orçamento')} disabled={fazendoUpload} accept=".pdf,.png,.jpg,.jpeg" />
                      </label>
                      <label className="button-primary" style={{ cursor: 'pointer', flex: 1, background: '#059669', borderColor: '#059669' }}>
                        {fazendoUpload ? 'Enviando...' : '+ Anexar Nota Fiscal / Comprovante'}
                        <input type="file" style={{ display: 'none' }} onChange={e => fazerUploadAnexo(e, 'Nota Fiscal / Comprovante')} disabled={fazendoUpload} accept=".pdf,.png,.jpg,.jpeg" />
                      </label>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: '20px' }}>
                  <span className="eyebrow">AUDITORIA</span>
                  <h4 style={{ margin: '0 0 8px 0' }}>Histórico de Eventos</h4>
                  <div className="timeline">
                    {historicoSolicitacao.map(evento => (
                      <div className="timeline-item" key={evento.id}>
                        <div className="timeline-date">{formatarDataHora(evento.data)}</div>
                        <div className="timeline-content"><strong>{evento.acao}</strong><span className="timeline-user">{evento.responsavel}</span></div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="modal-actions">
                {!ehControladoria && ['Aprovação pendente', 'Ajuste solicitado'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <>
                    <button className="button-primary" onClick={() => editarSolicitacao(solicitacaoSelecionada)}>Corrigir Pedido</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir Pedido</button>
                  </>
                )}
                {ehControladoria && ['Aprovação pendente', 'Ajuste solicitado'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <>
                    <button className="button-primary" onClick={() => aprovarSolicitacao(solicitacaoSelecionada)}>✓ Aprovar Solicitação</button>
                    <button className="button-secondary" onClick={() => solicitarAjuste(solicitacaoSelecionada)}>Solicitar Ajuste</button>
                    <button className="button-danger" onClick={() => reprovarSolicitacao(solicitacaoSelecionada)}>Reprovar</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir</button>
                  </>
                )}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Aprovada' && (
                  <>
                    <button className="button-primary" onClick={() => iniciarExecucao(solicitacaoSelecionada)}>▶ Iniciar Execução</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir</button>
                  </>
                )}
                {ehControladoria && textoStatus(solicitacaoSelecionada.status) === 'Em execução' && (
                  <>
                    <button className="button-primary" style={{ background: '#059669', borderColor: '#059669' }} onClick={() => finalizarSolicitacao(solicitacaoSelecionada)}>✓ Finalizar Compra</button>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir</button>
                  </>
                )}
                {ehControladoria && ['Finalizada', 'Reprovada'].includes(textoStatus(solicitacaoSelecionada.status)) && (
                  <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: '700', color: textoStatus(solicitacaoSelecionada.status) === 'Finalizada' ? '#059669' : '#dc2626' }}>
                      {textoStatus(solicitacaoSelecionada.status) === 'Finalizada' ? '✓ Solicitação concluída e auditada' : '✕ Solicitação reprovada'}
                    </span>
                    <button className="button-danger" onClick={() => excluirSolicitacao(solicitacaoSelecionada)}>Excluir</button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* MODAL: CRIAR / EDITAR SOLICITAÇÃO COM ANEXO DE ORÇAMENTO PARA O SOLICITANTE */}
        {mostrarFormulario && (
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) fecharFormulario() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{solicitacaoEditando ? 'EDIÇÃO' : 'NOVA SOLICITAÇÃO'}</span><h3>{solicitacaoEditando ? 'Editar Solicitação' : 'Abrir Solicitação de Compra'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormulario}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={salvarSolicitacao}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Condomínio *</label>
                        {ehControladoria && (
                          <button type="button" className="text-button" style={{ fontSize: '11.5px', padding: 0 }} onClick={e => { e.preventDefault(); abrirFormularioNovoCondominio() }}>+ Novo</button>
                        )}
                      </div>
                      <select value={formulario.condominio} onChange={e => atualizarCampoFormulario('condominio', e.target.value)} required>
                        <option value="">Selecione...</option>
                        {condominios.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                      </select>
                    </div>

                    <div className="form-group full">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Categoria da Despesa *</label>
                        {ehControladoria && (
                          <button type="button" className="text-button" style={{ fontSize: '11.5px', padding: 0 }} onClick={e => { e.preventDefault(); abrirFormularioNovoCategoria() }}>+ Nova</button>
                        )}
                      </div>
                      <select value={formulario.categoria} onChange={e => atualizarCampoFormulario('categoria', e.target.value)} required>
                        <option value="">Selecione...</option>
                        {categorias.map(cat => (<option key={cat.id} value={cat.nome}>{cat.nome}</option>))}
                      </select>
                    </div>

                    <div className="form-group full">
                      <label>O que está sendo comprado ou contratado? *</label>
                      <input type="text" placeholder="Ex: Manutenção corretiva do portão eletrônico..." value={formulario.descricao} onChange={e => atualizarCampoFormulario('descricao', e.target.value)} required />
                    </div>

                    <div className="form-group">
                      <label>Valor de Serviço (R$)</label>
                      <input type="text" placeholder="0,00" value={formulario.valor_servico} onChange={e => atualizarCampoFormulario('valor_servico', e.target.value)} />
                    </div>

                    <div className="form-group">
                      <label>Valor de Produto / Material (R$)</label>
                      <input type="text" placeholder="0,00" value={formulario.valor_produto} onChange={e => atualizarCampoFormulario('valor_produto', e.target.value)} />
                    </div>

                    <div className="form-group full">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label>Fornecedor / Prestador *</label>
                        <button type="button" className="text-button" style={{ fontSize: '11.5px', padding: 0 }} onClick={e => { e.preventDefault(); abrirFormularioNovoFornecedor() }}>+ Novo</button>
                      </div>
                      <select value={formulario.fornecedor} onChange={e => atualizarCampoFormulario('fornecedor', e.target.value)} required>
                        <option value="">Selecione...</option>
                        {fornecedores.map(forn => (<option key={forn.id || forn.nome} value={forn.nome}>{forn.nome}</option>))}
                      </select>
                    </div>

                    <div className="form-group full">
                      <label>Justificativa / Observação *</label>
                      <textarea rows="2" placeholder="Detalhes importantes para análise da controladoria..." value={formulario.observacao} onChange={e => atualizarCampoFormulario('observacao', e.target.value)} required />
                    </div>

                    {/* CAMPO DE ANEXO DE ORÇAMENTO / FOTO DIRETO NA ABERTURA DA SOLICITAÇÃO */}
                    <div className="form-group full">
                      <label>Anexar Orçamento / Documento / Foto (PDF ou Imagem)</label>
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={e => setArquivosNovaSolicitacao(Array.from(e.target.files || []))}
                        style={{ padding: '10px', background: '#f8fafc', border: '1px dashed #cbd5e1', cursor: 'pointer' }}
                      />
                      {arquivosNovaSolicitacao.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                          {arquivosNovaSolicitacao.map((arq, idx) => (
                            <span key={idx} style={{ fontSize: '12px', color: '#059669', fontWeight: '700' }}>
                              📎 {arq.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormulario}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarSolicitacao} disabled={salvando}>{salvando ? 'Enviando...' : 'Salvar Solicitação'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioCondominio && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCondominio() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{condominioEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{condominioEditando ? 'Editar Condomínio' : 'Cadastrar Condomínio'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCondominio}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={salvarCondominio}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Nome do Condomínio *</label>
                      <input type="text" value={formularioCondominio.nome} onChange={e => atualizarCampoCondominio('nome', e.target.value)} required autoFocus />
                    </div>
                    <div className="form-group">
                      <label>CNPJ</label>
                      <input type="text" value={formularioCondominio.cnpj} onChange={e => atualizarCampoCondominio('cnpj', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Código Interno</label>
                      <input type="text" value={formularioCondominio.codigo} onChange={e => atualizarCampoCondominio('codigo', e.target.value)} />
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioCondominio} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarCondominio} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioCategoria && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioCategoria() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{categoriaEditando ? 'ALÇADAS E REGRAS' : 'NOVO CADASTRO'}</span><h3>{categoriaEditando ? 'Editar Categoria' : 'Cadastrar Categoria'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioCategoria}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={salvarCategoria}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Nome da Categoria *</label>
                      <input type="text" value={formularioCategoria.nome} onChange={e => atualizarCampoCategoria('nome', e.target.value)} required autoFocus placeholder="Ex: Limpeza, Manutenção..." />
                    </div>
                    <div className="form-group full">
                      <label>Descrição Breve</label>
                      <input type="text" value={formularioCategoria.descricao} onChange={e => atualizarCampoCategoria('descricao', e.target.value)} />
                    </div>

                    <div className="form-group full" style={{ marginTop: '6px' }}>
                      <label>Teto de Aprovação Automática por Condomínio (R$)</label>
                      {condominios.length === 0 ? (
                        <div style={{ fontSize: '12.5px', color: '#64748b', padding: '12px', background: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1', textAlign: 'center' }}>
                          Cadastre condomínios primeiro para definir limites de aprovação automática.
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px', maxHeight: '210px', overflowY: 'auto', paddingRight: '4px' }}>
                          {condominios.map(c => (
                            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                              <span style={{ fontSize: '13px', fontWeight: '700', color: '#334155' }}>{c.nome}</span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: '700' }}>R$</span>
                                <input
                                  type="text"
                                  style={{ width: '110px', padding: '6px 10px', textAlign: 'right' }}
                                  placeholder="0,00"
                                  value={formularioCategoria.limites[c.nome] || ''}
                                  onChange={e => {
                                    setFormularioCategoria(prev => ({
                                      ...prev,
                                      limites: { ...prev.limites, [c.nome]: e.target.value }
                                    }))
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioCategoria} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarCategoria} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar Categoria'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarFormularioFornecedor && (
          <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={e => { if (e.target === e.currentTarget) fecharFormularioFornecedor() }}>
            <div className="modal">
              <div className="modal-header">
                <div><span className="eyebrow">{fornecedorEditando ? 'EDIÇÃO' : 'NOVO CADASTRO'}</span><h3>{fornecedorEditando ? 'Editar Fornecedor' : 'Cadastrar Fornecedor'}</h3></div>
                <button type="button" className="modal-close" onClick={fecharFormularioFornecedor}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={salvarFornecedor}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Nome / Razão Social *</label>
                      <input type="text" placeholder="Nome do fornecedor..." value={formularioFornecedor.nome} onChange={e => atualizarCampoFornecedor('nome', e.target.value)} required autoFocus />
                    </div>
                    <div className="form-group">
                      <label>CNPJ</label>
                      <input type="text" value={formularioFornecedor.cnpj} onChange={e => atualizarCampoFornecedor('cnpj', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Especialidade / Categoria</label>
                      <input type="text" value={formularioFornecedor.categoria} onChange={e => atualizarCampoFornecedor('categoria', e.target.value)} />
                    </div>
                  </div>
                </form>
              </div>
              <div className="modal-actions">
                <button type="button" className="button-secondary" onClick={fecharFormularioFornecedor} disabled={salvando}>Cancelar</button>
                <button type="button" className="button-primary" onClick={salvarFornecedor} disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </div>
          </div>
        )}

        {mostrarTrocaSenha && (
          <div className="modal-overlay" style={{ zIndex: 99999 }} onClick={e => { if (e.target === e.currentTarget) setMostrarTrocaSenha(false) }}>
            <div className="modal" style={{ maxWidth: 430 }} role="dialog" aria-modal="true" aria-label="Alterar senha">
              <div className="modal-header"><h3>Alterar minha senha</h3>
                <button className="modal-close" onClick={() => setMostrarTrocaSenha(false)} aria-label="Fechar">×</button>
              </div>
              <form onSubmit={trocarMinhaSenha}>
                <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
                  <div className="form-group"><label>Senha atual</label>
                    <input type="password" autoComplete="current-password" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} required /></div>
                  <div className="form-group"><label>Nova senha (mínimo 10 caracteres)</label>
                    <input type="password" autoComplete="new-password" value={senhaNova} onChange={e => setSenhaNova(e.target.value)} required minLength={10} /></div>
                  <p style={{ fontSize: 12, color: '#64748b' }}>Após alterar, você entrará novamente com a nova senha.</p>
                </div>
                <div className="modal-actions">
                  <button type="button" className="button-secondary" onClick={() => setMostrarTrocaSenha(false)}>Cancelar</button>
                  <button type="submit" className="button-primary" disabled={trocandoSenha}>{trocandoSenha ? 'Atualizando...' : 'Salvar nova senha'}</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App