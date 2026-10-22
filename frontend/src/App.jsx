import { useEffect, useState, useRef, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer
} from 'recharts'
import XLSX from 'xlsx-js-style'
import './App.css'

const API_URL = 'https://controladoria-api.onrender.com'

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
      status: 'atrasado',
      label: '⏳ Pendente',
      bg: '#f1f5f9',
      color: '#475569',
      border: '#cbd5e1'
    }
  }

  const dataUltima = parseDataSegura(ultimaExecucao.data_execucao)
  if (!dataUltima) {
    return {
      status: 'em_dia',
      label: '✓ Registrado',
      bg: '#ecfdf5',
      color: '#059669',
      border: '#a7f3d0'
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
      label: '🚨 Atrasado',
      bg: '#fef2f2',
      color: '#dc2626',
      border: '#fecaca'
    }
  }

  return {
    status: 'em_dia',
    label: '✓ Em dia',
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
  const [sidebarAberta, setSidebarAberta] = useState(false)

  const [backendOnline, setBackendOnline] = useState(true)
  const [sincronizando, setSincronizando] = useState(false)

  const [solicitacoes, setSolicitacoes] = useState(() => lerCache('solicitacoes', []))
  const [condominios, setCondominios] = useState(() => lerCache('condominios', []))
  const [fornecedores, setFornecedores] = useState(() => lerCache('fornecedores', []))
  const [categorias, setCategorias] = useState(() => lerCache('categorias', []))
  const [checklists, setChecklists] = useState(() => lerCache('checklists', []))

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
    link.download = nome
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
          limparCacheLocal()
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
        if (itemChecklistExecutando) { setItemChecklistExecutando(null); return }
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
    alertaPlanoAcao, dialog.isOpen, itemChecklistExecutando, itemChecklistHistorico,
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
      setUsuarioLogado(dadosUsuario)
      limparCacheLocal()
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
    setUsuarioLogado(null)
    sessionStorage.removeItem('usuarioControladoria')
    limparCacheLocal()
    setSolicitacoes([])
    setCondominios([])
    setFornecedores([])
    setCategorias([])
    setChecklists([])
    hashCacheRef.current = { sol: '', cond: '', forn: '', cat: '', chk: '' }
    setSolicitacaoSelecionada(null)
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

  async function carregarDados(forcarIndicador = false) {
    if (!usuarioLogado) return
    if (forcarIndicador) setSincronizando(true)
    try {
      const [resSol, resCond, resForn, resCat, resChk] = await Promise.all([
        fetch(`${API_URL}/solicitacoes`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/condominios`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/fornecedores`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/categorias`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/checklists`, { headers: getAuthHeaders() })
      ])

      if ([resSol, resCond, resForn, resCat, resChk].some(r => r.status === 401)) {
        fazerLogout()
        mostrarToast('Sua sessão expirou. Faça login novamente.', 'error')
        return
      }
      setBackendOnline(true)

      if (resSol.ok) {
        let dados = await resSol.json()
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
        const strCond = JSON.stringify(dadosCond)
        if (strCond !== hashCacheRef.current.cond) {
          hashCacheRef.current.cond = strCond
          setCondominios(dadosCond)
          salvarCache('condominios', dadosCond)
        }
      }

      if (resForn.ok) {
        const dadosForn = await resForn.json()
        const strForn = JSON.stringify(dadosForn)
        if (strForn !== hashCacheRef.current.forn) {
          hashCacheRef.current.forn = strForn
          setFornecedores(dadosForn)
          salvarCache('fornecedores', dadosForn)
        }
      }

      if (resCat.ok) {
        const dadosCat = await resCat.json()
        const strCat = JSON.stringify(dadosCat)
        if (strCat !== hashCacheRef.current.cat) {
          hashCacheRef.current.cat = strCat
          setCategorias(dadosCat)
          salvarCache('categorias', dadosCat)
        }
      }

      if (resChk.ok) {
        const dadosChk = await resChk.json()
        const strChk = JSON.stringify(dadosChk)
        if (strChk !== hashCacheRef.current.chk) {
          hashCacheRef.current.chk = strChk
          setChecklists(dadosChk)
          salvarCache('checklists', dadosChk)
          setItemChecklistHistorico(prev => prev ? (dadosChk.find(c => c.id === prev.id) || null) : null)
        }
      }
    } catch {
      setBackendOnline(false)
    } finally {
      if (forcarIndicador) setSincronizando(false)
    }
  }

  useEffect(() => {
    if (usuarioLogado) {
      if (usuarioLogado.perfil === 'Checklist' && pagina !== 'checklist') {
        setPagina('checklist')
      }
      carregarDados(false)
      const int = setInterval(() => {
        if (document.visibilityState === 'visible') {
          carregarDados(false)
        }
      }, 12000)
      return () => clearInterval(int)
    }
  }, [usuarioLogado])

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

  const comprasFiltradas = useMemo(() => {
    const buscaNorm = normalizarTexto(filtroCompra)
    return solicitacoes.filter(sol => {
      const st = textoStatus(sol.status)
      if (!['Aprovada', 'Em execução', 'Finalizada'].includes(st)) return false
      if (!buscaNorm) return true
      const t = normalizarTexto(`${sol.numero || ''} ${sol.condominio || ''} ${sol.categoria || ''} ${sol.descricao || ''}`)
      return t.includes(buscaNorm)
    })
  }, [solicitacoes, filtroCompra])

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

  const checklistsFiltrados = useMemo(() => {
    return checklists.filter(item => {
      const matchCond = filtroCondominioChecklist === 'todos' || item.condominio === filtroCondominioChecklist
      const matchFreq = filtroFrequenciaChecklist === 'todas' || item.frequencia === filtroFrequenciaChecklist
      if (!matchCond || !matchFreq) return false
      if (filtroSLAChecklist === 'atrasados') {
        const sla = calcularStatusSLA(item.frequencia, item.ultima_execucao)
        return sla.status === 'atrasado'
      }
      if (filtroSLAChecklist === 'divergencias') {
        return item.ultima_execucao?.status_conformidade === 'Não Conforme'
      }
      return true
    })
  }, [checklists, filtroCondominioChecklist, filtroFrequenciaChecklist, filtroSLAChecklist])

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
      carregarDados(false)
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
      setChecklists(prev => prev.filter(c => c.id !== item.id))
      mostrarToast('Atividade removida do checklist.', 'success')
      try {
        const res = await fetch(`${API_URL}/checklists/${item.id}`, {
          method: 'DELETE',
          headers: getAuthHeaders()
        })
        if (!res.ok) throw new Error('Erro ao excluir atividade.')
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
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
    e.preventDefault()
    if (formExecucaoChecklist.status_conformidade === 'Não Conforme' && !formExecucaoChecklist.observacao.trim()) {
      mostrarToast('Para itens fora dos conformes, descreva o problema nas observações.', 'error')
      return
    }

    const itemAtual = itemChecklistExecutando
    const statusEscolhido = formExecucaoChecklist.status_conformidade
    const relatoDigitado = formExecucaoChecklist.observacao.trim()
    const temFoto = Boolean(formExecucaoChecklist.foto)

    const formData = new FormData()
    formData.append('responsavel', usuarioLogado.nome)
    formData.append('status_conformidade', statusEscolhido)
    formData.append('observacao', relatoDigitado)
    if (formExecucaoChecklist.foto) {
      formData.append('foto', formExecucaoChecklist.foto)
    }

    const novaExecOtimista = {
      id: Date.now(),
      responsavel: usuarioLogado.nome,
      status_conformidade: statusEscolhido,
      observacao: relatoDigitado,
      data_execucao: new Date().toISOString(),
      tem_foto: temFoto
    }

    setChecklists(prev => prev.map(c => c.id === itemAtual.id ? {
      ...c,
      ultima_execucao: novaExecOtimista,
      historico_execucoes: [novaExecOtimista, ...(c.historico_execucoes || [])]
    } : c))

    setItemChecklistExecutando(null)

    if (statusEscolhido === 'Não Conforme') {
      setAlertaPlanoAcao({
        condominio: itemAtual.condominio,
        titulo: itemAtual.titulo,
        relato: relatoDigitado,
        plano_acao: itemAtual.plano_acao_padrao || 'Comunicar imediatamente a Controladoria Haize para providências corretivas.'
      })
    } else {
      mostrarToast('Checklist registrado com sucesso!', 'success')
    }

    try {
      const res = await fetch(`${API_URL}/checklists/${itemAtual.id}/executar`, {
        method: 'POST',
        headers: getAuthHeaders(true),
        body: formData
      })
      if (!res.ok) {
        const err = await extrairErro(res, 'Erro ao registrar vistoria no servidor.')
        throw new Error(err)
      }
      carregarDados(false)
    } catch (err) {
      mostrarToast(err.message, 'error')
      carregarDados(false)
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
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #0f172a;">${item.nome}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 600;">${item.qtdSolicitacoes || 0}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.aprovado)}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right;">${formatarValor(item.realizado)}</td>
        <td style="padding: 8px 10px; border: 1px solid #cbd5e1; text-align: right; color: ${item.saldo < 0 ? '#dc2626' : '#059669'}; font-weight: 700;">${formatarValor(item.saldo)}</td>
      </tr>
    `).join('')

    const linhasSols = solicitacoesAnaliseFiltradas.map((s, idx) => `
      <tr style="background: ${idx % 2 === 0 ? '#ffffff' : '#f8fafc'}; page-break-inside: avoid;">
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-family: monospace; font-size: 11px;">${s.numero || ''}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: 600;">${s.condominio || ''}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0; color: #475569;">${s.categoria || '-'}</td>
        <td style="padding: 6px 8px; border: 1px solid #e2e8f0;">${s.descricao || ''}</td>
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
            <div><strong>Filtro:</strong> ${condFormatado}</div>
            <div><strong>Período:</strong> ${periodoFormatado}</div>
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
      setCondominios(prev => prev.filter(c => c.id !== id))
      mostrarToast('Condomínio excluído.', 'success')
      try {
        const res = await fetch(`${API_URL}/condominios/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir condomínio.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
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
      setCategorias(prev => prev.filter(c => c.id !== id))
      mostrarToast('Categoria excluída.', 'success')
      try {
        const res = await fetch(`${API_URL}/categorias/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir categoria.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
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
      setFornecedores(prev => prev.filter(f => f.id !== id))
      mostrarToast('Fornecedor excluído.', 'success')
      try {
        const res = await fetch(`${API_URL}/fornecedores/${id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) throw new Error(await extrairErro(res, 'Erro ao excluir fornecedor.'))
        carregarDados(false)
      } catch (e) {
        mostrarToast(e.message, 'error')
        carregarDados(false)
      }
    }, true)
  }

  function atualizarCampoCondominio(campo, valor) { setFormularioCondominio(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoCategoria(campo, valor) { setFormularioCategoria(atual => ({ ...atual, [campo]: valor })) }
  function atualizarCampoFornecedor(campo, valor) { setFormularioFornecedor(atual => ({ ...atual, [campo]: valor })) }

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
              <button className={pagina === 'checklist' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('checklist'); setSidebarAberta(false); }}>
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
                <button className={pagina === 'checklist' ? 'nav-item active' : 'nav-item'} onClick={() => { setPagina('checklist'); setSidebarAberta(false); }}>
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
                {pagina === 'dashboard' ? 'Painel Geral' : pagina === 'solicitacoes' ? (ehControladoria ? 'Central de Aprovações' : 'Minhas Solicitações') : pagina === 'checklist' ? 'Checklist Operacional' : pagina.charAt(0).toUpperCase() + pagina.slice(1)}
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
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <span className="eyebrow">ROTINAS E MANUTENÇÃO PREVENTIVA</span>
                  <h3>Atividades do Checklist</h3>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <select value={filtroCondominioChecklist} onChange={e => setFiltroCondominioChecklist(e.target.value)}>
                    <option value="todos">Todos os Condomínios</option>
                    {condominios.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                  </select>

                  <select value={filtroFrequenciaChecklist} onChange={e => setFiltroFrequenciaChecklist(e.target.value)}>
                    <option value="todas">Todas as Frequências</option>
                    <option value="Diária">Diária</option>
                    <option value="Semanal">Semanal</option>
                    <option value="Quinzenal">Quinzenal</option>
                    <option value="Mensal">Mensal</option>
                  </select>

                  {filtroCondominioChecklist !== 'todos' && (
                    <button className="button-secondary" onClick={gerarRelatorioDivergenciasPDF} disabled={enviandoRelatorio}>
                      <span>📄</span> {enviandoRelatorio ? 'Enviando relatório...' : 'Gerar e Enviar PDF'}
                    </button>
                  )}

                  {ehControladoria && (
                    <button className="button-primary" onClick={abrirModalCriarChecklist}>
                      + Nova Atividade
                    </button>
                  )}
                </div>
              </div>

              <div className="filter-bar">
                <div className="pill-group">
                  <button className={`filter-pill ${filtroSLAChecklist === 'todos' ? 'active' : ''}`} onClick={() => setFiltroSLAChecklist('todos')}>
                    Todas ({checklists.length})
                  </button>
                  <button className={`filter-pill ${filtroSLAChecklist === 'atrasados' ? 'active' : ''}`} onClick={() => setFiltroSLAChecklist('atrasados')}>
                    🚨 Em Atraso / Pendentes
                  </button>
                  <button className={`filter-pill ${filtroSLAChecklist === 'divergencias' ? 'active' : ''}`} onClick={() => setFiltroSLAChecklist('divergencias')}>
                    ⚠️ Com Inconformidade
                  </button>
                </div>
              </div>

              {checklistsFiltrados.length === 0 ? (
                <div style={{ padding: '48px 24px', textAlign: 'center', color: '#64748b' }}>
                  Nenhuma atividade encontrada para o filtro selecionado.
                  {ehControladoria && ' Clique em "+ Nova Atividade" para adicionar tarefas ao checklist.'}
                </div>
              ) : (
                <div className="company-grid">
                  {checklistsFiltrados.map(item => {
                    const ult = item.ultima_execucao
                    const naoConforme = ult && ult.status_conformidade === 'Não Conforme'
                    const sla = calcularStatusSLA(item.frequencia, ult)
                    return (
                      <div className="company-card" key={item.id} style={{ borderLeft: ult ? (naoConforme ? '4px solid #dc2626' : '4px solid #10b981') : '4px solid #cbd5e1' }}>
                        <div>
                          <div className="company-card-top" style={{ flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '11px', fontWeight: '800', textTransform: 'uppercase', background: '#eff6ff', color: '#1d4ed8', padding: '4px 10px', borderRadius: '999px' }}>
                              🏢 {item.condominio}
                            </span>
                            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                              <span style={{ fontSize: '11px', fontWeight: '700', background: '#f1f5f9', color: '#475569', padding: '3px 9px', borderRadius: '999px' }}>
                                ⏱️ {item.frequencia}
                              </span>
                              <span style={{ fontSize: '11px', fontWeight: '700', background: sla.bg, color: sla.color, border: `1px solid ${sla.border}`, padding: '3px 8px', borderRadius: '999px' }}>
                                {sla.label}
                              </span>
                            </div>
                          </div>

                          <h4>{item.titulo}</h4>
                          {item.descricao_orientacao && (
                            <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 10px 0', lineHeight: '1.45' }}>
                              {item.descricao_orientacao}
                            </p>
                          )}

                          {item.plano_acao_padrao && (
                            <div style={{ fontSize: '12px', background: '#fffbeb', border: '1px solid #fde68a', padding: '9px 11px', borderRadius: '8px', color: '#92400e', marginBottom: '10px' }}>
                              <strong>Plano de Ação:</strong> {item.plano_acao_padrao}
                            </div>
                          )}

                          <div style={{ background: '#f8fafc', padding: '10px 12px', borderRadius: '9px', border: '1px solid #e2e8f0', fontSize: '12px', marginTop: '10px' }}>
                            {!ult ? (
                              <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Ainda não realizado nenhuma vez.</span>
                            ) : (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <strong style={{ color: naoConforme ? '#dc2626' : '#059669' }}>
                                    {naoConforme ? '⚠️ Fora dos Conformes' : '✅ Conforme (OK)'}
                                  </strong>
                                  <span style={{ fontSize: '11px', color: '#64748b' }}>{formatarDataHora(ult.data_execucao)}</span>
                                </div>
                                <span style={{ color: '#475569' }}>Vistoriador: <strong>{ult.responsavel}</strong></span>
                                {ult.observacao && (
                                  <span style={{ color: '#334155', fontStyle: 'italic', marginTop: '2px' }}>"{ult.observacao}"</span>
                                )}
                                {ult.tem_foto && ult.id && (
                                  <a
                                    href="#" onClick={e => { e.preventDefault(); abrirArquivoProtegido(`/checklists/execucoes/${ult.id}/foto`, `foto-vistoria-${ult.id}.jpg`).catch(err => mostrarToast(err.message, 'error')) }}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: '#2563eb', fontWeight: '700', textDecoration: 'none', marginTop: '4px', display: 'inline-block' }}
                                  >
                                    📷 Ver evidência anexada
                                  </a>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '16px', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                          <button
                            className="button-primary"
                            style={{ flex: 1, background: '#059669', borderColor: '#059669' }}
                            onClick={() => abrirModalExecutarChecklist(item)}
                          >
                            ✓ Registrar Vistoria
                          </button>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <button className="text-button" onClick={() => setItemChecklistHistorico(item)}>
                              Histórico ({item.historico_execucoes?.length || 0})
                            </button>
                            {ehControladoria && (
                              <>
                                <button className="text-button" onClick={() => abrirModalEditarChecklist(item)}>
                                  Editar
                                </button>
                                <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirItemChecklist(item)}>
                                  Excluir
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
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
          <div className="page">
            <section className="welcome" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div><span className="eyebrow">INTELIGÊNCIA E RELATÓRIOS</span><h2>Visão Analítica Global</h2></div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <select value={filtroCondominioAnalise} onChange={e => setFiltroCondominioAnalise(e.target.value)}>
                  <option value="todos">Todos os Condomínios</option>
                  {condominios?.map(c => (<option key={c.id} value={c.nome}>{c.nome}</option>))}
                </select>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '9px', padding: '4px 10px' }}>
                  <span style={{ fontSize: '11.5px', color: '#64748b', fontWeight: '700' }}>De:</span>
                  <input type="date" value={filtroDataInicio} onChange={e => setFiltroDataInicio(e.target.value)} style={{ border: 'none', padding: '4px', fontSize: '12.5px' }} />
                  <span style={{ fontSize: '11.5px', color: '#64748b', fontWeight: '700' }}>Até:</span>
                  <input type="date" value={filtroDataFim} onChange={e => setFiltroDataFim(e.target.value)} style={{ border: 'none', padding: '4px', fontSize: '12.5px' }} />
                  {(filtroDataInicio || filtroDataFim) && (
                    <button onClick={() => { setFiltroDataInicio(''); setFiltroDataFim('') }} className="text-button" style={{ fontSize: '11px' }}>Limpar</button>
                  )}
                </div>

                <button className="button-secondary" onClick={exportarRelatorioExcel}>
                  <span>📊</span> Excel (.xlsx)
                </button>
                <button className="button-secondary" onClick={exportarRelatorioPDF}>
                  <span>🖨️</span> Imprimir PDF
                </button>
              </div>
            </section>

            {filtroCondominioAnalise !== 'todos' && (
              <section className="dashboard-grid" style={{ marginTop: '22px' }}>
                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">RATEIO AUTOMÁTICO</span>
                      <h3>Distribuição por Fração Ideal — {filtroCondominioAnalise}</h3>
                    </div>
                    {rateioDados && (
                      <span className="badge approved" style={{ fontSize: '12.5px', padding: '6px 12px' }}>
                        Despesas Finalizadas: {formatarValor(rateioDados.total_gasto_condominio)} ({rateioDados.quantidade_solicitacoes} itens)
                      </span>
                    )}
                  </div>

                  {carregandoRateio ? (
                    <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Calculando rateio de despesas...</div>
                  ) : !rateioDados || rateioDados.rateio_unidades.length === 0 ? (
                    <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>
                      Nenhuma unidade/fração cadastrada para este condomínio. Vá na aba de <strong>Condomínios</strong> e clique em <strong>Unidades</strong> para configurar.
                    </div>
                  ) : (
                    <div className="table">
                      <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 1fr' }}>
                        <span>Unidade / Apartamento</span>
                        <span>Fração Ideal (%)</span>
                        <span style={{ textAlign: 'right' }}>Valor Rateado (R$)</span>
                      </div>
                      {rateioDados.rateio_unidades.map((u, i) => (
                        <div className="table-row" key={i} style={{ gridTemplateColumns: '2fr 1fr 1fr' }}>
                          <strong style={{ color: '#0f172a' }}>{u.unidade}</strong>
                          <span style={{ fontWeight: '700' }}>{formatarNumero(u.fracao_ideal)}%</span>
                          <strong style={{ textAlign: 'right', color: '#059669' }}>{formatarValor(u.valor_devido)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

            <section className="dashboard-grid" style={{ marginTop: '22px' }}>
              <div className="panel">
                <div className="panel-header">
                  <div><span className="eyebrow">COMPARATIVO ORÇAMENTÁRIO</span><h3>Solicitado × Aprovado × Realizado</h3></div>
                </div>
                <div style={{ width: '100%', height: 360 }}>
                  {dadosGraficoCondominios.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '48px', color: '#64748b' }}>Sem dados para gerar gráfico no filtro selecionado.</div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dadosGraficoCondominios} margin={{ top: 16, right: 24, left: 12, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} tickFormatter={v => `R$ ${v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v}`} />
                        <RechartsTooltip formatter={v => formatarValor(v)} cursor={{ fill: '#f8fafc' }} />
                        <Legend wrapperStyle={{ paddingTop: '16px' }} />
                        <Bar dataKey="Solicitado" fill="#94a3b8" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                        <Bar dataKey="Aprovado" fill="#2563eb" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                        <Bar dataKey="Realizado" fill="#10b981" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </section>

            <section className="dashboard-grid" style={{ marginTop: '22px' }}>
              <div className="panel">
                <div className="panel-header"><div><span className="eyebrow">POR CENTRO DE CUSTO</span><h3>Execução Orçamentária por Condomínio</h3></div></div>
                <div className="table">
                  <div className="table-header" style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 140px' }}>
                    <span>Condomínio</span><span>Teto Aprovado</span><span>Gasto Realizado</span><span>Saldo (R$)</span><span>Status</span>
                  </div>
                  {listaOrcamentoCondominio.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>Nenhuma solicitação encontrada para o filtro.</div>
                  ) : (
                    listaOrcamentoCondominio.map(item => {
                      let sBadge = 'neutral'; let sTexto = 'No Limite'
                      if (item.saldo > 0) { sBadge = 'positive'; sTexto = 'Economia' }
                      if (item.saldo < 0) { sBadge = 'negative'; sTexto = 'Estourado' }
                      if (item.aprovado === 0) { sBadge = 'neutral'; sTexto = 'Sem Orçamento' }
                      return (
                        <div className="table-row" key={item.nome} style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 140px' }}>
                          <strong style={{ color: '#0f172a' }}>{item.nome}</strong>
                          <span>{formatarValor(item.aprovado)}</span>
                          <span>{formatarValor(item.realizado)}</span>
                          <strong className={classeVariacao(item.saldo)}>{formatarValor(item.saldo)}</strong>
                          <span className={`badge ${sBadge}`}>{sTexto}</span>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </section>
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
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <span className="eyebrow">FLUXO DE COMPRAS</span>
                  <h3>{pagina === 'solicitacoes' ? 'Solicitações de Compra' : 'Compras Aprovadas & Em Execução'}</h3>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <input
                    type="text"
                    placeholder="🔍 Buscar por código, condomínio ou item..."
                    style={{ minWidth: '260px' }}
                    value={pagina === 'solicitacoes' ? filtroSolicitacao : filtroCompra}
                    onChange={e => pagina === 'solicitacoes' ? setFiltroSolicitacao(e.target.value) : setFiltroCompra(e.target.value)}
                  />
                </div>
              </div>

              {pagina === 'solicitacoes' && (
                <div className="filter-bar">
                  <div className="pill-group">
                    {[
                      { id: 'todos', label: 'Todas' },
                      { id: 'Aprovação pendente', label: '⏳ Pendentes' },
                      { id: 'Em análise', label: 'Em análise' },
                      { id: 'Ajuste solicitado', label: '📌 Em Ajuste' },
                      { id: 'Aprovada', label: '✓ Aprovadas' },
                      { id: 'Em execução', label: '▶ Em Execução' },
                      { id: 'Finalizada', label: '✅ Finalizadas' },
                      { id: 'Reprovada', label: '✕ Reprovadas' }
                    ].map(st => (
                      <button
                        key={st.id}
                        className={`filter-pill ${filtroStatus === st.id ? 'active' : ''}`}
                        onClick={() => setFiltroStatus(st.id)}
                      >
                        {st.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="table">
                <div className="table-header" style={pagina === 'compras' ? { gridTemplateColumns: '115px 1.2fr 2fr 1fr 1fr 140px' } : undefined}>
                  <span>Código</span>
                  <span>Condomínio</span>
                  <span>Descrição & Categoria</span>
                  {pagina === 'compras' && (<span>Solicitado</span>)}
                  <span>{pagina === 'compras' ? 'Aprovado' : 'Valor Total'}</span>
                  <span>Status</span>
                </div>
                {(pagina === 'solicitacoes' ? solicitacoesFiltradas : comprasFiltradas).length === 0 ? (
                  <div style={{ padding: '36px', textAlign: 'center', color: '#64748b' }}>
                    Nenhum registro encontrado para este filtro.
                  </div>
                ) : (
                  (pagina === 'solicitacoes' ? solicitacoesFiltradas : comprasFiltradas).map(sol => (
                    <div className="table-row clickable" key={sol.id} style={pagina === 'compras' ? { gridTemplateColumns: '115px 1.2fr 2fr 1fr 1fr 140px' } : undefined} onClick={() => abrirSolicitacao(sol)}>
                      <span className="id">{sol.numero}</span>
                      <strong style={{ color: '#0f172a' }}>{sol.condominio}</strong>
                      <div>
                        <div style={{ color: '#1e293b', fontWeight: '600' }}>{sol.descricao}</div>
                        {sol.categoria && <div style={{ fontSize: '11.5px', color: '#64748b', marginTop: '2px' }}>📁 {sol.categoria} {sol.fornecedor ? `• ${sol.fornecedor}` : ''}</div>}
                      </div>
                      {pagina === 'compras' && (<strong>{formatarValor(sol.valor)}</strong>)}
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ color: '#0f172a' }}>{formatarValor(pagina === 'compras' ? (aprovado(sol) || sol.valor) : sol.valor)}</strong>
                        {pagina === 'solicitacoes' && aprovado(sol) > 0 && aprovado(sol) < sol.valor && (<span style={{ fontSize: '11px', color: '#d97706', fontWeight: '700' }}>Aprov: {formatarValor(aprovado(sol))}</span>)}
                        {realizado(sol) > 0 && (<span style={{ fontSize: '11px', color: realizado(sol) <= (aprovado(sol) || sol.valor) ? '#059669' : '#dc2626', fontWeight: '700' }}>Pago: {formatarValor(realizado(sol))}</span>)}
                      </div>
                      {renderBadge(sol)}
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        {pagina === 'categorias' && !ehChecklist && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">REGRAS DE ALÇADA</span><h3>Categorias de Despesa</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoCategoria}>+ Nova Categoria</button>
              </div>
              <div className="company-grid">
                {categorias.map(cat => {
                  const nome = cat.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.categoria === nome).length
                  const limitesCadastrados = cat.limites?.length || 0

                  return (
                    <div className="company-card" key={cat.id}>
                      <div>
                        <div className="company-card-top">
                          <div className="company-avatar" style={{ background: '#f3e8ff', color: '#7e22ce' }}>{String(nome).charAt(0).toUpperCase()}</div>
                          <span className="badge neutral">Ativa</span>
                        </div>
                        <h4>{nome}</h4>
                        {cat.descricao && (<span className="company-detail">{cat.descricao}</span>)}

                        {limitesCadastrados > 0 ? (
                          <div style={{ marginTop: '12px', fontSize: '12px', color: '#059669', background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '7px 12px', borderRadius: '8px', fontWeight: '700' }}>
                            ⚡ Alçada Automática em {limitesCadastrados} {limitesCadastrados === 1 ? 'condomínio' : 'condomínios'}
                          </div>
                        ) : (
                          <div style={{ marginTop: '12px', fontSize: '12px', color: '#64748b', background: '#f8fafc', border: '1px dashed #cbd5e1', padding: '7px 12px', borderRadius: '8px' }}>
                            Aprovação manual padrão
                          </div>
                        )}
                      </div>

                      <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '16px', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button className="text-button" onClick={() => editarCategoria(cat)}>Configurar Alçadas</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirCategoria(cat.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {pagina === 'condominios' && !ehChecklist && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">CARTEIRA PREDIAL</span><h3>Condomínios Gerenciados</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoCondominio}>+ Novo Condomínio</button>
              </div>
              <div className="company-grid">
                {condominios.map(condominio => {
                  const nome = condominio.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.condominio === nome).length
                  return (
                    <div className="company-card" key={condominio.id}>
                      <div>
                        <div className="company-card-top">
                          <div className="company-avatar">{String(nome).charAt(0).toUpperCase()}</div>
                          <span className="badge approved">Ativo</span>
                        </div>
                        <h4>{nome}</h4>
                        {condominio.cnpj && (<span className="company-detail">CNPJ: {condominio.cnpj}</span>)}
                        {condominio.codigo && (<span className="company-detail">Código: {condominio.codigo}</span>)}
                      </div>

                      <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '16px', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Pedidos: </span>
                          <strong>{qtd}</strong>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <button className="text-button" onClick={() => abrirGerenciadorUnidades(condominio)}>Unidades</button>
                          <button className="text-button" onClick={() => editarCondominio(condominio)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirCondominio(condominio.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>
        )}

        {pagina === 'fornecedores' && !ehChecklist && (
          <div className="page">
            <section className="panel">
              <div className="panel-header">
                <div><span className="eyebrow">PARCEIROS E PRESTADORES</span><h3>Fornecedores Homologados</h3></div>
                <button className="button-primary" onClick={abrirFormularioNovoFornecedor}>+ Novo Fornecedor</button>
              </div>
              <div className="company-grid">
                {fornecedores.map(forn => {
                  const nome = forn.nome || 'Sem nome'
                  const qtd = solicitacoes.filter(s => s.fornecedor === nome).length
                  return (
                    <div className="company-card" key={forn.id}>
                      <div>
                        <div className="company-card-top">
                          <div className="company-avatar" style={{ background: '#f1f5f9', color: '#334155' }}>{String(nome).charAt(0).toUpperCase()}</div>
                          <span className="badge neutral">Homologado</span>
                        </div>
                        <h4>{nome}</h4>
                        {forn.cnpj && (<span className="company-detail">CNPJ: {forn.cnpj}</span>)}
                        {forn.categoria && (<span className="company-detail">Especialidade: {forn.categoria}</span>)}
                      </div>
                      <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '16px', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div><span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Solicitações: </span><strong>{qtd}</strong></div>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button className="text-button" onClick={() => editarFornecedor(forn)}>Editar</button>
                          <button className="text-button" style={{ color: 'var(--danger)' }} onClick={() => excluirFornecedor(forn.id, nome)}>Excluir</button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
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
          <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setItemChecklistExecutando(null) }}>
            <div className="modal">
              <div className="modal-header">
                <div>
                  <span className="eyebrow">{itemChecklistExecutando.condominio} • {itemChecklistExecutando.frequencia}</span>
                  <h3>{itemChecklistExecutando.titulo}</h3>
                </div>
                <button className="modal-close" onClick={() => setItemChecklistExecutando(null)}>×</button>
              </div>
              <div className="modal-body">
                <form className="form" onSubmit={confirmarExecucaoChecklist}>
                  <div className="form-grid">
                    <div className="form-group full">
                      <label>Resultado da Vistoria *</label>
                      <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                        <button
                          type="button"
                          onClick={() => setFormExecucaoChecklist(p => ({ ...p, status_conformidade: 'Conforme' }))}
                          style={{
                            flex: 1, padding: '12px', borderRadius: '10px', fontWeight: '700', fontSize: '13px', cursor: 'pointer',
                            border: formExecucaoChecklist.status_conformidade === 'Conforme' ? '2px solid #059669' : '1px solid #cbd5e1',
                            background: formExecucaoChecklist.status_conformidade === 'Conforme' ? '#ecfdf5' : '#ffffff',
                            color: formExecucaoChecklist.status_conformidade === 'Conforme' ? '#059669' : '#475569'
                          }}
                        >
                          ✅ Conforme (Tudo OK)
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormExecucaoChecklist(p => ({ ...p, status_conformidade: 'Não Conforme' }))}
                          style={{
                            flex: 1, padding: '12px', borderRadius: '10px', fontWeight: '700', fontSize: '13px', cursor: 'pointer',
                            border: formExecucaoChecklist.status_conformidade === 'Não Conforme' ? '2px solid #dc2626' : '1px solid #cbd5e1',
                            background: formExecucaoChecklist.status_conformidade === 'Não Conforme' ? '#fef2f2' : '#ffffff',
                            color: formExecucaoChecklist.status_conformidade === 'Não Conforme' ? '#dc2626' : '#475569'
                          }}
                        >
                          ⚠️ Fora dos Conformes
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
                <button type="button" className="button-secondary" onClick={() => setItemChecklistExecutando(null)}>Cancelar</button>
                <button type="button" className="button-primary" onClick={confirmarExecucaoChecklist} disabled={salvando}>
                  Confirmar Vistoria
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
                              href="#" onClick={e => { e.preventDefault(); abrirArquivoProtegido(`/checklists/execucoes/${ex.id}/foto`, `foto-vistoria-${ex.id}.jpg`).catch(err => mostrarToast(err.message, 'error')) }}
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